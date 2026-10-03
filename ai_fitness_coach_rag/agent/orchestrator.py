"""Minimal orchestration layer that routes inbound messages to agent intents.

Conversation state (pending_flow, last_intent) is persisted per-thread
(thread_id=phone) by a LangGraph SQLite checkpointer instead of an in-memory
dict, so state survives process restarts and is inspectable for debugging.
"""

from __future__ import annotations

import asyncio

from langchain.agents import create_agent

from ai_fitness_coach_rag.agent.state import ConversationState
from ai_fitness_coach_rag.agent.tools.onboarding_tools import (
    apply_onboarding_answer,
    get_or_create_user,
    next_onboarding_slot,
    onboarding_welcome_message,
)
from ai_fitness_coach_rag.db.session import SessionLocal
from ai_fitness_coach_rag.llm.factory import get_llm
from ai_fitness_coach_rag.memory.short_term import (
    get_checkpointer,
    get_summarization_middleware,
    thread_config,
)


def _handle_onboarding(user_id: str, text: str) -> tuple[str | None, str | None]:
    """Return (reply, pending_flow). Reply is None once the user is onboarded."""
    session = SessionLocal()
    try:
        user, is_new = get_or_create_user(session, user_id)

        if is_new:
            slot = next_onboarding_slot(user)
            assert slot is not None  # a brand-new profile always has slots left
            return f"{onboarding_welcome_message()} {slot.prompt}", "onboarding"

        if user.onboarding_complete:
            return None, None

        slot = next_onboarding_slot(user)
        if slot is None:
            return None, None

        if not apply_onboarding_answer(session, user, slot, text):
            return slot.error, "onboarding"

        next_slot = next_onboarding_slot(user)
        if next_slot is not None:
            return next_slot.prompt, "onboarding"

        return (
            "Thanks! Your profile is all set. You can now log food, workouts, "
            "and metrics, or ask me anything fitness-related."
        ), None
    finally:
        session.close()


class AgentOrchestrator:
    """Agent facade using course-style memory and summarization."""

    def __init__(self) -> None:
        self._agent = None
        self._agent_loop: asyncio.AbstractEventLoop | None = None

    async def _get_agent(self):
        """Create the LangChain agent once for the active event loop."""
        loop = asyncio.get_running_loop()
        if self._agent is None or self._agent_loop is not loop:
            self._agent = create_agent(
                model=get_llm(),
                tools=[],
                middleware=[get_summarization_middleware()],
                checkpointer=await get_checkpointer(),
            )
            self._agent_loop = loop
        return self._agent

    async def handle_message(self, user_id: str, text: str) -> str:
        onboarding_reply, _ = _handle_onboarding(user_id, text)
        if onboarding_reply is not None:
            return onboarding_reply

        agent = await self._get_agent()
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": text}]},
            config=thread_config(user_id),
        )
        return result["messages"][-1].content

    async def get_state(self, user_id: str) -> ConversationState:
        """Return the persisted conversation state for one user (debugging/tests)."""
        agent = await self._get_agent()
        snapshot = await agent.aget_state(thread_config(user_id))
        return snapshot.values


async def handle_message(user_id: str, text: str) -> str:
    """Convenience wrapper for callers that do not need a long-lived orchestrator."""
    orchestrator = AgentOrchestrator()
    return await orchestrator.handle_message(user_id, text)
