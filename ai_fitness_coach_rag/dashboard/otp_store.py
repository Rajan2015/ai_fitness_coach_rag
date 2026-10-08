"""Redis-backed OTP generation, delivery, verification, and rate limiting for dashboard login."""

from __future__ import annotations

import secrets
from functools import lru_cache

import redis

from ai_fitness_coach_rag.agent.tools.onboarding_tools import hash_phone
from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.db.models import User
from ai_fitness_coach_rag.db.session import SessionLocal
from ai_fitness_coach_rag.observability.logger import get_logger
from ai_fitness_coach_rag.whatsapp.twilio_client import get_twilio_client

logger = get_logger(__name__)

_OTP_TTL_SECONDS = 300
_OTP_LENGTH = 6
_MAX_SENDS_PER_WINDOW = 5
_SEND_WINDOW_SECONDS = 900
_MAX_VERIFY_ATTEMPTS = 5


class OtpRateLimitError(Exception):
    """Raised when a phone number has requested too many OTPs in the rate-limit window."""


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(config["redis"]["url"], decode_responses=True)


def _otp_key(phone_hash: str) -> str:
    return f"dashboard:otp:{phone_hash}"


def _attempts_key(phone_hash: str) -> str:
    return f"dashboard:otp:attempts:{phone_hash}"


def _send_count_key(phone_hash: str) -> str:
    return f"dashboard:otp:sends:{phone_hash}"


def generate_and_send_otp(phone_number: str, redis_client: redis.Redis | None = None) -> None:
    """Text a one-time code to an already-onboarded WhatsApp user; silently no-ops for unknown numbers."""
    client = redis_client or get_redis_client()
    phone_hash = hash_phone(phone_number)

    send_key = _send_count_key(phone_hash)
    sends = client.incr(send_key)
    if sends == 1:
        client.expire(send_key, _SEND_WINDOW_SECONDS)
    if sends > _MAX_SENDS_PER_WINDOW:
        raise OtpRateLimitError("Too many OTP requests for this number, try again later.")

    session = SessionLocal()
    try:
        user = session.query(User).filter_by(phone_hash=phone_hash).one_or_none()
    finally:
        session.close()
    if user is None:
        # Never confirm/deny registration to the caller — avoid user enumeration.
        logger.info("OTP requested for an unregistered phone number")
        return

    code = "".join(secrets.choice("0123456789") for _ in range(_OTP_LENGTH))
    client.set(_otp_key(phone_hash), code, ex=_OTP_TTL_SECONDS)
    client.delete(_attempts_key(phone_hash))

    get_twilio_client().send_text(
        phone_number,
        f"Your fitness coach dashboard login code is {code}. It expires in 5 minutes.",
    )


def verify_otp(
    phone_number: str, code: str, redis_client: redis.Redis | None = None
) -> dict | None:
    """Check a submitted code against the stored OTP; returns basic user info on success."""
    client = redis_client or get_redis_client()
    phone_hash = hash_phone(phone_number)

    attempts_key = _attempts_key(phone_hash)
    attempts = client.incr(attempts_key)
    if attempts == 1:
        client.expire(attempts_key, _OTP_TTL_SECONDS)
    if attempts > _MAX_VERIFY_ATTEMPTS:
        return None

    stored_code = client.get(_otp_key(phone_hash))
    if stored_code is None or not secrets.compare_digest(stored_code, code):
        return None

    client.delete(_otp_key(phone_hash))
    client.delete(attempts_key)

    session = SessionLocal()
    try:
        user = session.query(User).filter_by(phone_hash=phone_hash).one_or_none()
        if user is None:
            return None
        return {
            "phone_hash": user.phone_hash,
            "name": user.name,
            "onboarding_complete": user.onboarding_complete,
        }
    finally:
        session.close()
