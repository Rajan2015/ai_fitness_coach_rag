"""Singleton application logger (mirrors the Educosys_Claude_Code observability/logger.py pattern)."""

from __future__ import annotations

import logging
import sys
from functools import lru_cache

from ai_fitness_coach_rag.config import config

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


@lru_cache(maxsize=None)
def get_logger(name: str = "ai_fitness_coach") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(config["log_level"].upper())
        logger.propagate = False
    return logger
