"""Model validation tests for all SQLModel table classes."""


import pytest
from pydantic import ValidationError


class TestUserValidation:
    """User model and its Pydantic schemas."""

    def test_user_create_valid(self):
        from fourdpocket.models.user import UserCreate

        user = UserCreate(email="a@b.com", username="testuser", password="TestPass123!")
        assert user.email == "a@b.com"

    def test_user_create_invalid_email(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="not-an-email", username="u", password="TestPass123!")
        assert "email" in str(exc_info.value)

    def test_user_create_username_with_at(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="user@domain", password="TestPass123!")
        assert "cannot contain '@'" in str(exc_info.value)

    def test_user_create_username_too_short(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="u", password="TestPass123!")
        assert "at least 2" in str(exc_info.value)

    def test_user_create_username_too_long(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="a" * 31, password="TestPass123!")
        assert "at most 30" in str(exc_info.value)

    def test_user_create_username_invalid_chars(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="user with space", password="TestPass123!")
        assert "can only contain" in str(exc_info.value)

    def test_user_create_password_too_short(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="u", password="Short1!")
        assert "at least 8" in str(exc_info.value)

    def test_user_create_password_no_uppercase(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="u", password="lowercase123!")
        assert "uppercase" in str(exc_info.value)

    def test_user_create_password_no_digit(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="u", password="NoDigits!")
        assert "digit" in str(exc_info.value)

    def test_user_create_password_no_special_char(self):
        from fourdpocket.models.user import UserCreate

        with pytest.raises(ValidationError) as exc_info:
            UserCreate(email="a@b.com", username="u", password="NoSpecial1")
        assert "special" in str(exc_info.value)


class TestKnowledgeItemValidation:
    """KnowledgeItem model and its Pydantic schemas."""

    def test_item_create_valid(self):
        from fourdpocket.models.base import ItemType, SourcePlatform
        from fourdpocket.models.item import ItemCreate

        item = ItemCreate(
            url="https://example.com",
            title="Test",
            item_type=ItemType.url,
            source_platform=SourcePlatform.generic,
        )
        assert item.url == "https://example.com"

    def test_item_create_invalid_url_scheme(self):
        from fourdpocket.models.item import ItemCreate

        with pytest.raises(ValidationError) as exc_info:
            ItemCreate(url="javascript:alert(1)")
        assert "Only http and https" in str(exc_info.value)

    def test_item_create_ftp_url_rejected(self):
        from fourdpocket.models.item import ItemCreate

        with pytest.raises(ValidationError) as exc_info:
            ItemCreate(url="ftp://example.com")
        assert "Only http and https" in str(exc_info.value)

    def test_item_create_content_truncated_at_1mb(self):
        from fourdpocket.models.item import ItemCreate

        item = ItemCreate(content="x" * 1_000_001)
        assert len(item.content) == 1_000_000

    def test_item_create_description_truncated_at_50k(self):
        from fourdpocket.models.item import ItemCreate

        item = ItemCreate(description="x" * 50_001)
        assert len(item.description) == 50_000

    def test_item_create_valid_no_url(self):
        from fourdpocket.models.item import ItemCreate

        # URL is optional (note items may not have URL)
        item = ItemCreate(title="A note", content="Hello world")
        assert item.url is None


class TestItemLinkValidation:
    """ItemLink model and its Pydantic schemas."""

    def test_item_link_create_valid(self):
        from fourdpocket.models.item_link import ItemLinkCreate

        link = ItemLinkCreate(url="https://example.com", title="Example")
        assert link.url == "https://example.com"

    def test_item_link_rejects_javascript_scheme(self):
        from fourdpocket.models.item_link import ItemLinkCreate

        with pytest.raises(ValidationError) as exc_info:
            ItemLinkCreate(url="javascript:alert(1)")
        assert "not permitted" in str(exc_info.value)

    def test_item_link_rejects_data_scheme(self):
        from fourdpocket.models.item_link import ItemLinkCreate

        with pytest.raises(ValidationError) as exc_info:
            ItemLinkCreate(url="data:text/html,<script>alert(1)</script>")
        assert "not permitted" in str(exc_info.value)

    def test_item_link_rejects_vbscript_scheme(self):
        from fourdpocket.models.item_link import ItemLinkCreate

        with pytest.raises(ValidationError) as exc_info:
            ItemLinkCreate(url="vbscript:msgbox('x')")
        assert "not permitted" in str(exc_info.value)


