"""Accept the logic and unlock the editor (CLAUDE.md section 6.3)."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from app import config, llm
from app.prompts.summarizer import SUMMARIZER_SYSTEM, build_summarizer_user
from app.state import SessionState, message

log = logging.getLogger(__name__)


class SummaryOutput(BaseModel):
    approach_taken: str = ""
    key_steps: list[str] = Field(default_factory=list)
    misconceptions_corrected: list[str] = Field(default_factory=list)
    final_logic_text: str = ""


UNLOCK_MESSAGE = (
    "Your logic is accepted. The editor is unlocked - now write the code that "
    "does exactly what you just described."
)


def summarize_logic(state: SessionState) -> dict[str, Any]:
    user_logic = state.get("user_logic", "")

    earlier = [
        m["text"] for m in (state.get("messages") or [])
        if m.get("role") == "student" and m.get("kind") == "logic" and m.get("text") != user_logic
    ]

    try:
        parsed = llm.complete_json(
            model=config.LLM_MODEL_TUTOR,
            system=SUMMARIZER_SYSTEM,
            user=build_summarizer_user(student_logic=user_logic, earlier_attempts=earlier),
            schema=SummaryOutput,
            temperature=0.0,
        )
        summary = parsed.model_dump()
        if not summary.get("final_logic_text"):
            summary["final_logic_text"] = user_logic
    except Exception as e:                       # noqa: BLE001
        # Section 6.3 is explicit: on any failure, fall back to the student's own
        # words. The student has already earned the pass; a summariser hiccup
        # must not block them from the editor.
        log.warning("summarize_logic failed, falling back to the raw text: %s", e)
        summary = {
            "approach_taken": "",
            "key_steps": [],
            "misconceptions_corrected": [],
            "final_logic_text": user_logic,
        }

    accepted = summary["final_logic_text"]
    node_path = list(state.get("node_path") or []) + ["summarize_logic"]

    log.info("summarize_logic accepted logic, phase -> CODE (approach=%r, %d key steps)",
             summary.get("approach_taken"), len(summary.get("key_steps") or []))

    return {
        "logic_summary": summary,
        "accepted_logic": accepted,
        "phase": "CODE",
        "status": "CODE_WRITE",
        "messages": [message("system", "info", UNLOCK_MESSAGE)],
        "node_path": node_path,
    }
