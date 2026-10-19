"""Deterministic safety/integrity checks for LLM-authored workout plans.

The LLM drafts and edits workout-plan JSON; this validator is the one piece
that must stay code-enforced regardless of structured-output guarantees. It
never trusts the model for catalog existence, equipment compatibility, basic
volume sanity, or the warm-up/cool-down bookends -- and it enforces the
text-only injury-disclaimer requirement: any user-reported injury or
limitation must be surfaced verbatim in ``safety_note`` rather than silently
worked around.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ai_fitness_coach_rag.context.catalog import ExerciseCatalogEntry

_ALWAYS_AVAILABLE_EQUIPMENT = {"bodyweight", "none"}
_MIN_SETS, _MAX_SETS = 1, 6
_MIN_REST_SECONDS, _MAX_REST_SECONDS = 15, 300


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Outcome of validating a plan; empty ``errors`` means it is approvable."""

    errors: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _equipment_compatible(
    entry_equipment: tuple[str, ...], available_equipment: tuple[str, ...]
) -> bool:
    if any(item in _ALWAYS_AVAILABLE_EQUIPMENT for item in entry_equipment):
        return True
    return any(item in available_equipment for item in entry_equipment)


def validate_workout_plan(
    plan: dict[str, Any],
    *,
    catalog_by_slug: dict[str, ExerciseCatalogEntry],
    available_equipment: tuple[str, ...],
    injuries_or_limitations: str | None,
) -> ValidationResult:
    """Re-check a freshly generated or user-edited plan before it may be saved."""
    errors: list[str] = []
    days = plan.get("days") or []
    if not days:
        errors.append("Plan must include at least one training day.")

    for day in days:
        day_label = day.get("day", "<unnamed day>")
        exercises = day.get("exercises") or []
        if not exercises:
            errors.append(f"{day_label}: must include at least one exercise.")
            continue

        seen_ids: set[str] = set()
        for exercise in exercises:
            slug = exercise.get("exercise_id")
            entry = catalog_by_slug.get(slug)
            if entry is None:
                errors.append(f"{day_label}: unsupported exercise '{slug}'.")
                continue
            if slug in seen_ids:
                errors.append(f"{day_label}: exercise '{slug}' is duplicated.")
            seen_ids.add(slug)
            if not _equipment_compatible(entry.equipment, available_equipment):
                errors.append(
                    f"{day_label}: '{slug}' requires unavailable equipment "
                    f"{list(entry.equipment)}."
                )
            sets = exercise.get("sets")
            if not isinstance(sets, int) or not (_MIN_SETS <= sets <= _MAX_SETS):
                errors.append(f"{day_label}: '{slug}' has invalid sets ({sets!r}).")
            rest_seconds = exercise.get("rest_seconds")
            if not isinstance(rest_seconds, int) or not (
                _MIN_REST_SECONDS <= rest_seconds <= _MAX_REST_SECONDS
            ):
                errors.append(
                    f"{day_label}: '{slug}' has invalid rest_seconds "
                    f"({rest_seconds!r})."
                )
            if not str(exercise.get("reps") or "").strip():
                errors.append(f"{day_label}: '{slug}' is missing a reps target.")

        first_entry = catalog_by_slug.get(exercises[0].get("exercise_id"))
        last_entry = catalog_by_slug.get(exercises[-1].get("exercise_id"))
        if exercises[0].get("exercise_type") != "warm_up" or (
            first_entry is not None and first_entry.movement_pattern != "mobility"
        ):
            errors.append(f"{day_label}: must start with a warm-up stretch.")
        if exercises[-1].get("exercise_type") != "cool_down" or (
            last_entry is not None and last_entry.movement_pattern != "mobility"
        ):
            errors.append(f"{day_label}: must end with a cool-down stretch.")

    safety_note = str(plan.get("safety_note") or "").strip()
    if not safety_note:
        errors.append("Plan must include a non-empty safety_note.")
    elif (
        injuries_or_limitations
        and injuries_or_limitations.strip().lower() not in safety_note.lower()
    ):
        errors.append(
            "safety_note must restate the user's reported injuries/limitations "
            "verbatim; the LLM must never silently work around them."
        )

    return ValidationResult(errors=tuple(errors))
