"""Stack Overflow processor - extract questions and answers via SE API."""

import logging
import re

import httpx

from fourdpocket.processors.base import BaseProcessor, ProcessorResult, ProcessorStatus
from fourdpocket.processors.registry import register_processor

logger = logging.getLogger(__name__)


def _extract_question_id(url: str) -> str | None:
    match = re.search(r"stackoverflow\.com/questions/(\d+)", url)
    return match.group(1) if match else None


@register_processor
class StackOverflowProcessor(BaseProcessor):
    """Extract Stack Overflow questions and answers via the SE API."""

    url_patterns = [r"stackoverflow\.com/questions/\d+"]
    priority = 10

    async def process(self, url: str, **kwargs) -> ProcessorResult:
        question_id = _extract_question_id(url)
        if not question_id:
            return ProcessorResult(
                title=url,
                source_platform="stackoverflow",
                status=ProcessorStatus.failed,
                error="Could not extract question ID from URL",
                metadata={"url": url},
            )

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                q_url = (
                    f"https://api.stackexchange.com/2.3/questions/{question_id}"
                    "?site=stackoverflow&filter=withbody"
                )
                q_resp = await client.get(q_url)
                q_resp.raise_for_status()
                q_data = q_resp.json()

                a_url = (
                    f"https://api.stackexchange.com/2.3/questions/{question_id}/answers"
                    "?site=stackoverflow&filter=withbody&sort=votes&pagesize=3"
                )
                a_resp = await client.get(a_url)
                a_resp.raise_for_status()
                a_data = a_resp.json()
        except httpx.HTTPStatusError as e:
            return ProcessorResult(
                title=url,
                source_platform="stackoverflow",
                status=ProcessorStatus.partial,
                error=f"HTTP {e.response.status_code}",
                metadata={"url": url, "question_id": question_id},
            )
        except Exception as e:
            return ProcessorResult(
                title=url,
                source_platform="stackoverflow",
                status=ProcessorStatus.failed,
                error=str(e)[:200],
                metadata={"url": url},
            )

        questions = q_data.get("items", [])
        if not questions:
            return ProcessorResult(
                title=url,
                source_platform="stackoverflow",
                status=ProcessorStatus.failed,
                error="Question not found in API response",
                metadata={"url": url, "question_id": question_id},
            )

        question = questions[0]
        title = question.get("title", url)
        body = question.get("body", "")
        tags = question.get("tags", [])
        owner = question.get("owner", {}).get("display_name", "")
        score = question.get("score", 0)

        answers = a_data.get("items", [])
        accepted_answer = next(
            (a for a in answers if a.get("is_accepted")), None
        )
        top_answers = answers[:3]

        content_parts = []
        if body:
            content_parts.append(f"## Question\n\n{body}")
        if accepted_answer:
            content_parts.append(
                f"## Accepted Answer\n\n{accepted_answer.get('body', '')}"
            )
        remaining = [a for a in top_answers if not a.get("is_accepted")]
        if remaining:
            content_parts.append("## Top Answers\n")
            for ans in remaining:
                ans_owner = ans.get("owner", {}).get("display_name", "")
                content_parts.append(
                    f"**{ans_owner}** (score: {ans.get('score', 0)}):\n{ans.get('body', '')}\n"
                )

        metadata = {
            "url": url,
            "question_id": question_id,
            "author": owner,
            "score": score,
            "tags": tags,
            "answer_count": len(answers),
            "has_accepted_answer": accepted_answer is not None,
        }

        return ProcessorResult(
            title=title,
            description=body[:300] if body else None,
            content="\n\n".join(content_parts) if content_parts else None,
            metadata=metadata,
            source_platform="stackoverflow",
            item_type="url",
            status=ProcessorStatus.success,
        )
