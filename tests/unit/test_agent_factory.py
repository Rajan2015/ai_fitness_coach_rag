from ai_fitness_coach_rag.agent.factory import create_orchestrator, get_orchestrator
from ai_fitness_coach_rag.agent.orchestrator import AgentOrchestrator
from ai_fitness_coach_rag.whatsapp.webhook import InboundMessage, _build_reply


def test_factory_returns_agent_orchestrator() -> None:
    orchestrator = create_orchestrator()
    assert isinstance(orchestrator, AgentOrchestrator)
    assert isinstance(get_orchestrator(), AgentOrchestrator)


def test_build_reply_uses_agent_orchestrator_for_text() -> None:
    message = InboundMessage(
        message_sid="abc123",
        from_number="+15551234567",
        to_number="+15550000000",
        body="I ate 2 eggs and toast",
        num_media=0,
    )

    reply = _build_reply(message)

    assert "food" in reply.lower()
