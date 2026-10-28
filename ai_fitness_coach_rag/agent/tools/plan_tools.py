"""Workout-profile capture and workout-plan draft/validate/save tools.

Flow: `get_workout_profile_gaps` -> one question at a time -> explicit answers
via `save_workout_profile_answer` -> once sufficient, `build_workout_plan_draft`
builds a safe candidate shortlist (`context.workout_plan.shortlist`), asks the
LLM for a structured draft constrained to that shortlist
(`context.workout_plan.schemas`), and re-checks it with the deterministic
`context.workout_plan.validator` before it is ever shown as valid. The LLM
never silently infers profile values, selects exercises outside the
shortlist, or works around a reported injury/limitation -- `safety_note` must
always restate it verbatim and recommend a qualified professional.
"""

from __future__ import annotations

import datetime
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from langchain_core.tools import tool
from langgraph.config import get_config

from ai_fitness_coach_rag.agent.tools.onboarding_tools import get_or_create_user
from ai_fitness_coach_rag.context.catalog import (
    ExerciseCatalogEntry,
    load_exercise_catalog,
)
from ai_fitness_coach_rag.context.retrievers.exercise_qdrant import (
    exercise_entry_to_dict,
    search_exercise_options as _search_exercise_candidates,
)
from ai_fitness_coach_rag.context.workout_plan.schemas import build_plan_schema
from ai_fitness_coach_rag.context.workout_plan.shortlist import (
    ExerciseShortlist,
    build_exercise_shortlist,
)
from ai_fitness_coach_rag.context.workout_plan.query_rewriter import (
    WorkoutRetrievalSpec,
    rewrite_workout_query,
)
from ai_fitness_coach_rag.context.workout_plan.validator import (
    ValidationResult,
    validate_workout_plan as _validate_workout_plan,
)
from ai_fitness_coach_rag.db.models import (
    GoalType,
    WorkoutPlan,
    WorkoutPlanStatus,
    WorkoutProfile,
)
from ai_fitness_coach_rag.db.session import SessionLocal
from ai_fitness_coach_rag.llm.factory import get_llm

_MAX_DRAFT_ATTEMPTS = 2

# Twilio WhatsApp body cap is ~1600 chars; keep a safety margin below it.
_MAX_SUMMARY_CHARS = 1400
_TRUNCATION_SUFFIX = "\n…see your dashboard for the full plan."


def _hard_truncate(text: str, limit: int) -> str:
    """Cut ``text`` at a line boundary under ``limit`` chars, never exceeding it."""
    if len(text) <= limit:
        return text
    cutoff = limit - len(_TRUNCATION_SUFFIX)
    truncated = text[:cutoff].rsplit("\n", 1)[0]
    return truncated + _TRUNCATION_SUFFIX


def _plan_summary(plan_json: dict[str, Any]) -> str:
    """Build a short, per-day WhatsApp summary; the full plan stays in the DB/UI."""
    title = str(plan_json.get("title") or "Workout Plan")
    lines = [f'Saved and activated "{title}"!']
    for day in plan_json.get("days", []):
        day_name = day.get("day", "Day")
        focus = day.get("focus", "")
        main_names = [
            ex.get("name", "")
            for ex in day.get("exercises", [])
            if ex.get("exercise_type") == "main"
        ]
        exercises = ", ".join(main_names) or "rest/active recovery"
        lines.append(f"- {day_name} ({focus}): {exercises}")
    lines.append("Full plan with sets/reps is on your dashboard.")
    return _hard_truncate("\n".join(lines), _MAX_SUMMARY_CHARS)


def _current_user_id() -> str:
    """Thread id == hashed-phone user id, set by orchestrator's thread_config()."""
    return get_config()["configurable"]["thread_id"]


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


# --- Workout-profile slots -------------------------------------------------

_TRAINING_EXPERIENCES = ("beginner", "intermediate", "advanced")

