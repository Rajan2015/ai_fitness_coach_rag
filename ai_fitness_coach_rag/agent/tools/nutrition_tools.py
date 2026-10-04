"""BM25 (sparse lexical) retrieval over the curated nutrition seed dataset.

This module only retrieves candidates — the tool-calling agent decides which
candidate (if any) is the right match and how to scale it, or estimates the
values itself when nothing matches well. Never used as a silent source of
truth on its own (RAG pattern: retrieve, then let the LLM reason over it).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from ai_fitness_coach_rag.config import config

_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "db" / "seed_data" / "nutrition_facts.json"
)
_SPARSE_MODEL = "Qdrant/bm25"


def _load_seed_data() -> list[dict]:
    raw = _SEED_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else []


@lru_cache(maxsize=1)
def _store() -> QdrantVectorStore:
    """Connect to the sparse-only nutrition collection, indexing it if missing."""
    qdrant_config = config.get("qdrant", {})
    url = qdrant_config.get("url", "http://localhost:6333")
    api_key = qdrant_config.get("api_key") or None
    collection_name = qdrant_config.get("nutrition_collection", "nutrition_facts")
    model = qdrant_config.get("nutrition_model", _SPARSE_MODEL)
    sparse_embeddings = FastEmbedSparse(model_name=model)
    client = QdrantClient(url=url, api_key=api_key)

    if client.collection_exists(collection_name):
        return QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.SPARSE,
        )

    documents = [
        Document(
            page_content=entry["name"]
            + (f" ({', '.join(entry['aliases'])})" if entry.get("aliases") else ""),
            metadata=entry,
        )
        for entry in _load_seed_data()
    ]
    return QdrantVectorStore.from_documents(
        documents,
        embedding=None,
        sparse_embedding=sparse_embeddings,
        url=url,
        api_key=api_key,
        collection_name=collection_name,
        retrieval_mode=RetrievalMode.SPARSE,
    )


def ensure_nutrition_collection_indexed() -> None:
    """Create+index the nutrition_facts Qdrant collection if it doesn't exist yet.

    Safe to call on every app startup — a no-op when the collection is already
    present (idempotent), since `_store()` only indexes on first creation.
    """
    _store()


def search_nutrition_candidates(query: str, k: int = 5) -> list[dict]:
    """Return up to k BM25-matched nutrition candidates, or an error dict."""
    try:
        results = _store().similarity_search(query, k=k)
    except Exception as exc:  # Qdrant unreachable/misconfigured
        return [{"error": f"nutrition search unavailable: {exc}"}]
    return [doc.metadata for doc in results]


@tool
def lookup_nutrition(query: str) -> list[dict]:
    """Search the curated nutrition database for a food item via BM25 lexical
    search. Returns up to 5 candidates, each with name, serving_desc, calories,
    protein_g, carbs_g, fat_g. Pick the best candidate and scale its values to
    the user's stated quantity (source='database'); if none are a good match,
    estimate the values yourself (source='estimated').
    """
    return search_nutrition_candidates(query)

