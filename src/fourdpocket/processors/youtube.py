"""YouTube video/shorts processor using yt-dlp and youtube-transcript-api."""

import json
import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_video_id(url: str) -> str | None:
    """Extract video ID from various YouTube URL formats."""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
        r"youtube\.com/embed/([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


@register_processor
class YouTubeProcessor(BaseProcessor):
    """Extract metadata and transcript from YouTube videos."""

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

        # Extract metadata via yt-dlp
        metadata = {}
        title = None
        description = None
        media = []

        try:
            import yt_dlp

            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extract_flat": False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if info:
                title = info.get("title")
                description = info.get("description", "")

                metadata = {
                    "video_id": video_id,
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
                }

                # Chapters
                chapters = info.get("chapters")
                if chapters:
                    metadata["chapters"] = [
                        {
                            "title": ch.get("title", ""),
                            "start_time": ch.get("start_time", 0),
                            "end_time": ch.get("end_time", 0),
                        }
                        for ch in chapters
                    ]

                # Thumbnail
                thumbnail = info.get("thumbnail")
                if thumbnail:
                    media.append({"type": "image", "url": thumbnail, "role": "thumbnail"})

                # Additional thumbnails
                for thumb in (info.get("thumbnails") or [])[:3]:
                    if thumb.get("url") and thumb["url"] != thumbnail:
                        media.append({"type": "image", "url": thumb["url"], "role": "thumbnail_alt"})

        except ImportError:
            return ProcessorResult(
                title=url,
                source_platform="youtube",
                status=ProcessorStatus.failed,
                error="yt-dlp not installed",
                metadata={"video_id": video_id},
            )
        except Exception as e:
            logger.warning("yt-dlp extraction failed for %s: %s", url, e)
            # Continue with partial data
            title = url
            metadata = {"video_id": video_id, "yt_dlp_error": str(e)[:200]}

        # Extract transcript
        transcript_text = None
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Prefer manual transcripts, fall back to auto-generated
            transcript = None
            try:
                transcript = transcript_list.find_manually_created_transcript(["en"])
            except Exception:
                try:
                    transcript = transcript_list.find_generated_transcript(["en"])
                except Exception:
                    # Try any available language
                    try:
                        for t in transcript_list:
                            transcript = t
                            break
                    except Exception:
                        pass

            if transcript:
                fetched = transcript.fetch()
                transcript_text = " ".join(
                    entry.get("text", "") if isinstance(entry, dict) else str(entry)
                    for entry in fetched
                )
                metadata["transcript_language"] = transcript.language
                metadata["transcript_auto_generated"] = transcript.is_generated

        except ImportError:
            metadata["transcript_error"] = "youtube-transcript-api not installed"
        except Exception as e:
            logger.debug("Transcript extraction failed for %s: %s", video_id, e)
            metadata["transcript_error"] = str(e)[:200]

        # Build content from description + transcript
        content_parts = []
        if description:
            content_parts.append(f"## Description\n\n{description}")
        if transcript_text:
            content_parts.append(f"## Transcript\n\n{transcript_text}")
        content = "\n\n---\n\n".join(content_parts) if content_parts else None

        status = ProcessorStatus.success
        error = None
        if not title or title == url:
            status = ProcessorStatus.partial
            error = "Could not extract full metadata"

        return ProcessorResult(
            title=title or url,
            description=(description or "")[:500],
            content=content,
            raw_content=json.dumps(metadata, default=str)[:100000],
            media=media,
            metadata=metadata,
            source_platform="youtube",
            item_type="url",
            status=status,
            error=error,
        )
