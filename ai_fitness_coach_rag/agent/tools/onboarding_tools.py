"""Minimal onboarding flow: new-user detection and slot-by-slot profile capture."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ai_fitness_coach_rag.db.models import GoalType, Sex, User


def normalize_phone_number(phone_number: str) -> str:
    """Canonicalize any input (whatsapp: scheme, spacing, trunk 0, bare 10-digit) to +91XXXXXXXXXX."""
    digits = re.sub(r"\D", "", phone_number)
    if digits.startswith("91") and len(digits) == 12:
        national = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        national = digits[1:]
    elif len(digits) == 10:
        national = digits
    else:
        raise ValueError(f"Unsupported Indian phone number: {phone_number!r}")
    return f"+91{national}"


def hash_phone(phone_number: str) -> str:
    """Stable, non-reversible user id derived from the normalized phone number."""
    return hashlib.sha256(normalize_phone_number(phone_number).encode("utf-8")).hexdigest()


def get_or_create_user(session: Session, phone_number: str) -> tuple[User, bool]:
    """Return the user for this phone number, creating a blank profile if new."""
    normalized = normalize_phone_number(phone_number)
    phone_hash = hash_phone(normalized)
    user = session.query(User).filter_by(phone_hash=phone_hash).one_or_none()
    if user is not None:
        return user, False

    user = User(phone_hash=phone_hash, phone_number=normalized)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user, True


ACTIVITY_LEVELS = ["sedentary", "light", "moderate", "active", "very_active"]


def _parse_age(text: str) -> int | None:
    match = re.search(r"\d{1,3}", text)
    if not match:
        return None
    age = int(match.group())
    return age if 10 <= age <= 100 else None


def _parse_sex(text: str) -> Sex | None:
    lowered = text.strip().lower()
    if lowered == "1":
        return Sex.MALE
    if lowered == "2":
        return Sex.FEMALE
    if lowered in {"m", "male"}:
        return Sex.MALE
    if lowered in {"f", "female"}:
        return Sex.FEMALE
    return None


def _parse_height_cm(text: str) -> float | None:
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None
    value = float(match.group())
    if value < 10:  # e.g. "1.75" meters
        value *= 100
    return value if 100 <= value <= 250 else None


def _parse_weight_kg(text: str) -> float | None:
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None
    value = float(match.group())
    return value if 20 <= value <= 300 else None


def _parse_activity_level(text: str) -> str | None:
    lowered = text.strip().lower().replace(" ", "_").replace("-", "_")
    numbered = {
        "1": "sedentary",
        "2": "light",
        "3": "moderate",
        "4": "active",
        "5": "very_active",
    }
    if lowered in numbered:
        return numbered[lowered]
    for level in ACTIVITY_LEVELS:
        if level in lowered:
            return level
    return None


def _parse_goal_type(text: str) -> GoalType | None:
    lowered = text.strip().lower()
    numbered = {"1": GoalType.LOSE, "2": GoalType.GAIN, "3": GoalType.MAINTAIN}
    if lowered in numbered:
        return numbered[lowered]
    if any(term in lowered for term in ("lose", "cut", "fat loss", "weight loss")):
        return GoalType.LOSE
    if any(term in lowered for term in ("gain", "bulk", "muscle")):
        return GoalType.GAIN
    if "maintain" in lowered or "stay" in lowered:
        return GoalType.MAINTAIN
    return None


@dataclass(frozen=True)
class OnboardingSlot:
    field: str
    prompt: str
    parser: Callable[[str], object | None]
    error: str


ONBOARDING_SLOTS: list[OnboardingSlot] = [
    OnboardingSlot(
        "age",
        "First, how old are you?",
        _parse_age,
        "Please share your age as a number (10-100).",
    ),
    OnboardingSlot(
        "sex",
        "What's your sex? Reply 1 for male or 2 for female.",
        _parse_sex,
        "Please reply with 1 (male) or 2 (female).",
    ),
    OnboardingSlot(
        "height_cm",
        "What's your height? (e.g. 175 cm or 1.75 m)",
        _parse_height_cm,
        "Please share your height in cm (e.g. 175).",
    ),
    OnboardingSlot(
        "weight_kg",
        "What's your current weight in kg?",
        _parse_weight_kg,
        "Please share your weight in kg (e.g. 70).",
    ),
    OnboardingSlot(
        "activity_level",
        "How active are you? Reply 1 sedentary, 2 light, 3 moderate, 4 active, or 5 very active.",
        _parse_activity_level,
        "Please reply with 1, 2, 3, 4, or 5.",
    ),
    OnboardingSlot(
        "goal_type",
        "What's your main goal? Reply 1 lose weight, 2 gain muscle, or 3 maintain.",
        _parse_goal_type,
        "Please reply with 1 (lose), 2 (gain), or 3 (maintain).",
    ),
]


def next_onboarding_slot(user: User) -> OnboardingSlot | None:
    """Return the first unanswered onboarding slot, or None if complete."""
    for slot in ONBOARDING_SLOTS:
        if getattr(user, slot.field) is None:
            return slot
    return None


def apply_onboarding_answer(
    session: Session, user: User, slot: OnboardingSlot, text: str
) -> bool:
    """Parse and store the answer for one onboarding slot. Returns False on parse failure."""
    value = slot.parser(text)
    if value is None:
        return False
    setattr(user, slot.field, value)
    if next_onboarding_slot(user) is None:
        user.onboarding_complete = True
    session.commit()
    return True


def onboarding_welcome_message() -> str:
    return (
        "Welcome! Let's set up your profile so I can personalize your coaching. "
        "I'll ask a few quick questions."
    )
