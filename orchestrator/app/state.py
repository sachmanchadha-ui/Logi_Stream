"""Graph state (CLAUDE.md section 6.2).

Plain JSON-serialisable types only -- this is checkpointed to Postgres on Day 2,
and anything exotic in here becomes a serialisation bug at the worst moment.

Note what is deliberately absent: the problem description and rubric. They are
fetched from Java via domain_client and cached in-process per problem_id, so the
checkpoint stays small and a rubric edit does not need a state migration.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

Phase = Literal["LOGIC", "CODE", "DONE"]
Status = Literal["LOGIC_WRITE", "LOGIC_CHAT", "CODE_WRITE", "CODE_CHAT", "SUCCESS"]
EventType = Literal["logic", "chat", "code"]


class SessionState(TypedDict, total=False):
    problem_id: str
    user_id: str
    thread_id: str

    phase: Phase
    status: Status

    pending_event: dict[str, Any] | None      # {type, text}
    user_logic: str
    user_code: str
    accepted_logic: str | None
    logic_summary: dict[str, Any] | None

    last_eval: dict[str, Any] | None
    last_execution: dict[str, Any] | None     # full Java detail, Python-side only

    attempts: dict[str, int]                  # {"logic": int, "code": int}

    draft: str | None                         # tutor draft awaiting verification
    regenerations: int
    verifier_rejections: list[dict[str, str]]
    fallback_used: bool

    node_path: list[str]                      # reset at each await_input

    # the only reducer: messages accumulate, everything else is last-write-wins
    messages: Annotated[list[dict[str, Any]], operator.add]


def initial_state(problem_id: str, user_id: str, thread_id: str) -> SessionState:
    return {
        "problem_id": problem_id,
        "user_id": user_id,
        "thread_id": thread_id,
        "phase": "LOGIC",
        "status": "LOGIC_WRITE",
        "pending_event": None,
        "user_logic": "",
        "user_code": "",
        "accepted_logic": None,
        "logic_summary": None,
        "last_eval": None,
        "last_execution": None,
        "attempts": {"logic": 0, "code": 0},
        "draft": None,
        "regenerations": 0,
        "verifier_rejections": [],
        "fallback_used": False,
        "node_path": [],
        "messages": [],
    }


def message(role: str, kind: str, text: str) -> dict[str, Any]:
    """One transcript entry. ts is ISO-8601 UTC, as the SessionView contract says."""
    from datetime import datetime, timezone
    return {
        "role": role,
        "kind": kind,
        "text": text,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
