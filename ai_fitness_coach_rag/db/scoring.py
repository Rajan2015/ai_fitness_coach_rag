"""Deterministic scoring/calculation functions — no LLM, no DB access, pure math."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from ai_fitness_coach_rag.db.models import Sex

KCAL_PER_KG_BODYFAT = 7700

ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: Sex) -> float:
    """Basal Metabolic Rate via the Mifflin-St Jeor equation."""
    if weight_kg <= 0 or height_cm <= 0 or age <= 0:
        raise ValueError("weight_kg, height_cm, and age must be positive")

    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if sex == Sex.MALE:
        return base + 5
    if sex == Sex.FEMALE:
        return base - 161
    raise ValueError(f"Unsupported sex: {sex}")


def calculate_tdee(bmr: float, activity_level: str) -> float:
    """Total Daily Energy Expenditure: BMR scaled by activity multiplier."""
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level)
    if multiplier is None:
        valid = ", ".join(ACTIVITY_MULTIPLIERS)
        raise ValueError(
            f"Unknown activity_level '{activity_level}', expected one of: {valid}"
        )
    return bmr * multiplier


def _pct_of_target_score(actual: float, target: float) -> float:
    """% of a target hit, capped at 100. Target must be positive."""
    if target <= 0:
        raise ValueError("target must be positive")
    return min(100.0, max(0.0, (actual / target) * 100))


def calorie_adherence_score(
    actual_calories: float, target_calories: float, tolerance_pct: float = 0.10
) -> float:
    """100 pts within tolerance band of target; decays linearly to 0 at 2x the tolerance's deviation."""
    if target_calories <= 0:
        raise ValueError("target_calories must be positive")
    deviation_pct = abs(actual_calories - target_calories) / target_calories
    if deviation_pct <= tolerance_pct:
        return 100.0
    decay_band = tolerance_pct  # extra deviation beyond tolerance needed to reach 0
    overshoot = deviation_pct - tolerance_pct
    return 100.0 * max(0.0, 1 - overshoot / decay_band)


def protein_score(
    actual_protein_g: float, weight_kg: float, target_g_per_kg: float = 1.8
) -> float:
    """% of a bodyweight-scaled protein target hit, capped at 100."""
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    return _pct_of_target_score(actual_protein_g, weight_kg * target_g_per_kg)


def activity_score(actual_steps: float, target_steps: float = 10000) -> float:
    """% of a daily step target hit, capped at 100."""
    return _pct_of_target_score(actual_steps, target_steps)


def water_score(actual_water_ml: float, target_water_ml: float = 2500) -> float:
    """% of a daily water intake target hit, capped at 100."""
    return _pct_of_target_score(actual_water_ml, target_water_ml)


def consistency_score(logged_days: list[bool]) -> float:
    """% of days in the given rolling window that had at least one log entry."""
    if not logged_days:
        raise ValueError("logged_days must not be empty")
    return (sum(logged_days) / len(logged_days)) * 100


def daily_score(
    calorie_score: float,
    protein_score: float,
    activity_score: float,
    water_score: float,
    consistency_score: float,
    weights: dict[str, float],
) -> float:
    """Weighted sum of the five sub-scores; weights must sum to 1.0."""
    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total_weight}")
    return (
        calorie_score * weights["calorie"]
        + protein_score * weights["protein"]
        + activity_score * weights["activity"]
        + water_score * weights["water"]
        + consistency_score * weights["consistency"]
    )


@dataclass
class GoalProjection:
    projected_date: datetime.date | None
    on_track: bool
    required_daily_delta_kcal: float
    actual_daily_delta_kcal: float


def project_goal_eta(
    current_weight_kg: float,
    target_weight_kg: float,
    target_date: datetime.date,
    daily_calorie_deltas: list[float],
    today: datetime.date,
) -> GoalProjection:
    """Project goal-achievability from a rolling window of actual (intake - TDEE) daily deltas."""
    if not daily_calorie_deltas:
        raise ValueError("daily_calorie_deltas must not be empty")
    days_remaining = (target_date - today).days
    if days_remaining <= 0:
        raise ValueError("target_date must be in the future relative to today")

    total_kcal_delta_needed = (
        target_weight_kg - current_weight_kg
    ) * KCAL_PER_KG_BODYFAT
    required_daily_delta_kcal = total_kcal_delta_needed / days_remaining
    actual_daily_delta_kcal = sum(daily_calorie_deltas) / len(daily_calorie_deltas)

    # Maintain goal: just check the actual delta stays within a small band of zero.
    if total_kcal_delta_needed == 0:
        on_track = abs(actual_daily_delta_kcal) <= 50
        return GoalProjection(
            target_date, on_track, required_daily_delta_kcal, actual_daily_delta_kcal
        )

    same_direction = (actual_daily_delta_kcal > 0) == (total_kcal_delta_needed > 0)
    if not same_direction or actual_daily_delta_kcal == 0:
        return GoalProjection(
            None, False, required_daily_delta_kcal, actual_daily_delta_kcal
        )

    projected_days = total_kcal_delta_needed / actual_daily_delta_kcal
    projected_date = today + datetime.timedelta(days=round(projected_days))
    on_track = projected_date <= target_date
    return GoalProjection(
        projected_date, on_track, required_daily_delta_kcal, actual_daily_delta_kcal
    )
