"""Deterministic DailyLog tool functions bound to the tool-calling agent.

Each tool only persists values the agent has already decided on (e.g. via
`nutrition_tools.lookup_nutrition`) — no extraction or estimation happens
here. Confirmation-before-save is handled by `HumanInTheLoopMiddleware`
pausing the graph before these tools execute (see orchestrator.py), backed by
the LangGraph `AsyncSqliteSaver` checkpointer. No separate pending-state table.
"""

from __future__ import annotations

from typing import Annotated, Literal

from langchain_core.tools import tool
from langgraph.config import get_config
from pydantic import BaseModel, Field

from ai_fitness_coach_rag.agent.tools.onboarding_tools import get_or_create_user
from ai_fitness_coach_rag.db.models import DailyLog, EntrySource, LogType, Score, User
from ai_fitness_coach_rag.db.score_service import (
    daily_targets,
    upsert_daily_score,
    user_local_date,
)
from ai_fitness_coach_rag.db.session import SessionLocal


def _current_user_id() -> str:
    """Thread id == hashed-phone user id, set by orchestrator's thread_config()."""
    return get_config()["configurable"]["thread_id"]


def _score_message(prefix: str, score: Score, user: User) -> str:
    """Return deterministic score facts for the agent to explain to the user."""
    maintenance_calories, protein_target = daily_targets(user)
    target_message = ""
    if maintenance_calories is not None and protein_target is not None:
        target_message = (
            f" Targets: maintenance calories {maintenance_calories:.0f} kcal/day, "
            f"protein {protein_target:.0f} g/day."
        )
    return (
        f"{prefix} Daily score: {score.overall_score:.1f}/100. "
        f"Breakdown: calories {score.calorie_score:.1f}, "
        f"protein {score.protein_score:.1f}, activity {score.activity_score:.1f}, "
        f"water {score.water_score:.1f}, consistency {score.consistency_score:.1f}."
        f"{target_message}"
    )


class FoodLogEntry(BaseModel):
    item: str = Field(description="Food name")
    quantity_desc: str = Field(description="e.g. '2 rotis'")
    calories: float
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    source: Literal["database", "estimated"] = Field(
        description="'database' if values came from lookup_nutrition, "
        "'estimated' if you estimated them yourself"
    )


@tool
def log_food(entries: list[FoodLogEntry]) -> str:
    """Log one or more food items with their calories/macros for today. Call
    lookup_nutrition first for each item to get verified values; only use
    source='estimated' if lookup_nutrition had no good match.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        today = user_local_date(user)
        for entry in entries:
            session.add(
                DailyLog(
                    user_id=user.id,
                    log_type=LogType.FOOD,
                    log_date=today,
                    description=entry.item,
                    quantity=entry.quantity_desc,
                    calories=entry.calories,
                    protein_g=entry.protein_g,
                    carbs_g=entry.carbs_g,
                    fat_g=entry.fat_g,
                    source=EntrySource(entry.source),
                )
            )
        score = upsert_daily_score(session, user, today)
        session.commit()
        return _score_message(f"Logged {len(entries)} food item(s).", score, user)
    finally:
        session.close()


@tool
def log_workout(
    activity: Annotated[
        str, Field(description="Workout/exercise name, e.g. 'running', 'bench press'")
    ],
    duration_minutes: Annotated[
        float | None,
        Field(description="Duration in minutes, if stated or reasonably inferable"),
    ] = None,
    calories_burned: Annotated[
        float | None,
        Field(
            description="Calories burned. Use the user's stated value if given; "
            "otherwise estimate from the activity type and duration (typical MET "
            "values) rather than leaving it blank"
        ),
    ] = None,
) -> str:
    """Log a workout/exercise session for today. Always try to populate
    duration_minutes and calories_burned — estimate calories_burned yourself
    when the user doesn't state it.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        today = user_local_date(user)
        session.add(
            DailyLog(
                user_id=user.id,
                log_type=LogType.WORKOUT,
                log_date=today,
                description=activity,
                duration_minutes=duration_minutes,
                calories_burned=calories_burned,
                source=EntrySource.USER_REPORTED,
            )
        )
        score = upsert_daily_score(session, user, today)
        session.commit()
        return _score_message(f"Logged workout: {activity}.", score, user)
    finally:
        session.close()


@tool
def log_metric(
    metric_name: Annotated[
        str,
        Field(
            description="Normalized lowercase metric key, e.g. 'weight', "
            "'steps', 'sleep_hours', 'heart_rate', 'body_fat_pct'. Use "
            "'water' for water intake in ml."
        ),
    ],
    value: Annotated[float, Field(description="Numeric value of the metric")],
    unit: Annotated[
        str | None,
        Field(description="Unit for the value, e.g. 'kg', 'steps', 'hours', 'bpm'"),
    ] = None,
) -> str:
    """Log a body/health metric for today (e.g. weight, steps, sleep,
    heart_rate). Use metric_name='water' for water intake in ml.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        today = user_local_date(user)
        name = metric_name.strip().lower()
        if name == "water":
            session.add(
                DailyLog(
                    user_id=user.id,
                    log_type=LogType.WATER,
                    log_date=today,
                    water_ml=value,
                    source=EntrySource.USER_REPORTED,
                )
            )
        else:
            session.add(
                DailyLog(
                    user_id=user.id,
                    log_type=LogType.METRIC,
                    log_date=today,
                    metric_name=name,
                    metric_value=value,
                    source=EntrySource.USER_REPORTED,
                )
            )
        score = upsert_daily_score(session, user, today)
        session.commit()
        return _score_message(
            f"Logged metric: {name}={value}{unit or ''}.", score, user
        )
    finally:
        session.close()

