"""FastAPI application entrypoint: mounts the WhatsApp webhook router."""

from __future__ import annotations

from fastapi import FastAPI

from ai_fitness_coach_rag.whatsapp.webhook import router as whatsapp_router

app = FastAPI(title="AI Fitness Coach")
app.include_router(whatsapp_router)


def run() -> None:
    """Entrypoint for the `fitness_coach` poetry script: runs the app with uvicorn."""
    import uvicorn

    uvicorn.run("ai_fitness_coach_rag.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
