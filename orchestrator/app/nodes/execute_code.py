"""Run the student's code and route on the bucket (CLAUDE.md section 6.3)."""
from __future__ import annotations

import logging
from typing import Any

from app import domain_client
from app.state import SessionState, message

log = logging.getLogger(__name__)

INFRA_MESSAGE = "The sandbox failed; this attempt does not count. Please try again."


def execute_code(state: SessionState) -> dict[str, Any]:
    problem_id = state["problem_id"]
    source = state.get("user_code", "")

    node_path = list(state.get("node_path") or []) + ["execute_code"]
    attempts = dict(state.get("attempts") or {"logic": 0, "code": 0})

    try:
        execution = domain_client.execute(problem_id, source)
    except Exception as e:                       # noqa: BLE001
        # Java unreachable is an infrastructure failure, treated exactly like a
        # sandbox failure: the student is not charged an attempt for it.
        log.error("execute_code could not reach the domain service: %s", e)
        return {
            "last_execution": {"bucket": "INFRA_ERROR", "passed": 0, "total": 0,
                               "tests": [], "error": str(e)},
            "attempts": attempts,
            "messages": [message("system", "info", INFRA_MESSAGE)],
            "node_path": node_path,
        }

    bucket = execution.get("bucket")

    # section 6.3: attempts.code increments unless the bucket is INFRA_ERROR
    if bucket != "INFRA_ERROR":
        attempts["code"] = attempts.get("code", 0) + 1

    log.info("execute_code bucket=%s passed=%s/%s attempts_code=%s",
             bucket, execution.get("passed"), execution.get("total"), attempts["code"])

    update: dict[str, Any] = {
        "last_execution": execution,
        "attempts": attempts,
        "node_path": node_path,
    }

    if bucket == "INFRA_ERROR":
        update["messages"] = [message("system", "info", INFRA_MESSAGE)]
    else:
        passed, total = execution.get("passed", 0), execution.get("total", 0)
        update["messages"] = [
            message("system", "result", f"{bucket}: {passed}/{total} tests passed.")
        ]

    return update


def route_after_execute(state: SessionState) -> str:
    bucket = (state.get("last_execution") or {}).get("bucket")
    if bucket == "ACCEPTED":
        return "finish"
    if bucket == "INFRA_ERROR":
        # no tutor turn: there is nothing about the student's code to discuss
        return "await_input"
    return "code_tutor"
