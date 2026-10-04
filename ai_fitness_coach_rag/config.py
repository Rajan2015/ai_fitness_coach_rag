import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_YAML_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _env_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in ("false", "0", "no", "")


def load_config() -> dict:
    """Load config.yaml and layer in secrets/overrides from environment variables."""
    config: dict = yaml.safe_load(_CONFIG_YAML_PATH.read_text()) or {}

    # Secrets never live in config.yaml — always sourced from the environment.
    twilio = config.setdefault("twilio", {})
    twilio["account_sid"] = os.environ.get("TWILIO_ACCOUNT_SID", "")
    twilio["auth_token"] = os.environ.get("TWILIO_AUTH_TOKEN", "")
    twilio["whatsapp_number"] = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
    twilio["validate_signature"] = _env_bool(
        os.environ.get("TWILIO_VALIDATE_SIGNATURE"),
        twilio.get("validate_signature", True),
    )

    config["public_base_url"] = os.environ.get(
        "PUBLIC_BASE_URL", config.get("public_base_url", "")
    ).rstrip("/")
    config["log_level"] = os.environ.get("LOG_LEVEL", config.get("log_level", "INFO"))

    database = config.setdefault("database", {})
    database["path"] = os.environ.get(
        "DATABASE_PATH", database.get("path", "./data/fitness_coach.db")
    )

    qdrant = config.setdefault("qdrant", {})
    # Secrets never live in config.yaml — always sourced from the environment.
    qdrant["url"] = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant["api_key"] = os.environ.get("QDRANT_API_KEY", "")

    return config


config = load_config()
