"""Deterministic DailyLog tool functions bound to the tool-calling agent.

Each tool only persists values the agent has already decided on (e.g. via
`nutrition_tools.lookup_nutrition`) — no extraction or estimation happens
here. Confirmation-before-save is handled by `HumanInTheLoopMiddleware`
pausing the graph before these tools execute (see orchestrator.py), backed by
the LangGraph `AsyncSqliteSaver` checkpointer. No separate pending-state table.
"""

from __future__ import annotations

import datetime
from typing import Literal

from langchain_core.tools import tool
from langgraph.config import get_config
from pydantic import BaseModel, Field

from ai_fitness_coach_rag.agent.tools.onboarding_tools import get_or_create_user
from ai_fitness_coach_rag.db.models import DailyLog, EntrySource, LogType
from ai_fitness_coach_rag.db.session import SessionLocal


def _current_user_id() -> str:
    """Thread id == hashed-phone user id, set by orchestrator's thread_config()."""
    return get_config()["configurable"]["thread_id"]


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
        today = datetime.date.today()
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
        session.commit()
        return f"Logged {len(entries)} food item(s)."
    finally:
        session.close()


@tool
def log_workout(
    activity: str,
    duration_minutes: float | None = None,
    calories_burned: float | None = None,
) -> str:
    """Log a workout/exercise session for today."""
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        session.add(
            DailyLog(
                user_id=user.id,
                log_type=LogType.WORKOUT,
                log_date=datetime.date.today(),
                description=activity,
                duration_minutes=duration_minutes,
                calories_burned=calories_burned,
                source=EntrySource.USER_REPORTED,
            )
        )
        session.commit()
        return f"Logged workout: {activity}."
    finally:
        session.close()


@tool
def log_metric(metric_name: str, value: float, unit: str | None = None) -> str:
    """Log a body/health metric for today (e.g. weight, steps, sleep,
    heart_rate). Use metric_name='water' for water intake in ml.
    """
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, _current_user_id())
        today = datetime.date.today()
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
        session.commit()
        return f"Logged metric: {name}={value}{unit or ''}."
    finally:
        session.close()

