"""Terminal node (CLAUDE.md section 6.3)."""
from __future__ import annotations

import logging
from typing import Any

from app.state import SessionState, message

log = logging.getLogger(__name__)

SUCCESS_MESSAGE = (
    "All tests passed. You described the algorithm in your own words first, then "
    "wrote code that does exactly that - which is the whole point."
)


def finish(state: SessionState) -> dict[str, Any]:
    execution = state.get("last_execution") or {}
    log.info("finish: session complete passed=%s/%s logic_attempts=%s code_attempts=%s",
             execution.get("passed"), execution.get("total"),
             (state.get("attempts") or {}).get("logic"),
             (state.get("attempts") or {}).get("code"))

    return {
        "phase": "DONE",
        "status": "SUCCESS",
        "messages": [message("system", "info", SUCCESS_MESSAGE)],
        "node_path": list(state.get("node_path") or []) + ["finish"],
    }
