"""Client for the Java domain service (CLAUDE.md section 5.4).

Python never touches the sandbox or the database directly: it asks Java. That
boundary is the point of the architecture, so it is worth keeping clean.

The problem context is cached in-process per problem_id (section 6.2) so the
rubric stays out of graph state and out of every checkpoint.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app import config

log = logging.getLogger(__name__)

_context_cache: dict[str, dict[str, Any]] = {}


class DomainError(RuntimeError):
    """The domain service could not answer."""


def _headers(trace_id: str | None = None) -> dict[str, str]:
    h = {"X-Internal-Token": config.INTERNAL_TOKEN}
    if trace_id:
        h["X-Trace-Id"] = trace_id
    return h


def get_problem_context(problem_id: str, *, trace_id: str | None = None) -> dict[str, Any]:
    """Problem description + rubric. Cached; call clear_cache() after a reseed."""
    if problem_id in _context_cache:
        return _context_cache[problem_id]

    url = f"{config.DOMAIN_URL}/internal/problems/{problem_id}/context"
    try:
        r = httpx.get(url, headers=_headers(trace_id), timeout=20.0)
    except httpx.HTTPError as e:
        raise DomainError(f"cannot reach the domain service at {url}: {e}") from e

    if r.status_code == 404:
        raise DomainError(f"unknown problem: {problem_id}")
    if r.status_code != 200:
        raise DomainError(f"domain returned {r.status_code} for {url}: {r.text[:200]}")

    ctx = r.json()
    _context_cache[problem_id] = ctx
    log.info("cached problem context problem=%s rubric_version=%s",
             problem_id, ctx.get("rubric_version"))
    return ctx


def execute(problem_id: str, source: str, *, trace_id: str | None = None) -> dict[str, Any]:
    """Run the student's code. Returns Java's full detail, hidden tests included.

    The caller is responsible for stripping hidden-test data before any of this
    reaches a SessionView (section 5.4).

    The timeout is generous because the sandbox runs every test in sequence; a
    TLE case alone burns its whole limit before returning.
    """
    url = f"{config.DOMAIN_URL}/internal/execute"
    payload = {"problem_id": problem_id, "language": "python", "source": source}
    try:
        r = httpx.post(url, json=payload, headers=_headers(trace_id), timeout=180.0)
    except httpx.HTTPError as e:
        raise DomainError(f"cannot reach the domain service at {url}: {e}") from e

    if r.status_code != 200:
        raise DomainError(f"domain returned {r.status_code} for {url}: {r.text[:200]}")
    return r.json()


def clear_cache() -> None:
    _context_cache.clear()


def health() -> bool:
    try:
        return httpx.get(f"{config.DOMAIN_URL}/health", timeout=5.0).status_code == 200
    except httpx.HTTPError:
        return False
