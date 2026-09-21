"""Code tutor and its verification loop (CLAUDE.md sections 6.3, 6.4)."""
from __future__ import annotations

import logging
from typing import Any

from app import config, domain_client, llm, redact, verifier
from app.prompts.code_tutor import CODE_TUTOR_SYSTEM, build_code_tutor_user
from app.state import SessionState, message

log = logging.getLogger(__name__)


def code_tutor(state: SessionState) -> dict[str, Any]:
    ctx = domain_client.get_problem_context(state["problem_id"])
    execution = state.get("last_execution")
    bucket = (execution or {}).get("bucket", "UNKNOWN")

    # the tutor sees redacted results: hidden tests are label + outcome only, so
    # the model cannot quote a hidden input back to the student (section 5.4)
    results_summary = redact.summarize_for_tutor(execution)

    regen = state.get("regenerations", 0)
    user = build_code_tutor_user(
        title=ctx["title"],
        bucket=bucket,
        results_summary=results_summary,
        student_code=state.get("user_code", ""),
        logic_summary=state.get("logic_summary"),
        recent_messages=state.get("messages") or [],
    )

    if regen:
        reasons = "; ".join(r["reason"] for r in (state.get("verifier_rejections") or [])[-3:])
        user += (
            f"\n\nYour previous attempt was REJECTED by an automatic checker for: {reasons}. "
            "Write a different explanation that does not do that."
        )

    draft = llm.complete(
        model=config.LLM_MODEL_TUTOR,
        system=CODE_TUTOR_SYSTEM,
        user=user,
        temperature=0.4,
    )

    node_path = list(state.get("node_path") or []) + ["code_tutor"]
    log.info("code_tutor drafted %d chars for bucket=%s (regeneration %d)",
             len(draft), bucket, regen)
    return {"draft": draft, "node_path": node_path}


def verify_code(state: SessionState) -> dict[str, Any]:
    """Gate every code-phase tutor turn (section 6.4)."""
    ctx = domain_client.get_problem_context(state["problem_id"])
    rubric = ctx["rubric"]
    draft = state.get("draft") or ""

    result = verifier.verify_code_draft(draft, rubric)
    node_path = list(state.get("node_path") or []) + ["verify_code"]
    rejections = list(state.get("verifier_rejections") or [])

    if result.ok:
        log.info("verify_code ACCEPTED the draft")
        return {
            "messages": [message("tutor", "hint", draft)],
            "draft": None,
            "node_path": node_path,
            "status": "CODE_CHAT",
        }

    rejections.extend(result.rejections)
    regen = state.get("regenerations", 0) + 1
    log.warning("verify_code REJECTED draft (regeneration %d/%d): %s",
                regen, config.MAX_REGENERATIONS, result.reasons)

    if regen > config.MAX_REGENERATIONS:
        fallback = verifier.code_fallback()
        log.warning("verify_code exhausted regenerations - delivering the canned fallback")
        return {
            "messages": [message("tutor", "hint", fallback)],
            "draft": None,
            "regenerations": regen,
            "verifier_rejections": rejections,
            "fallback_used": True,
            "node_path": node_path,
            "status": "CODE_CHAT",
        }

    return {
        "regenerations": regen,
        "verifier_rejections": rejections,
        "node_path": node_path,
    }


def route_after_verify_code(state: SessionState) -> str:
    return "code_tutor" if state.get("draft") else "await_input"
