"""Tests for ai/connector.py — Related items / connections engine."""

import uuid
from unittest.mock import MagicMock, patch


def _mock_select_result(items):
    """Create a mock select result that supports .all() and iteration."""
    mock_result = MagicMock()
    mock_result.all.return_value = items
    mock_result.__iter__ = lambda self: iter(items)
    return mock_result


class TestFindRelated:
    """Tests for find_related() function."""

    def test_returns_empty_list_when_item_not_found(self, monkeypatch):
        """Item not found in DB → empty list."""
        from fourdpocket.ai.connector import find_related

        mock_db = MagicMock()
        mock_db.get.return_value = None

        result = find_related(
            item_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            db=mock_db,
        )

        assert result == []

    def test_finds_items_with_shared_tags(self, monkeypatch):
        """Items sharing tags are ranked by shared_tags signal."""
        from fourdpocket.ai.connector import find_related

        item_id = uuid.uuid4()
        user_id = uuid.uuid4()
        other_id = uuid.uuid4()
        tag_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = item_id
        mock_item.user_id = user_id
        mock_item.url = None

        mock_db = MagicMock()
        mock_db.get.return_value = mock_item

        # Two exec calls:
        # 1. select(ItemTag.tag_id).where(ItemTag.item_id == item_id) -> [tag_id]
        # 2. select(ItemTag.item_id, ItemTag.tag_id).where(...) -> [(other_id, tag_id)]
        # 3. select(KnowledgeItem).where(...) -> []
        # 4. query_similar -> []
        mock_db.exec.side_effect = [
            _mock_select_result([tag_id]),
            _mock_select_result([(other_id, tag_id)]),
            _mock_select_result([]),
        ]

        mock_other_item = MagicMock()
        mock_other_item.id = other_id
        mock_other_item.user_id = user_id

        def get_item(model, id):
            if id == item_id:
                return mock_item
            if id == other_id:
                return mock_other_item
            return None

        mock_db.get.side_effect = get_item

        with patch("fourdpocket.search.semantic.query_similar", return_value=[]):
            result = find_related(item_id=item_id, user_id=user_id, db=mock_db, limit=5)

        assert len(result) == 1
        assert result[0].item_id == other_id
        assert "shared_tags" in result[0].signals

    def test_skips_other_users_items(self, monkeypatch):
        """Items belonging to different users are excluded."""
        from fourdpocket.ai.connector import find_related

        item_id = uuid.uuid4()
        user_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        other_id = uuid.uuid4()
        tag_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = item_id
        mock_item.user_id = user_id
        mock_item.url = None

        mock_db = MagicMock()
        mock_db.get.return_value = mock_item
        # item_tag_ids, shared tags lookup, domain lookup
        mock_db.exec.side_effect = [
            _mock_select_result([tag_id]),
            _mock_select_result([(other_id, tag_id)]),
            _mock_select_result([]),
        ]

        # Item belongs to different user
        mock_other_item = MagicMock()
        mock_other_item.id = other_id
        mock_other_item.user_id = other_user_id  # different user

        def get_item(model, id):
            if id == item_id:
                return mock_item
            if id == other_id:
                return mock_other_item
            return None

        mock_db.get.side_effect = get_item

        with patch("fourdpocket.search.semantic.query_similar", return_value=[]):
            result = find_related(item_id=item_id, user_id=user_id, db=mock_db, limit=5)

        # other_id should not be included since it belongs to different user
        assert all(r.item_id != other_id for r in result)

    def test_respects_limit_parameter(self, monkeypatch):
        """Returns at most `limit` related items."""
        from fourdpocket.ai.connector import find_related

        item_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_item = MagicMock()
        mock_item.id = item_id
        mock_item.user_id = user_id
        mock_item.url = None

        mock_db = MagicMock()
        mock_db.get.return_value = mock_item
        # item_tag_ids empty, domain lookup empty, semantic empty
        mock_db.exec.side_effect = [
            _mock_select_result([]),
            _mock_select_result([]),
            _mock_select_result([]),
        ]

        with patch("fourdpocket.search.semantic.query_similar", return_value=[]):
            result = find_related(item_id=item_id, user_id=user_id, db=mock_db, limit=3)

        assert len(result) <= 3


class TestFindRelatedOnSave:
    """Tests for find_related_on_save() fast path."""

    def test_uses_only_semantic_similarity(self, monkeypatch):
        """find_related_on_save() only uses semantic signal (fast path)."""
        from fourdpocket.ai.connector import find_related_on_save

        item_id = uuid.uuid4()
        user_id = uuid.uuid4()

        mock_db = MagicMock()

        mock_similar_result = [
            {"item_id": str(uuid.uuid4()), "similarity": 0.8},
            {"item_id": str(uuid.uuid4()), "similarity": 0.7},
        ]

        with patch(
            "fourdpocket.search.semantic.query_similar",
            return_value=mock_similar_result
        ) as mock_query:
            result = find_related_on_save(item_id=item_id, user_id=user_id, db=mock_db, limit=5)

            mock_query.assert_called_once()
            assert len(result) == 2
            assert result[0].signals == ["semantic"]

    def test_returns_empty_on_semantic_error(self, monkeypatch):
        """query_similar failure → empty list."""
        from fourdpocket.ai.connector import find_related_on_save

        item_id = uuid.uuid4()
        user_id = uuid.uuid4()
        mock_db = MagicMock()

        with patch(
            "fourdpocket.search.semantic.query_similar",
            side_effect=Exception("ChromaDB unavailable")
        ):
            result = find_related_on_save(item_id=item_id, user_id=user_id, db=mock_db)

        assert result == []
