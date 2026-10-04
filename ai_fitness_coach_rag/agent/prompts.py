"""Loader for LLM-facing prompt templates kept in prompts.json (not Python)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.json"


@lru_cache(maxsize=1)
def _load_prompts() -> dict[str, str | list[str]]:
    return json.loads(_PROMPTS_PATH.read_text(encoding="utf-8"))


def get_prompt(name: str, **kwargs: str) -> str:
    """Return the named prompt template, formatted with any given placeholders.

    Templates may be stored as a JSON array of strings (joined with spaces) so
    long prompts stay readable as multiple lines in prompts.json.
    """
    template = _load_prompts()[name]
    if isinstance(template, list):
        template = " ".join(template)
    return template.format(**kwargs) if kwargs else template
