"""Instagram processor — extract posts via instaloader."""

import json
import logging
import re

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_shortcode(url: str) -> str | None:
    """Extract Instagram shortcode from URL."""
    match = re.search(r"instagram\.com/(?:p|reel|reels)/([A-Za-z0-9_-]+)", url)
    return match.group(1) if match else None


@register_processor
class InstagramProcessor(BaseProcessor):
    """Extract Instagram post content via instaloader."""

    url_patterns = [
        r"instagram\.com/p/[A-Za-z0-9_-]+",
        r"instagram\.com/reel/[A-Za-z0-9_-]+",
        r"instagram\.com/reels/[A-Za-z0-9_-]+",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        shortcode = _extract_shortcode(url)
        if not shortcode:
            return ProcessorResult(
                title=url,
                source_platform="instagram",
                status=ProcessorStatus.failed,
                error="Could not extract shortcode from URL",
            )

        try:
            import instaloader

            L = instaloader.Instaloader(
                download_pictures=False,
                download_videos=False,
                download_video_thumbnails=False,
                download_geotags=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                quiet=True,
            )

            post = instaloader.Post.from_shortcode(L.context, shortcode)

            caption = post.caption or ""
            owner = post.owner_username
            is_reel = "/reel/" in url or "/reels/" in url

            # Extract hashtags from caption
            hashtags = re.findall(r"#(\w+)", caption)

            # Extract media URLs
            media = []
            if post.typename == "GraphSidecar":
                # Carousel post
                for node in post.get_sidecar_nodes():
                    if node.is_video:
                        media.append({
                            "type": "video",
                            "url": node.video_url,
                            "role": "content",
                        })
                    else:
                        media.append({
                            "type": "image",
                            "url": node.display_url,
                            "role": "content",
                        })
            elif post.is_video:
                media.append({
                    "type": "video",
                    "url": post.video_url,
                    "role": "content",
                })
                if post.url:
                    media.append({
                        "type": "image",
                        "url": post.url,
                        "role": "thumbnail",
                    })
            else:
                media.append({
                    "type": "image",
                    "url": post.url,
                    "role": "content",
                })

            metadata = {
                "url": url,
                "shortcode": shortcode,
                "owner": owner,
                "likes": post.likes,
                "comments_count": post.comments,
                "is_video": post.is_video,
                "is_reel": is_reel,
                "typename": post.typename,
                "hashtags": hashtags,
                "date": post.date.isoformat() if post.date else None,
                "media_count": len(media),
            }

            # Alt text
            if hasattr(post, "accessibility_caption") and post.accessibility_caption:
                metadata["alt_text"] = post.accessibility_caption

            title = f"@{owner}: {caption[:80]}{'...' if len(caption) > 80 else ''}"

            return ProcessorResult(
                title=title,
                description=caption[:300] if caption else None,
                content=caption,
                raw_content=None,
                media=media,
                metadata=metadata,
                source_platform="instagram",
                item_type="url",
                status=ProcessorStatus.success,
            )

        except ImportError:
            logger.warning("instaloader not installed")
            # Fall back to OG metadata via generic processor
            try:
                response = await self._fetch_url(url)
                og_meta = self._extract_og_metadata(response.text)
                return ProcessorResult(
                    title=og_meta.get("og_title", url),
                    description=og_meta.get("og_description"),
                    media=[{"type": "image", "url": og_meta["og_image"], "role": "thumbnail"}]
                    if og_meta.get("og_image")
                    else [],
                    metadata={"url": url, "shortcode": shortcode, "fallback": "og_metadata"},
                    source_platform="instagram",
                    item_type="url",
                    status=ProcessorStatus.partial,
                    error="instaloader not installed, using OG metadata fallback",
                )
            except Exception:
                return ProcessorResult(
                    title=url,
                    source_platform="instagram",
                    status=ProcessorStatus.partial,
                    error="instaloader not installed",
                    metadata={"url": url, "shortcode": shortcode},
                )

        except Exception as e:
            logger.warning("Instagram extraction failed for %s: %s", url, e)
            return ProcessorResult(
                title=url,
                source_platform="instagram",
                status=ProcessorStatus.partial,
                error=f"Extraction failed: {str(e)[:200]}",
                metadata={"url": url, "shortcode": shortcode},
            )
