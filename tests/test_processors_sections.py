"""Verify Phase 2 platform processors emit structured sections.

Uses ``respx`` to mock the HTTP layer so these run without network. We
test the section *shape* (kind, ordering, parent_id, author, score) and
back-compat (title/metadata still populated). Live API behaviour belongs
in a separate integration suite — these are unit tests.
"""

from __future__ import annotations

import asyncio

import httpx
import respx

# ─── Reddit ─────────────────────────────────────────────────


REDDIT_PAYLOAD = [
    {  # post listing
        "data": {"children": [{
            "kind": "t3",
            "data": {
                "id": "abc",
                "title": "Why does dict ordering matter?",
                "selftext": "Question body here.",
                "subreddit": "python",
                "author": "op_user",
                "score": 42,
                "num_comments": 2,
                "permalink": "/r/python/comments/abc/why/",
                "created_utc": 1700000000,
                "url": "https://reddit.com/r/python/comments/abc/why/",
                "is_self": True,
                "link_flair_text": "Discussion",
            },
        }]},
    },
    {  # comments listing
        "data": {"children": [
            {
                "kind": "t1",
                "data": {
                    "id": "c1",
                    "author": "raymond_h",
                    "body": "It's a CPython implementation detail.",
                    "score": 311,
                    "permalink": "/r/python/comments/abc/why/c1/",
                    "replies": {"data": {"children": [
                        {
                            "kind": "t1",
                            "data": {
                                "id": "c2",
                                "author": "curious_dev",
                                "body": "PEP 468 also relies on this.",
                                "score": 42,
                                "permalink": "/r/python/comments/abc/why/c2/",
                            },
                        },
                    ]}},
                },
            },
            {
                "kind": "t1",
                "data": {
                    "id": "c3",
                    "author": "another",
                    "body": "Worth reading the PEP discussion.",
                    "score": 88,
                    "permalink": "/r/python/comments/abc/why/c3/",
                },
            },
            # deleted comment should be skipped
            {"kind": "t1", "data": {"id": "c4", "author": "x", "body": "[deleted]", "score": 0}},
            # 'more' continuation should be ignored
            {"kind": "more", "data": {"children": ["c5", "c6"]}},
        ]},
    },
]


def test_reddit_emits_sectioned_post_and_threaded_comments():
    from fourdpocket.processors.reddit import RedditProcessor

    proc = RedditProcessor()

    with respx.mock(assert_all_called=False) as r:
        # _fetch_reddit_json hits the .json endpoint with our query string
        r.get(url__regex=r"https://www\.reddit\.com/r/python/comments/abc/why\.json.*").mock(
            return_value=httpx.Response(200, json=REDDIT_PAYLOAD)
        )
        result = asyncio.run(
            proc.process("https://www.reddit.com/r/python/comments/abc/why/")
        )

    assert result.source_platform == "reddit"
    assert result.title.startswith("[r/python]")

    sections = result.sections
    # 1 post + 2 top-level comments + 1 nested reply (deleted skipped)
    assert sum(1 for s in sections if s.kind == "post") == 1
    assert sum(1 for s in sections if s.kind == "comment") == 2
    assert sum(1 for s in sections if s.kind == "reply") == 1

    post = next(s for s in sections if s.kind == "post")
    assert post.author == "op_user"
    assert post.score == 42
    assert post.parent_id is None

    # Top-scored comment first (score-weighted DFS)
    comments = [s for s in sections if s.kind == "comment"]
    assert comments[0].author == "raymond_h"
    assert comments[0].score == 311
    assert comments[0].parent_id == post.id

    reply = next(s for s in sections if s.kind == "reply")
    assert reply.depth == 2
    assert reply.parent_id == comments[0].id


# ─── Hacker News ─────────────────────────────────────────────


