"""LLM-based routing for inbound WhatsApp fitness messages."""

from __future__ import annotations

from enum import Enum

from ai_fitness_coach_rag.agent.prompts import get_prompt
from ai_fitness_coach_rag.llm.factory import get_llm


class Intent(str, Enum):
    LOG_FOOD = "log_food"
    LOG_WORKOUT = "log_workout"
    LOG_METRIC = "log_metric"
    ONBOARDING = "onboarding"
    QUERY_KNOWLEDGE = "query_knowledge"
    REQUEST_SUMMARY = "request_summary"
    REQUEST_PLAN = "request_plan"
    CONFIRM_PENDING = "confirm_pending"
    OFF_TOPIC = "off_topic"


def _contains_any(text: str, *terms: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _coerce_llm_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "content"):
        return str(value.content)
    if isinstance(value, list):
        return " ".join(_coerce_llm_text(item) for item in value)
    return str(value)


def _classify_with_llm(text: str) -> Intent | None:
    llm = get_llm("intent")
    if llm is None:
        return None

    prompt = get_prompt("intent_classifier", message=text)

    try:
        response = llm.invoke(prompt)
    except Exception:
        return None

    raw = _coerce_llm_text(response).strip().lower()
    if not raw:
        return None

    normalized = (
        raw.replace("intent:", "")
        .replace("answer:", "")
        .strip()
        .replace("-", "_")
        .replace(" ", "_")
    )

    for intent in Intent:
        if normalized == intent.value or normalized == intent.name.lower():
            return intent

    if normalized in {"logfood", "food"}:
        return Intent.LOG_FOOD
    if normalized in {"logworkout", "workout"}:
        return Intent.LOG_WORKOUT
    if normalized in {"logmetric", "metric"}:
        return Intent.LOG_METRIC
    return None


def route_message(text: str, *, pending_flow: str | None = None) -> Intent:
    """Classify a text message into a high-level fitness coach intent."""
    if pending_flow:
        return Intent.CONFIRM_PENDING

    normalized = (text or "").strip()
    if not normalized:
        return Intent.OFF_TOPIC

    llm_intent = _classify_with_llm(normalized)
    if llm_intent is not None:
        return llm_intent

    txt = normalized.lower()
    if _contains_any(
        txt,
        "ate ",
        "meal",
        "breakfast",
        "lunch",
        "dinner",
        "snack",
        "food",
        "calories",
        "protein",
        "egg",
        "toast",
        "rice",
        "dal",
        "roti",
    ):
        return Intent.LOG_FOOD

    if _contains_any(
        txt,
        "workout",
        "exercise",
        "training",
        "run",
        "lift",
        "gym",
        "pushup",
        "squat",
        "walked",
    ):
        return Intent.LOG_WORKOUT

    if _contains_any(
        txt,
        "steps",
        "weight",
        "water",
        "sleep",
        "heart rate",
        "metric",
        "today's stats",
    ):
        return Intent.LOG_METRIC

    if _contains_any(
        txt,
        "onboard",
        "profile",
        "setup",
        "goal",
        "weight goal",
        "age",
        "height",
        "sex",
        "diet",
        "dietary",
        "begin",
        "start",
    ):
        return Intent.ONBOARDING

    if _contains_any(
        txt,
        "summary",
        "report",
        "progress",
        "score",
        "how am i doing",
        "stats",
    ):
        return Intent.REQUEST_SUMMARY

    if _contains_any(
        txt,
        "plan",
        "meal plan",
        "workout plan",
        "routine",
        "program",
    ):
        return Intent.REQUEST_PLAN

    if _contains_any(
        txt,
        "what is",
        "how do i",
        "benefits",
        "nutrition",
        "fitness",
        "muscle",
        "protein",
        "recovery",
    ):
        return Intent.QUERY_KNOWLEDGE

    return Intent.OFF_TOPIC
