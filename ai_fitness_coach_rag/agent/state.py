"""Runtime state for the fitness coach message pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

from ai_fitness_coach_rag.agent.router import Intent


@dataclass
class AgentState:
    """Tracks pending flows and most recent intent for the active user."""

    last_intent: Intent | None = None
    pending_flow: str | None = None
    pending_payload: dict[str, object] = field(default_factory=dict)
    user_id: str | None = None
