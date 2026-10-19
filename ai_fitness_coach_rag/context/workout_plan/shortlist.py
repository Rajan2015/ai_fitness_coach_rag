"""Deterministic candidate shortlists for the LLM workout-plan drafter.

The LLM never sees the full catalog. It is only shown exercises that are
already filtered by the user's saved equipment and training experience, so
its structured-output choices are hallucination-proof by construction (see
``schemas.build_plan_schema``) rather than merely checked after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai_fitness_coach_rag.context.catalog import (
    ExerciseCatalogEntry,
    load_exercise_catalog,
)

_ALWAYS_AVAILABLE_EQUIPMENT = {"bodyweight", "none"}

_DIFFICULTY_CEILING: dict[str, frozenset[str]] = {
    "beginner": frozenset({"beginner"}),
    "intermediate": frozenset({"beginner", "intermediate"}),
    "advanced": frozenset({"beginner", "intermediate", "advanced"}),
}

_MAIN_MOVEMENT_PATTERNS = (
    "squat",
    "hinge",
    "lunge",
    "push",
    "pull",
    "core",
    "carry",
    "full-body",
)


@dataclass(frozen=True, slots=True)
class ExerciseShortlist:
    """Candidate pools grouped for prompt assembly and schema construction."""

    warm_up: tuple[ExerciseCatalogEntry, ...]
    cool_down: tuple[ExerciseCatalogEntry, ...]
    main: dict[str, tuple[ExerciseCatalogEntry, ...]]

    def all_entries(self) -> tuple[ExerciseCatalogEntry, ...]:
        main_entries = tuple(entry for pool in self.main.values() for entry in pool)
        return self.warm_up + self.cool_down + main_entries

    def allowed_slugs(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(entry.slug for entry in self.all_entries()))


def _is_equipment_compatible(
    entry_equipment: tuple[str, ...], available_equipment: tuple[str, ...]
) -> bool:
    if any(item in _ALWAYS_AVAILABLE_EQUIPMENT for item in entry_equipment):
        return True
    return any(item in available_equipment for item in entry_equipment)


def build_exercise_shortlist(
    *,
    equipment: tuple[str, ...],
    training_experience: str,
    per_pattern_limit: int = 6,
    stretch_limit: int = 8,
) -> ExerciseShortlist:
    """Filter the authoritative catalog into safe, compatible candidate pools.

    ``equipment`` and ``training_experience`` must come from the user's saved
    ``WorkoutProfile`` -- never inferred by the LLM. Bodyweight/no-equipment
    exercises are always included since they require nothing the user lacks.
    """
    allowed_difficulties = _DIFFICULTY_CEILING.get(
        training_experience, _DIFFICULTY_CEILING["beginner"]
    )
    compatible = [
        entry
        for entry in load_exercise_catalog()
        if entry.difficulty in allowed_difficulties
        and _is_equipment_compatible(entry.equipment, equipment)
    ]

    stretch_pool = tuple(
        entry for entry in compatible if entry.source_dataset == "stretch"
    )
    warm_up = stretch_pool[:stretch_limit]
    cool_down = stretch_pool[:stretch_limit]

    main: dict[str, tuple[ExerciseCatalogEntry, ...]] = {}
    for pattern in _MAIN_MOVEMENT_PATTERNS:
        pool = tuple(
            entry
            for entry in compatible
            if entry.source_dataset != "stretch" and entry.movement_pattern == pattern
        )
        if pool:
            main[pattern] = pool[:per_pattern_limit]

    return ExerciseShortlist(warm_up=warm_up, cool_down=cool_down, main=main)
