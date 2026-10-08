"""Database-backed daily score calculation and upsert operations."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.db.models import DailyLog, DeviceMetric, LogType, Score, User
from ai_fitness_coach_rag.db.scoring import (
    activity_score,
    calorie_adherence_score,
    calculate_bmr,
    calculate_tdee,
    consistency_score,
    daily_score,
    protein_score,
    water_score,
)


def user_local_date(user: User) -> datetime.date:
    """Return today's date in the user's configured timezone."""
    try:
        timezone = ZoneInfo(user.timezone or "UTC")
    except Exception:
        timezone = ZoneInfo("UTC")
    return datetime.datetime.now(timezone).date()


def daily_targets(user: User) -> tuple[float | None, float | None]:
    """Return maintenance calories and protein grams for a complete profile."""
    if (
        user.weight_kg is None
        or user.height_cm is None
        or user.age is None
        or user.sex is None
        or user.activity_level is None
    ):
        return None, None

    bmr = calculate_bmr(user.weight_kg, user.height_cm, user.age, user.sex)
    maintenance_calories = calculate_tdee(bmr, user.activity_level)
    protein_target = user.weight_kg * float(
        config.get("scoring", {}).get("protein_target_g_per_kg", 1.8)
    )
    return maintenance_calories, protein_target


def upsert_daily_score(
    session: Session, user: User, score_date: datetime.date
) -> Score:
    """Recalculate one user's score for a date and add/update it in the session."""
    session.flush()
    scoring_config = config.get("scoring", {})
    window_days = int(scoring_config.get("consistency_window_days", 7))
    window_start = score_date - datetime.timedelta(days=window_days - 1)

    logs = (
        session.query(DailyLog)
        .filter(
            DailyLog.user_id == user.id,
            DailyLog.log_date == score_date,
        )
        .all()
    )
    calories = sum(log.calories or 0.0 for log in logs if log.log_type == LogType.FOOD)
    protein = sum(log.protein_g or 0.0 for log in logs if log.log_type == LogType.FOOD)
    water = sum(log.water_ml or 0.0 for log in logs if log.log_type == LogType.WATER)

    logged_steps = [
        log.metric_value
        for log in logs
        if log.log_type == LogType.METRIC
        and log.metric_name == "steps"
        and log.metric_value is not None
    ]
    device_steps = [
        metric.steps
        for metric in session.query(DeviceMetric).filter(
            DeviceMetric.user_id == user.id,
            DeviceMetric.metric_date == score_date,
        )
        if metric.steps is not None
    ]
    steps = max([*logged_steps, *device_steps], default=0.0)

    logged_dates = {
        row[0]
        for row in session.query(DailyLog.log_date)
        .filter(
            DailyLog.user_id == user.id,
            DailyLog.log_date >= window_start,
            DailyLog.log_date <= score_date,
        )
        .distinct()
    }
    consistency = consistency_score(
        [window_start + datetime.timedelta(days=offset) in logged_dates for offset in range(window_days)]
    )

    calorie_target, protein_target = daily_targets(user)
    calorie = (
        calorie_adherence_score(
            calories,
            calorie_target,
            float(scoring_config.get("calorie_tolerance_pct", 0.10)),
        )
        if calorie_target is not None
        else 0.0
    )
    protein_value = (
        protein_score(
            protein,
            user.weight_kg,
            float(scoring_config.get("protein_target_g_per_kg", 1.8)),
        )
        if protein_target is not None and user.weight_kg is not None
        else 0.0
    )
    activity = activity_score(steps, float(scoring_config.get("steps_target", 10000)))
    water_value = water_score(
        water, float(scoring_config.get("water_target_ml", 2500))
    )
    weights = dict(scoring_config.get("weights", {}))
    overall = daily_score(
        calorie,
        protein_value,
        activity,
        water_value,
        consistency,
        weights,
    )

    score = (
        session.query(Score)
        .filter(Score.user_id == user.id, Score.score_date == score_date)
        .one_or_none()
    )
    if score is None:
        score = Score(user_id=user.id, score_date=score_date)
        session.add(score)
    score.overall_score = overall
    score.calorie_score = calorie
    score.protein_score = protein_value
    score.activity_score = activity
    score.water_score = water_value
    score.consistency_score = consistency
    return score