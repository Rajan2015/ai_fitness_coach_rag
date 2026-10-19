"""Index the curated exercise catalog in Qdrant using hybrid dense+sparse retrieval.

Dense embeddings let semantic queries ("a leg exercise easier on my knees")
match exercises with no lexical overlap in their catalog text; sparse BM25
still rewards exact name/equipment matches. Payload filters (equipment,
difficulty, movement_pattern) remain the deterministic safety/programming
authority — Qdrant only narrows candidates for the LLM to describe.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import FastEmbedSparse, QdrantVectorStore, RetrievalMode
from qdrant_client import QdrantClient

from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.context.catalog import load_exercise_catalog

_SPARSE_MODEL = "Qdrant/bm25"
_DEFAULT_DENSE_MODEL = "text-embedding-3-small"


def _qdrant_settings() -> tuple[str, str | None, str]:
    settings = config.get("qdrant", {})
    return (
        settings.get("url", "http://localhost:6333"),
        settings.get("api_key") or None,
        settings.get("exercise_collection", "exercise_knowledge"),
    )


def _dense_model() -> str:
    return config.get("embeddings", {}).get("model", _DEFAULT_DENSE_MODEL)


def _documents() -> list[Document]:
    return [
        Document(
            page_content=entry.search_text,
            metadata={
                "exercise_slug": entry.slug,
                "equipment": list(entry.equipment),
                "difficulty": entry.difficulty,
                "movement_pattern": entry.movement_pattern,
                "primary_muscles": list(entry.primary_muscles),
                "source_dataset": entry.source_dataset,
            },
        )
        for entry in load_exercise_catalog()
    ]


@lru_cache(maxsize=1)
def exercise_store() -> QdrantVectorStore:
    """Return the exercise store, creating and indexing it when absent."""
    url, api_key, collection_name = _qdrant_settings()
    dense_embeddings = OpenAIEmbeddings(model=_dense_model())
    sparse_embeddings = FastEmbedSparse(model_name=_SPARSE_MODEL)
    client = QdrantClient(url=url, api_key=api_key)
    if client.collection_exists(collection_name):
        return QdrantVectorStore(
            client=client,
            collection_name=collection_name,
            embedding=dense_embeddings,
            sparse_embedding=sparse_embeddings,
            retrieval_mode=RetrievalMode.HYBRID,
        )
    return QdrantVectorStore.from_documents(
        _documents(),
        embedding=dense_embeddings,
        sparse_embedding=sparse_embeddings,
        url=url,
        api_key=api_key,
        collection_name=collection_name,
        retrieval_mode=RetrievalMode.HYBRID,
    )


def ensure_exercise_collection_indexed() -> None:
    """Create the exercise collection and index the catalog if it is absent."""
    exercise_store()