class TestCollectionValidation:
    """Collection model and its Pydantic schemas."""

    def test_collection_create_valid(self):
        from fourdpocket.models.collection import CollectionCreate

        coll = CollectionCreate(name="My Collection", description="A collection")
        assert coll.name == "My Collection"

    def test_collection_create_extra_forbidden(self):
        from fourdpocket.models.collection import CollectionCreate

        with pytest.raises(ValidationError):
            CollectionCreate(name="C", extra_field="not allowed")


class TestTagValidation:
    """Tag model and its Pydantic schemas."""

    def test_tag_create_valid(self):
        from fourdpocket.models.tag import TagCreate

        tag = TagCreate(name="python", color="#FF0000")
        assert tag.name == "python"

    def test_tag_create_extra_forbidden(self):
        from fourdpocket.models.tag import TagCreate

        with pytest.raises(ValidationError):
            TagCreate(name="t", extra_field="x")


class TestNoteValidation:
    """Note model and its Pydantic schemas."""

    def test_note_create_valid(self):
        from fourdpocket.models.note import NoteCreate

        note = NoteCreate(title="A note", content="Note content here")
        assert note.content == "Note content here"

    def test_note_create_extra_forbidden(self):
        from fourdpocket.models.note import NoteCreate

        with pytest.raises(ValidationError):
            NoteCreate(content="c", extra_field="x")


