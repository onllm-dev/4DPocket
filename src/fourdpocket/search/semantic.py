"""Semantic search using ChromaDB for vector storage."""

import logging
import uuid

from fourdpocket.config import get_settings

logger = logging.getLogger(__name__)

_client = None
_collection_cache: dict[str, object] = {}


def _get_client():
    global _client
    if _client is None:
        import chromadb

        _client = chromadb.Client()
        logger.info("ChromaDB client initialized (in-process)")
    return _client


def _get_collection(user_id: uuid.UUID):
    collection_name = f"user_{str(user_id)[:8]}"
    if collection_name not in _collection_cache:
        client = _get_client()
        _collection_cache[collection_name] = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection_cache[collection_name]


def add_embedding(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    embedding: list[float],
    metadata: dict | None = None,
) -> None:
    """Add an item embedding to ChromaDB."""
    collection = _get_collection(user_id)
    doc_id = str(item_id)
    meta = metadata or {}
    meta["user_id"] = str(user_id)

    collection.upsert(
        ids=[doc_id],
        embeddings=[embedding],
        metadatas=[meta],
    )


def query_similar(
    item_id: uuid.UUID,
    user_id: uuid.UUID,
    limit: int = 5,
) -> list[dict]:
    """Find items similar to the given item using vector similarity."""
    collection = _get_collection(user_id)
    doc_id = str(item_id)

    try:
        # Get the item's embedding
        result = collection.get(ids=[doc_id], include=["embeddings"])
        if not result["embeddings"] or not result["embeddings"][0]:
            return []

        embedding = result["embeddings"][0]

        # Query for similar items
        query_result = collection.query(
            query_embeddings=[embedding],
            n_results=limit + 1,  # +1 to exclude self
            where={"user_id": str(user_id)},
        )

        similar = []
        for i, doc_id_result in enumerate(query_result["ids"][0]):
            if doc_id_result == doc_id:
                continue
            distance = query_result["distances"][0][i] if query_result["distances"] else 0
            similarity = 1.0 - distance  # cosine distance to similarity
            similar.append({
                "item_id": doc_id_result,
                "similarity": round(max(0, similarity), 4),
            })

        return similar[:limit]

    except Exception as e:
        logger.warning("Semantic query failed for item %s: %s", item_id, e)
        return []


def search_by_text(
    query_text: str,
    user_id: uuid.UUID,
    embedding_provider=None,
    limit: int = 10,
) -> list[dict]:
    """Search by text query using embedding provider."""
    if embedding_provider is None:
        from fourdpocket.ai.factory import get_embedding_provider

        embedding_provider = get_embedding_provider()

    query_embedding = embedding_provider.embed_single(query_text)
    if not query_embedding:
        return []

    collection = _get_collection(user_id)

    try:
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where={"user_id": str(user_id)},
        )

        return [
            {
                "item_id": doc_id,
                "similarity": round(1.0 - (result["distances"][0][i] if result["distances"] else 0), 4),
            }
            for i, doc_id in enumerate(result["ids"][0])
        ]
    except Exception as e:
        logger.warning("Semantic text search failed: %s", e)
        return []
