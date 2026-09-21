"""Hidden-test redaction and SessionView construction (sections 5.2, 5.4).

These guard two leaks that would be invisible in a demo but fatal in review: the
browser seeing hidden test data, and the evaluator's private rationale escaping
to the student.
"""
from __future__ import annotations

import json

import pytest

from app import redact
from app.view import build_session_view

SECRET_STDIN = '{"nums": [-3, 4, 3, 90], "target": 0}'
SECRET_EXPECTED = "[0, 2]"
SECRET_STDOUT = "[1, 3]"


@pytest.fixture
def execution() -> dict:
    """Shaped exactly like the Java /internal/execute response (section 5.4)."""
    return {
        "bucket": "WRONG_ANSWER",
        "passed": 1,
        "total": 3,
        "infra_retry_used": False,
        "tests": [
            {"index": 1, "label": "basic", "is_public": True, "status_id": 3,
             "status_description": "Accepted", "passed": True, "time": "0.02",
             "stdin": '{"nums": [2, 7, 11, 15], "target": 9}', "expected": "[0, 1]",
             "stdout": "[0, 1]", "stderr": ""},
            {"index": 2, "label": "middle pair", "is_public": True, "status_id": 3,
             "status_description": "Accepted", "passed": False, "time": "0.02",
             # deliberately NOT equal to any hidden value, so the grep-style
             # assertions below cannot pass or fail by coincidence
             "stdin": '{"nums": [3, 2, 4], "target": 6}', "expected": "[1, 2]",
             "stdout": "[0, 0]", "stderr": ""},
            {"index": 4, "label": "negatives", "is_public": False, "status_id": 3,
             "status_description": "Accepted", "passed": False, "time": "0.03",
             "stdin": SECRET_STDIN, "expected": SECRET_EXPECTED,
             "stdout": SECRET_STDOUT, "stderr": ""},
        ],
    }


# ------------------------------------------------------------------ the view


def test_public_tests_keep_their_data(execution):
    view = redact.strip_for_view(execution)
    public = [t for t in view["tests"] if t["is_public"]]
    assert len(public) == 2
    for t in public:
        assert t["stdin"] and t["expected"] is not None and t["stdout"] is not None


def test_hidden_test_data_is_stripped(execution):
    view = redact.strip_for_view(execution)
    hidden = [t for t in view["tests"] if not t["is_public"]]
    assert len(hidden) == 1
    h = hidden[0]
    assert "stdin" not in h
    assert "expected" not in h
    assert "stdout" not in h
    # but the student still learns which case broke, and whether it passed
    assert h["label"] == "negatives"
    assert h["passed"] is False
    assert h["status"] == "Accepted"


def test_no_hidden_value_survives_anywhere_in_the_view(execution):
    """The blunt check: serialise the whole view and grep it."""
    blob = json.dumps(redact.strip_for_view(execution))
    assert SECRET_STDIN not in blob
    assert SECRET_STDOUT not in blob
    assert "-3, 4, 3, 90" not in blob


def test_counts_are_preserved(execution):
    view = redact.strip_for_view(execution)
    assert view["bucket"] == "WRONG_ANSWER"
    assert view["passed"] == 1
    assert view["total"] == 3
    assert len(view["tests"]) == 3


def test_none_execution_is_none():
    assert redact.strip_for_view(None) is None


def test_stderr_is_truncated():
    huge = {"bucket": "RUNTIME_ERROR", "passed": 0, "total": 1, "tests": [
        {"index": 1, "label": "basic", "is_public": True, "passed": False,
         "status_description": "Runtime Error", "stderr": "x" * 50_000}]}
    excerpt = redact.strip_for_view(huge)["tests"][0]["stderr_excerpt"]
    assert len(excerpt) < 2000
    assert excerpt.endswith("[truncated]")


# ---------------------------------------------------------- the tutor's view


def test_tutor_summary_hides_hidden_test_data(execution):
    summary = redact.summarize_for_tutor(execution)
    assert SECRET_STDIN not in summary
    assert SECRET_EXPECTED not in summary
    assert SECRET_STDOUT not in summary
    assert "-3, 4, 3, 90" not in summary


def test_tutor_summary_keeps_what_it_needs(execution):
    summary = redact.summarize_for_tutor(execution)
    assert "WRONG_ANSWER" in summary
    assert "1/3" in summary
    assert "negatives" in summary          # the label is the whole point
    assert "[hidden]" in summary
    assert '{"nums": [3, 2, 4], "target": 6}' in summary   # public data is fine


def test_first_failing_public_test(execution):
    t = redact.first_failing_public_test(execution)
    assert t["index"] == 2
    assert t["label"] == "middle pair"


def test_first_failing_public_test_skips_hidden(execution):
    for t in execution["tests"]:
        if t["is_public"]:
            t["passed"] = True
    assert redact.first_failing_public_test(execution) is None


# -------------------------------------------------------------- SessionView


def test_rationale_never_reaches_the_view(execution):
    values = {
        "problem_id": "two-sum",
        "phase": "CODE",
        "status": "CODE_WRITE",
        "last_eval": {
            "verdict": "PASS",
            "matched_approach": "lookup-single-pass",
            "missing_steps": [],
            "violated_invariants": [],
            "misconception_id": None,
            "confidence": 0.98,
            "cache_hit": False,
            "rationale": "TEACHER ONLY: the student nearly missed the ordering constraint.",
        },
        "last_execution": execution,
    }
    view = build_session_view(values, thread_id="abc", trace_id="t-1")

    assert "rationale" not in view["last_eval"]
    assert "TEACHER ONLY" not in json.dumps(view)
    assert view["last_eval"]["verdict"] == "PASS"
    assert view["last_eval"]["matched_approach"] == "lookup-single-pass"


def test_view_shape_matches_the_contract():
    view = build_session_view({}, thread_id="abc", trace_id="t-1")
    for key in ("thread_id", "problem_id", "phase", "status", "attempts",
                "accepted_logic", "messages", "last_eval", "last_execution", "debug"):
        assert key in view
    for key in ("trace_id", "last_node_path", "regenerations",
                "verifier_rejections", "fallback_used"):
        assert key in view["debug"]
    # null until they exist (section 5.2)
    assert view["last_eval"] is None
    assert view["last_execution"] is None
    assert view["attempts"] == {"logic": 0, "code": 0}


def test_view_strips_hidden_tests_end_to_end(execution):
    view = build_session_view({"last_execution": execution}, thread_id="abc")
    assert SECRET_STDIN not in json.dumps(view)
