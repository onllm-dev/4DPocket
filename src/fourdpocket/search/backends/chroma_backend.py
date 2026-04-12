"""ChromaDB vector backend — wraps existing semantic module."""

import uuid

from fourdpocket.search.base import VectorHit


class ChromaBackend:
    def upsert_item(
        self,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None,
    ) -> None:
        from fourdpocket.search.semantic import add_embedding

        add_embedding(item_id, user_id, embedding, metadata)

    def upsert_chunk(
        self,
        chunk_id: uuid.UUID,
        item_id: uuid.UUID,
        user_id: uuid.UUID,
        embedding: list[float],
        metadata: dict | None,
    ) -> None:
        from fourdpocket.search.semantic import add_chunk_embedding

        add_chunk_embedding(chunk_id, user_id, item_id, embedding, metadata)

    def delete_item(self, item_id: uuid.UUID, user_id: uuid.UUID) -> None:
        import logging

        from fourdpocket.search.semantic import _get_collection, delete_chunk_embeddings

        # Delete chunk-level embeddings
        delete_chunk_embeddings(user_id, item_id)

        # Delete item-level embedding
        try:
            collection = _get_collection(user_id)
            collection.delete(ids=[str(item_id)])
        except Exception as e:
            logging.getLogger(__name__).debug(
                "Failed to delete item embedding %s: %s", item_id, e
            )

    def search(
        self,
        user_id: uuid.UUID,
        embedding: list[float],
        k: int,
    ) -> list[VectorHit]:
        # This method receives a pre-computed embedding, so query ChromaDB directly
        try:
            from fourdpocket.search.semantic import _get_collection

            collection = _get_collection(user_id)
            result = collection.query(
                query_embeddings=[embedding],
                n_results=k,
                where={"user_id": str(user_id)},
            )

            hits = []
            seen_items: set[str] = set()
            for i, doc_id in enumerate(result["ids"][0]):
                meta = result["metadatas"][0][i] if result["metadatas"] else {}
                item_id = meta.get("item_id", doc_id)
                distance = result["distances"][0][i] if result["distances"] else 0
                # Deduplicate by item_id (keep best)
                if item_id not in seen_items:
                    seen_items.add(item_id)
                    hits.append(VectorHit(
                        item_id=item_id,
                        chunk_id=doc_id if meta.get("is_chunk") == "true" else None,
                        similarity=round(1.0 - distance, 4),
                    ))
            return hits
        except Exception:
            return []
