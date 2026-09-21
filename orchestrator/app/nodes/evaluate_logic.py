"""Evaluate the student's plain-language algorithm (CLAUDE.md section 6.3)."""
from __future__ import annotations

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from app import cache, config, domain_client, llm
from app.prompts.evaluator import EVALUATOR_SYSTEM, build_evaluator_user
from app.state import SessionState

log = logging.getLogger(__name__)


class EvaluatorOutput(BaseModel):
    """The model's contract. Parsed strictly; never defaulted (trap 11)."""

    verdict: Literal["PASS", "FAIL"]
    matched_approach: str | None = None
    missing_steps: list[str] = Field(default_factory=list)
    violated_invariants: list[str] = Field(default_factory=list)
    misconception_id: str | None = None
    confidence: float = 0.0
    rationale: str = ""


def evaluate_logic(state: SessionState) -> dict[str, Any]:
    problem_id = state["problem_id"]
    text = state.get("user_logic", "")

    ctx = domain_client.get_problem_context(problem_id)
    rubric = ctx["rubric"]
    rubric_version = ctx.get("rubric_version", 1)

    attempts = dict(state.get("attempts") or {"logic": 0, "code": 0})
    attempts["logic"] = attempts.get("logic", 0) + 1

    key = cache.cache_key(problem_id, rubric_version, text)
    cached = cache.get(key)

    if cached is not None:
        log.info("evaluate_logic CACHE HIT key=%s verdict=%s", key[:12], cached.get("verdict"))
        evaluation = dict(cached)
        evaluation["cache_hit"] = True
    else:
        parsed = llm.complete_json(
            model=config.LLM_MODEL_EVALUATOR,
            system=EVALUATOR_SYSTEM,
            user=build_evaluator_user(
                title=ctx["title"],
                description=ctx["description"],
                rubric=rubric,
                student_text=text,
            ),
            schema=EvaluatorOutput,
            temperature=0.0,
        )

        verdict = _apply_flagged_rule(parsed)

        # rationale is for the teacher, and never leaves the server (section 5.2)
        log.info(
            "evaluate_logic verdict=%s approach=%s misconception=%s confidence=%.2f rationale=%r",
            verdict, parsed.matched_approach, parsed.misconception_id,
            parsed.confidence, parsed.rationale[:300],
        )

        evaluation = {
            "verdict": verdict,
            "matched_approach": parsed.matched_approach,
            "missing_steps": parsed.missing_steps,
            "violated_invariants": parsed.violated_invariants,
            "misconception_id": parsed.misconception_id,
            "confidence": parsed.confidence,
            "cache_hit": False,
        }
        cache.put(key, problem_id, evaluation)

    node_path = list(state.get("node_path") or []) + ["evaluate_logic"]
    return {"last_eval": evaluation, "attempts": attempts, "node_path": node_path}


def _apply_flagged_rule(parsed: EvaluatorOutput) -> str:
    """FLAGGED is computed here, in code -- the model never returns it (section 6.3).

    The model is only asked for PASS/FAIL. FLAGGED means "this looks like a novel
    approach we have no rubric entry for, and the model is not confident": no
    approach matched, nothing was actually violated, and confidence is low. It is
    treated as a pass, because failing a student for our own gap in coverage is
    the worse error.
    """
    if (
        parsed.matched_approach is None
        and not parsed.violated_invariants
        and parsed.confidence < config.FLAG_CONFIDENCE_THRESHOLD
    ):
        log.warning(
            "FLAGGED - would enter review queue (cut for MVP): confidence=%.2f rationale=%r",
            parsed.confidence, parsed.rationale[:300],
        )
        return "FLAGGED"
    return parsed.verdict


def route_after_eval(state: SessionState) -> str:
    verdict = (state.get("last_eval") or {}).get("verdict")
    return "summarize_logic" if verdict in ("PASS", "FLAGGED") else "logic_tutor"
