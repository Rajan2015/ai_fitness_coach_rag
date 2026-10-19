"""Filtered exercise retrieval with catalog hydration."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from qdrant_client import models

from ai_fitness_coach_rag.context.catalog import (
    ExerciseCatalogEntry,
    load_exercise_catalog,
)
from ai_fitness_coach_rag.context.indexers.exercise_qdrant import exercise_store


@lru_cache(maxsize=1)
def _catalog_by_slug() -> dict[str, ExerciseCatalogEntry]:
    return {entry.slug: entry for entry in load_exercise_catalog()}


def _match_filter(
    *,
    equipment: tuple[str, ...] | None = None,
    difficulty: str | None = None,
    movement_pattern: str | None = None,
    source_dataset: str | None = None,
) -> models.Filter | None:
    conditions: list[models.FieldCondition] = []
    if equipment:
        conditions.append(
            models.FieldCondition(
                key="equipment",
                match=models.MatchAny(any=list(equipment)),
            )
        )
    if difficulty:
        conditions.append(
            models.FieldCondition(
                key="difficulty",
                match=models.MatchValue(value=difficulty),
            )
        )
    if movement_pattern:
        conditions.append(
            models.FieldCondition(
                key="movement_pattern",
                match=models.MatchValue(value=movement_pattern),
            )
        )
    if source_dataset:
        conditions.append(
            models.FieldCondition(
                key="source_dataset",
                match=models.MatchValue(value=source_dataset),
            )
        )
    return models.Filter(must=conditions) if conditions else None


def search_exercise_options(
    query: str,
    *,
    equipment: tuple[str, ...] | None = None,
    difficulty: str | None = None,
    movement_pattern: str | None = None,
    source_dataset: str | None = None,
    k: int = 5,
) -> list[ExerciseCatalogEntry]:
    """Search Qdrant with payload filters and hydrate authoritative entries.

    Pass ``source_dataset="stretch"`` (or ``movement_pattern="mobility"``) to
    retrieve only warm-up/cool-down mobility work instead of main-set lifts.
    """
    if not query.strip():
        return []
    if k < 1:
        return []

    documents = exercise_store().similarity_search(
        query,
        k=k,
        filter=_match_filter(
            equipment=equipment,
            difficulty=difficulty,
            movement_pattern=movement_pattern,
            source_dataset=source_dataset,
        ),
    )
    catalog = _catalog_by_slug()
    return [
        catalog[slug]
        for document in documents
        if (slug := document.metadata.get("exercise_slug")) in catalog
    ]


def exercise_entry_to_dict(entry: ExerciseCatalogEntry) -> dict[str, Any]:
    """Serialize a hydrated entry for agent tools and API responses."""
    return {
        "slug": entry.slug,
        "name": entry.name,
        "equipment": list(entry.equipment),
        "difficulty": entry.difficulty,
        "movement_pattern": entry.movement_pattern,
        "primary_muscles": list(entry.primary_muscles),
        "preparation": entry.preparation,
        "execution": entry.execution,
        "search_text": entry.search_text,
        "source_dataset": entry.source_dataset,
    }
