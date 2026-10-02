"""Thin wrapper around the Twilio REST client for sending WhatsApp messages via the Sandbox."""

from __future__ import annotations

from functools import lru_cache

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.observability.logger import get_logger

logger = get_logger(__name__)


def _whatsapp_address(number: str) -> str:
    """Prefix a raw phone number with Twilio's required 'whatsapp:' scheme if missing."""
    return number if number.startswith("whatsapp:") else f"whatsapp:{number}"


class TwilioClient:
    """Sends outbound WhatsApp messages (text and media) through Twilio."""

    def __init__(self, client: Client | None = None) -> None:
        twilio_settings = config["twilio"]
        self._from_number = _whatsapp_address(twilio_settings["whatsapp_number"])
        self._client = client or Client(
            twilio_settings["account_sid"], twilio_settings["auth_token"]
        )

    def send_text(self, to: str, body: str) -> str:
        """Send a plain text WhatsApp message. Returns the Twilio MessageSid."""
        try:
            message = self._client.messages.create(
                from_=self._from_number,
                to=_whatsapp_address(to),
                body=body,
            )
        except TwilioRestException:
            logger.exception("Failed to send WhatsApp text message to %s", to)
            raise
        return message.sid

    def send_media(self, to: str, body: str, media_url: str) -> str:
        """Send a WhatsApp message with a media attachment. Returns the Twilio MessageSid."""
        try:
            message = self._client.messages.create(
                from_=self._from_number,
                to=_whatsapp_address(to),
                body=body,
                media_url=[media_url],
            )
        except TwilioRestException:
            logger.exception("Failed to send WhatsApp media message to %s", to)
            raise
        return message.sid


@lru_cache(maxsize=1)
def get_twilio_client() -> TwilioClient:
    return TwilioClient()