HN_PAYLOAD = {
    "id": 1,
    "title": "Show HN: Cool thing",
    "author": "founder",
    "points": 250,
    "text": "We built X to solve Y.",
    "url": "https://example.com/cool",
    "created_at": "2026-01-01T00:00:00Z",
    "children": [
        {
            "id": 10, "type": "comment", "author": "alice",
            "text": "Looks great.", "points": 50, "created_at": "2026-01-01T01:00:00Z",
            "children": [
                {
                    "id": 11, "type": "comment", "author": "bob",
                    "text": "Agreed.", "points": 5, "children": [],
                },
            ],
        },
        {
            "id": 12, "type": "comment", "author": "carol",
            "text": "Question: does it scale?", "points": 30, "children": [],
        },
    ],
}


def test_hackernews_emits_post_and_comment_tree():
    from fourdpocket.processors.hackernews import HackerNewsProcessor

    proc = HackerNewsProcessor()

    with respx.mock(assert_all_called=False) as r:
        r.get("https://hn.algolia.com/api/v1/items/1").mock(
            return_value=httpx.Response(200, json=HN_PAYLOAD)
        )
        result = asyncio.run(proc.process("https://news.ycombinator.com/item?id=1"))

    sections = result.sections
    post = next(s for s in sections if s.kind == "post")
    assert post.author == "founder"
    assert post.score == 250
    comments = [s for s in sections if s.kind in ("comment", "reply")]
    assert {s.author for s in comments} == {"alice", "carol", "bob"}
    # alice has highest score → comes first among top-level
    top = [s for s in sections if s.kind == "comment"]
    assert top[0].author == "alice"
    bob = next(s for s in sections if s.author == "bob")
    assert bob.depth == 2
    assert bob.kind == "reply"


# ─── Stack Overflow ─────────────────────────────────────────


SO_RICH_PAYLOAD = {
    "items": [{
        "question_id": 12345,
        "title": "How do I do X?",
        "body": "<p>I want to do X.</p>",
        "score": 100,
        "tags": ["python", "regex"],
        "owner": {"display_name": "asker"},
        "creation_date": 1700000000,
        "view_count": 5000,
        "answers": [
            {
                "answer_id": 222, "is_accepted": False, "score": 5,
                "body": "Try Y.",
                "owner": {"display_name": "ans2"},
                "comments": [],
            },
            {
                "answer_id": 111, "is_accepted": True, "score": 50,
                "body": "Use the X library.",
                "owner": {"display_name": "expert"},
                "creation_date": 1700000100,
                "comments": [
                    {
                        "comment_id": 333, "body": "Worked for me too",
                        "owner": {"display_name": "fan"}, "score": 3,
                    },
                ],
            },
        ],
        "comments": [],
    }],
}


def test_stackoverflow_orders_accepted_answer_first():
    from fourdpocket.processors.stackoverflow import StackOverflowProcessor

    proc = StackOverflowProcessor()

    with respx.mock(assert_all_called=False) as r:
        r.get(url__regex=r"https://api\.stackexchange\.com/2\.3/questions/12345.*").mock(
            return_value=httpx.Response(200, json=SO_RICH_PAYLOAD)
        )
        result = asyncio.run(proc.process(
            "https://stackoverflow.com/questions/12345/how"
        ))

    sections = result.sections
    question = next(s for s in sections if s.kind == "question")
    assert question.author == "asker"
    assert question.score == 100

    answers = [s for s in sections if s.kind in ("answer", "accepted_answer")]
    assert answers[0].kind == "accepted_answer"
    assert answers[0].author == "expert"
    assert answers[0].is_accepted is True
    assert answers[1].kind == "answer"

    # Comment on accepted answer should be parented to it
    comment = next(s for s in sections if s.author == "fan")
    assert comment.parent_id == answers[0].id
    assert comment.depth == 2


# ─── Twitter ─────────────────────────────────────────────


FX_PAYLOAD = {
    "tweet": {
        "text": "Hot take: dependency injection is overrated.",
        "created_at": "2026-01-01T00:00:00Z",
        "lang": "en",
        "likes": 200,
        "retweets": 30,
        "replies": 12,
        "author": {
            "name": "Some Dev", "screen_name": "somedev",
            "followers": 10_000, "avatar_url": "https://pbs.twimg.com/avatar.jpg",
        },
        "media": {"all": [
            {"type": "photo", "url": "https://pbs.twimg.com/media/x.jpg"},
        ]},
        "quote": {
            "text": "Original take I'm responding to",
            "author": {"name": "Other Dev", "screen_name": "otherdev"},
            "likes": 50,
        },
    },
}


