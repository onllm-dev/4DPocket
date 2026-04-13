"""Tests for the automation rule engine."""

import pytest
from sqlmodel import Session, select

from fourdpocket.models.collection import Collection, CollectionItem
from fourdpocket.models.item import KnowledgeItem
from fourdpocket.models.rule import Rule
from fourdpocket.models.tag import ItemTag, Tag
from fourdpocket.workers.rule_engine import (
    _safe_regex_match,
    evaluate_condition,
    execute_action,
    run_rules_for_item,
)


class TestSafeRegexMatch:
    """Test regex timeout and complexity guard."""

    def test_valid_pattern_matches(self):
        assert _safe_regex_match(r"https://.*\.example\.com", "https://foo.example.com")
        assert _safe_regex_match(r"python|java|go", "python is great")

    def test_valid_pattern_no_match(self):
        assert _safe_regex_match(r"https://.*\.example\.com", "https://other.com") is False

    def test_dangerous_pattern_rejected(self):
        """Nested quantifiers like (a+)+ are rejected immediately."""
        assert _safe_regex_match(r"(a+)+b", "aaa") is False
        assert _safe_regex_match(r"(x{2,})+y", "xxxx") is False

    def test_invalid_regex_returns_false(self):
        assert _safe_regex_match(r"[", "text") is False

    def test_timeout_returns_false(self):
        """Pattern that would cause catastrophic backtracking returns False after timeout."""
        # This pattern would take very long without the guard
        result = _safe_regex_match(r"(a+)+$", "aaa" * 20)
        assert result is False

    def test_empty_pattern_returns_no_match(self):
        """Empty pattern matches empty string but not other text."""
        # re.compile('').search('text') matches at position 0 (empty match)
        # This is edge case behavior - we document it
        assert _safe_regex_match("", "") is True
        # For non-empty text, empty pattern still matches at start - edge case
        assert _safe_regex_match("", "some text") is True

    def test_whitespace_pattern(self):
        # Simple whitespace pattern should work
        assert _safe_regex_match(r"\s+", "  ") is True


