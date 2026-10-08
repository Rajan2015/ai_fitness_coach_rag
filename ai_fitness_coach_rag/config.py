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
    # Secrets never live in config.yaml — always sourced from the environment.
    database["url"] = os.environ.get("DATABASE_URL", "")

    qdrant = config.setdefault("qdrant", {})
    # Secrets never live in config.yaml — always sourced from the environment.
    qdrant["url"] = os.environ.get("QDRANT_URL", "http://localhost:6333")
    qdrant["api_key"] = os.environ.get("QDRANT_API_KEY", "")

    redis_config = config.setdefault("redis", {})
    redis_config["url"] = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_config.setdefault("otp_ttl_seconds", 300)
    redis_config.setdefault("otp_length", 6)
    redis_config.setdefault("max_sends_per_window", 5)
    redis_config.setdefault("send_window_seconds", 900)
    redis_config.setdefault("max_verify_attempts", 5)

    return config


config = load_config()
