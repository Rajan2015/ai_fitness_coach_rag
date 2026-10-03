"""LangGraph async SQLite checkpointer for per-user conversation state."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from ai_fitness_coach_rag.config import config

_checkpoint_path = Path(config["memory"]["db_path"])
_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

_checkpointer: AsyncSqliteSaver | None = None
_checkpointer_loop: asyncio.AbstractEventLoop | None = None


async def get_checkpointer() -> AsyncSqliteSaver:
    """Return the initialized async checkpointer for the active event loop."""
    global _checkpointer, _checkpointer_loop
    loop = asyncio.get_running_loop()
    if _checkpointer is None or _checkpointer_loop is not loop:
        connection = await aiosqlite.connect(str(_checkpoint_path))
        _checkpointer = AsyncSqliteSaver(connection)
        await _checkpointer.setup()
        _checkpointer_loop = loop
    return _checkpointer


def thread_config(user_id: str) -> dict:
    """LangGraph `config` dict that scopes checkpointed state to one user's thread."""
    return {"configurable": {"thread_id": user_id}}


def get_summarization_middleware() -> SummarizationMiddleware:
    """Create the course-style conversation summarization middleware."""
    memory_config = config["memory"]
    from ai_fitness_coach_rag.llm.factory import get_llm

    return SummarizationMiddleware(
        model=get_llm(),
        trigger=("tokens", memory_config["summarize_at_tokens"]),
        keep=("messages", memory_config["keep_last_messages"]),
    )