_EQUIPMENT_SYNONYMS = {
    "bodyweight": "bodyweight",
    "body weight": "bodyweight",
    "no equipment": "none",
    "none": "none",
    "dumbbells": "dumbbell",
    "dumbbell": "dumbbell",
    "barbell": "barbell",
    "barbells": "barbell",
    "kettlebell": "kettlebell",
    "kettlebells": "kettlebell",
    "cable": "cable",
    "cables": "cable",
    "cable machine": "cable",
    "band": "band",
    "bands": "band",
    "resistance band": "band",
    "resistance bands": "band",
    "machine": "machine",
    "machines": "machine",
    "gym machine": "machine",
    "gym machines": "machine",
    "weight machine": "machine",
    "weight machines": "machine",
    "smith machine": "smith-machine",
    "smith": "smith-machine",
    "weighted": "weighted",
    "weighted vest": "weighted",
}

_NO_PREFERENCE_PHRASES = {
    "none",
    "no",
    "n/a",
    "na",
    "nothing",
    "no preference",
    "no preferences",
}
_NO_INJURY_PHRASES = {
    "none",
    "no",
    "n/a",
    "na",
    "nothing",
    "no injuries",
    "no injury",
    "no limitations",
    "no limitation",
}


def _parse_training_experience(text: str) -> str | None:
    lowered = text.strip().lower()
    numbered = {"1": "beginner", "2": "intermediate", "3": "advanced"}
    if lowered in numbered:
        return numbered[lowered]
    for level in _TRAINING_EXPERIENCES:
        if level in lowered:
            return level
    return None


def _parse_equipment(text: str) -> tuple[str, ...] | None:
    lowered = text.strip().lower()
    if not lowered:
        return None
    tokens = re.split(r"[,/]|\band\b", lowered)
    canonical: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        mapped = _EQUIPMENT_SYNONYMS.get(token)
        if mapped is None:
            for key, value in _EQUIPMENT_SYNONYMS.items():
                if key in token:
                    mapped = value
                    break
        if mapped and mapped not in canonical:
            canonical.append(mapped)
    return tuple(canonical) if canonical else None


def _parse_days_per_week(text: str) -> int | None:
    match = re.search(r"\d", text)
    if not match:
        return None
    days = int(match.group())
    return days if 1 <= days <= 7 else None


def _parse_session_duration(text: str) -> int | None:
    match = re.search(r"\d+", text)
    if not match:
        return None
    minutes = int(match.group())
    return minutes if 10 <= minutes <= 180 else None


def _parse_preferences(text: str) -> list[str] | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.lower() in _NO_PREFERENCE_PHRASES:
        return []
    return [
        item.strip() for item in re.split(r"[,/]|\band\b", stripped) if item.strip()
    ]


def _parse_injuries(text: str) -> str | None:
    """Return '' for an explicit 'no injuries' answer, None only on blank input."""
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.lower() in _NO_INJURY_PHRASES:
        return ""
    return stripped


@dataclass(frozen=True)
class WorkoutProfileSlot:
    field: str
    prompt: str
    parser: Callable[[str], object | None]
    error: str


WORKOUT_PROFILE_SLOTS: list[WorkoutProfileSlot] = [
    WorkoutProfileSlot(
        "training_experience",
        "What's your training experience? Reply 1 beginner, 2 intermediate, or 3 advanced.",
        _parse_training_experience,
        "Please reply with 1 (beginner), 2 (intermediate), or 3 (advanced).",
    ),
    WorkoutProfileSlot(
        "equipment",
        "What equipment do you have access to? (e.g. bodyweight only, dumbbells, "
        "barbell, kettlebell, resistance bands, gym machines)",
        _parse_equipment,
        "Please list your equipment, e.g. 'dumbbells and gym machines' or 'bodyweight only'.",
    ),
    WorkoutProfileSlot(
        "workout_days_per_week",
        "How many days a week can you train? (3 or 4 recommended)",
        _parse_days_per_week,
        "Please share a number between 1 and 7.",
    ),
    WorkoutProfileSlot(
        "session_duration_minutes",
        "How long is each session, in minutes? (30-60 recommended)",
        _parse_session_duration,
        "Please share your session length in minutes (e.g. 45).",
    ),
    WorkoutProfileSlot(
        "preferences",
        "Any exercises or activities you particularly like or want included? "
        "Reply 'none' if you don't have a preference.",
        _parse_preferences,
        "Please list any preferences, or reply 'none'.",
    ),
    WorkoutProfileSlot(
        "injuries_or_limitations",
        "Do you have any injuries or physical limitations I should know about? "
        "Reply 'none' if not.",
        _parse_injuries,
        "Please describe any injuries/limitations, or reply 'none'.",
    ),
]


