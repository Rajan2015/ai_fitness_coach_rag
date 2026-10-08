"""SQLAlchemy 2.0 models: User, DailyLog, DeviceMetric, Score, Plan, ConversationLog."""

from __future__ import annotations

import datetime
import enum
from functools import partial

from sqlalchemy import Enum as _Enum
from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Store enums as plain VARCHAR under Postgres too (skip native CREATE TYPE DDL).
SAEnum = partial(_Enum, native_enum=False)


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class GoalType(str, enum.Enum):
    LOSE = "lose"
    GAIN = "gain"
    MAINTAIN = "maintain"


class Sex(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"


class UnitSystem(str, enum.Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class LogType(str, enum.Enum):
    FOOD = "food"
    WORKOUT = "workout"
    METRIC = "metric"
    WATER = "water"


class EntrySource(str, enum.Enum):
    DATABASE = "database"
    ESTIMATED = "estimated"
    USER_REPORTED = "user_reported"


class PlanType(str, enum.Enum):
    MEAL = "meal"
    WORKOUT = "workout"


class Direction(str, enum.Enum):
    IN = "in"
    OUT = "out"


class Modality(str, enum.Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"


class User(Base):
    """Profile captured during onboarding; phone_hash is the stable internal user_id."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    phone_number: Mapped[str] = mapped_column(String(32))

    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[Sex | None] = mapped_column(SAEnum(Sex), nullable=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dietary_preference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)

    unit_system: Mapped[UnitSystem] = mapped_column(
        SAEnum(UnitSystem), default=UnitSystem.METRIC
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    goal_type: Mapped[GoalType | None] = mapped_column(SAEnum(GoalType), nullable=True)
    target_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_date: Mapped[datetime.date | None] = mapped_column(nullable=True)

    onboarding_complete: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=_utcnow, onupdate=_utcnow
    )


class DailyLog(Base):
    """A single logged food/workout/metric/water entry for a user."""

    __tablename__ = "daily_logs"
    __table_args__ = (Index("ix_daily_logs_user_date", "user_id", "log_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    log_type: Mapped[LogType] = mapped_column(SAEnum(LogType))
    log_date: Mapped[datetime.date] = mapped_column()

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[str | None] = mapped_column(String(64), nullable=True)

    calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)

    duration_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    calories_burned: Mapped[float | None] = mapped_column(Float, nullable=True)

    water_ml: Mapped[float | None] = mapped_column(Float, nullable=True)
    metric_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metric_value: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[EntrySource] = mapped_column(
        SAEnum(EntrySource), default=EntrySource.USER_REPORTED
    )

    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)


class DeviceMetric(Base):
    """Simulated wearable data point (steps, heart rate, sleep) for a user/date."""

    __tablename__ = "device_metrics"
    __table_args__ = (Index("ix_device_metrics_user_date", "user_id", "metric_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    metric_date: Mapped[datetime.date] = mapped_column()

    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_calories: Mapped[float | None] = mapped_column(Float, nullable=True)
    resting_heart_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)

    source: Mapped[str] = mapped_column(String(32), default="simulated")
    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)


class Score(Base):
    """Computed daily score breakdown, derived from DailyLog/DeviceMetric via scoring.py."""

    __tablename__ = "scores"
    __table_args__ = (
        Index("ix_scores_user_date", "user_id", "score_date", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    score_date: Mapped[datetime.date] = mapped_column()

    overall_score: Mapped[float] = mapped_column(Float)
    calorie_score: Mapped[float] = mapped_column(Float)
    protein_score: Mapped[float] = mapped_column(Float)
    activity_score: Mapped[float] = mapped_column(Float)
    water_score: Mapped[float] = mapped_column(Float)
    consistency_score: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)


class Plan(Base):
    """A generated meal or workout plan snapshot for a user."""

    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    plan_type: Mapped[PlanType] = mapped_column(SAEnum(PlanType))
    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)


class ConversationLog(Base):
    """Durable, append-only raw record of every inbound/outbound WhatsApp message."""

    __tablename__ = "conversation_logs"
    __table_args__ = (
        Index("ix_conversation_logs_phone_hash_created_at", "phone_hash", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone_hash: Mapped[str] = mapped_column(String(64))
    direction: Mapped[Direction] = mapped_column(SAEnum(Direction))
    modality: Mapped[Modality] = mapped_column(SAEnum(Modality))
    raw_text: Mapped[str] = mapped_column(Text)
    message_sid: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(default=_utcnow)
