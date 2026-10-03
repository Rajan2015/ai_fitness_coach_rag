"""Minimal orchestration layer that routes inbound messages to agent intents."""

from __future__ import annotations

from ai_fitness_coach_rag.agent.router import Intent, route_message
from ai_fitness_coach_rag.agent.state import AgentState


class AgentOrchestrator:
    """Thin facade around the message router and state tracking."""

    def __init__(self) -> None:
        self._states: dict[str, AgentState] = {}

    def _get_state(self, user_id: str) -> AgentState:
        state = self._states.get(user_id)
        if state is None:
            state = AgentState(user_id=user_id)
            self._states[user_id] = state
        return state

    def handle_message(self, user_id: str, text: str) -> str:
        state = self._get_state(user_id)
        intent = route_message(text, pending_flow=state.pending_flow)
        state.last_intent = intent

        if intent == Intent.LOG_FOOD:
            return "I can log that food entry. Tell me the item and calories or protein if you want it recorded."
        if intent == Intent.LOG_WORKOUT:
            return "I can capture that workout. Share the exercise, duration, and any calories burned."
        if intent == Intent.LOG_METRIC:
            return "I can record that metric. Send the metric name and value."
        if intent == Intent.ONBOARDING:
            state.pending_flow = "onboarding"
            return "Let’s set up your profile. I’ll ask for age, sex, height, weight, activity level, and goals."
        if intent == Intent.REQUEST_SUMMARY:
            return (
                "I can summarize your recent progress once your log data is available."
            )
        if intent == Intent.REQUEST_PLAN:
            return "I can build a meal or workout plan based on your profile and food preferences."
        if intent == Intent.QUERY_KNOWLEDGE:
            return "I can answer fitness and nutrition questions, but keep the answer grounded in your goals and known facts."
        if intent == Intent.CONFIRM_PENDING:
            return (
                "I’m waiting on your pending confirmation before I finalize that step."
            )
        return "I can help with food logging, workouts, metrics, onboarding, or fitness guidance."


def handle_message(user_id: str, text: str) -> str:
    """Convenience wrapper for callers that do not need a long-lived state object."""
    orchestrator = AgentOrchestrator()
    return orchestrator.handle_message(user_id, text)