def _get_workout_profile(session, user) -> WorkoutProfile | None:
    return session.query(WorkoutProfile).filter_by(user_id=user.id).one_or_none()


def _slot_is_filled(profile: WorkoutProfile | None, slot: WorkoutProfileSlot) -> bool:
    if profile is None:
        return False
    value = getattr(profile, slot.field)
    if slot.field == "equipment":
        return bool(value)
    return value is not None


def next_workout_profile_slot(
    profile: WorkoutProfile | None,
) -> WorkoutProfileSlot | None:
    """Return the first unanswered workout-profile slot, or None if complete."""
    for slot in WORKOUT_PROFILE_SLOTS:
        if not _slot_is_filled(profile, slot):
            return slot
    return None


def apply_workout_profile_answer(
    session, user, slot: WorkoutProfileSlot, text: str
) -> bool:
    """Parse and persist one slot answer. Returns False on parse failure."""
    value = slot.parser(text)
    if value is None:
        return False
    profile = _get_workout_profile(session, user)
    if profile is None:
        profile = WorkoutProfile(user_id=user.id)
        session.add(profile)
    setattr(profile, slot.field, value)
    session.commit()
    return True


def _profile_to_dict(profile: WorkoutProfile) -> dict[str, Any]:
    return {
        "training_experience": profile.training_experience,
        "equipment": list(profile.equipment or []),
        "workout_days_per_week": profile.workout_days_per_week,
        "session_duration_minutes": profile.session_duration_minutes,
        "preferences": list(profile.preferences or []),
        "injuries_or_limitations": profile.injuries_or_limitations or None,
    }


