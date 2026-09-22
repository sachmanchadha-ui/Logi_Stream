"""LLM result cache (CLAUDE.md section 6.3, extended on Day 3).

Keyed on sha256(kind : problem_id : rubric_version : normalised text). A cache
hit skips the LLM entirely, which on the free tier is the difference between a
2-second demo beat and a 30-second one, and it is what makes the D3-T4 pre-warm
step work.

TWO KINDS share one table. Section 6.3 specified caching the evaluator verdict,
and that alone left the F3 "editor unlocks" beat costing ~30s even on a cache
hit, because summarize_logic still made its own LLM call. Both are now cached.

The kind is folded into the hash rather than added as a column, so this needed
no schema migration the day before the demo. The rows are not interchangeable:
a verdict key and a summary key for the same text hash differently and cannot
collide.

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


def cache_key(
    problem_id: str,
    rubric_version: int | str,
    text: str,
    kind: str = "verdict",
) -> str:
    """kind is "verdict" or "summary"; it namespaces the key so the two cannot mix."""
    raw = f"{kind}:{problem_id}:{rubric_version}:{normalize(text)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get(key: str) -> dict[str, Any] | None:
    """The cached payload for this key, or None. Never raises."""
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT verdict FROM orch.verdict_cache WHERE cache_key = %s", (key,)
            ).fetchone()
            return row[0] if row else None
    except Exception as e:                       # noqa: BLE001 - never fatal
        log.warning("verdict cache read failed (continuing without it): %s", e)
        return None


def put(key: str, problem_id: str, payload: dict[str, Any]) -> None:
    """Store a payload. The column is named `verdict` for historical reasons and
    now holds either an evaluation or a logic summary, distinguished by the key."""
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=5) as conn:
            conn.execute(
                """
                INSERT INTO orch.verdict_cache (cache_key, problem_id, verdict)
                VALUES (%s, %s, %s)
                ON CONFLICT (cache_key) DO NOTHING
                """,
                (key, problem_id, json.dumps(payload)),
            )
    except Exception as e:                       # noqa: BLE001 - never fatal
        log.warning("verdict cache write failed (continuing without it): %s", e)
