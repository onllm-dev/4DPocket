"""AI auto-summarization."""

import logging
import uuid

from sqlmodel import Session

from fourdpocket.ai.factory import get_chat_provider
from fourdpocket.config import get_settings
from fourdpocket.models.item import KnowledgeItem

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """You are a concise summarizer. Given content from a saved knowledge item, write a 2-3 sentence summary that captures the key points. Be specific and informative. Do not use filler phrases like "This article discusses..." — jump straight to the substance."""


def summarize_item(
    item_id: uuid.UUID,
    db: Session,
) -> str | None:
    """Generate a summary for a knowledge item and save it."""
    settings = get_settings()
    if not settings.ai.auto_summarize:
        return None

    item = db.get(KnowledgeItem, item_id)
    if not item:
        return None

    # Build content for summarization
    text_parts = []
    if item.title:
        text_parts.append(f"Title: {item.title}")
    if item.description:
        text_parts.append(f"Description: {item.description[:500]}")
    if item.content:
        text_parts.append(f"Content: {item.content[:4000]}")

    if not text_parts:
        return None

    chat = get_chat_provider()
    prompt = f"Summarize this in 2-3 sentences:\n\n{'\\n'.join(text_parts)}"
    summary = chat.generate(prompt, system_prompt=SUMMARY_SYSTEM_PROMPT)

    if summary:
        item.summary = summary.strip()
        db.add(item)
        db.commit()
        logger.info("Generated summary for item %s", item_id)

    return summary