@tool
def get_workout_profile_gaps() -> dict[str, Any]:
    """Return the next missing workout-profile field and the question to ask,
    or confirm the profile is complete. Always call this before asking the
    user anything about their workout preferences, and call it again after
    each answer -- never infer equipment, experience, available time, or
    injuries yourself.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        profile = _get_workout_profile(session, user)
        slot = next_workout_profile_slot(profile)
        if slot is None:
            return {"complete": True, "profile": _profile_to_dict(profile)}
        return {"complete": False, "field": slot.field, "question": slot.prompt}
    finally:
        session.close()


@tool
def save_workout_profile_answer(field: str, value: str) -> dict[str, Any]:
    """Validate and persist the user's explicit answer for one workout-profile
    field. `field` must be the field name returned by get_workout_profile_gaps
    (e.g. 'training_experience', 'equipment', 'workout_days_per_week',
    'session_duration_minutes', 'preferences', 'injuries_or_limitations').
    `value` must be the user's own words -- do not paraphrase or guess it.
    """
    slot_by_field = {slot.field: slot for slot in WORKOUT_PROFILE_SLOTS}
    slot = slot_by_field.get(field)
    if slot is None:
        return {"saved": False, "error": f"Unknown workout-profile field '{field}'."}

    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        if not apply_workout_profile_answer(session, user, slot, value):
            return {"saved": False, "error": slot.error}
        profile = _get_workout_profile(session, user)
        next_slot = next_workout_profile_slot(profile)
        if next_slot is None:
            return {
                "saved": True,
                "complete": True,
                "profile": _profile_to_dict(profile),
            }
        return {
            "saved": True,
            "complete": False,
            "field": next_slot.field,
            "question": next_slot.prompt,
        }
    finally:
        session.close()


# --- Exercise search --------------------------------------------------------


@tool
def search_exercise_options(
    query: str,
    movement_pattern: str | None = None,
    source_dataset: str | None = None,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Search the exercise_knowledge catalog for candidates compatible with the
    user's saved equipment. Pass source_dataset="stretch" for warm-up/cool-down
    mobility work, or movement_pattern (squat/hinge/lunge/push/pull/core/carry/
    full-body) to narrow main-set work. Returns hydrated catalog entries.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        profile = _get_workout_profile(session, user)
        equipment = (
            tuple(profile.equipment) if profile and profile.equipment else None
        )
        entries = _search_exercise_candidates(
            query,
            equipment=equipment,
            movement_pattern=movement_pattern,
            source_dataset=source_dataset,
            k=k,
        )
        return [exercise_entry_to_dict(entry) for entry in entries]
    finally:
        session.close()


# --- Plan drafting, validation, and persistence ----------------------------


@lru_cache(maxsize=1)
def _catalog_by_slug() -> dict[str, ExerciseCatalogEntry]:
    return {entry.slug: entry for entry in load_exercise_catalog()}


def _shortlist_prompt_section(shortlist: ExerciseShortlist) -> str:
    """Render the shortlist as plain text so the LLM can pick sensible slugs."""

    def _lines(entries: tuple[ExerciseCatalogEntry, ...]) -> str:
        return (
            "\n".join(
                f"  - {entry.slug}: {entry.name} ({', '.join(entry.equipment)})"
                for entry in entries
            )
            or "  (none available)"
        )

    sections = [
        "Warm-up / cool-down (mobility) options:",
        _lines(shortlist.warm_up),
    ]
    for pattern, entries in shortlist.main.items():
        sections.append(f"Main-set options ({pattern}):")
        sections.append(_lines(entries))
    return "\n".join(sections)


def _draft_prompt(
    profile: WorkoutProfile,
    shortlist: ExerciseShortlist,
    retrieval_spec: WorkoutRetrievalSpec,
    retry_errors: tuple[str, ...],
) -> str:
    base = (
        "Design a workout plan using ONLY the exercise_id slugs listed below.\n"
        f"Goal/training experience: {profile.training_experience}.\n"
        f"Days per week: {profile.workout_days_per_week}. "
        f"Session length: {profile.session_duration_minutes} minutes.\n"
        f"Equipment available: {', '.join(profile.equipment) or 'none stated'}.\n"
        f"Preferences: {', '.join(profile.preferences) or 'none stated'}.\n"
        f"Injuries/limitations reported: {profile.injuries_or_limitations or 'none reported'}.\n"
        "Every day must start with one warm_up exercise and end with one "
        "cool_down exercise, both drawn from the mobility options; main sets "
        "come from the main-set options. The safety_note must restate any "
        "reported injuries/limitations verbatim and recommend a qualified "
        "professional; never silently work around them.\n\n"
        "Use these semantic retrieval queries as relevance guidance only. "
        "They do not change the hard profile and catalog constraints:\n"
        f"- Warm-up: {retrieval_spec.warm_up_query}\n"
        f"- Cool-down: {retrieval_spec.cool_down_query}\n"
        + "\n".join(
            f"- {pattern}: {query}"
            for pattern, query in retrieval_spec.main_queries.items()
        )
        + f"\n- Soft terms: {', '.join(retrieval_spec.soft_terms) or 'none'}\n\n"
        f"{_shortlist_prompt_section(shortlist)}"
    )
    if retry_errors:
        base += "\n\nThe previous draft was rejected for:\n" + "\n".join(
            f"- {error}" for error in retry_errors
        )
    return base


def _validate_plan_dict(
    plan: dict[str, Any], profile: WorkoutProfile
) -> ValidationResult:
    return _validate_workout_plan(
        plan,
        catalog_by_slug=_catalog_by_slug(),
        available_equipment=tuple(profile.equipment or ()),
        injuries_or_limitations=profile.injuries_or_limitations or None,
    )


@tool
def build_workout_plan_draft(user_request: str) -> dict[str, Any]:
    """Generate a structured workout-plan draft for the user's saved profile.
    Only call this once get_workout_profile_gaps reports complete=True. The
    user_request must be the complete workout-plan request from the current
    user message, so semantic retrieval can reflect the requested intent.
    exercise choices are schema-constrained to a safe, equipment-compatible
    shortlist and re-checked by a deterministic validator; present the
    returned plan (or its errors) to the user rather than editing it yourself.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        profile = _get_workout_profile(session, user)
        if next_workout_profile_slot(profile) is not None:
            return {
                "error": "Workout profile is incomplete; call get_workout_profile_gaps first."
            }

        shortlist = build_exercise_shortlist(
            equipment=tuple(profile.equipment),
            training_experience=profile.training_experience,
        )
        if not shortlist.allowed_slugs():
            return {
                "error": "No compatible exercises found for this equipment/experience combination."
            }

        schema = build_plan_schema(shortlist)
        retrieval_spec = rewrite_workout_query(user_request, profile)
        structured_llm = get_llm("workout_plan").with_structured_output(schema)

        plan: dict[str, Any] = {}
        errors: tuple[str, ...] = ()
        for attempt in range(_MAX_DRAFT_ATTEMPTS):
            prompt = _draft_prompt(
                profile,
                shortlist,
                retrieval_spec,
                errors if attempt else (),
            )
            try:
                draft = structured_llm.invoke(prompt)
            except Exception as exc:  # LLM/provider error
                return {"error": f"Plan generation failed: {exc}"}
            plan = draft.model_dump()
            result = _validate_plan_dict(plan, profile)
            if result.is_valid:
                return {"plan": plan, "valid": True}
            errors = result.errors

        return {"plan": plan, "valid": False, "errors": list(errors)}
    finally:
        session.close()


