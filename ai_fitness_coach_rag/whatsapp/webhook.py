"""Twilio WhatsApp inbound webhook: signature validation, payload parsing, idempotency, and reply dispatch."""

from __future__ import annotations

import threading
import time
import asyncio
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import PlainTextResponse
from twilio.request_validator import RequestValidator

from ai_fitness_coach_rag.agent.factory import get_orchestrator
from ai_fitness_coach_rag.agent.tools.onboarding_tools import normalize_phone_number
from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.observability.logger import get_logger
from ai_fitness_coach_rag.whatsapp.media_handlers import get_media_handler
from ai_fitness_coach_rag.whatsapp.twilio_client import get_twilio_client

logger = get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["whatsapp"])

_IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


@dataclass
class InboundMessage:
    """Normalized representation of an inbound Twilio WhatsApp payload."""

    message_sid: str
    from_number: str
    to_number: str
    body: str
    num_media: int
    media_urls: list[str] = field(default_factory=list)
    media_content_types: list[str] = field(default_factory=list)

    @property
    def is_media(self) -> bool:
        return self.num_media > 0


class _SeenMessageCache:
    """In-memory MessageSid dedupe store with TTL eviction.

    Interim implementation for Phase 5 scope — should move to a durable store
    (e.g. the future ConversationLog table) once the DB layer exists, so
    dedupe survives restarts and works across multiple worker processes.
    """

    def __init__(self, ttl_seconds: int = _IDEMPOTENCY_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def seen_before(self, message_sid: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if message_sid in self._seen:
                return True
            self._seen[message_sid] = now
            return False

    def _evict_expired(self, now: float) -> None:
        expired = [
            sid
            for sid, seen_at in self._seen.items()
            if now - seen_at > self._ttl_seconds
        ]
        for sid in expired:
            del self._seen[sid]


_seen_messages = _SeenMessageCache()


def _validate_signature(request: Request, form_params: dict[str, str]) -> None:
    twilio_settings = config["twilio"]
    if not twilio_settings["validate_signature"]:
        return

    signature = request.headers.get("X-Twilio-Signature", "")
    base_url = config["public_base_url"]
    url = f"{base_url}{request.url.path}" if base_url else str(request.url)

    validator = RequestValidator(twilio_settings["auth_token"])
    if not validator.validate(url, form_params, signature):
        logger.warning(
            "Rejected inbound webhook request with invalid X-Twilio-Signature"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Twilio signature"
        )


def _parse_inbound_message(form_params: dict[str, str]) -> InboundMessage:
    num_media = int(form_params.get("NumMedia", "0") or "0")
    media_urls = [
        form_params[f"MediaUrl{i}"]
        for i in range(num_media)
        if f"MediaUrl{i}" in form_params
    ]
    media_content_types = [
        form_params[f"MediaContentType{i}"]
        for i in range(num_media)
        if f"MediaContentType{i}" in form_params
    ]
    return InboundMessage(
        message_sid=form_params.get("MessageSid", ""),
        from_number=form_params.get("From", ""),
        to_number=form_params.get("To", ""),
        body=form_params.get("Body", ""),
        num_media=num_media,
        media_urls=media_urls,
        media_content_types=media_content_types,
    )


async def _build_reply_async(message: InboundMessage) -> str:
    """Route a message through the active agent orchestrator."""
    if message.is_media:
        content_type = (
            message.media_content_types[0] if message.media_content_types else ""
        )
        handler = get_media_handler(content_type)
        if handler is None:
            return "Thanks, I received your attachment. Processing it is coming soon!"

        transcript = await handler(message.media_urls[0], content_type)
        if not transcript:
            return "Sorry, I couldn't process that voice note. Could you try again or type it?"

        orchestrator = get_orchestrator()
        return await orchestrator.handle_message(message.from_number, transcript)

    if not message.body.strip():
        return "Sorry, I didn't catch a message. Could you try again?"

    orchestrator = get_orchestrator()
    return await orchestrator.handle_message(message.from_number, message.body)


def _build_reply(message: InboundMessage) -> str:
    """Synchronous compatibility wrapper for callers outside the HTTP path."""
    return asyncio.run(_build_reply_async(message))


@router.post("/twilio", response_class=PlainTextResponse)
async def twilio_webhook(request: Request) -> PlainTextResponse:
    """Twilio WhatsApp Sandbox inbound message webhook."""
    form = await request.form()
    form_params = {key: str(value) for key, value in form.items()}

    _validate_signature(request, form_params)

    message = _parse_inbound_message(form_params)
    if not message.message_sid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing MessageSid"
        )

    if _seen_messages.seen_before(message.message_sid):
        logger.info("Duplicate inbound message %s ignored", message.message_sid)
        return PlainTextResponse("", status_code=status.HTTP_200_OK)

    logger.info(
        "Inbound WhatsApp message %s from %s (media=%d)",
        message.message_sid,
        message.from_number,
        message.num_media,
    )

    reply_text = await _build_reply_async(message)
    get_twilio_client().send_text(to=message.from_number, body=reply_text)

    return PlainTextResponse("", status_code=status.HTTP_200_OK)
