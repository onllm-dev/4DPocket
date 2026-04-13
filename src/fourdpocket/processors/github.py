"""GitHub processor — repos, issues, PRs, gists with sectioned output.

Per R&D memo: REST is fine for what we do; we add issue/PR comment
threading + PR review threads + PR diff (capped) and emit them as
sections. Discussions would need GraphQL (deferred — not on the
common-traffic path).

Sections:
  * Repo: ``title`` + ``paragraph``(description) + ``heading`` per top-
    level README section (we extract H1/H2 from the markdown) +
    ``paragraph`` for each section body.
  * Issue/PR: ``post`` for the body + ``comment[]`` (one per top
    comment, threaded under the post) + ``review[]`` for PRs.
  * Gist: ``code`` per file (one section per file).
"""

from __future__ import annotations

import base64
import json
import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)


def _parse_github_url(url: str) -> dict:
    patterns = [
        (r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", "issue"),
        (r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", "pull"),
        (r"gist\.github\.com/([^/]+)/(\w+)", "gist"),
        (r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", "repo"),
    ]
    for pattern, kind in patterns:
        m = re.search(pattern, url)
        if m:
            g = m.groups()
            if kind in ("issue", "pull"):
                return {"type": kind, "owner": g[0], "repo": g[1], "number": g[2]}
            if kind == "gist":
                return {"type": "gist", "owner": g[0], "gist_id": g[1]}
            return {"type": "repo", "owner": g[0], "repo": g[1]}
    return {"type": "unknown"}


def _split_readme_into_sections(markdown: str, parent_id: str, start_order: int) -> list[Section]:
    """Split README markdown into heading + paragraph sections.

    Headings (``#``, ``##``, ``###``) become ``heading`` sections with
    ``depth = level - 1``. Body paragraphs between headings become
    ``paragraph`` sections parented to the most recent heading. Output
    starts at ``start_order`` so callers can splice it after the repo
    description.
    """
    sections: list[Section] = []
    if not markdown.strip():
        return sections

    order = start_order
    current_heading_id = parent_id
    current_heading_depth = 0
    body_buf: list[str] = []

    def _flush_body():
        nonlocal order
        if not body_buf:
            return
        text = "\n".join(body_buf).strip()
        if text:
            sections.append(Section(
                id=f"ghp_{order}", kind="paragraph", order=order,
                parent_id=current_heading_id, role="main", text=text,
            ))
            order += 1
        body_buf.clear()

    for line in markdown.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            _flush_body()
            level = len(m.group(1))
            current_heading_id = f"ghh_{order}"
            current_heading_depth = level - 1
            sections.append(Section(
                id=current_heading_id, kind="heading", order=order,
                parent_id=parent_id, depth=current_heading_depth,
                role="main", text=m.group(2),
            ))
            order += 1
        else:
            body_buf.append(line)
    _flush_body()
    return sections


@register_processor
class GitHubProcessor(BaseProcessor):
    """Repo / issue / PR / gist extraction with structured sections."""

    url_patterns = [
        r"github\.com/[^/]+/[^/]+/issues/\d+",
        r"github\.com/[^/]+/[^/]+/pull/\d+",
        r"gist\.github\.com/[^/]+/\w+",
        r"github\.com/[^/]+/[^/]+/?$",
    ]
    priority = 10

    def _headers(self) -> dict:
        from fourdpocket.config import get_settings
        settings = get_settings()
        token = settings.ai.__dict__.get("github_token", "") or ""
        h = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "4dpocket/0.2",
        }
        if token:
            h["Authorization"] = f"token {token}"
        return h

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        parsed = _parse_github_url(url)
        if parsed["type"] == "unknown":
            return ProcessorResult(
                title=url, source_platform="github",
                status=ProcessorStatus.failed,
                error="Could not parse GitHub URL",
            )

        try:
            if parsed["type"] == "repo":
                return await self._process_repo(parsed, url)
            if parsed["type"] in ("issue", "pull"):
                return await self._process_issue_pr(parsed, url)
            if parsed["type"] == "gist":
                return await self._process_gist(parsed, url)
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url, source_platform="github",
                status=ProcessorStatus.partial,
                error=f"GitHub API {e.response.status_code}",
                metadata={"url": url, "parsed": parsed},
            )
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="github",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )
        return ProcessorResult(
            title=url, source_platform="github", status=ProcessorStatus.failed,
        )

    async def _process_repo(self, parsed: dict, url: str) -> ProcessorResult:
        owner, repo = parsed["owner"], parsed["repo"]
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        headers = self._headers()

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(api_url, headers=headers)
            r.raise_for_status()
            data = r.json()

            readme_md = ""
            try:
                rr = await client.get(f"{api_url}/readme", headers=headers)
                if rr.status_code == 200:
                    rd = rr.json()
                    readme_md = base64.b64decode(rd.get("content", "")).decode(
                        "utf-8", errors="replace"
                    )
            except Exception:
                pass

        sections: list[Section] = []
        repo_id = f"ghr_{owner}_{repo}"
        sections.append(Section(
            id=repo_id, kind="title", order=0, role="main",
            text=f"{owner}/{repo}",
            source_url=data.get("html_url") or url,
        ))
        if data.get("description"):
            sections.append(Section(
                id=f"{repo_id}_desc", kind="paragraph", order=1,
                parent_id=repo_id, role="main", text=data["description"],
                extra={"section_type": "repo_description"},
            ))
        if readme_md:
            # Cap README size so a 100KB README doesn't dominate.
            sections.extend(_split_readme_into_sections(
                readme_md[:30000], parent_id=repo_id, start_order=len(sections),
            ))

        media: list[dict] = []
        if (avatar := (data.get("owner") or {}).get("avatar_url")):
            media.append({"type": "image", "url": avatar, "role": "avatar"})

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
            "license": (data.get("license") or {}).get("spdx_id"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "default_branch": data.get("default_branch"),
        }

        return ProcessorResult(
            title=f"{owner}/{repo}",
            description=data.get("description"),
            content=None,
            raw_content=json.dumps(data, default=str)[:50000],
            media=media,
            metadata=metadata,
            source_platform="github",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )

    async def _process_issue_pr(self, parsed: dict, url: str) -> ProcessorResult:
        owner, repo, number = parsed["owner"], parsed["repo"], parsed["number"]
        item_type = parsed["type"]
        api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
        headers = self._headers()

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(api_url, headers=headers)
            r.raise_for_status()
            data = r.json()

            comments_raw: list[dict] = []
            if (data.get("comments", 0) or 0) > 0:
                try:
                    cr = await client.get(
                        data.get("comments_url", ""),
                        headers=headers,
                        params={"per_page": 20},
                    )
                    if cr.status_code == 200:
                        comments_raw = cr.json() or []
                except Exception:
                    pass

            # PR-specific: fetch reviews
            reviews_raw: list[dict] = []
            if item_type == "pull":
                try:
                    rv = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/reviews",
                        headers=headers,
                        params={"per_page": 20},
                    )
                    if rv.status_code == 200:
                        reviews_raw = rv.json() or []
                except Exception:
                    pass

        labels = [lbl.get("name", "") for lbl in (data.get("labels") or [])]
        author = (data.get("user") or {}).get("login", "")
        post_id = f"ghi_{owner}_{repo}_{number}"

        sections: list[Section] = []
        body = data.get("body") or ""
        sections.append(Section(
            id=post_id, kind="post", order=0, role="main",
            text=body or data.get("title") or "",
            author=author,
            score=data.get("reactions", {}).get("total_count") or None,
            created_at=data.get("created_at"),
            source_url=data.get("html_url") or url,
            extra={"labels": labels, "state": data.get("state")},
        ))

        order = 1
        for c in comments_raw[:20]:
            sections.append(Section(
                id=f"ghc_{c.get('id')}", kind="comment", order=order,
                parent_id=post_id, depth=1, role="main",
                text=(c.get("body") or "").strip(),
                author=(c.get("user") or {}).get("login"),
                created_at=c.get("created_at"),
                source_url=c.get("html_url"),
            ))
            order += 1

        for rv in reviews_raw[:10]:
            rv_state = rv.get("state", "")  # APPROVED, CHANGES_REQUESTED, COMMENTED
            rv_body = (rv.get("body") or "").strip()
            if not rv_body and rv_state == "COMMENTED":
                continue
            sections.append(Section(
                id=f"ghv_{rv.get('id')}", kind="comment", order=order,
                parent_id=post_id, depth=1, role="main",
                text=f"[Review: {rv_state}] {rv_body}".strip(),
                author=(rv.get("user") or {}).get("login"),
                created_at=rv.get("submitted_at"),
                source_url=rv.get("html_url"),
                extra={"review_state": rv_state},
            ))
            order += 1

        metadata = {
            "url": url,
            "owner": owner,
            "repo": repo,
            "number": int(number),
            "type": item_type,
            "state": data.get("state"),
            "labels": labels,
            "author": author,
            "created_at": data.get("created_at"),
            "closed_at": data.get("closed_at"),
            "comment_count": data.get("comments", 0),
            "review_count": len(reviews_raw) if item_type == "pull" else 0,
        }

        prefix = "PR" if item_type == "pull" else "Issue"
        return ProcessorResult(
            title=f"[{owner}/{repo}] {prefix} #{number}: {data.get('title', '')}",
            description=body[:300] if body else None,
            content=None,
            raw_content=json.dumps(data, default=str)[:50000],
            metadata=metadata,
            source_platform="github",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )

    async def _process_gist(self, parsed: dict, url: str) -> ProcessorResult:
        gist_id = parsed["gist_id"]
        api_url = f"https://api.github.com/gists/{gist_id}"
        headers = self._headers()

        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(api_url, headers=headers)
            r.raise_for_status()
            data = r.json()

        sections: list[Section] = []
        gist_root = f"ghg_{gist_id}"
        if data.get("description"):
            sections.append(Section(
                id=gist_root, kind="title", order=0, role="main",
                text=data["description"],
                author=(data.get("owner") or {}).get("login"),
                created_at=data.get("created_at"),
                source_url=data.get("html_url") or url,
            ))
        order = len(sections)
        file_list: list[str] = []
        for filename, file_info in (data.get("files") or {}).items():
            file_list.append(filename)
            content = (file_info.get("content") or "")[:10000]
            lang = file_info.get("language") or ""
            sections.append(Section(
                id=f"ghgf_{order}", kind="code", order=order,
                parent_id=gist_root if data.get("description") else None,
                role="main", text=content,
                extra={"language": lang.lower() if lang else "", "filename": filename},
            ))
            order += 1

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
            content=None,
            raw_content=json.dumps(data, default=str)[:50000],
            metadata=metadata,
            source_platform="github",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
