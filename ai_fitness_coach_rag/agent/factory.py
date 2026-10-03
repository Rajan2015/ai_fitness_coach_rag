"""Factory helpers for creating the fitness coach agent runtime."""

from __future__ import annotations

from ai_fitness_coach_rag.agent.orchestrator import AgentOrchestrator

_default_orchestrator: AgentOrchestrator | None = None


def create_orchestrator() -> AgentOrchestrator:
    """Create a fresh agent orchestrator instance."""
    return AgentOrchestrator()


def get_orchestrator() -> AgentOrchestrator:
    """Return a shared default orchestrator for request handling."""
    global _default_orchestrator
    if _default_orchestrator is None:
        _default_orchestrator = AgentOrchestrator()
    return _default_orchestrator