@tool
def validate_workout_plan(plan_json: dict[str, Any]) -> dict[str, Any]:
    """Re-check a freshly generated or user-edited workout-plan draft against
    catalog existence, equipment compatibility, duplicate/volume bounds, the
    warm-up/cool-down bookends, and the injury-disclaimer requirement. Call
    this after any user-requested edit, before presenting the plan again.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        profile = _get_workout_profile(session, user)
        if profile is None:
            return {"valid": False, "errors": ["Workout profile not found."]}
        result = _validate_plan_dict(plan_json, profile)
        return {"valid": result.is_valid, "errors": list(result.errors)}
    finally:
        session.close()


@tool
def save_workout_plan(plan_json: dict[str, Any]) -> str:
    """Persist the exact user-approved plan JSON and archive any prior active
    plan. Only call this after the user has explicitly approved the plan.
    Re-validates one final time and refuses to save an invalid plan. Returns
    a short per-day summary capped well under the WhatsApp/Twilio message
    limit -- the full plan is always saved to the DB and viewable on the
    dashboard. Relay this return value to the user as-is, without adding
    extra commentary that could push the reply past the limit.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        profile = _get_workout_profile(session, user)
        if profile is None:
            return "Cannot save: workout profile not found."

        result = _validate_plan_dict(plan_json, profile)
        if not result.is_valid:
            return "Cannot save, plan failed validation: " + "; ".join(result.errors)

        session.query(WorkoutPlan).filter_by(
            user_id=user.id, status=WorkoutPlanStatus.ACTIVE
        ).update({"status": WorkoutPlanStatus.ARCHIVED})

        plan_row = WorkoutPlan(
            user_id=user.id,
            status=WorkoutPlanStatus.ACTIVE,
            title=str(plan_json.get("title") or "Workout Plan"),
            goal_type=GoalType(plan_json["goal"]),
            plan_json=plan_json,
            profile_snapshot_json=_profile_to_dict(profile),
            approved_at=_utcnow(),
        )
        session.add(plan_row)
        session.commit()
        return _plan_summary(plan_json)
    finally:
        session.close()