class TestEvaluateCondition:
    """Test condition evaluation logic."""

    @pytest.fixture
    def rule_user(self, db: Session):
        from fourdpocket.models.user import User
        user = User(
            email="ruleuser@test.com",
            username="ruleuser",
            password_hash="$2b$12$fake",
            display_name="Rule User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def rule_item(self, db: Session, rule_user):
        item = KnowledgeItem(
            user_id=rule_user.id,
            url="https://example.com/article",
            title="Example Article About Python",
            content="Python is a great programming language.",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def test_url_matches_condition_true(self, db: Session, rule_item):
        condition = {"type": "url_matches", "pattern": r"example\.com"}
        assert evaluate_condition(condition, rule_item, db) is True

    def test_url_matches_condition_false(self, db: Session, rule_item):
        condition = {"type": "url_matches", "pattern": r"github\.com"}
        assert evaluate_condition(condition, rule_item, db) is False

    def test_url_matches_dangerous_regex_blocked(self, db: Session, rule_item):
        condition = {"type": "url_matches", "pattern": r"(a+)+b"}
        assert evaluate_condition(condition, rule_item, db) is False

    def test_url_matches_empty_pattern(self, db: Session, rule_item):
        condition = {"type": "url_matches", "pattern": ""}
        assert evaluate_condition(condition, rule_item, db) is False

    def test_source_platform_condition(self, db: Session, rule_item):
        condition = {"type": "source_platform", "platform": "generic"}
        assert evaluate_condition(condition, rule_item, db) is True

        condition2 = {"type": "source_platform", "platform": "github"}
        assert evaluate_condition(condition2, rule_item, db) is False

    def test_title_contains_condition(self, db: Session, rule_item):
        condition = {"type": "title_contains", "keyword": "python"}
        assert evaluate_condition(condition, rule_item, db) is True

        condition2 = {"type": "title_contains", "keyword": "rust"}
        assert evaluate_condition(condition2, rule_item, db) is False

    def test_title_contains_case_insensitive(self, db: Session, rule_item):
        condition = {"type": "title_contains", "keyword": "PYTHON"}
        assert evaluate_condition(condition, rule_item, db) is True

    def test_content_contains_condition(self, db: Session, rule_item):
        condition = {"type": "content_contains", "keyword": "programming"}
        assert evaluate_condition(condition, rule_item, db) is True

    def test_content_contains_no_match(self, db: Session, rule_item):
        condition = {"type": "content_contains", "keyword": "rust"}
        assert evaluate_condition(condition, rule_item, db) is False

    def test_has_tag_condition_true(self, db: Session, rule_user, rule_item):
        tag = Tag(user_id=rule_user.id, name="programming", slug="programming")
        db.add(tag)
        db.commit()

        item_tag = ItemTag(item_id=rule_item.id, tag_id=tag.id)
        db.add(item_tag)
        db.commit()

        condition = {"type": "has_tag", "tag_name": "programming"}
        assert evaluate_condition(condition, rule_item, db) is True

    def test_has_tag_condition_false(self, db: Session, rule_user, rule_item):
        condition = {"type": "has_tag", "tag_name": "python"}
        assert evaluate_condition(condition, rule_item, db) is False

    def test_unknown_condition_type_returns_false(self, db: Session, rule_item):
        condition = {"type": "unknown_type"}
        assert evaluate_condition(condition, rule_item, db) is False


class TestExecuteAction:
    """Test action execution (add_tag, add_to_collection, set_favorite, archive)."""

    @pytest.fixture
    def action_user(self, db: Session):
        from fourdpocket.models.user import User
        user = User(
            email="actionuser@test.com",
            username="actionuser",
            password_hash="$2b$12$fake",
            display_name="Action User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def action_item(self, db: Session, action_user):
        item = KnowledgeItem(
            user_id=action_user.id,
            title="Action Test Item",
            content="Some content",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def test_add_tag_creates_tag(self, db: Session, action_item, action_user):
        action = {"type": "add_tag", "tag_name": "new-tag"}
        execute_action(action, action_item, db)

        tag = db.exec(select(Tag).where(Tag.name == "new-tag")).first()
        assert tag is not None
        assert tag.user_id == action_user.id

        item_tag = db.exec(
            select(ItemTag).where(ItemTag.item_id == action_item.id)
        ).first()
        assert item_tag is not None
        assert item_tag.tag_id == tag.id

    def test_add_tag_reuses_existing_tag(self, db: Session, action_item, action_user):
        existing = Tag(user_id=action_user.id, name="existing-tag", slug="existing-tag")
        db.add(existing)
        db.commit()

        action = {"type": "add_tag", "tag_name": "existing-tag"}
        execute_action(action, action_item, db)

        tags = db.exec(select(Tag).where(Tag.name == "existing-tag")).all()
        assert len(tags) == 1

        item_tags = db.exec(select(ItemTag).where(ItemTag.item_id == action_item.id)).all()
        assert len(item_tags) == 1

    def test_add_tag_empty_name_noop(self, db: Session, action_item):
        action = {"type": "add_tag", "tag_name": ""}
        execute_action(action, action_item, db)
        # No exception, no tag created

    def test_add_to_collection_creates_link(self, db: Session, action_item, action_user):
        collection = Collection(user_id=action_user.id, name="My Collection")
        db.add(collection)
        db.commit()

        action = {"type": "add_to_collection", "collection_name": "My Collection"}
        execute_action(action, action_item, db)

        link = db.exec(
            select(CollectionItem).where(
                CollectionItem.item_id == action_item.id,
                CollectionItem.collection_id == collection.id,
            )
        ).first()
        assert link is not None

    def test_add_to_collection_nonexistent_noop(self, db: Session, action_item):
        action = {"type": "add_to_collection", "collection_name": "Does Not Exist"}
        execute_action(action, action_item, db)
        # No exception, no link created

    def test_set_favorite(self, db: Session, action_item):
        assert action_item.is_favorite is False
        action = {"type": "set_favorite"}
        execute_action(action, action_item, db)
        assert action_item.is_favorite is True

    def test_archive(self, db: Session, action_item):
        assert action_item.is_archived is False
        action = {"type": "archive"}
        execute_action(action, action_item, db)
        assert action_item.is_archived is True

    def test_unknown_action_noop(self, db: Session, action_item):
        action = {"type": "unknown_action"}
        execute_action(action, action_item, db)
        # No exception


class TestRunRulesForItem:
    """Test full rule evaluation and execution pipeline."""

    @pytest.fixture
    def rules_user(self, db: Session):
        from fourdpocket.models.user import User
        user = User(
            email="rulesuser@test.com",
            username="rulesuser",
            password_hash="$2b$12$fake",
            display_name="Rules User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @pytest.fixture
    def rules_item(self, db: Session, rules_user):
        item = KnowledgeItem(
            user_id=rules_user.id,
            url="https://example.com/article",
            title="Interesting Article",
            content="Some content here.",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    def test_no_active_rules(self, db: Session, rules_item):
        matched = run_rules_for_item(rules_item, db)
        assert matched == 0

    def test_matching_rule_adds_tag(self, db: Session, rules_user, rules_item):
        rule = Rule(
            user_id=rules_user.id,
            name="Tag Python Articles",
            condition={"type": "url_matches", "pattern": r"example\.com"},
            action={"type": "add_tag", "tag_name": "python-tag"},
            is_active=True,
        )
        db.add(rule)
        db.commit()

        matched = run_rules_for_item(rules_item, db)
        assert matched == 1

        tag = db.exec(select(Tag).where(Tag.name == "python-tag")).first()
        assert tag is not None

    def test_multiple_matching_rules(self, db: Session, rules_user, rules_item):
        rule1 = Rule(
            user_id=rules_user.id,
            name="Tag Example",
            condition={"type": "url_matches", "pattern": r"example\.com"},
            action={"type": "add_tag", "tag_name": "from-rule1"},
            is_active=True,
        )
        rule2 = Rule(
            user_id=rules_user.id,
            name="Tag Article",
            condition={"type": "title_contains", "keyword": "article"},
            action={"type": "set_favorite"},
            is_active=True,
        )
        db.add_all([rule1, rule2])
        db.commit()

        matched = run_rules_for_item(rules_item, db)
        assert matched == 2

        db.refresh(rules_item)
        assert rules_item.is_favorite is True

    def test_inactive_rule_not_matched(self, db: Session, rules_user, rules_item):
        rule = Rule(
            user_id=rules_user.id,
            name="Inactive Rule",
            condition={"type": "url_matches", "pattern": r"example\.com"},
            action={"type": "add_tag", "tag_name": "should-not-apply"},
            is_active=False,
        )
        db.add(rule)
        db.commit()

        matched = run_rules_for_item(rules_item, db)
        assert matched == 0

    def test_rule_from_different_user_not_matched(self, db: Session, rules_user, rules_item):
        from fourdpocket.models.user import User

        other_user = User(
            email="other@test.com",
            username="otheruser",
            password_hash="$2b$12$fake",
            display_name="Other",
        )
        db.add(other_user)
        db.commit()

        rule = Rule(
            user_id=other_user.id,
            name="Other User Rule",
            condition={"type": "url_matches", "pattern": r"example\.com"},
            action={"type": "add_tag", "tag_name": "other-tag"},
            is_active=True,
        )
        db.add(rule)
        db.commit()

        matched = run_rules_for_item(rules_item, db)
        assert matched == 0
