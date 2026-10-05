"""Minimal orchestration layer that drives the main tool-calling agent.

Conversation state (chat history + pending tool-call confirmations) is
persisted per-thread (thread_id=phone) by a LangGraph SQLite checkpointer, so
state survives process restarts and is inspectable for debugging. Food/
workout/metric logging is confirmed via `HumanInTheLoopMiddleware`, which
pauses the graph (`interrupt()`) before `log_food`/`log_workout`/`log_metric`
execute and resumes on the user's next YES/NO reply (`Command(resume=...)`)
— no separate pending-state table. All intent decisions (what to log, when
to fetch a summary, etc.) are made by the main agent itself via its tools
and system prompt — there is no separate LLM intent-classification step.
"""

from __future__ import annotations

import asyncio
import json

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command

from ai_fitness_coach_rag.agent.state import ConversationState
from ai_fitness_coach_rag.agent.tools.log_retrieval_tools import get_fitness_logs
from ai_fitness_coach_rag.agent.tools.logging_tools import (
    log_food,
    log_metric,
    log_workout,
)
from ai_fitness_coach_rag.agent.tools.nutrition_tools import lookup_nutrition
from ai_fitness_coach_rag.agent.tools.onboarding_tools import (
    apply_onboarding_answer,
    get_or_create_user,
    next_onboarding_slot,
    onboarding_welcome_message,
)
from ai_fitness_coach_rag.agent.prompts import get_prompt
from ai_fitness_coach_rag.db.session import SessionLocal
from ai_fitness_coach_rag.llm.factory import get_llm
from ai_fitness_coach_rag.memory.short_term import (
    get_checkpointer,
    get_summarization_middleware,
    thread_config,
)

SYSTEM_PROMPT = get_prompt("fitness_coach_system")

CONFIRM_YES = {"yes", "y", "confirm", "ok", "okay", "sure", "yep", "yeah"}
CONFIRM_NO = {"no", "n", "cancel", "nope", "discard"}

# Exit strategy: after this many unrecognized replies, auto-cancel the pending log
# instead of looping forever waiting for a clear YES/NO.
MAX_CONFIRM_RETRIES = 2


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


def _parse_decision(text: str) -> dict | None:
    """Map a free-text reply to a HumanInTheLoopMiddleware decision.

    Returns None when the reply is neither a clear YES nor a clear NO, so the
    caller can re-prompt instead of guessing.
    """
    normalized = text.strip().lower()
    if normalized in CONFIRM_YES:
        return {"type": "approve"}
    if normalized in CONFIRM_NO:
        return {"type": "reject", "message": "User declined to log this."}
    return None


def _format_interrupt(interrupts) -> str:
    """Render the paused tool-call(s) as a plain-text confirmation prompt (LLM fallback)."""
    lines = []
    for item in interrupts:
        for action in item.value.get("action_requests", []):
            lines.append(f"- {action['name']}({action['args']})")
    return "Log this?\n" + "\n".join(lines) + "\nReply YES to confirm or NO to cancel."


class AgentOrchestrator:
    """Agent facade using course-style memory and summarization."""

    def __init__(self) -> None:
        self._agent = None
        self._agent_loop: asyncio.AbstractEventLoop | None = None
        self._confirm_retries: dict[str, int] = {}

    async def _get_agent(self):
        """Create the LangChain agent once for the active event loop."""
        loop = asyncio.get_running_loop()
        if self._agent is None or self._agent_loop is not loop:
            self._agent = create_agent(
                model=get_llm(),
                tools=[
                    lookup_nutrition,
                    log_food,
                    log_workout,
                    log_metric,
                    get_fitness_logs,
                ],
                system_prompt=SYSTEM_PROMPT,
                middleware=[
                    get_summarization_middleware(),
                    HumanInTheLoopMiddleware(
                        interrupt_on={
                            "log_food": True,
                            "log_workout": True,
                            "log_metric": True,
                        }
                    ),
                ],
                checkpointer=await get_checkpointer(),
            )
            self._agent_loop = loop
        return self._agent

    async def _pending_interrupts(self, agent, config: dict):
        snapshot = await agent.aget_state(config)
        for task in snapshot.tasks:
            if task.interrupts:
                return task.interrupts
        return None

    async def _natural_language_confirm(self, interrupts) -> str:
        """Ask the LLM to phrase the pending tool-call(s) as a natural-language question."""
        action_requests = [
            action
            for item in interrupts
            for action in item.value.get("action_requests", [])
        ]
        llm = get_llm("confirm")
        prompt = get_prompt(
            "confirm_pending_action", actions=json.dumps(action_requests)
        )
        try:
            response = await llm.ainvoke(prompt)
            text = (getattr(response, "content", None) or str(response)).strip()
        except Exception:
            text = ""
        return text or _format_interrupt(interrupts)

    async def handle_message(self, user_id: str, text: str) -> str:
        onboarding_reply, _ = _handle_onboarding(user_id, text)
        if onboarding_reply is not None:
            return onboarding_reply

        agent = await self._get_agent()
        config = thread_config(user_id)

        pending = await self._pending_interrupts(agent, config)
        if pending:
            action_count = len(pending[0].value.get("action_requests", []))
            decision = _parse_decision(text)

            if decision is None:
                retries = self._confirm_retries.get(user_id, 0) + 1
                if retries > MAX_CONFIRM_RETRIES:
                    # Exit strategy: give up waiting for a clear answer and cancel the log.
                    self._confirm_retries.pop(user_id, None)
                    decision = {
                        "type": "reject",
                        "message": f"No clear confirmation after {MAX_CONFIRM_RETRIES} attempts; cancelled.",
                    }
                else:
                    self._confirm_retries[user_id] = retries
                    prompt = await self._natural_language_confirm(pending)
                    return prompt
            else:
                self._confirm_retries.pop(user_id, None)

            resume_value = {"decisions": [decision] * action_count}
            result = await agent.ainvoke(
                Command(resume={pending[0].id: resume_value}),
                config=config,
            )
        else:
            result = await agent.ainvoke(
                {"messages": [{"role": "user", "content": text}]}, config=config
            )

        new_interrupts = result.get("__interrupt__")
        if new_interrupts:
            return await self._natural_language_confirm(new_interrupts)
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
