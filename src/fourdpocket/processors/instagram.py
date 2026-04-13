"""Instagram processor — instaloader primary, OG metadata fallback.

Phase 4b — Instagram is heavily login-walled. instaloader gets the
public post payload anonymously most of the time but hits IP rate
limits quickly. We treat instaloader as the optimistic path and OG
metadata as the always-works floor.

Sections:
  * ``post`` — caption, with hashtags hoisted into ``extra``
  * ``visual_caption`` — accessibility_caption (Instagram's own
    auto-generated alt text)
  * ``metadata_block`` (when limited) — honest note about the public-
    preview limitation
"""

from __future__ import annotations

import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section, make_section_id

logger = logging.getLogger(__name__)


def _extract_shortcode(url: str) -> str | None:
    m = re.search(r"instagram\.com/(?:[^/]+/)?(?:p|reel|reels)/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else None


@register_processor
class InstagramProcessor(BaseProcessor):
    """Instagram post / reel → typed sections + media."""

    url_patterns = [
        r"instagram\.com/p/[A-Za-z0-9_-]+",
        r"instagram\.com/reel/[A-Za-z0-9_-]+",
        r"instagram\.com/reels/[A-Za-z0-9_-]+",
        r"instagram\.com/[^/]+/p/[A-Za-z0-9_-]+",
        r"instagram\.com/[^/]+/reel/[A-Za-z0-9_-]+",
    ]
    priority = 10

    async def _og_fallback(self, url: str, shortcode: str | None, reason: str) -> ProcessorResult:
        """Best-effort fallback when instaloader fails or isn't installed."""
        try:
            response = await self._fetch_url(url, timeout=15)
            og = self._extract_og_metadata(response.text)
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="instagram",
                status=ProcessorStatus.partial,
                error=f"{reason}; fetch fallback failed: {str(e)[:120]}",
                metadata={"url": url, "shortcode": shortcode, "limited_extraction": True},
            )

        title = og.get("og_title") or "Instagram post"
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
                text=description, source_url=url,
            ))
        sections.append(Section(
            id=make_section_id(url, len(sections)), kind="metadata_block",
            order=len(sections), role="supplemental",
            text=(
                "Instagram returned only the public preview. Sign-in or "
                "instaloader is required to fetch the full caption + media."
            ),
        ))

        return ProcessorResult(
            title=title,
            description=description[:300] or None,
            content=None,
            media=media,
            metadata={
                "url": url,
                "shortcode": shortcode,
                "fallback": "og_metadata",
                "limited_extraction": True,
            },
            source_platform="instagram",
            item_type="url",
            status=ProcessorStatus.partial,
            error=reason,
            sections=sections,
        )

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        shortcode = _extract_shortcode(url)
        if not shortcode:
            return ProcessorResult(
                title=url, source_platform="instagram",
                status=ProcessorStatus.failed,
                error="Could not extract shortcode from URL",
            )

        try:
            import instaloader
        except ImportError:
            return await self._og_fallback(url, shortcode, "instaloader not installed")

        try:
            loader = instaloader.Instaloader(
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                quiet=True,
            )
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
        except Exception as e:
            # Common: rate-limited, login-required, deleted post.
            return await self._og_fallback(
                url, shortcode, f"instaloader failed: {str(e)[:120]}"
            )

        caption = post.caption or ""
        owner = post.owner_username
        is_reel = "/reel/" in url or "/reels/" in url
        hashtags = re.findall(r"#(\w+)", caption)

        # ─── Media ───
        media: list[dict] = []
        try:
            if post.typename == "GraphSidecar":
                for node in post.get_sidecar_nodes():
                    if node.is_video:
                        media.append({"type": "video", "url": node.video_url, "role": "content"})
                    else:
                        media.append({"type": "image", "url": node.display_url, "role": "content"})
            elif post.is_video:
                media.append({"type": "video", "url": post.video_url, "role": "content"})
                if post.url:
                    media.append({"type": "image", "url": post.url, "role": "thumbnail"})
            else:
                media.append({"type": "image", "url": post.url, "role": "content"})
        except Exception as e:
            logger.debug("Media URL extraction failed for %s: %s", shortcode, e)

        # ─── Sections ───
        sections: list[Section] = []
        order = 0
        post_id = make_section_id(url, order)
        sections.append(Section(
            id=post_id, kind="post", order=order, role="main",
            text=caption or "(no caption)",
            author=owner,
            score=post.likes,
            created_at=post.date.isoformat() if post.date else None,
            source_url=url,
            extra={
                "hashtags": hashtags,
                "is_reel": is_reel,
                "media_count": len(media),
                "is_video": post.is_video,
                "comments_count": post.comments,
            },
        ))
        order += 1

        alt = getattr(post, "accessibility_caption", None)
        if alt:
            sections.append(Section(
                id=make_section_id(url, order), kind="visual_caption",
                order=order, parent_id=post_id, role="supplemental",
                text=alt,
                extra={"source": "instagram_accessibility"},
            ))
            order += 1

        metadata = {
            "url": url,
            "shortcode": shortcode,
            "owner": owner,
            "author": owner,
            "likes": post.likes,
            "comments_count": post.comments,
            "is_video": post.is_video,
            "is_reel": is_reel,
            "typename": post.typename,
            "hashtags": hashtags,
            "date": post.date.isoformat() if post.date else None,
            "media_count": len(media),
        }
        if alt:
            metadata["alt_text"] = alt

        title = f"@{owner}: {caption[:80]}{'...' if len(caption) > 80 else ''}"

        return ProcessorResult(
            title=title,
            description=caption[:300] if caption else None,
            content=None,
            raw_content=None,
            media=media,
            metadata=metadata,
            source_platform="instagram",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
