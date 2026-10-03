"""Graph state schema for the fitness coach message pipeline."""

from __future__ import annotations

from typing import TypedDict


class ConversationState(TypedDict, total=False):
    """Per-thread (phone) state persisted by the LangGraph SQLite checkpointer."""

    user_id: str
    text: str
    reply: str
    pending_flow: str | None
    last_intent: str
