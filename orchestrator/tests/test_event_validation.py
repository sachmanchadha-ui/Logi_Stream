"""Event validation rules (CLAUDE.md section 5.3).

    logic -> only in phase LOGIC
    code  -> only in phase CODE
    chat  -> LOGIC or CODE
    nothing in DONE
    empty/whitespace text -> 422

Tested directly against the validator rather than over HTTP, so these run in
milliseconds and need no database, no LLM and no open port.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.main import EventBody, _validate_event


def check(etype: str, phase: str, text: str = "something") -> int | None:
    """Returns the HTTP status that would be raised, or None if allowed."""
    try:
        _validate_event(EventBody(type=etype, text=text), {"phase": phase})
        return None
    except HTTPException as e:
        return e.status_code


@pytest.mark.parametrize(
    "etype,phase",
    [("logic", "LOGIC"), ("chat", "LOGIC"), ("code", "CODE"), ("chat", "CODE")],
)
def test_allowed_combinations(etype, phase):
    assert check(etype, phase) is None


@pytest.mark.parametrize(
    "etype,phase",
    [("code", "LOGIC"), ("logic", "CODE")],
)
def test_wrong_phase_is_409(etype, phase):
    assert check(etype, phase) == 409


@pytest.mark.parametrize("etype", ["logic", "chat", "code"])
def test_nothing_is_allowed_in_done(etype):
    assert check(etype, "DONE") == 409


@pytest.mark.parametrize("text", ["", "   ", "\n", "\t  \n "])
def test_empty_text_is_422(text):
    assert check("logic", "LOGIC", text) == 422


def test_empty_text_is_checked_before_the_phase():
    """422 beats 409: the clearer error wins when both apply."""
    assert check("code", "LOGIC", "   ") == 422


def test_unknown_event_type_is_rejected():
    assert check("sudo", "LOGIC") == 409


def test_missing_phase_defaults_to_logic():
    try:
        _validate_event(EventBody(type="logic", text="hi"), {})
        allowed = True
    except HTTPException:
        allowed = False
    assert allowed, "a state with no phase yet should behave as LOGIC"


def test_409_message_names_what_is_allowed():
    """The gateway passes this straight through, so a student may read it."""
    with pytest.raises(HTTPException) as e:
        _validate_event(EventBody(type="code", text="print(1)"), {"phase": "LOGIC"})
    detail = e.value.detail
    assert "LOGIC" in detail
    assert "logic" in detail and "chat" in detail
