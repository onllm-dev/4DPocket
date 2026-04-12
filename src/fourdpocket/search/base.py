"""Search backend protocols and shared types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Protocol

from sqlmodel import Session


@dataclass
class KeywordHit:
    item_id: str
    chunk_id: str | None = None
    rank: float = 0.0
    title_snippet: str | None = None
    content_snippet: str | None = None


@dataclass
class VectorHit:
    item_id: str
    chunk_id: str | None = None
    similarity: float = 0.0


@dataclass
class SearchResult:
    item_id: str
    score: float = 0.0
    title_snippet: str | None = None
    content_snippet: str | None = None
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "rank": self.score,
            "title_snippet": self.title_snippet,
            "content_snippet": self.content_snippet,
            "sources": self.sources,
        }


@dataclass
class SearchFilters:
    """Unified search filters passed to backends."""

    item_type: str | None = None
    source_platform: str | None = None
    is_favorite: bool | None = None
    is_archived: bool | None = None
    tags: list[str] | None = None
    after: str | None = None
    before: str | None = None


class KeywordBackend(Protocol):
    def init(self, db: Session) -> None: ...

    def index_item(self, db: Session, item: object) -> None: ...

    def index_chunks(
        self,
        db: Session,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        chunks: list,
        title: str | None,
        url: str | None,
    ) -> None: ...

    def delete_item(self, db: Session, item_id: uuid.UUID) -> None: ...

    def search(
        self,
        db: Session,
        query: str,
        user_id: uuid.UUID,
        filters: SearchFilters,
        limit: int,
        offset: int,
    ) -> list[KeywordHit]: ...


class VectorBackend(Protocol):
    def upsert_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None,
    ) -> None: ...

    def upsert_chunk(
        self,
        chunk_id: uuid.UUID,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None,
    ) -> None: ...

    def delete_item(self, item_id: uuid.UUID, user_id: uuid.UUID) -> None: ...

    def search(
        self,
        user_id: uuid.UUID,
        embedding: list[float],
        k: int,
    ) -> list[VectorHit]: ...


class Reranker(Protocol):
    def rerank(
        self, query: str, docs: list[str], top_k: int
    ) -> list[tuple[int, float]]: ...
