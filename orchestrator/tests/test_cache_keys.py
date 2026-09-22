"""Cache key namespacing (Day 3 summariser cache).

The two kinds share one table, so the only thing stopping a verdict being served
as a summary is that their keys differ. That is worth a test.
"""
from __future__ import annotations

from app.cache import cache_key, normalize


def test_verdict_and_summary_keys_differ_for_the_same_text():
    text = "Main array ko ek hi baar traverse karunga."
    assert cache_key("two-sum", 1, text, kind="verdict") != cache_key(
        "two-sum", 1, text, kind="summary"
    )


def test_default_kind_is_verdict():
    text = "some logic"
    assert cache_key("two-sum", 1, text) == cache_key("two-sum", 1, text, kind="verdict")


def test_key_is_stable():
    a = cache_key("two-sum", 1, "hello world", kind="summary")
    b = cache_key("two-sum", 1, "hello world", kind="summary")
    assert a == b and len(a) == 64


def test_rubric_version_busts_the_cache():
    """A rubric edit must not serve stale verdicts."""
    assert cache_key("two-sum", 1, "x") != cache_key("two-sum", 2, "x")


def test_problem_id_busts_the_cache():
    assert cache_key("two-sum", 1, "x") != cache_key("three-sum", 1, "x")


def test_normalisation_makes_trivial_edits_hit():
    """Whitespace and case only; anything else is a different answer."""
    assert normalize("  Hello   World  ") == "hello world"
    assert cache_key("two-sum", 1, "Hello   World") == cache_key("two-sum", 1, "hello world")
    assert cache_key("two-sum", 1, "hello world") != cache_key("two-sum", 1, "hello worlds")
