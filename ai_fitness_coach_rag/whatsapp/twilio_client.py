"""Thin wrapper around the Twilio REST client for sending WhatsApp messages via the Sandbox."""

from __future__ import annotations

from functools import lru_cache

import requests
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
        self._account_sid = twilio_settings["account_sid"]
        self._auth_token = twilio_settings["auth_token"]
        self._from_number = _whatsapp_address(twilio_settings["whatsapp_number"])
        self._client = client or Client(self._account_sid, self._auth_token)

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

    def download_media(self, media_url: str) -> bytes:
        """Download a Twilio media attachment, which requires account auth to fetch."""
        response = requests.get(
            media_url, auth=(self._account_sid, self._auth_token), timeout=30
        )
        response.raise_for_status()
        return response.content


@lru_cache(maxsize=1)
def get_twilio_client() -> TwilioClient:
    return TwilioClient()
