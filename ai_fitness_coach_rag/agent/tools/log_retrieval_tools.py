"""DB-log retrieval tool bound to the main tool-calling agent.

This only fetches raw rows — the main agent narrates them itself (same
retrieve-then-let-the-LLM-reason pattern as `nutrition_tools.lookup_nutrition`),
so no separate classifier or narration LLM call is needed for summary requests.
"""

from __future__ import annotations

import datetime
from typing import Literal

from langchain_core.tools import tool
from langgraph.config import get_config

from ai_fitness_coach_rag.agent.tools.onboarding_tools import get_or_create_user
from ai_fitness_coach_rag.db.models import DailyLog, LogType
from ai_fitness_coach_rag.db.session import SessionLocal


def _current_user_id() -> str:
    """Thread id == hashed-phone user id, set by orchestrator's thread_config()."""
    return get_config()["configurable"]["thread_id"]


def get_recent_logs(user_id: str, log_type: str = "all", days: int = 1) -> list[dict]:
    """Read-only fetch of a user's logged entries; no summarization happens here."""
    session = SessionLocal()
    try:
        user, _ = get_or_create_user(session, user_id)
        since = datetime.date.today() - datetime.timedelta(days=days - 1)
        query = session.query(DailyLog).filter(
            DailyLog.user_id == user.id, DailyLog.log_date >= since
        )
        if log_type != "all":
            query = query.filter(DailyLog.log_type == LogType(log_type))
        rows = query.order_by(DailyLog.log_date, DailyLog.id).all()
        return [
            {
                "date": row.log_date.isoformat(),
                "type": row.log_type.value,
                "description": row.description,
                "quantity": row.quantity,
                "calories": row.calories,
                "protein_g": row.protein_g,
                "carbs_g": row.carbs_g,
                "fat_g": row.fat_g,
                "duration_minutes": row.duration_minutes,
                "calories_burned": row.calories_burned,
                "metric_name": row.metric_name,
                "metric_value": row.metric_value,
                "water_ml": row.water_ml,
            }
            for row in rows
        ]
    finally:
        session.close()


@tool
def get_fitness_logs(
    log_type: Literal["all", "food", "workout", "metric", "water"] = "all",
    days: int = 1,
) -> list[dict]:
    """Fetch the user's logged fitness entries so you can summarize their
    progress. Use log_type to narrow to one category, and days=7 for a
    weekly summary (days=1 for today only). Narrate the returned entries
    yourself — do not invent entries not present in the result.
    """
    return get_recent_logs(_current_user_id(), log_type, days)
