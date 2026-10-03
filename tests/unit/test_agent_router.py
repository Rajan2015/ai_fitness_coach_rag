from ai_fitness_coach_rag.agent.router import Intent, route_message


class _FakeLLM:
    def invoke(self, prompt: str) -> str:
        if "2 eggs and toast" in prompt:
            return "log_food"
        if "set up my profile" in prompt:
            return "onboarding"
        return "off_topic"


def test_food_log_intent_is_detected(monkeypatch) -> None:
    monkeypatch.setattr(
        "ai_fitness_coach_rag.agent.router.get_llm",
        lambda _flow=None: _FakeLLM(),
    )
    assert route_message("I ate 2 eggs and toast") == Intent.LOG_FOOD


def test_onboarding_intent_is_detected(monkeypatch) -> None:
    monkeypatch.setattr(
        "ai_fitness_coach_rag.agent.router.get_llm",
        lambda _flow=None: _FakeLLM(),
    )
    assert route_message("help me set up my profile") == Intent.ONBOARDING


def test_off_topic_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(
        "ai_fitness_coach_rag.agent.router.get_llm",
        lambda _flow=None: _FakeLLM(),
    )
    assert route_message("write a poem about the moon") == Intent.OFF_TOPIC
