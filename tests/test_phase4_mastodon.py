"""Mastodon processor tests — the only Phase 4 platform with a real
public API to mock against (LinkedIn/Instagram/TikTok/Threads need
live HTML/auth that we can't usefully simulate here).
"""

from __future__ import annotations

import asyncio

import httpx
import respx

STATUS_PAYLOAD = {
    "id": "1001",
    "url": "https://mastodon.social/@alice/1001",
    "content": "<p>Main toot here</p>",
    "created_at": "2026-01-01T00:00:00Z",
    "language": "en",
    "favourites_count": 42,
    "reblogs_count": 5,
    "replies_count": 2,
    "account": {"acct": "alice", "display_name": "Alice", "username": "alice"},
    "media_attachments": [
        {
            "type": "image", "url": "https://files.example/x.jpg",
            "preview_url": "https://files.example/x_small.jpg",
            "description": "A photo of a bird on a fence.",
        },
    ],
}

CONTEXT_PAYLOAD = {
    "ancestors": [
        {
            "id": "999",
            "url": "https://mastodon.social/@bob/999",
            "content": "<p>Original question that prompted the toot</p>",
            "favourites_count": 3,
            "created_at": "2025-12-31T23:00:00Z",
            "account": {"acct": "bob", "display_name": "Bob"},
        },
    ],
    "descendants": [
        {
            "id": "1002",
            "url": "https://mastodon.social/@carol/1002",
            "content": "<p>Reply 1 with high score</p>",
            "favourites_count": 12,
            "created_at": "2026-01-01T01:00:00Z",
            "in_reply_to_id": "1001",
            "account": {"acct": "carol"},
        },
        {
            "id": "1003",
            "url": "https://mastodon.social/@dan/1003",
            "content": "<p>Reply 2 lower score</p>",
            "favourites_count": 1,
            "created_at": "2026-01-01T02:00:00Z",
            "in_reply_to_id": "1001",
            "account": {"acct": "dan"},
        },
    ],
}


def test_mastodon_emits_post_ancestors_descendants_alt_text():
    from fourdpocket.processors.mastodon import MastodonProcessor

    proc = MastodonProcessor()
    with respx.mock(assert_all_called=False) as r:
        r.get("https://mastodon.social/api/v1/statuses/1001").mock(
            return_value=httpx.Response(200, json=STATUS_PAYLOAD)
        )
        r.get("https://mastodon.social/api/v1/statuses/1001/context").mock(
            return_value=httpx.Response(200, json=CONTEXT_PAYLOAD)
        )
        result = asyncio.run(proc.process(
            "https://mastodon.social/@alice/1001"
        ))

    sections = result.sections

    # Main post present
    post = next(s for s in sections if s.kind == "post")
    assert post.author == "alice"
    assert "Main toot" in post.text
    assert post.score == 42

    # Ancestor came in as a reply with negative depth
    ancestors = [s for s in sections if s.kind == "reply" and s.depth == -1]
    assert ancestors
    assert ancestors[0].author == "bob"

    # Descendants — score-weighted sort means carol (12) before dan (1)
    descendants = [s for s in sections if s.kind == "reply" and s.depth >= 1]
    assert [s.author for s in descendants] == ["carol", "dan"]
    assert all(s.parent_id == post.id for s in descendants)

    # Alt text → visual_caption
    captions = [s for s in sections if s.kind == "visual_caption"]
    assert captions and "bird" in captions[0].text


def test_mastodon_follows_reblogs_to_underlying_status():
    from fourdpocket.processors.mastodon import MastodonProcessor

    reblog_payload = {
        "id": "555",
        "reblog": STATUS_PAYLOAD,
    }
    with respx.mock(assert_all_called=False) as r:
        r.get("https://mastodon.social/api/v1/statuses/555").mock(
            return_value=httpx.Response(200, json=reblog_payload)
        )
        # Context for the boost id 555 — empty
        r.get("https://mastodon.social/api/v1/statuses/555/context").mock(
            return_value=httpx.Response(200, json={"ancestors": [], "descendants": []})
        )
        result = asyncio.run(MastodonProcessor().process(
            "https://mastodon.social/@booster/555"
        ))

    post = next(s for s in result.sections if s.kind == "post")
    assert post.author == "alice"  # original author, not booster