def test_twitter_emits_post_and_quoted_post():
    from fourdpocket.processors.twitter import TwitterProcessor

    proc = TwitterProcessor()

    with respx.mock(assert_all_called=False) as r:
        r.get("https://api.fxtwitter.com/somedev/status/123456").mock(
            return_value=httpx.Response(200, json=FX_PAYLOAD)
        )
        result = asyncio.run(proc.process("https://x.com/somedev/status/123456"))

    sections = result.sections
    main = next(s for s in sections if s.kind == "post")
    assert main.author == "somedev"
    assert main.score == 200

    quoted = next(s for s in sections if s.kind == "quoted_post")
    assert quoted.author == "otherdev"
    assert quoted.parent_id == main.id


# ─── GitHub ─────────────────────────────────────────────


REPO_PAYLOAD = {
    "full_name": "torvalds/linux",
    "description": "Linux kernel source tree",
    "stargazers_count": 100_000,
    "forks_count": 30_000,
    "language": "C",
    "topics": ["kernel"],
    "owner": {"login": "torvalds", "avatar_url": "https://github.com/torvalds.png"},
    "html_url": "https://github.com/torvalds/linux",
    "default_branch": "master",
}
README_PAYLOAD = {
    "content": __import__("base64").b64encode(
        b"# Linux\nA kernel.\n\n## Building\nrun make.\n"
    ).decode(),
    "encoding": "base64",
}


def test_github_repo_splits_readme_into_heading_sections():
    from fourdpocket.processors.github import GitHubProcessor

    proc = GitHubProcessor()

    with respx.mock(assert_all_called=False) as r:
        r.get("https://api.github.com/repos/torvalds/linux").mock(
            return_value=httpx.Response(200, json=REPO_PAYLOAD)
        )
        r.get("https://api.github.com/repos/torvalds/linux/readme").mock(
            return_value=httpx.Response(200, json=README_PAYLOAD)
        )
        result = asyncio.run(proc.process("https://github.com/torvalds/linux"))

    sections = result.sections
    assert any(s.kind == "title" for s in sections)
    headings = [s for s in sections if s.kind == "heading"]
    assert "Linux" in {h.text for h in headings}
    assert "Building" in {h.text for h in headings}
    paragraphs = [s for s in sections if s.kind == "paragraph"]
    assert any("kernel" in p.text.lower() for p in paragraphs)


ISSUE_PAYLOAD = {
    "title": "Kernel panic on boot",
    "body": "It panics when I do X.",
    "user": {"login": "reporter"},
    "comments": 1,
    "comments_url": "https://api.github.com/repos/torvalds/linux/issues/42/comments",
    "labels": [{"name": "bug"}],
    "state": "open",
    "html_url": "https://github.com/torvalds/linux/issues/42",
    "created_at": "2026-01-01T00:00:00Z",
    "reactions": {"total_count": 5},
}
ISSUE_COMMENTS = [
    {
        "id": 1, "body": "Confirmed on my machine too.",
        "user": {"login": "another"}, "created_at": "2026-01-02T00:00:00Z",
        "html_url": "https://github.com/torvalds/linux/issues/42#issuecomment-1",
    },
]


def test_github_issue_emits_post_and_comments():
    from fourdpocket.processors.github import GitHubProcessor

    proc = GitHubProcessor()

    with respx.mock(assert_all_called=False) as r:
        r.get("https://api.github.com/repos/torvalds/linux/issues/42").mock(
            return_value=httpx.Response(200, json=ISSUE_PAYLOAD)
        )
        r.get("https://api.github.com/repos/torvalds/linux/issues/42/comments").mock(
            return_value=httpx.Response(200, json=ISSUE_COMMENTS)
        )
        result = asyncio.run(proc.process("https://github.com/torvalds/linux/issues/42"))

    sections = result.sections
    post = next(s for s in sections if s.kind == "post")
    assert post.author == "reporter"
    comment = next(s for s in sections if s.kind == "comment")
    assert comment.author == "another"
    assert comment.parent_id == post.id
