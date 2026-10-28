"""Structured-output schemas for the LLM-authored workout-plan draft.

``build_plan_schema`` narrows ``exercise_id`` to a ``Literal`` of the slugs
actually present in a given :class:`ExerciseShortlist`. This makes selecting
an exercise the model was never shown -- or one incompatible with the user's
equipment/experience -- a schema validation failure during generation,
rather than something caught only after the fact.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, create_model

from ai_fitness_coach_rag.context.workout_plan.shortlist import ExerciseShortlist

ExerciseType = Literal["warm_up", "main", "cool_down"]


class PlanExerciseDraft(BaseModel):
    """One exercise entry inside a single workout day."""

    exercise_id: str = Field(description="Catalog slug of the chosen exercise.")
    name: str = Field(description="Human-readable exercise name shown to the user.")
    exercise_type: ExerciseType = Field(
        description="warm_up (first), main (working sets), or cool_down (last)."
    )
    sets: int = Field(ge=1, le=6)
    reps: str = Field(description='Rep target, e.g. "8-12", "30s", "AMRAP".')
    rest_seconds: int = Field(ge=15, le=300)
    # No default: OpenAI's strict json_schema structured-output mode rejects any
    # property with a "default" key, and strict mode already forces every
    # property into "required" regardless, so a default here would be both
    # unusable and schema-invalid. Use "" explicitly in the prompt/validator
    # if an empty note is an acceptable value.
    notes: str = Field(description="Short coaching cue for this exercise.")


class PlanDayDraft(BaseModel):
    """One training day: ordered warm-up, main-set, and cool-down exercises."""

    day: str
    focus: str
    exercises: list[PlanExerciseDraft]


class WorkoutPlanDraft(BaseModel):
    """Full structured plan the LLM proposes; re-checked before persistence."""

    title: str
    goal: Literal["lose", "gain", "maintain"]
    days: list[PlanDayDraft]
    progression_rule: str
    safety_note: str = Field(
        description=(
            "Always-visible disclaimer. Must restate any user-reported "
            "injuries or limitations verbatim and recommend consulting a "
            "qualified professional; never silently work around them."
        )
    )


def _exercise_id_literal(allowed_slugs: tuple[str, ...]) -> type:
    if len(allowed_slugs) == 1:
        return Literal[allowed_slugs[0]]
    return Literal[allowed_slugs]


def build_plan_schema(shortlist: ExerciseShortlist) -> type[BaseModel]:
    """Return a ``WorkoutPlanDraft`` variant whose ``exercise_id`` is restricted
    to slugs actually present in ``shortlist`` for this request.
    """
    allowed_slugs = shortlist.allowed_slugs()
    if not allowed_slugs:
        return WorkoutPlanDraft

    constrained_exercise = create_model(
        "ConstrainedPlanExerciseDraft",
        __base__=PlanExerciseDraft,
        exercise_id=(
            _exercise_id_literal(allowed_slugs),
            Field(description="Catalog slug of the chosen exercise."),
        ),
    )
    constrained_day = create_model(
        "ConstrainedPlanDayDraft",
        __base__=PlanDayDraft,
        exercises=(list[constrained_exercise], ...),
    )
    return create_model(
        "ConstrainedWorkoutPlanDraft",
        __base__=WorkoutPlanDraft,
        days=(list[constrained_day], ...),
    )
