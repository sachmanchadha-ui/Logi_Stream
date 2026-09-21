"""Prompt templates for the orchestrator nodes.

Kept as python strings rather than files so they are importable and testable,
and so the placeholders are checked by the same tooling as the rest of the code.
"""
from app.prompts.evaluator import EVALUATOR_SYSTEM, build_evaluator_user
from app.prompts.logic_tutor import LOGIC_TUTOR_SYSTEM, build_logic_tutor_user
from app.prompts.summarizer import SUMMARIZER_SYSTEM, build_summarizer_user

__all__ = [
    "EVALUATOR_SYSTEM",
    "build_evaluator_user",
    "LOGIC_TUTOR_SYSTEM",
    "build_logic_tutor_user",
    "SUMMARIZER_SYSTEM",
    "build_summarizer_user",
]
