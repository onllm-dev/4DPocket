"""GitHub processor — repos, issues, PRs, gists via REST API."""

import base64
import json
import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _parse_github_url(url: str) -> dict:
    """Parse GitHub URL into components."""
    patterns = [
        (r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", "issue"),
        (r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", "pull"),
        (r"gist\.github\.com/([^/]+)/(\w+)", "gist"),
        (r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", "repo"),
    ]
    for pattern, url_type in patterns:
        match = re.search(pattern, url)
        if match:
            groups = match.groups()
            if url_type in ("issue", "pull"):
                return {"type": url_type, "owner": groups[0], "repo": groups[1], "number": groups[2]}
            elif url_type == "gist":
                return {"type": "gist", "owner": groups[0], "gist_id": groups[1]}
            else:
                return {"type": "repo", "owner": groups[0], "repo": groups[1]}
    return {"type": "unknown"}


@register_processor
class GitHubProcessor(BaseProcessor):
    """Extract metadata from GitHub repos, issues, PRs, and gists."""

    url_patterns = [
        r"github\.com/[^/]+/[^/]+/issues/\d+",
        r"github\.com/[^/]+/[^/]+/pull/\d+",
        r"gist\.github\.com/[^/]+/\w+",
        r"github\.com/[^/]+/[^/]+/?$",
    ]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        parsed = _parse_github_url(url)
        if parsed["type"] == "unknown":
            return ProcessorResult(
                title=url,
                source_platform="github",
                status=ProcessorStatus.failed,
                error="Could not parse GitHub URL",
            )

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "4DPocket/0.1",
        }

        # Add auth token if configured
        from fourdpocket.config import get_settings
        settings = get_settings()
        github_token = settings.ai.__dict__.get("github_token", "")
        if github_token:
            headers["Authorization"] = f"token {github_token}"

        try:
            if parsed["type"] == "repo":
                return await self._process_repo(parsed, headers, url)
            elif parsed["type"] in ("issue", "pull"):
                return await self._process_issue_pr(parsed, headers, url)
            elif parsed["type"] == "gist":
                return await self._process_gist(parsed, headers, url)
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="github",
                status=ProcessorStatus.partial,
                error=f"GitHub API {e.response.status_code}: rate limit or auth required",
                metadata={"url": url, "parsed": parsed},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="github",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        return ProcessorResult(title=url, source_platform="github", status=ProcessorStatus.failed)

    async def _process_repo(self, parsed: dict, headers: dict, url: str) -> ProcessorResult:
        owner, repo = parsed["owner"], parsed["repo"]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # Fetch README
            readme_content = None
            try:
                readme_resp = await client.get(f"{api_url}/readme", headers=headers)
                if readme_resp.status_code == 200:
                    readme_data = readme_resp.json()
                    readme_b64 = readme_data.get("content", "")
                    readme_content = base64.b64decode(readme_b64).decode("utf-8", errors="replace")
            except Exception:
                pass

        metadata = {
            "url": url,
            "owner": owner,
            "repo": repo,
            "full_name": data.get("full_name"),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "watchers": data.get("watchers_count", 0),
            "language": data.get("language"),
            "topics": data.get("topics", []),
            "open_issues": data.get("open_issues_count", 0),
            "license": data.get("license", {}).get("spdx_id") if data.get("license") else None,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "default_branch": data.get("default_branch"),
        }

        content_parts = []
        if data.get("description"):
            content_parts.append(data["description"])
        if readme_content:
            content_parts.append(f"\n\n## README\n\n{readme_content[:20000]}")

        media = []
        if data.get("owner", {}).get("avatar_url"):
            media.append({"type": "image", "url": data["owner"]["avatar_url"], "role": "avatar"})

        return ProcessorResult(
            title=f"{owner}/{repo}",
            description=data.get("description"),
            content="\n".join(content_parts) if content_parts else None,
            raw_content=json.dumps(data, default=str)[:50000],
            media=media,
            metadata=metadata,
            source_platform="github",
            item_type="url",
            status=ProcessorStatus.success,
        )

    async def _process_issue_pr(self, parsed: dict, headers: dict, url: str) -> ProcessorResult:
        owner, repo, number = parsed["owner"], parsed["repo"], parsed["number"]
        item_type = parsed["type"]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # Fetch top comments
            comments = []
            comments_url = data.get("comments_url", "")
            if comments_url and data.get("comments", 0) > 0:
                try:
                    comments_resp = await client.get(
                        comments_url, headers=headers, params={"per_page": 10}
                    )
                    if comments_resp.status_code == 200:
                        for c in comments_resp.json()[:10]:
                            comments.append({
                                "author": c.get("user", {}).get("login", ""),
                                "body": c.get("body", "")[:2000],
                                "created_at": c.get("created_at"),
                            })
                except Exception:
                    pass

        labels = [l.get("name", "") for l in data.get("labels", [])]

        content_parts = [data.get("body", "") or ""]
        if comments:
            content_parts.append("\n\n## Comments\n")
            for c in comments:
                content_parts.append(f"**{c['author']}**:\n{c['body']}\n")

        metadata = {
            "url": url,
            "owner": owner,
            "repo": repo,
            "number": int(number),
            "type": item_type,
            "state": data.get("state"),
            "labels": labels,
            "author": data.get("user", {}).get("login"),
            "created_at": data.get("created_at"),
            "closed_at": data.get("closed_at"),
            "comment_count": data.get("comments", 0),
        }

        prefix = "PR" if item_type == "pull" else "Issue"
        return ProcessorResult(
            title=f"[{owner}/{repo}] {prefix} #{number}: {data.get('title', '')}",
            description=data.get("body", "")[:300] if data.get("body") else None,
            content="\n\n".join(content_parts),
            raw_content=json.dumps(data, default=str)[:50000],
            metadata=metadata,
            source_platform="github",
            item_type="url",
            status=ProcessorStatus.success,
        )

    async def _process_gist(self, parsed: dict, headers: dict, url: str) -> ProcessorResult:
        gist_id = parsed["gist_id"]
        api_url = f"https://api.github.com/gists/{gist_id}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(api_url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        files_content = []
        file_list = []
        for filename, file_info in data.get("files", {}).items():
            file_list.append(filename)
            content = file_info.get("content", "")
            lang = file_info.get("language", "")
            files_content.append(f"### {filename} ({lang})\n```\n{content[:10000]}\n```")

        metadata = {
            "url": url,
            "gist_id": gist_id,
            "owner": parsed["owner"],
            "files": file_list,
            "description": data.get("description"),
            "public": data.get("public", True),
            "created_at": data.get("created_at"),
        }

        return ProcessorResult(
            title=data.get("description") or f"Gist: {', '.join(file_list[:3])}",
            description=data.get("description"),
            content="\n\n".join(files_content) if files_content else None,
            raw_content=json.dumps(data, default=str)[:50000],
            metadata=metadata,
            source_platform="github",
            item_type="url",
            status=ProcessorStatus.success,
        )
