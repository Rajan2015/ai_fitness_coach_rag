"""Media-type-specific handlers that turn WhatsApp attachments into agent-ready text.

New attachment types (e.g. food images) plug in by registering a handler here —
webhook.py stays a thin dispatcher and never grows per-media-type branches.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from ai_fitness_coach_rag.llm.factory import get_stt, get_stt_translate_model
from ai_fitness_coach_rag.observability.logger import get_logger
from ai_fitness_coach_rag.whatsapp.twilio_client import get_twilio_client

logger = get_logger(__name__)

# (media_url, content_type) -> text to feed the orchestrator, or None on failure.
MediaHandler = Callable[[str, str], Awaitable[str | None]]


def _translate_to_english(client: Any, audio_bytes: bytes, content_type: str) -> str:
    extension = content_type.split("/")[-1].split(";")[0] or "ogg"
    response = client.audio.translations.create(
        model=get_stt_translate_model(),
        file=(f"voice.{extension}", audio_bytes, content_type),
    )
    return response.text


async def handle_voice_note(media_url: str, content_type: str) -> str | None:
    """Download a WhatsApp voice note and translate it (any language) to English text."""
    try:
        audio_bytes = get_twilio_client().download_media(media_url)
    except Exception:
        logger.exception("Failed to download voice note media")
        return None

    client = get_stt()
    if client is None:
        logger.warning("STT not configured (missing OPENAI_API_KEY); skipping transcription")
        return None

    try:
        transcript = _translate_to_english(client, audio_bytes, content_type)
    except Exception:
        logger.exception("Failed to transcribe voice note")
        return None

    return transcript.strip() or None


# Keyed by content-type prefix so e.g. "audio/ogg" and "audio/mpeg" share one handler.
_HANDLERS: dict[str, MediaHandler] = {
    "audio/": handle_voice_note,
}


def get_media_handler(content_type: str) -> MediaHandler | None:
    """Return the handler registered for this content type's prefix, if any."""
    for prefix, handler in _HANDLERS.items():
        if content_type.startswith(prefix):
            return handler
    return None
