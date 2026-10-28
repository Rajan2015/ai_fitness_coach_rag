"""Stateless query rewriting for profile-aware exercise retrieval.

The rewriter only improves semantic relevance.  Equipment, difficulty,
movement-pattern, and injury constraints remain deterministic concerns owned by
the saved profile and the catalog filters.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from ai_fitness_coach_rag.db.models import WorkoutProfile
from ai_fitness_coach_rag.llm.factory import get_llm

MAIN_MOVEMENT_PATTERNS = (
    "squat",
    "hinge",
    "lunge",
    "push",
    "pull",
    "core",
    "carry",
    "full-body",
)


class WorkoutRetrievalSpec(BaseModel):
    """Semantic retrieval requests for each part of a workout plan."""

    warm_up_query: str = Field(min_length=1)
    cool_down_query: str = Field(min_length=1)
    main_queries: dict[str, str]
    soft_terms: list[str] = Field(default_factory=list)

    @field_validator("main_queries")
    @classmethod
    def validate_main_queries(cls, value: dict[str, str]) -> dict[str, str]:
        missing = set(MAIN_MOVEMENT_PATTERNS) - set(value)
        if missing:
            raise ValueError(
                "main_queries must include every supported movement pattern: "
                + ", ".join(sorted(missing))
            )
        if any(not query.strip() for query in value.values()):
            raise ValueError("main_queries values must not be blank")
        return {pattern: value[pattern].strip() for pattern in MAIN_MOVEMENT_PATTERNS}

    @field_validator("warm_up_query", "cool_down_query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return value.strip()


def _profile_terms(profile: WorkoutProfile) -> list[str]:
    terms = [
        profile.training_experience or "",
        *(profile.preferences or []),
    ]
    if profile.injuries_or_limitations:
        terms.append(profile.injuries_or_limitations)
    return [term.strip() for term in terms if term and term.strip()]


def _fallback_spec(user_request: str, profile: WorkoutProfile) -> WorkoutRetrievalSpec:
    """Build useful keyword queries without making any safety decisions."""
    request = user_request.strip() or "personalized workout"
    terms = _profile_terms(profile)
    context = " ".join([request, *terms])
    soft_terms = list(dict.fromkeys([*profile.preferences, request]))
    return WorkoutRetrievalSpec(
        warm_up_query=f"gentle warm-up mobility for {context}",
        cool_down_query=f"gentle cool-down mobility for {context}",
        main_queries={
            pattern: f"{pattern} exercise for {context}"
            for pattern in MAIN_MOVEMENT_PATTERNS
        },
        soft_terms=soft_terms,
    )


def _rewriter_prompt(user_request: str, profile: WorkoutProfile) -> str:
    return (
        "Rewrite the request into semantic exercise-search queries. Return one "
        "warm-up query, one cool-down query, and one query for every movement "
        f"pattern ({', '.join(MAIN_MOVEMENT_PATTERNS)}).\n"
        "Use the request, goals, and preferences as soft relevance signals. "
        "Do not decide whether equipment, difficulty, movement patterns, or "
        "injury-related constraints are allowed; those are enforced separately "
        "by deterministic catalog filters. Do not provide medical advice.\n\n"
        f"Current request: {user_request.strip() or 'personalized workout'}\n"
        f"Goal: {getattr(profile, 'goal_type', '') or 'not specified'}\n"
        f"Training experience: {profile.training_experience}\n"
        f"Equipment (context only): {', '.join(profile.equipment) or 'none stated'}\n"
        f"Preferences: {', '.join(profile.preferences) or 'none stated'}\n"
        f"Injuries or limitations (context only): "
        f"{profile.injuries_or_limitations or 'none reported'}\n"
        f"Days: {profile.workout_days_per_week}; "
        f"Duration: {profile.session_duration_minutes} minutes"
    )


def rewrite_workout_query(
    user_request: str,
    profile: WorkoutProfile,
    *,
    llm: Any | None = None,
) -> WorkoutRetrievalSpec:
    """Return an LLM rewrite, falling back to deterministic keyword queries.

    The call has no tools, persistence, checkpointer, or conversation state.
    """
    fallback = _fallback_spec(user_request, profile)
    rewriter = llm if llm is not None else get_llm("workout_query_rewriter")
    try:
        structured_rewriter = rewriter.with_structured_output(
            WorkoutRetrievalSpec, method="json_schema"
        )
        result = structured_rewriter.invoke(_rewriter_prompt(user_request, profile))
        if isinstance(result, WorkoutRetrievalSpec):
            return result
        return WorkoutRetrievalSpec.model_validate(result)
    except Exception:
        return fallback
