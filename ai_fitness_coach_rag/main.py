"""FastAPI application entrypoint: mounts the WhatsApp webhook router."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_fitness_coach_rag.agent.tools.nutrition_tools import (
    ensure_nutrition_collection_indexed,
)
from ai_fitness_coach_rag.dashboard.auth_router import router as dashboard_auth_router
from ai_fitness_coach_rag.db.session import initialize_database
from ai_fitness_coach_rag.config import config
from ai_fitness_coach_rag.jobs.score_worker import ScoreWorker
from ai_fitness_coach_rag.whatsapp.webhook import router as whatsapp_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    ensure_nutrition_collection_indexed()
    worker = ScoreWorker(
        float(config.get("scoring", {}).get("worker_interval_seconds", 3600))
    )
    worker.start()
    try:
        yield
    finally:
        worker.stop()


app = FastAPI(title="AI Fitness Coach", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("DASHBOARD_WEB_ORIGIN", "http://localhost:3000")],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Minimal liveness check for the app runtime."""
    return {"status": "ok"}


app.include_router(whatsapp_router)
app.include_router(dashboard_auth_router)


def run() -> None:
    """Entrypoint for the `fitness_coach` poetry script: runs the app with uvicorn."""
    import uvicorn

    uvicorn.run("ai_fitness_coach_rag.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
