"""Unit tests for the domain tagger."""

import uuid

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from fourdpocket.ai.domain_tagger import (
    attach_domain_tag,
    extract_domain,
    is_platform_url,
)
from fourdpocket.models.tag import ItemTag, Tag

# ─── extract_domain ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.theverge.com/2024/foo", "theverge.com"),
        ("https://theverge.com/2024/foo", "theverge.com"),
        ("http://m.theverge.com/2024/foo", "theverge.com"),
        ("https://blog.example.com/post", "blog.example.com"),
        ("https://en.wikipedia.org/wiki/Foo", "en.wikipedia.org"),
        # PSL edge: bbc.co.uk's registrable is bbc.co.uk, not co.uk
        ("https://www.bbc.co.uk/news/x", "bbc.co.uk"),
        ("https://news.bbc.co.uk/story", "news.bbc.co.uk"),
        # URL without scheme still parses
        ("example.org/path", "example.org"),
        # Case-insensitive
        ("HTTPS://EXAMPLE.COM/Foo", "example.com"),
    ],
)
def test_extract_domain_happy_path(url, expected):
    assert extract_domain(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "http://localhost:8080/foo",
        "http://127.0.0.1/foo",
        "not a url at all",
    ],
)
def test_extract_domain_returns_none_for_unsuitable(url):
    # localhost/IPs have no public suffix so extract returns None → correct.
    assert extract_domain(url) is None


# ─── is_platform_url ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://reddit.com/r/python", True),
        ("https://www.reddit.com/r/python", True),
        ("https://youtu.be/abc", True),
        ("https://github.com/foo/bar", True),
        ("https://x.com/user/status/1", True),
        ("https://theverge.com/foo", False),
        ("https://news.ycombinator.com/item?id=1", True),
        ("", False),
    ],
)
def test_is_platform_url(url, expected):
    assert is_platform_url(url) is expected


# ─── attach_domain_tag ──────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _tag_count(db: Session, user_id, slug) -> int:
    return len(db.exec(select(Tag).where(Tag.user_id == user_id, Tag.slug == slug)).all())


def _link_count(db: Session, item_id, tag_slug, user_id) -> int:
    tag = db.exec(
        select(Tag).where(Tag.user_id == user_id, Tag.slug == tag_slug)
    ).first()
    if not tag:
        return 0
    return len(
        db.exec(select(ItemTag).where(ItemTag.item_id == item_id, ItemTag.tag_id == tag.id)).all()
    )


def test_attach_domain_tag_generic(db):
    item_id = uuid.uuid4()
    user_id = uuid.uuid4()
    slug = attach_domain_tag(
        item_id=item_id,
        user_id=user_id,
        url="https://www.theverge.com/2024/foo",
        source_platform="generic",
        db=db,
    )
    assert slug == "theverge.com"
    assert _tag_count(db, user_id, "theverge.com") == 1
    assert _link_count(db, item_id, "theverge.com", user_id) == 1


def test_attach_domain_tag_is_idempotent(db):
    item_id = uuid.uuid4()
    user_id = uuid.uuid4()
    for _ in range(3):
        attach_domain_tag(
            item_id=item_id,
            user_id=user_id,
            url="https://theverge.com/x",
            source_platform="generic",
            db=db,
        )
    assert _link_count(db, item_id, "theverge.com", user_id) == 1


def test_attach_domain_tag_skips_known_platforms(db):
    item_id = uuid.uuid4()
    user_id = uuid.uuid4()
    slug = attach_domain_tag(
        item_id=item_id,
        user_id=user_id,
        url="https://reddit.com/r/python/comments/abc",
        source_platform="reddit",
        db=db,
    )
    assert slug is None


def test_attach_domain_tag_skips_when_platform_set(db):
    """Even if URL is non-platform, a dedicated processor name suppresses tag."""
    item_id = uuid.uuid4()
    user_id = uuid.uuid4()
    slug = attach_domain_tag(
        item_id=item_id,
        user_id=user_id,
        url="https://custom.example.com/item",
        source_platform="medium",  # dedicated processor claimed it
        db=db,
    )
    assert slug is None


def test_attach_domain_tag_handles_empty_url(db):
    item_id = uuid.uuid4()
    user_id = uuid.uuid4()
    slug = attach_domain_tag(
        item_id=item_id,
        user_id=user_id,
        url="",
        source_platform="generic",
        db=db,
    )
    assert slug is None
