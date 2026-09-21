"""Verdict cache (CLAUDE.md section 6.3).

Keyed on sha256(problem_id : rubric_version : normalised text). A cache hit
skips the LLM entirely, which on the free tier is the difference between a
2-second demo beat and a 20-second one -- and it is what makes the D3-T4
pre-warm step work.

Degrades to a no-op if Postgres is unreachable: a cache is an optimisation, and
losing it must never take a session down.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any

import psycopg

from app import config

log = logging.getLogger(__name__)

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    """lowercase, strip, collapse whitespace (section 6.3)."""
    return _WS.sub(" ", (text or "").strip().lower())


def cache_key(problem_id: str, rubric_version: int | str, text: str) -> str:
    raw = f"{problem_id}:{rubric_version}:{normalize(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> dict[str, Any] | None:
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT verdict FROM orch.verdict_cache WHERE cache_key = %s", (key,)
            ).fetchone()
            return row[0] if row else None
    except Exception as e:                       # noqa: BLE001 - never fatal
        log.warning("verdict cache read failed (continuing without it): %s", e)
        return None


def put(key: str, problem_id: str, verdict: dict[str, Any]) -> None:
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            conn.execute(
                """
                INSERT INTO orch.verdict_cache (cache_key, problem_id, verdict)
                VALUES (%s, %s, %s)
                ON CONFLICT (cache_key) DO NOTHING
                """,
                (key, problem_id, json.dumps(verdict)),
            )
    except Exception as e:                       # noqa: BLE001 - never fatal
        log.warning("verdict cache write failed (continuing without it): %s", e)
