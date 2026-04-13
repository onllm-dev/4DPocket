"""Tests for GitHub processor extract() and edge cases."""

from __future__ import annotations

import asyncio
import base64

import httpx
import pytest
import respx

from fourdpocket.processors.github import GitHubProcessor, _parse_github_url

# ─── URL pattern matching ────────────────────────────────────────────────────


class TestURLPatternMatching:
    """Processor matches expected URL patterns."""

    @pytest.mark.parametrize("url", [
        "https://github.com/facebook/react",
        "https://github.com/facebook/react/",
        "https://github.com/facebook/react/issues/123",
        "https://github.com/facebook/react/pull/456",
        "https://gist.github.com/user/abc123def",
        "https://github.com/Microsoft/vscode",
    ])
    def test_parses_known_url_types(self, url: str):
        result = _parse_github_url(url)
        assert result["type"] != "unknown", f"Failed to parse: {url}"


class TestGitHubProcessor:
    """Test the GitHubProcessor.process() method with mocked HTTP responses."""

    # ─── Repository extraction ───────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_extract_repo_success(self):
        """Happy path: valid repo URL returns ProcessorResult with sections."""
        proc = GitHubProcessor()

        repo_payload = {
            "full_name": "facebook/react",
            "description": "A declarative UI library",
            "stargazers_count": 250000,
            "forks_count": 55000,
            "language": "JavaScript",
            "topics": ["ui", "react", "frontend"],
            "owner": {"login": "facebook", "avatar_url": "https://github.com/facebook.png"},
            "html_url": "https://github.com/facebook/react",
            "default_branch": "main",
        }
        readme_content = base64.b64encode(
            b"# React\n\nA UI library.\n\n## Getting Started\n\nInstall with npm."
        ).decode()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/facebook/react").mock(
                return_value=httpx.Response(200, json=repo_payload)
            )
            r.get("https://api.github.com/repos/facebook/react/readme").mock(
                return_value=httpx.Response(200, json={"content": readme_content, "encoding": "base64"})
            )
            result = asyncio.run(proc.process("https://github.com/facebook/react"))

        assert result.source_platform == "github"
        assert result.status.value == "success"
        assert result.title == "facebook/react"
        assert result.metadata.get("stars") == 250000
        assert result.metadata.get("forks") == 55000
        assert result.metadata.get("language") == "JavaScript"
        sections = result.sections
        assert any(s.kind == "title" for s in sections)
        assert any(s.kind == "paragraph" for s in sections)

    @respx.mock(assert_all_called=False)
    def test_extract_repo_readme_heading_sections(self):
        """README is split into heading + paragraph sections."""
        proc = GitHubProcessor()

        repo_payload = {
            "full_name": "example/repo", "description": "Example repo",
            "stargazers_count": 0, "forks_count": 0, "owner": {"login": "e", "avatar_url": ""},
            "html_url": "https://github.com/example/repo", "default_branch": "main",
        }
        readme_md = base64.b64encode(
            b"# Title\n\nIntro.\n\n## Section One\n\nBody one.\n\n## Section Two\n\nBody two."
        ).decode()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/example/repo").mock(
                return_value=httpx.Response(200, json=repo_payload)
            )
            r.get("https://api.github.com/repos/example/repo/readme").mock(
                return_value=httpx.Response(200, json={"content": readme_md, "encoding": "base64"})
            )
            result = asyncio.run(proc.process("https://github.com/example/repo"))

        headings = [s for s in result.sections if s.kind == "heading"]
        heading_texts = {h.text for h in headings}
        assert "Title" in heading_texts
        assert "Section One" in heading_texts
        assert "Section Two" in heading_texts

    @respx.mock(assert_all_called=False)
    def test_extract_repo_no_readme(self):
        """Repo with no README still returns success."""
        proc = GitHubProcessor()

        repo_payload = {
            "full_name": "example/empty", "description": None,
            "stargazers_count": 0, "forks_count": 0, "owner": {"login": "e", "avatar_url": ""},
            "html_url": "https://github.com/example/empty", "default_branch": "main",
        }

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/example/empty").mock(
                return_value=httpx.Response(200, json=repo_payload)
            )
            r.get("https://api.github.com/repos/example/empty/readme").mock(
                return_value=httpx.Response(404)
            )
            result = asyncio.run(proc.process("https://github.com/example/empty"))

        assert result.status.value == "success"
        assert result.title == "example/empty"

    # ─── Issue extraction ────────────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_extract_issue_success(self):
        """Issue URL returns ProcessorResult with post + comment sections."""
        proc = GitHubProcessor()

        issue_payload = {
            "title": "Bug: component crashes on mount",
            "body": "Steps to reproduce...",
            "user": {"login": "reporter"},
            "comments": 1,
            "comments_url": "https://api.github.com/repos/facebook/react/issues/123/comments",
            "labels": [{"name": "bug"}, {"name": "priority-high"}],
            "state": "open",
            "html_url": "https://github.com/facebook/react/issues/123",
            "created_at": "2026-01-01T00:00:00Z",
            "reactions": {"total_count": 5},
        }
        issue_comments = [
            {
                "id": 1, "body": "I can reproduce this.",
                "user": {"login": "helper"}, "created_at": "2026-01-02T00:00:00Z",
                "html_url": "https://github.com/facebook/react/issues/123#issuecomment-1",
            },
        ]

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/facebook/react/issues/123").mock(
                return_value=httpx.Response(200, json=issue_payload)
            )
            r.get("https://api.github.com/repos/facebook/react/issues/123/comments").mock(
                return_value=httpx.Response(200, json=issue_comments)
            )
            result = asyncio.run(
                proc.process("https://github.com/facebook/react/issues/123")
            )

        assert result.source_platform == "github"
        assert result.status.value == "success"
        assert "Bug: component crashes on mount" in result.title
        sections = result.sections
        post = next((s for s in sections if s.kind == "post"), None)
        assert post is not None
        assert post.author == "reporter"
        comment = next((s for s in sections if s.kind == "comment"), None)
        assert comment is not None
        assert comment.author == "helper"
        assert comment.parent_id == post.id

    @respx.mock(assert_all_called=False)
    def test_extract_issue_404(self):
        """Issue returns 404 → partial status with error."""
        proc = GitHubProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/facebook/react/issues/999999").mock(
                return_value=httpx.Response(404)
            )
            result = asyncio.run(
                proc.process("https://github.com/facebook/react/issues/999999")
            )

        assert result.status.value == "partial"
        assert result.error is not None
        assert "404" in result.error

    @respx.mock(assert_all_called=False)
    def test_extract_repo_rate_limited(self):
        """API rate limit returns partial status."""
        proc = GitHubProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/facebook/react").mock(
                return_value=httpx.Response(403, json={"message": "rate limit exceeded"})
            )
            result = asyncio.run(proc.process("https://github.com/facebook/react"))

        assert result.status.value == "partial"
        assert result.error is not None

    # ─── Network errors ───────────────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_extract_network_error(self):
        """Network error returns failed status gracefully."""
        proc = GitHubProcessor()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/facebook/react").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = asyncio.run(proc.process("https://github.com/facebook/react"))

        assert result.status.value == "failed"
        assert result.error is not None

    # ─── Gist extraction ─────────────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_extract_gist_success(self):
        """Gist URL returns ProcessorResult with code sections."""
        proc = GitHubProcessor()

        gist_payload = {
            "description": "Useful snippet",
            "public": True,
            "owner": {"login": "someuser"},
            "html_url": "https://gist.github.com/someuser/abc123",
            "files": {
                "hello.py": {
                    "content": "print('hello world')",
                    "language": "Python",
                },
                "utils.js": {
                    "content": "const x = 1;",
                    "language": "JavaScript",
                },
            },
        }

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/gists/abc123").mock(
                return_value=httpx.Response(200, json=gist_payload)
            )
            result = asyncio.run(
                proc.process("https://gist.github.com/someuser/abc123")
            )

        assert result.source_platform == "github"
        assert result.status.value == "success"
        assert result.title == "Useful snippet"
        sections = result.sections
        assert any(s.kind == "title" for s in sections)
        code_sections = [s for s in sections if s.kind == "code"]
        assert len(code_sections) == 2
        assert any("hello" in s.text for s in code_sections)

    # ─── Metadata ────────────────────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_extract_repo_metadata(self):
        """Repo metadata is correctly extracted into metadata dict."""
        proc = GitHubProcessor()

        repo_payload = {
            "full_name": "docker/docker",
            "description": "Docker container runtime",
            "stargazers_count": 100000,
            "forks_count": 30000,
            "watchers_count": 10000,
            "language": "Go",
            "topics": ["containers", "devops"],
            "owner": {"login": "docker", "avatar_url": "https://github.com/docker.png"},
            "html_url": "https://github.com/docker/docker",
            "default_branch": "main",
            "license": {"spdx_id": "Apache-2.0"},
            "created_at": "2013-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "open_issues_count": 500,
        }
        readme_md = base64.b64encode(b"# Docker\n").decode()

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/docker/docker").mock(
                return_value=httpx.Response(200, json=repo_payload)
            )
            r.get("https://api.github.com/repos/docker/docker/readme").mock(
                return_value=httpx.Response(200, json={"content": readme_md, "encoding": "base64"})
            )
            result = asyncio.run(proc.process("https://github.com/docker/docker"))

        assert result.metadata.get("stars") == 100000
        assert result.metadata.get("forks") == 30000
        assert result.metadata.get("watchers") == 10000
        assert result.metadata.get("language") == "Go"
        assert result.metadata.get("topics") == ["containers", "devops"]
        assert result.metadata.get("license") == "Apache-2.0"
        assert result.metadata.get("default_branch") == "main"

    # ─── PR extraction ───────────────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_extract_pr_success(self):
        """PR URL returns ProcessorResult with post + review sections."""
        proc = GitHubProcessor()

        pr_payload = {
            "title": "feat: add new API",
            "body": "This PR adds a new API endpoint.",
            "user": {"login": "author"},
            "comments": 0,
            "comments_url": "https://api.github.com/repos/example/repo/issues/1/comments",
            "labels": [],
            "state": "open",
            "html_url": "https://github.com/example/repo/pull/1",
            "created_at": "2026-01-01T00:00:00Z",
            "reactions": {"total_count": 10},
        }
        pr_reviews = [
            {
                "id": 1, "state": "APPROVED", "body": "LGTM!",
                "user": {"login": "reviewer"}, "submitted_at": "2026-01-02T00:00:00Z",
                "html_url": "https://github.com/example/repo/pull/1#pullrequestreview-1",
            },
        ]

        with respx.mock(assert_all_called=False) as r:
            # PRs use /issues/{number} endpoint
            r.get("https://api.github.com/repos/example/repo/issues/1").mock(
                return_value=httpx.Response(200, json=pr_payload)
            )
            r.get("https://api.github.com/repos/example/repo/issues/1/comments").mock(
                return_value=httpx.Response(200, json=[])
            )
            r.get("https://api.github.com/repos/example/repo/pulls/1/reviews").mock(
                return_value=httpx.Response(200, json=pr_reviews)
            )
            result = asyncio.run(proc.process("https://github.com/example/repo/pull/1"))

        assert result.source_platform == "github"
        assert result.status.value == "success", f"Got error: {result.error}"
        assert "PR #1" in result.title
        sections = result.sections
        post = next((s for s in sections if s.kind == "post"), None)
        assert post is not None
        assert post.author == "author"

    # ─── Sections structure ─────────────────────────────────────────────────

    @respx.mock(assert_all_called=False)
    def test_sections_structure(self):
        """Sections have correct kind, author, score, depth fields."""
        proc = GitHubProcessor()

        issue_payload = {
            "title": "Test issue", "body": "Issue body.",
            "user": {"login": "issue_author"},
            "comments": 1,
            "comments_url": "https://api.github.com/repos/test/repo/issues/1/comments",
            "labels": [], "state": "open",
            "html_url": "https://github.com/test/repo/issues/1",
            "created_at": "2026-01-01T00:00:00Z",
            "reactions": {"total_count": 3},
        }
        issue_comments = [
            {
                "id": 10, "body": "First comment",
                "user": {"login": "commenter1"}, "created_at": "2026-01-02T00:00:00Z",
                "html_url": "https://github.com/test/repo/issues/1#issuecomment-10",
            },
        ]

        with respx.mock(assert_all_called=False) as r:
            r.get("https://api.github.com/repos/test/repo/issues/1").mock(
                return_value=httpx.Response(200, json=issue_payload)
            )
            r.get("https://api.github.com/repos/test/repo/issues/1/comments").mock(
                return_value=httpx.Response(200, json=issue_comments)
            )
            result = asyncio.run(proc.process("https://github.com/test/repo/issues/1"))

        sections = result.sections
        assert len(sections) == 2  # post + 1 comment

        post = next(s for s in sections if s.kind == "post")
        assert post.author == "issue_author"
        assert post.score == 3
        assert post.parent_id is None
        assert post.depth == 0
        assert post.role == "main"

        comment = next(s for s in sections if s.kind == "comment")
        assert comment.author == "commenter1"
        assert comment.parent_id == post.id
        assert comment.depth == 1
        assert comment.role == "main"
