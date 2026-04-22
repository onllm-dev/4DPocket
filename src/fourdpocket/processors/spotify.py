"""Spotify processor - extract track, album, and playlist metadata via oEmbed."""

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)

_TYPE_PATTERN = re.compile(r"open\.spotify\.com/(track|album|playlist)/", re.IGNORECASE)


@register_processor
class SpotifyProcessor(BaseProcessor):
    """Extract Spotify metadata using the oEmbed endpoint (no auth required)."""

    url_patterns = [
        r"open\.spotify\.com/track/",
        r"open\.spotify\.com/album/",
        r"open\.spotify\.com/playlist/",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        oembed_url = f"https://open.spotify.com/oembed?url={url}"

        try:
            response = await self._fetch_url(oembed_url, timeout=15)
            data = response.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="spotify",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="spotify",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        title = data.get("title", "")
        author = data.get("author_name", "")
        thumbnail_url = data.get("thumbnail_url", "")
        provider = data.get("provider_name", "Spotify")

        # Determine content type from URL
        type_match = _TYPE_PATTERN.search(url)
        item_subtype = type_match.group(1) if type_match else "track"

        media = []
        if thumbnail_url:
            media.append({"type": "image", "url": thumbnail_url, "role": "thumbnail"})

        metadata = {
            "url": url,
            "author": author,
            "provider": provider,
            "spotify_type": item_subtype,
            "thumbnail_url": thumbnail_url,
            "oembed_html": data.get("html", ""),
        }

        description = f"{item_subtype.capitalize()} by {author}" if author else item_subtype.capitalize()

        sections: list[Section] = []
        order = 0
        if title:
            sections.append(Section(
                id=make_section_id(url, order), kind="title", order=order,
                role="main", text=title,
            ))
            order += 1
        body_parts = [title, f"by {author}" if author else "", item_subtype.capitalize()]
        body_text = "\n".join(p for p in body_parts if p)
        if body_text:
            sections.append(Section(
                id=make_section_id(url, order), kind="paragraph", order=order,
                role="main", text=body_text,
            ))
            order += 1
        oembed_html = data.get("html", "")
        if oembed_html:
            plain = re.sub(r"<[^>]+>", " ", oembed_html).strip()
            if plain:
                sections.append(Section(
                    id=make_section_id(url, order), kind="metadata_block", order=order,
                    role="supplemental", text=plain,
                ))

        return ProcessorResult(
            title=title,
            description=description,
            media=media,
            metadata=metadata,
            source_platform="spotify",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
