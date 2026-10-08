"""FastAPI routes for the web dashboard's WhatsApp-OTP login (auth-only; no data endpoints)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ai_fitness_coach_rag.dashboard.otp_store import (
    OtpRateLimitError,
    generate_and_send_otp,
    verify_otp,
)
from ai_fitness_coach_rag.observability.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/dashboard/auth", tags=["dashboard-auth"])


class RequestOtpBody(BaseModel):
    phone_number: str


class VerifyOtpBody(BaseModel):
    phone_number: str
    code: str


class VerifyOtpResponse(BaseModel):
    phone_hash: str
    name: str | None
    onboarding_complete: bool


@router.post("/request-otp")
def request_otp(body: RequestOtpBody) -> dict[str, str]:
    """Always returns the same generic message, regardless of whether the number is registered."""
    try:
        generate_and_send_otp(body.phone_number)
    except OtpRateLimitError:
        logger.warning("OTP rate limit hit for a dashboard login attempt")
    return {"message": "If this number is registered, a login code has been sent."}


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp_endpoint(body: VerifyOtpBody) -> dict:
    user_info = verify_otp(body.phone_number, body.code)
    if user_info is None:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")
    return user_info
