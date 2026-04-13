"""Attach the source domain as a tag for generic-web items.

Generic-platform items otherwise only get AI topical tags. Adding the
registrable domain (e.g. ``theverge.com``) gives users a deterministic
way to find "everything from this site" and prevents two identical
articles on the same site from looking unrelated in search.
"""

from __future__ import annotations

import logging
import re
import uuid
from urllib.parse import urlparse

import tldextract
from sqlmodel import Session, select

from fourdpocket.models.tag import ItemTag, Tag

logger = logging.getLogger(__name__)

# Platforms that already set their own source_platform and therefore
# don't need a fallback domain tag — adding "reddit.com" on every Reddit
# post would be noise.
_PLATFORM_DOMAINS: set[str] = {
    # Registrable domains only — tldextract collapses subdomains (e.g.
    # "news.ycombinator.com" → "ycombinator.com", "open.spotify.com" →
    # "spotify.com") so we match at the registrable level.
    "reddit.com",
    "redd.it",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "github.com",
    "medium.com",
    "substack.com",
    "linkedin.com",
    "instagram.com",
    "tiktok.com",
    "threads.net",
    "spotify.com",
    "ycombinator.com",
    "stackoverflow.com",
    "stackexchange.com",
    "mastodon.social",
    "mastodon.online",
}


def _slug(name: str) -> str:
    slug = name.lower().strip()[:100]
    slug = re.sub(r"[^\w.-]", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-.")
    return slug


def extract_domain(url: str) -> str | None:
    """Return the registrable domain for *url* or None if it can't be parsed.

    Uses tldextract's PSL (handles edge cases like ``bbc.co.uk`` correctly).
    Strips ``www.`` and other common throwaway subdomains.
    """
    if not url:
        return None
    try:
        # tldextract handles URLs with or without scheme
        ext = tldextract.extract(url)
    except Exception:
        return None

    if not ext.domain or not ext.suffix:
        # Try to salvage localhost/IP-style URLs — not useful as tags, skip.
        return None

    registrable = f"{ext.domain}.{ext.suffix}"

    # Keep meaningful subdomains (e.g. "blog.example.com", "en.wikipedia.org")
    # but drop generic ones.
    skip_subdomains = {"", "www", "m", "mobile", "amp"}
    if ext.subdomain and ext.subdomain.lower() not in skip_subdomains:
        # Only prepend the *last* subdomain segment to avoid very long tags
        # like "en-uk.blog.subdomain.site.example.com"
        last_sub = ext.subdomain.split(".")[-1].lower()
        if last_sub not in skip_subdomains and len(last_sub) <= 40:
            registrable = f"{last_sub}.{registrable}"

    # Basic hostname sanity — urlparse gives us the raw netloc
    parsed = urlparse(url if "://" in url else f"http://{url}")
    if not parsed.netloc:
        return None

    return registrable.lower()


def is_platform_url(url: str) -> bool:
    """True if *url* belongs to a domain we already have a dedicated processor for."""
    if not url:
        return False
    try:
        ext = tldextract.extract(url)
    except Exception:
        return False
    registrable = f"{ext.domain}.{ext.suffix}".lower() if ext.domain and ext.suffix else ""
    return registrable in _PLATFORM_DOMAINS


def attach_domain_tag(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    url: str | None,
    source_platform: str | None,
    db: Session,
) -> str | None:
    """Attach a domain-derived tag to *item_id* if eligible.

    Eligibility:
      * ``url`` is non-empty
      * ``source_platform`` is a generic/web fallback (not a dedicated processor)
      * domain extraction yields a registrable name

    Returns the tag slug that was attached, or None if skipped.
    """
    if not url:
        return None

    platform = (source_platform or "").lower()
    if platform not in {"", "generic", "web", "url"}:
        # A dedicated processor already claimed this — don't tag with domain.
        return None

    if is_platform_url(url):
        # Defensive — even if source_platform is "generic", don't pollute
        # platform items with their own domain tag.
        return None

    domain = extract_domain(url)
    if not domain:
        return None

    slug = _slug(domain)
    if not slug:
        return None

    # Find-or-create tag
    tag = db.exec(
        select(Tag).where(Tag.user_id == user_id, Tag.slug == slug)
    ).first()
    if tag is None:
        tag = Tag(
            user_id=user_id,
            name=domain,
            slug=slug,
            ai_generated=False,
        )
        db.add(tag)
        db.flush()

    # Idempotent link
    existing = db.exec(
        select(ItemTag).where(
            ItemTag.item_id == item_id,
            ItemTag.tag_id == tag.id,
        )
    ).first()
    if existing is None:
        db.add(ItemTag(item_id=item_id, tag_id=tag.id, confidence=1.0))
        tag.usage_count = Tag.usage_count + 1  # SQL-level increment
        db.add(tag)
        db.commit()
        logger.info("Attached domain tag %s to item %s", domain, item_id)
    return slug
