"""Periodic score reconciliation worker."""

from __future__ import annotations

import datetime
import logging
import threading

from ai_fitness_coach_rag.db.models import User
from ai_fitness_coach_rag.db.score_service import upsert_daily_score, user_local_date
from ai_fitness_coach_rag.db.session import SessionLocal

logger = logging.getLogger(__name__)


class ScoreWorker:
    """Recalculate current and previous-day scores in a managed daemon thread."""

    def __init__(self, interval_seconds: float = 3600) -> None:
        self.interval_seconds = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="daily-score-worker",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=min(self.interval_seconds, 10))
        self._thread = None

    def run_once(self) -> None:
        session = SessionLocal()
        try:
            for user in session.query(User).all():
                today = user_local_date(user)
                upsert_daily_score(session, user, today)
                upsert_daily_score(
                    session, user, today - datetime.timedelta(days=1)
                )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Periodic score reconciliation failed")
        finally:
            session.close()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self.run_once()
            self._stop_event.wait(self.interval_seconds)