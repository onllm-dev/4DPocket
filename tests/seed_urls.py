"""Seed URL corpus for testing processor selection and extraction quality.

Drawn from real URLs in the production database plus edge cases for
each platform (hyphenated subreddits, username-prefixed Instagram, etc.).
"""

SEED_URLS: dict[str, list[str]] = {
    "youtube": [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=aircAruvnKk",
        "https://youtu.be/uPIuHpG7PTw",
        "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    ],
    "instagram": [
        "https://www.instagram.com/reel/DXBB07DjAtr/",
        "https://www.instagram.com/wasted/p/DXCwcT4ASEw/",
        "https://www.instagram.com/p/ABC123xyz/",
        "https://www.instagram.com/someuser/reel/XYZ789/",
    ],
    "reddit": [
        "https://www.reddit.com/r/programming/comments/1b6yw0p/what_programming_language_should_i_learn_first/",
        "https://www.reddit.com/r/opencodeCLI/comments/1sjsir3/ohmyopencodeslim_vs_superpowers/",
        "https://www.reddit.com/r/some-sub-name/comments/abc123/test_post/",
        "https://old.reddit.com/r/python/comments/abc/test/",
        "https://redd.it/1b6yw0p",
    ],
    "twitter": [
        "https://x.com/TweetsSupportin/status/1468827581315108864",
        "https://twitter.com/elikisFan/status/9999999999",
    ],
    "github": [
        "https://github.com/anthropics/claude-code",
        "https://github.com/microsoft/vscode",
        "https://github.com/torvalds/linux",
        "https://github.com/onllm-dev/onWatch/issues/61",
        "https://gist.github.com/user/abc123def456",
    ],
    "hackernews": [
        "https://news.ycombinator.com/item?id=39599903",
        "https://news.ycombinator.com/item?id=47742200",
    ],
    "stackoverflow": [
        "https://stackoverflow.com/questions/11227809/why-is-processing-a-sorted-array-faster-than-processing-an-unsorted-array",
        "https://stackoverflow.com/questions/79924639/how-to-implement-a-seamless-animation-maui",
        "https://code-review.stackexchange.com/questions/12345/test",
        "https://math.stackexchange.com/questions/67890/test",
    ],
    "substack": [
        "https://substack.com/home/post/p-163234449",
        "https://example.substack.com/p/my-awesome-post",
    ],
    "medium": [
        "https://medium.com/@karpathy/software-2-0-a64152b37c35",
        "https://medium.com/@nikhil.cse16/mastering-the-sliding-window-technique-a-comprehensive-guide-6bb5e1e86f99",
    ],
    "linkedin": [
        "https://www.linkedin.com/posts/will-mctighe_my-friend-laid-off-his-80000year-assistant-activity-7449078921297424384-A7pg",
        "https://www.linkedin.com/pulse/some-article-title",
    ],
    "mastodon": [
        "https://mastodon.social/@pluralistic@mamot.fr/116395778750506218",
        "https://fosstodon.org/@user/12345",
    ],
    "tiktok": [
        "https://www.tiktok.com/@user/video/1234567890",
        "https://vm.tiktok.com/ZMabc123/",
    ],
    "threads": [
        "https://www.threads.net/@zuck/post/abc123",
    ],
    "spotify": [
        "https://open.spotify.com/track/4uLU6hMCjMI75M1A2tKUQC",
    ],
}

# URLs that should NOT match any specialized processor (fall to generic)
GENERIC_URLS = [
    "https://en.wikipedia.org/wiki/Machine_learning",
    "https://arxiv.org/abs/1706.03762",
    "https://news.ycombinator.com/",  # HN homepage — no /item
    "https://pmnco.co.in/blog/5-pvt-ltd-registration-indore-2026/",
]
