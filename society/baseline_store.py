"""Shared ChromaDB-backed row store for the faithful baseline memory backends.

`ChromaRows` mirrors the chromadb Client/collection usage pattern established
by `society.ltm.SharedMemory` (see that module for the canonical example),
but exposes a minimal CRUD + cosine-query surface intended to be reused by
several baseline memory implementations rather than encoding any memory
policy itself.

Chroma collection metadata values must be scalars (str/int/float/bool), so
list-valued fields (e.g. `owners`, `acl`, `affiliated`) must be JSON-encoded
before being stored and decoded after being read back; `dumps_meta` /
`loads_meta` are provided for that purpose.
"""

import json
import uuid

import chromadb


def dumps_meta(v):
    """JSON-encode a list-valued metadata field for storage as a Chroma scalar."""
    return json.dumps(v)


def loads_meta(s):
    """Decode a JSON-encoded metadata field back into a list (default: [])."""
    return json.loads(s or "[]")


class ChromaRows:
    """Thin CRUD + cosine-similarity-query wrapper around a Chroma collection."""

    def __init__(self, embed_fn, *, collection_name: str | None = None):
        """
        Initialize ChromaRows.

        Args:
            embed_fn: async callable(list[str]) -> list[vector], used by
                `query` to embed the query text.
            collection_name: name of the underlying chroma collection.
                Default None auto-generates a unique name — chromadb's
                default clients share one in-process store, so same-name
                collections in the same process would silently share data.
        """
        self._embed_fn = embed_fn
        if collection_name is None:
            collection_name = f"baseline_{uuid.uuid4().hex[:8]}"
        self._client = chromadb.Client()
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    async def add(self, row_id: str, text: str, embedding: list[float], metadata: dict) -> None:
        self._collection.add(
            ids=[row_id],
            documents=[text],
            embeddings=[list(embedding)],
            metadatas=[dict(metadata)],
        )

    def get(self, row_id: str) -> dict | None:
        got = self._collection.get(
            ids=[row_id], include=["documents", "metadatas", "embeddings"]
        )
        if not got["ids"]:
            return None
        return {
            "id": row_id,
            "text": got["documents"][0],
            "metadata": got["metadatas"][0],
            "embedding": list(got["embeddings"][0]),
        }

    async def query(
        self,
        query: str,
        n: int,
        where: dict | None = None,
        return_query_embedding: bool = False,
    ) -> list[dict] | tuple[list[dict], list[float] | None]:
        if self._collection.count() == 0:
            return ([], None) if return_query_embedding else []
        emb = (await self._embed_fn([query]))[0]
        res = self._collection.query(
            query_embeddings=[emb],
            n_results=min(n, self._collection.count()),
            where=where,
            include=["documents", "metadatas", "embeddings"],
        )
        hits = [
            {"id": i, "text": d, "metadata": m, "embedding": list(e)}
            for i, d, m, e in zip(
                res["ids"][0], res["documents"][0], res["metadatas"][0], res["embeddings"][0]
            )
        ]
        return (hits, emb) if return_query_embedding else hits

    def update_metadata(self, row_id: str, metadata: dict) -> None:
        self._collection.update(ids=[row_id], metadatas=[dict(metadata)])

    def delete(self, row_id: str) -> None:
        self._collection.delete(ids=[row_id])

    def count(self) -> int:
        return self._collection.count()

    def all_rows(self) -> list[dict]:
        if self._collection.count() == 0:
            return []
        got = self._collection.get(include=["documents", "metadatas", "embeddings"])
        return [
            {"id": i, "text": d, "metadata": m, "embedding": list(e)}
            for i, d, m, e in zip(
                got["ids"], got["documents"], got["metadatas"], got["embeddings"]
            )
        ]
