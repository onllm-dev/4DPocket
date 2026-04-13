"""Stack Overflow / Stack Exchange processor.

Per R&D memo: a custom SE 2.3 filter pulls question + body + answers +
answer bodies + comments in a single call. ``!nNPvSNdWme`` includes
question.body, answer.body, and answer.comments — generated via the SE
docs filter builder. Falls back to the legacy two-call approach if the
custom filter is rejected (rare but possible if SE retires the filter).

Sections:
  * ``question`` — the question body
  * ``accepted_answer`` (if present) — first
  * ``answer[]`` — top scored, in score order
  * ``comment[]`` — parented to the appropriate question/answer
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import urlparse

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor
from fourdpocket.processors.sections import Section

logger = logging.getLogger(__name__)

# Filter built from https://api.stackexchange.com/docs/questions ; include
# question.body, answers, answers.body, answers.comments, comments.
# If SE retires it, the two-call fallback below still works.
_RICH_FILTER = "!nNPvSNdWme"


def _extract_question_id(url: str) -> str | None:
    m = re.search(r"/questions/(\d+)", url)
    return m.group(1) if m else None


def _extract_site(url: str) -> str:
    """Map host → SE API ``site`` parameter (stackoverflow, serverfault, …)."""
    host = (urlparse(url).hostname or "").lower()
    table = {
        "stackoverflow.com": "stackoverflow",
        "serverfault.com": "serverfault",
        "superuser.com": "superuser",
        "askubuntu.com": "askubuntu",
        "math.stackexchange.com": "math",
        "stats.stackexchange.com": "stats",
        "unix.stackexchange.com": "unix",
        "tex.stackexchange.com": "tex",
        "softwareengineering.stackexchange.com": "softwareengineering",
        "datascience.stackexchange.com": "datascience",
    }
    return table.get(host, "stackoverflow")


@register_processor
class StackOverflowProcessor(BaseProcessor):
    """SO/SE question + answers + comments as sections."""

    url_patterns = [
        r"stackoverflow\.com/questions/\d+",
        r"serverfault\.com/questions/\d+",
        r"superuser\.com/questions/\d+",
        r"askubuntu\.com/questions/\d+",
        r"[\w-]+\.stackexchange\.com/questions/\d+",
    ]
    priority = 10

    async def _fetch_rich(self, qid: str, site: str) -> dict | None:
        """Try the single-call rich endpoint."""
        url = (
            f"https://api.stackexchange.com/2.3/questions/{qid}"
            f"?site={site}&filter={_RICH_FILTER}"
        )
        try:
            r = await self._fetch_url(url, timeout=20)
            return r.json()
        except Exception as e:
            logger.debug("Rich SE filter failed for %s: %s", qid, e)
            return None

    async def _fetch_legacy(self, qid: str, site: str) -> tuple[dict, dict]:
        q_url = (
            f"https://api.stackexchange.com/2.3/questions/{qid}"
            f"?site={site}&filter=withbody"
        )
        a_url = (
            f"https://api.stackexchange.com/2.3/questions/{qid}/answers"
            f"?site={site}&filter=withbody&sort=votes&pagesize=5"
        )
        q_resp = await self._fetch_url(q_url, timeout=15)
        a_resp = await self._fetch_url(a_url, timeout=15)
        return q_resp.json(), a_resp.json()

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        qid = _extract_question_id(url)
        if not qid:
            return ProcessorResult(
                title=url, source_platform="stackoverflow",
                status=ProcessorStatus.failed,
                error="Could not extract question ID",
                metadata={"url": url},
            )
        site = _extract_site(url)

        # ─── Fetch (one-call rich, two-call fallback) ───
        question_data: dict | None = None
        answers_raw: list[dict] = []
        try:
            rich = await self._fetch_rich(qid, site)
            if rich and rich.get("items"):
                question_data = rich["items"][0]
                answers_raw = question_data.get("answers", []) or []
            else:
                q_data, a_data = await self._fetch_legacy(qid, site)
                if q_data.get("items"):
                    question_data = q_data["items"][0]
                answers_raw = a_data.get("items", []) or []
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url, source_platform="stackoverflow",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url, "question_id": qid},
            )
        except Exception as e:
            return ProcessorResult(
                title=url, source_platform="stackoverflow",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        if not question_data:
            return ProcessorResult(
                title=url, source_platform="stackoverflow",
                status=ProcessorStatus.failed,
                error="Question not found in API response",
                metadata={"url": url, "question_id": qid},
            )

        title = question_data.get("title") or url
        body = question_data.get("body") or ""
        tags = question_data.get("tags", [])
        owner = (question_data.get("owner") or {}).get("display_name", "")
        score = question_data.get("score", 0)

        # ─── Sections ───
        sections: list[Section] = []
        q_id_str = f"soq_{qid}"
        sections.append(Section(
            id=q_id_str, kind="question", order=0, role="main",
            text=body or title, raw_html=body if body else None,
            author=owner, score=score,
            created_at=str(question_data.get("creation_date") or ""),
            source_url=url,
            extra={"tags": tags, "view_count": question_data.get("view_count")},
        ))

        # Question comments
        order = 1
        for c in question_data.get("comments") or []:
            sections.append(Section(
                id=f"soqc_{c.get('comment_id')}", kind="comment", order=order,
                parent_id=q_id_str, depth=1, role="main",
                text=(c.get("body") or c.get("body_markdown") or "").strip(),
                author=(c.get("owner") or {}).get("display_name", ""),
                score=c.get("score"),
                created_at=str(c.get("creation_date") or ""),
            ))
            order += 1

        # Sort answers: accepted first, then by score desc
        answers_sorted = sorted(
            answers_raw,
            key=lambda a: (not a.get("is_accepted"), -(a.get("score") or 0)),
        )
        for a in answers_sorted[:5]:
            ans_id = f"soa_{a.get('answer_id')}"
            kind = "accepted_answer" if a.get("is_accepted") else "answer"
            ans_owner = (a.get("owner") or {}).get("display_name", "")
            sections.append(Section(
                id=ans_id, kind=kind, order=order, parent_id=q_id_str,
                depth=1, role="main",
                text=(a.get("body") or "").strip(),
                raw_html=a.get("body") if a.get("body") else None,
                author=ans_owner,
                score=a.get("score"),
                is_accepted=bool(a.get("is_accepted")),
                created_at=str(a.get("creation_date") or ""),
            ))
            order += 1
            for c in a.get("comments") or []:
                sections.append(Section(
                    id=f"soac_{c.get('comment_id')}", kind="comment",
                    order=order, parent_id=ans_id, depth=2, role="main",
                    text=(c.get("body") or c.get("body_markdown") or "").strip(),
                    author=(c.get("owner") or {}).get("display_name", ""),
                    score=c.get("score"),
                    created_at=str(c.get("creation_date") or ""),
                ))
                order += 1

        accepted = next((a for a in answers_raw if a.get("is_accepted")), None)
        metadata = {
            "url": url,
            "question_id": qid,
            "site": site,
            "author": owner,
            "score": score,
            "tags": tags,
            "answer_count": len(answers_raw),
            "has_accepted_answer": accepted is not None,
            "view_count": question_data.get("view_count"),
        }

        return ProcessorResult(
            title=title,
            description=body[:300] if body else None,
            content=None,
            raw_content=json.dumps(question_data, default=str)[:100000],
            metadata=metadata,
            source_platform="stackoverflow",
            item_type="url",
            status=ProcessorStatus.success,
            sections=sections,
        )