class TestHighlightValidation:
    """Highlight model validation."""

    def test_highlight_create_valid(self, db):
        from fourdpocket.models.highlight import Highlight
        from fourdpocket.models.user import User

        u = User(email="hl@test.com", username="hl", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        hl = Highlight(user_id=u.id, text="highlighted text")
        db.add(hl)
        db.commit()

        assert hl.color == "yellow"  # default


class TestEnrichmentStageValidation:
    """EnrichmentStage model validation."""

    def test_enrichment_stage_defaults(self, db):
        from fourdpocket.models.enrichment import EnrichmentStage
        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.user import User

        u = User(email="es@test.com", username="es", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        item = KnowledgeItem(user_id=u.id, title="Test", content="test", item_type="note", source_platform="generic")
        db.add(item)
        db.commit()
        db.refresh(item)

        stage = EnrichmentStage(item_id=item.id, stage="chunked")
        db.add(stage)
        db.commit()

        assert stage.status == "pending"
        assert stage.attempts == 0


class TestItemChunkValidation:
    """ItemChunk model validation."""

    def test_item_chunk_defaults(self, db):
        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.item_chunk import ItemChunk
        from fourdpocket.models.user import User

        u = User(email="chunk@test.com", username="chunk", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        item = KnowledgeItem(user_id=u.id, title="T", content="test", item_type="note", source_platform="generic")
        db.add(item)
        db.commit()
        db.refresh(item)

        chunk = ItemChunk(
            item_id=item.id,
            user_id=u.id,
            chunk_order=0,
            text="chunk text",
            token_count=2,
            char_start=0,
            char_end=10,
            content_hash="abc",
        )
        db.add(chunk)
        db.commit()

        assert chunk.is_accepted_answer is False


class TestEntityValidation:
    """Entity model validation."""

    def test_entity_defaults(self, db):
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.user import User

        u = User(email="ent@test.com", username="ent", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        entity = Entity(user_id=u.id, canonical_name="Test Entity", entity_type="person")
        db.add(entity)
        db.commit()

        assert entity.item_count == 0
        assert entity.synthesis is None
        assert entity.synthesis_confidence is None


class TestEntityRelationValidation:
    """EntityRelation model validation."""

    def test_entity_relation_defaults(self, db):
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.entity_relation import EntityRelation
        from fourdpocket.models.user import User

        u = User(email="rel@test.com", username="rel", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        e1 = Entity(user_id=u.id, canonical_name="E1", entity_type="person")
        e2 = Entity(user_id=u.id, canonical_name="E2", entity_type="org")
        db.add(e1)
        db.add(e2)
        db.commit()
        db.refresh(e1)
        db.refresh(e2)

        rel = EntityRelation(user_id=u.id, source_id=e1.id, target_id=e2.id)
        db.add(rel)
        db.commit()

        assert rel.weight == 1.0
        assert rel.item_count == 1
        assert rel.keywords is None


class TestApiTokenValidation:
    """ApiToken model validation."""

    def test_api_token_defaults(self, db):
        from fourdpocket.models.api_token import ApiToken
        from fourdpocket.models.base import ApiTokenRole
        from fourdpocket.models.user import User

        u = User(email="tok@test.com", username="tok", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        tok = ApiToken(
            user_id=u.id,
            name="test-token",
            token_prefix="abc",
            token_hash="hash",
        )
        db.add(tok)
        db.commit()

        assert tok.role == ApiTokenRole.viewer
        assert tok.all_collections is True
        assert tok.allow_deletion is False
        assert tok.admin_scope is False


class TestRuleValidation:
    """Rule model validation."""

    def test_rule_defaults(self, db):
        from fourdpocket.models.rule import Rule
        from fourdpocket.models.user import User

        u = User(email="rule@test.com", username="rule", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        rule = Rule(user_id=u.id, name="Test Rule", condition={}, action={})
        db.add(rule)
        db.commit()

        assert rule.is_active is True
        assert rule.condition == {}


class TestRSSFeedValidation:
    """RSSFeed model validation."""

    def test_rss_feed_defaults(self, db):
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        u = User(email="rss@test.com", username="rss", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        feed = RSSFeed(user_id=u.id, url="https://example.com/feed.xml", title="Example Feed")
        db.add(feed)
        db.commit()

        assert feed.is_active is True
        assert feed.poll_interval == 3600
        assert feed.format == "rss"
        assert feed.mode == "auto"
        assert feed.error_count == 0


class TestEmbeddingValidation:
    """Embedding model validation."""

    def test_embedding_defaults(self, db):
        from fourdpocket.models.embedding import Embedding
        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.user import User

        u = User(email="emb@test.com", username="emb", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        item = KnowledgeItem(user_id=u.id, title="T", content="test", item_type="note", source_platform="generic")
        db.add(item)
        db.commit()
        db.refresh(item)

        emb = Embedding(item_id=item.id, model="test-model", content_hash="abc123")
        db.add(emb)
        db.commit()

        assert emb.item_type == "knowledge_item"
        assert emb.vector is None


class TestLLMCacheValidation:
    """LLMCache model validation."""

    def test_llm_cache_defaults(self, db):
        from fourdpocket.models.llm_cache import LLMCache

        cache = LLMCache(content_hash="abc", cache_type="summary", response="{}")
        db.add(cache)
        db.commit()

        assert cache.model_name == ""


class TestRateLimitEntryValidation:
    """RateLimitEntry model validation."""

    def test_rate_limit_defaults(self, db):
        from fourdpocket.models.rate_limit import RateLimitEntry

        entry = RateLimitEntry(key="login:127.0.0.1", action="login")
        db.add(entry)
        db.commit()

        assert entry.attempts == 1
        assert entry.locked_until is None


class TestSavedFilterValidation:
    """SavedFilter model validation."""

    def test_saved_filter_defaults(self, db):
        from fourdpocket.models.saved_filter import SavedFilter
        from fourdpocket.models.user import User

        u = User(email="sf@test.com", username="sf", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        sf = SavedFilter(user_id=u.id, name="My Filter", query="python", filters={})
        db.add(sf)
        db.commit()

        assert sf.filters == {}


class TestShareValidation:
    """Share model validation."""

    def test_share_type_enum(self, db):
        from fourdpocket.models.share import Share, ShareType
        from fourdpocket.models.user import User

        u = User(email="share@test.com", username="share", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        share = Share(owner_id=u.id, share_type=ShareType.item)
        db.add(share)
        db.commit()

        assert share.share_type == ShareType.item
        assert share.public is False


class TestKnowledgeFeedValidation:
    """KnowledgeFeed model validation."""

    def test_knowledge_feed_defaults(self, db):
        from fourdpocket.models.feed import KnowledgeFeed
        from fourdpocket.models.user import User

        u1 = User(email="sub@test.com", username="sub", password_hash="x")
        u2 = User(email="pub@test.com", username="pub", password_hash="x")
        db.add(u1)
        db.add(u2)
        db.commit()
        db.refresh(u1)
        db.refresh(u2)

        feed = KnowledgeFeed(subscriber_id=u1.id, publisher_id=u2.id)
        db.add(feed)
        db.commit()

        assert feed.filter_config == {}


class TestFeedEntryValidation:
    """FeedEntry model validation."""

    def test_feed_entry_defaults(self, db):
        from fourdpocket.models.feed_entry import FeedEntry
        from fourdpocket.models.rss_feed import RSSFeed
        from fourdpocket.models.user import User

        u = User(email="fe@test.com", username="fe", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        feed = RSSFeed(user_id=u.id, url="https://example.com/feed.xml")
        db.add(feed)
        db.commit()
        db.refresh(feed)

        entry = FeedEntry(feed_id=feed.id, user_id=u.id, title="Entry Title")
        db.add(entry)
        db.commit()

        assert entry.status == "pending"
        assert entry.content_snippet is None


class TestInstanceSettingsValidation:
    """InstanceSettings model validation."""

    def test_instance_settings_singleton_default(self, db):
        from fourdpocket.models.instance_settings import InstanceSettings

        settings = InstanceSettings()
        db.add(settings)
        db.commit()

        assert settings.instance_name == "4DPocket"
        assert settings.registration_enabled is True
        assert settings.registration_mode == "open"
        assert settings.default_user_role == "user"


class TestCollectionNoteValidation:
    """CollectionNote junction table validation."""

    def test_collection_note_defaults(self, db):
        from fourdpocket.models.collection import Collection
        from fourdpocket.models.collection_note import CollectionNote
        from fourdpocket.models.note import Note
        from fourdpocket.models.user import User

        u = User(email="cn@test.com", username="cn", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        coll = Collection(user_id=u.id, name="Coll")
        note = Note(user_id=u.id, title="N", content="c")
        db.add(coll)
        db.add(note)
        db.commit()
        db.refresh(coll)
        db.refresh(note)

        cn = CollectionNote(collection_id=coll.id, note_id=note.id)
        db.add(cn)
        db.commit()

        assert cn.position == 0


class TestNoteTagValidation:
    """NoteTag junction table validation."""

    def test_note_tag_defaults(self, db):
        from fourdpocket.models.note import Note
        from fourdpocket.models.note_tag import NoteTag
        from fourdpocket.models.tag import Tag
        from fourdpocket.models.user import User

        u = User(email="nt@test.com", username="nt", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        note = Note(user_id=u.id, title="N", content="c")
        tag = Tag(user_id=u.id, name="tag", slug="tag")
        db.add(note)
        db.add(tag)
        db.commit()
        db.refresh(note)
        db.refresh(tag)

        nt = NoteTag(note_id=note.id, tag_id=tag.id)
        db.add(nt)
        db.commit()

        assert nt.confidence is None


class TestEntityAliasValidation:
    """EntityAlias model validation."""

    def test_entity_alias_defaults(self, db):
        from fourdpocket.models.entity import Entity, EntityAlias
        from fourdpocket.models.user import User

        u = User(email="ea@test.com", username="ea", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        entity = Entity(user_id=u.id, canonical_name="Canonical", entity_type="person")
        db.add(entity)
        db.commit()
        db.refresh(entity)

        alias = EntityAlias(entity_id=entity.id, alias="alt-name")
        db.add(alias)
        db.commit()

        assert alias.source == "extraction"


class TestRelationEvidenceValidation:
    """RelationEvidence model validation."""

    def test_relation_evidence_defaults(self, db):
        from fourdpocket.models.entity import Entity
        from fourdpocket.models.entity_relation import EntityRelation, RelationEvidence
        from fourdpocket.models.item import KnowledgeItem
        from fourdpocket.models.user import User

        u = User(email="rev@test.com", username="rev", password_hash="x")
        db.add(u)
        db.commit()
        db.refresh(u)

        e1 = Entity(user_id=u.id, canonical_name="E1", entity_type="person")
        e2 = Entity(user_id=u.id, canonical_name="E2", entity_type="org")
        db.add(e1)
        db.add(e2)
        db.commit()
        db.refresh(e1)
        db.refresh(e2)

        rel = EntityRelation(user_id=u.id, source_id=e1.id, target_id=e2.id)
        db.add(rel)
        db.commit()
        db.refresh(rel)

        item = KnowledgeItem(user_id=u.id, title="T", content="test", item_type="note", source_platform="generic")
        db.add(item)
        db.commit()
        db.refresh(item)

        evidence = RelationEvidence(relation_id=rel.id, item_id=item.id)
        db.add(evidence)
        db.commit()

        assert evidence.chunk_id is None
