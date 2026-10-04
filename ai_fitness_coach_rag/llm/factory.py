"""Factory for LLM clients used by the fitness coach agent."""

from __future__ import annotations

import os
from typing import Any

from ai_fitness_coach_rag.config import config


class _FallbackLLM:
    """Graceful no-op implementation when no provider credentials are configured."""

    def __init__(self, flow: str | None = None) -> None:
        self.flow = flow

    def invoke(self, *args: Any, **kwargs: Any) -> str:
        return ""


def _resolve_model_name(flow: str | None = None) -> str:
    llm_config = config.get("llm", {})
    model_map = llm_config.get("models", {}) or {}
    default_model = llm_config.get("default_model") or llm_config.get("model")

    flow_key = (flow or "default").strip().lower()
    if flow_key in model_map:
        return model_map[flow_key]

    return model_map.get("default") or default_model or "gpt-4o-mini"


def get_llm(flow: str | None = None) -> _FallbackLLM | Any:
    """Return the configured model for the active flow, or a safe fallback."""
    llm_config = config.get("llm", {})
    provider = (
        os.getenv("LLM_PROVIDER") or llm_config.get("provider") or "openai"
    ).lower()
    model = (
        os.getenv(f"LLM_{(flow or 'default').upper()}_MODEL")
        or os.getenv("LLM_MODEL")
        or _resolve_model_name(flow)
    )
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        return _FallbackLLM(flow=flow)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(model=model, temperature=0)
        except Exception:
            return _FallbackLLM(flow=flow)

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(model=model, temperature=0)
        except Exception:
            return _FallbackLLM(flow=flow)

    return _FallbackLLM(flow=flow)
