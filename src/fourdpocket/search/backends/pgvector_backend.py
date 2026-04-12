"""pgvector backend for Postgres deployments.

Stores embeddings on the item_chunks table and uses HNSW index for search.
Requires: pgvector extension installed in PostgreSQL, pgvector Python package.
"""

import logging
import uuid

from fourdpocket.search.base import VectorHit

logger = logging.getLogger(__name__)

_initialized = False
_embedding_dim: int | None = None


def _detect_embedding_dim() -> int:
    """Detect embedding dimension from the configured embedding provider."""
    global _embedding_dim
    if _embedding_dim is not None:
        return _embedding_dim

    try:
        from fourdpocket.ai.factory import get_embedding_provider

        provider = get_embedding_provider()
        test_emb = provider.embed_single("dimension test")
        if test_emb:
            _embedding_dim = len(test_emb)
            logger.info("Detected embedding dimension: %d", _embedding_dim)
            return _embedding_dim
    except Exception as e:
        logger.debug("Embedding dimension detection failed: %s", e)

    # Fallback: check config for known models
    try:
        from fourdpocket.config import get_settings

        settings = get_settings()
        model = settings.ai.embedding_model.lower()
        known_dims = {
            "all-minilm-l6-v2": 384,
            "all-minilm-l12-v2": 384,
            "all-mpnet-base-v2": 768,
            "nv-embed-v1": 4096,
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        _embedding_dim = known_dims.get(model, 384)
    except Exception:
        _embedding_dim = 384

    logger.info("Using embedding dimension: %d (fallback)", _embedding_dim)
    return _embedding_dim


class PgVectorBackend:
    def __init__(self):
        self._available: bool | None = None

    def _check_available(self) -> bool:
        """Check if pgvector extension is available."""
        if self._available is not None:
            return self._available
        try:
            from sqlmodel import Session

            from fourdpocket.db.session import get_engine

            engine = get_engine()
            with Session(engine) as db:
                from sqlalchemy import text

                db.exec(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
                row = db.exec(text(
                    "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
                )).one()
                self._available = row[0] > 0
                if not self._available:
                    logger.warning(
                        "pgvector extension not found. Run: CREATE EXTENSION vector; "
                        "Falling back to ChromaDB."
                    )
        except Exception as e:
            logger.warning("pgvector availability check failed: %s", e)
            self._available = False
        return self._available

    def _ensure_column(self) -> None:
        """Add embedding column to item_chunks if not present (Postgres only).

        Detects the embedding dimension dynamically from the configured provider.
        If the column exists with a different dimension, drops and recreates it.
        """
        global _initialized
        if _initialized:
            return
        try:
            from sqlalchemy import text
            from sqlmodel import Session

            from fourdpocket.db.session import get_engine

            dim = _detect_embedding_dim()
            engine = get_engine()
            with Session(engine) as db:
                db.exec(text("CREATE EXTENSION IF NOT EXISTS vector"))

                # Check if column exists and its current dimension
                row = db.exec(text(
                    "SELECT atttypmod FROM pg_attribute "
                    "WHERE attrelid = 'item_chunks'::regclass "
                    "AND attname = 'embedding'"
                )).first()

                if row is not None:
                    current_dim = row[0]
                    if current_dim != dim:
                        logger.warning(
                            "pgvector dimension mismatch: column has %d, need %d. "
                            "Recreating column (existing embeddings will be lost).",
                            current_dim, dim,
                        )
                        db.exec(text("DROP INDEX IF EXISTS idx_chunks_embedding"))
                        db.exec(text(
                            "ALTER TABLE item_chunks DROP COLUMN embedding"
                        ))
                        db.exec(text(
                            f"ALTER TABLE item_chunks ADD COLUMN "
                            f"embedding vector({dim})"
                        ))
                else:
                    db.exec(text(
                        f"ALTER TABLE item_chunks ADD COLUMN IF NOT EXISTS "
                        f"embedding vector({dim})"
                    ))

                # Create HNSW index if not exists
                db.exec(text(
                    "CREATE INDEX IF NOT EXISTS idx_chunks_embedding "
                    "ON item_chunks USING hnsw (embedding vector_cosine_ops) "
                    "WITH (m = 16, ef_construction = 64)"
                ))
                db.commit()
            _initialized = True
        except Exception as e:
            logger.warning("pgvector column setup failed: %s", e)

    def upsert_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None,
    ) -> None:
        # For pgvector, item-level embeddings are not stored separately.
        # The item content is chunked and each chunk gets its own embedding.
        pass

    def upsert_chunk(
        self,
        chunk_id: uuid.UUID,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None,
    ) -> None:
        if not self._check_available():
            return
        self._ensure_column()

        try:
            from sqlalchemy import text
            from sqlmodel import Session

            from fourdpocket.db.session import get_engine

            engine = get_engine()
            with Session(engine) as db:
                # pgvector expects the vector as a string like '[0.1, 0.2, ...]'
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                db.exec(
                    text(
                        "UPDATE item_chunks SET embedding = :vec::vector "
                        "WHERE id = :chunk_id"
                    ),
                    params={"vec": vec_str, "chunk_id": str(chunk_id)},
                )
                db.commit()
        except Exception as e:
            logger.warning("pgvector upsert_chunk failed: %s", e)

    def delete_item(self, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
        # Embeddings are on item_chunks rows — they get deleted with the chunks
        pass

    def search(
        self,
        user_id: uuid.UUID,
        embedding: list[float],
        k: int,
    ) -> list[VectorHit]:
        if not self._check_available():
            return []
        self._ensure_column()

        try:
            from sqlalchemy import text
            from sqlmodel import Session

            from fourdpocket.db.session import get_engine

            engine = get_engine()
            vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

            with Session(engine) as db:
                result = db.exec(
                    text(
                        "SELECT c.id, c.item_id, c.embedding <=> :query::vector AS distance "
                        "FROM item_chunks c "
                        "WHERE c.user_id = :uid AND c.embedding IS NOT NULL "
                        "ORDER BY c.embedding <=> :query::vector "
                        "LIMIT :k"
                    ),
                    params={
                        "query": vec_str,
                        "uid": str(user_id),
                        "k": k,
                    },
                )
                rows = result.all()

            # Deduplicate by item_id (best chunk per item)
            seen: set[str] = set()
            hits = []
            for row in rows:
                item_id = str(row[1])
                if item_id not in seen:
                    seen.add(item_id)
                    hits.append(VectorHit(
                        item_id=item_id,
                        chunk_id=str(row[0]),
                        similarity=round(1.0 - float(row[2]), 4),
                    ))
            return hits
        except Exception as e:
            logger.warning("pgvector search failed: %s", e)
            return []
