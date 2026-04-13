"""YouTube processor — metadata + chapters + transcript-segment sections.

Extraction primitives:
  * yt-dlp for metadata, chapter boundaries, thumbnails (already in
    deps; actively maintained against YouTube's player.js churn).
  * youtube-transcript-api for per-segment transcript with timestamps.
    Per-segment is the key — we used to concat into a single blob, which
    threw away the timing info needed for ``transcript_segment`` sections.

Sections:
  * ``title``                — video title
  * ``paragraph``           — description, role=supplemental
  * ``chapter`` (one each)   — chapter title, depth=0, role=navigational
  * ``transcript_segment``  — per ~12-30s segment, parented to its chapter
                               when timestamps overlap. Keeps timestamps
                               so the UI can show "found at 03:42".
"""

from __future__ import annotations

import json
import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _chapter_for_timestamp(chapters: list[dict], t_start: float) -> int | None:
    """Return the index of the chapter whose [start, end) contains t_start."""
    for i, ch in enumerate(chapters):
        start = ch.get("start_time", 0)
        end = ch.get("end_time", 1e18)
        if start <= t_start < end:
            return i
    return None


@register_processor
class YouTubeProcessor(BaseProcessor):
    """Extract YouTube video as structured sections (chapters + transcript)."""

    url_patterns = [
        r"youtube\.com/watch\?v=",
        r"youtu\.be/[a-zA-Z0-9_-]+",
        r"youtube\.com/shorts/[a-zA-Z0-9_-]+",
        r"youtube\.com/embed/[a-zA-Z0-9_-]+",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        video_id = _extract_video_id(url)
        if not video_id:
            return ProcessorResult(
                title=url,
                source_platform="youtube",
                status=ProcessorStatus.failed,
                error="Could not extract video ID from URL",
            )

        title: str | None = None
        description: str = ""
        media: list[dict] = []
        chapters: list[dict] = []
        metadata: dict = {"video_id": video_id}

        # ─── yt-dlp: metadata + chapters ───
        try:
            import yt_dlp

            with yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True,
                "skip_download": True, "extract_flat": False,
            }) as ydl:
                info = ydl.extract_info(url, download=False)
            if info:
                title = info.get("title")
                description = info.get("description") or ""
                metadata.update({
                    "channel": info.get("channel") or info.get("uploader"),
                    "channel_id": info.get("channel_id"),
                    "channel_url": info.get("channel_url"),
                    "duration": info.get("duration"),
                    "view_count": info.get("view_count"),
                    "like_count": info.get("like_count"),
                    "upload_date": info.get("upload_date"),
                    "categories": info.get("categories", []),
                    "tags": info.get("tags", []),
                    "is_short": "/shorts/" in url,
                })
                chapters = info.get("chapters") or []
                if chapters:
                    metadata["chapters"] = chapters

                # Thumbnail — prefer maxres, fall back to standard.
                thumb = info.get("thumbnail")
                if thumb:
                    media.append({"type": "image", "url": thumb, "role": "thumbnail"})
                # Always include a video reference so cards can show "watch on YouTube".
                media.append({
                    "type": "video", "url": url, "role": "external",
                    "platform": "youtube",
                })
        except ImportError:
            return ProcessorResult(
                title=url, source_platform="youtube",
                status=ProcessorStatus.failed,
                error="yt-dlp not installed",
                metadata={"video_id": video_id},
            )
        except Exception as e:
            logger.warning("yt-dlp failed for %s: %s", url, e)
            metadata["yt_dlp_error"] = str(e)[:200]

        # ─── Transcript with per-segment timing ───
        transcript_segments: list[dict] = []
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            try:
                tlist = YouTubeTranscriptApi.list_transcripts(video_id)
                t = None
                try:
                    t = tlist.find_manually_created_transcript(["en"])
                except Exception:
                    try:
                        t = tlist.find_generated_transcript(["en"])
                    except Exception:
                        for any_t in tlist:
                            t = any_t
                            break
                if t:
                    fetched = t.fetch()
                    for entry in fetched:
                        if isinstance(entry, dict):
                            transcript_segments.append({
                                "text": entry.get("text", ""),
                                "start": float(entry.get("start", 0.0)),
                                "duration": float(entry.get("duration", 0.0)),
                            })
                    metadata["transcript_language"] = t.language
                    metadata["transcript_auto_generated"] = t.is_generated
            except Exception as e:
                logger.debug("Transcript fetch failed for %s: %s", video_id, e)
                metadata["transcript_error"] = str(e)[:200]
        except ImportError:
            metadata["transcript_error"] = "youtube-transcript-api not installed"

        # ─── Build sections ───
        sections: list[Section] = []
        order = 0

        if title:
            sections.append(Section(
                id=make_section_id(url, order), kind="title", order=order,
                role="main", text=title,
            ))
            order += 1

        if description.strip():
            sections.append(Section(
                id=make_section_id(url, order), kind="paragraph", order=order,
                role="supplemental", text=description.strip(),
                extra={"source": "video_description"},
            ))
            order += 1

        # One chapter section per chapter — they're navigational, not main
        # content; chunker will skip them by default thanks to short text.
        chapter_section_ids: list[str] = []
        for i, ch in enumerate(chapters):
            cid = make_section_id(url, order)
            chapter_section_ids.append(cid)
            sections.append(Section(
                id=cid, kind="chapter", order=order, role="navigational",
                depth=0, text=ch.get("title", f"Chapter {i + 1}"),
                timestamp_start_s=float(ch.get("start_time", 0)),
                timestamp_end_s=float(ch.get("end_time", 0)),
            ))
            order += 1

        # Transcript segments — group very short adjacent segments so we
        # don't end up with a chunk per single line.
        if transcript_segments:
            buf_text: list[str] = []
            buf_start: float | None = None
            buf_end: float = 0.0
            buf_chapter_idx: int | None = None
            target_chars = 600  # roughly one screenful

            def _flush():
                nonlocal order, buf_text, buf_start, buf_end, buf_chapter_idx
                if not buf_text or buf_start is None:
                    return
                parent_id = (
                    chapter_section_ids[buf_chapter_idx]
                    if buf_chapter_idx is not None and buf_chapter_idx < len(chapter_section_ids)
                    else None
                )
                sections.append(Section(
                    id=make_section_id(url, order),
                    kind="transcript_segment",
                    order=order,
                    role="main",
                    parent_id=parent_id,
                    text=" ".join(buf_text).strip(),
                    timestamp_start_s=buf_start,
                    timestamp_end_s=buf_end,
                ))
                order += 1
                buf_text = []
                buf_start = None

            for seg in transcript_segments:
                seg_text = (seg.get("text") or "").strip()
                if not seg_text:
                    continue
                seg_start = seg["start"]
                seg_end = seg_start + seg.get("duration", 0.0)
                seg_chapter = (
                    _chapter_for_timestamp(chapters, seg_start) if chapters else None
                )
                # New chapter or buffer too big → flush
                if (
                    buf_chapter_idx is not None and seg_chapter != buf_chapter_idx
                ) or sum(len(t) for t in buf_text) > target_chars:
                    _flush()
                if buf_start is None:
                    buf_start = seg_start
                    buf_chapter_idx = seg_chapter
                buf_text.append(seg_text)
                buf_end = seg_end
            _flush()

        # ─── Status ───
        status = ProcessorStatus.success
        error = None
        if not title:
            status = ProcessorStatus.partial
            error = "Could not extract full metadata"
        elif not transcript_segments and "transcript_error" in metadata:
            # Successful metadata but no transcript — still OK, don't downgrade
            pass

        return ProcessorResult(
            title=title or url,
            description=(description or "")[:500],
            content=None,
            raw_content=json.dumps(metadata, default=str)[:100000],
            media=media,
            metadata=metadata,
            source_platform="youtube",
            item_type="video",
            status=status,
            error=error,
            sections=sections,
        )
