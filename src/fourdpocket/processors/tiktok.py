"""TikTok processor — yt-dlp metadata + sectioned output (Phase 4c).

Per R&D: yt-dlp's TikTok extractor is the most maintained option;
TikTokApi (davidteather) requires Playwright + cookies. We stay
yt-dlp-only for the core path, with an OG metadata fallback when
yt-dlp's extractor breaks (TikTok ships protocol changes weekly).

Sections:
  * ``title``                — first line of description
  * ``post``                 — full caption with hashtags hoisted
  * ``visual_caption``       — yt-dlp ``description`` if it contains
                                meaningful text vs just the hashtags
  * ``transcript_segment[]`` — when subtitles are available
                                (rare on TikTok but increasing)
  * ``metadata_block``       — fallback note when extraction is limited
"""

from __future__ import annotations

import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


def _split_caption(text: str) -> tuple[str, list[str]]:
    """Separate caption body from hashtags so search ranks the body higher."""
    hashtags = re.findall(r"#(\w+)", text or "")
    body = re.sub(r"\s*#\w+", "", text or "").strip()
    return body, hashtags


@register_processor
class TikTokProcessor(BaseProcessor):
    """TikTok video → typed sections via yt-dlp."""

    url_patterns = [
        r"tiktok\.com/@[^/]+/video/",
        r"vm\.tiktok\.com/",
        r"tiktok\.com/t/",
    ]
    priority = 10

    async def _og_fallback(self, url: str, reason: str) -> ProcessorResult:
        try:
            r = await self._fetch_url(url, timeout=15)
            og = self._extract_og_metadata(r.text)
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="tiktok",
                status=ProcessorStatus.partial,
                error=f"{reason}; OG fallback failed: {str(e)[:120]}",
                metadata={"url": url, "limited_extraction": True},
            )

        title = og.get("og_title") or "TikTok video"
        description = og.get("og_description") or ""
        media: list[dict] = []
        if og.get("og_image"):
            media.append({"type": "image", "url": og["og_image"], "role": "thumbnail"})

        sections: list[Section] = []
        sections.append(Section(
            id=make_section_id(url, 0), kind="title", order=0, role="main",
            text=title,
        ))
        if description:
            sections.append(Section(
                id=make_section_id(url, 1), kind="post", order=1, role="main",
                text=description,
            ))
        sections.append(Section(
            id=make_section_id(url, len(sections)), kind="metadata_block",
            order=len(sections), role="supplemental",
            text="Limited TikTok preview — full caption + transcript not available.",
        ))

        return ProcessorResult(
            title=title,
            description=description[:300] or None,
            content=None,
            media=media,
            metadata={"url": url, "fallback": "og_metadata", "limited_extraction": True},
            source_platform="tiktok",
            item_type="url",
            status=ProcessorStatus.partial,
            error=reason,
            sections=sections,
        )

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        try:
            import yt_dlp
        except ImportError:
            return ProcessorResult(
                title=url, source_platform="tiktok",
                status=ProcessorStatus.failed,
                error="yt-dlp not installed",
                metadata={"url": url},
            )

        try:
            with yt_dlp.YoutubeDL({
                "quiet": True, "no_warnings": True,
                "skip_download": True, "extract_flat": False,
            }) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            # TikTok's extractor breaks regularly. Fall back rather than fail.
            return await self._og_fallback(url, f"yt-dlp failed: {str(e)[:120]}")

        if not info:
            return await self._og_fallback(url, "yt-dlp returned no info")

        full_desc = info.get("description") or ""
        body, hashtags = _split_caption(full_desc)
        title = info.get("title") or body[:100] or url
        author = info.get("uploader") or info.get("creator") or info.get("channel") or ""
        thumbnail_url = info.get("thumbnail")

        media: list[dict] = []
        if thumbnail_url:
            media.append({"type": "image", "url": thumbnail_url, "role": "thumbnail"})
        # Always attach a video-link reference so cards can render an
        # external watch link even if we can't embed.
        media.append({"type": "video", "url": url, "role": "external", "platform": "tiktok"})

        # ─── Sections ───
        sections: list[Section] = []
        order = 0
        sections.append(Section(
            id=make_section_id(url, order), kind="title", order=order,
            role="main", text=title,
        ))
        order += 1

        if body:
            sections.append(Section(
                id=make_section_id(url, order), kind="post", order=order,
                role="main", text=body,
                author=author,
                score=info.get("like_count"),
                created_at=info.get("upload_date"),
                source_url=url,
                extra={"hashtags": hashtags, "duration_s": info.get("duration")},
            ))
            order += 1

        # Transcript subtitles if yt-dlp surfaced them. TikTok rarely
        # ships them, but increasingly so on western markets.
        for lang, tracks in (info.get("subtitles") or {}).items():
            if not tracks:
                continue
            # Prefer English, take first track. We don't fetch+parse VTT
            # here — too expensive for a usually-empty result. Just record
            # availability so a later enrichment can fetch them.
            sections.append(Section(
                id=make_section_id(url, order), kind="transcript_segment",
                order=order, role="main",
                text=f"(Subtitle track available: {lang})",
                extra={"language": lang, "track_url": tracks[0].get("url")},
            ))
            order += 1
            break

        metadata = {
            "url": url,
            "author": author,
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "repost_count": info.get("repost_count"),
            "comment_count": info.get("comment_count"),
            "upload_date": info.get("upload_date"),
            "hashtags": hashtags,
            "duration": info.get("duration"),
        }

        return ProcessorResult(
            title=title,
            description=body[:300] if body else None,
            content=None,
            media=media,
            metadata=metadata,
            source_platform="tiktok",
            item_type="video",
            status=ProcessorStatus.success,
            sections=sections,
        )
