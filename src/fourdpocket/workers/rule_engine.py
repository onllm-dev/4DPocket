"""Execute automation rules on item events."""

import re

from sqlmodel import Session, select

MAX_PATTERN_LEN = 200

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.rule import Rule
from fourdpocket.models.tag import ItemTag, Tag


def evaluate_condition(condition: dict, item: KnowledgeItem, db: Session | None = None) -> bool:
    """Evaluate a rule condition against an item."""
    cond_type = condition.get("type", "")

    if cond_type == "url_matches":
        pattern = condition.get("pattern", "")
        if not pattern or len(pattern) > MAX_PATTERN_LEN:
            return False
        try:
            compiled = re.compile(pattern)
        except re.error:
            return False
        return bool(item.url and compiled.search(item.url[:2000]))

    elif cond_type == "source_platform":
        return item.source_platform == condition.get("platform", "")

    elif cond_type == "title_contains":
        keyword = condition.get("keyword", "").lower()
        return keyword in (item.title or "").lower()

    elif cond_type == "content_contains":
        keyword = condition.get("keyword", "").lower()
        return keyword in (item.content or "").lower()

    elif cond_type == "has_tag":
        tag_name = condition.get("tag_name", "").lower()
        if not tag_name or not db:
            return False
        result = db.exec(
            select(ItemTag).join(Tag, ItemTag.tag_id == Tag.id).where(
                ItemTag.item_id == item.id,
                Tag.name == tag_name,
            )
        ).first()
        return result is not None

    return False


def execute_action(action: dict, item: KnowledgeItem, db: Session) -> None:
    """Execute a rule action on an item."""
    action_type = action.get("type", "")

    if action_type == "add_tag":
        tag_name = action.get("tag_name", "")
        if not tag_name:
            return
        # Find or create tag
        tag = db.exec(
            select(Tag).where(Tag.user_id == item.user_id, Tag.name == tag_name)
        ).first()
        if not tag:
            from fourdpocket.api.tags import _slugify

            tag = Tag(user_id=item.user_id, name=tag_name, slug=_slugify(tag_name))
            db.add(tag)
            db.flush()
        # Add tag to item if not already tagged
        existing_link = db.exec(
            select(ItemTag).where(ItemTag.item_id == item.id, ItemTag.tag_id == tag.id)
        ).first()
        if not existing_link:
            db.add(ItemTag(item_id=item.id, tag_id=tag.id))

    elif action_type == "add_to_collection":
        collection_name = action.get("collection_name", "")
        if not collection_name:
            return
        collection = db.exec(
            select(Collection).where(
                Collection.user_id == item.user_id, Collection.name == collection_name
            )
        ).first()
        if collection:
            existing = db.exec(
                select(CollectionItem).where(
                    CollectionItem.collection_id == collection.id,
                    CollectionItem.item_id == item.id,
                )
            ).first()
            if not existing:
                db.add(CollectionItem(collection_id=collection.id, item_id=item.id, position=0))

    elif action_type == "set_favorite":
        item.is_favorite = True

    elif action_type == "archive":
        item.is_archived = True


def run_rules_for_item(item: KnowledgeItem, db: Session) -> int:
    """Run all active rules for the item's owner. Returns number of rules matched."""
    rules = db.exec(
        select(Rule).where(Rule.user_id == item.user_id, Rule.is_active == True)  # noqa: E712
    ).all()

    matched = 0
    for rule in rules:
        if evaluate_condition(rule.condition, item, db):
            execute_action(rule.action, item, db)
            matched += 1

    if matched > 0:
        db.commit()

    return matched
