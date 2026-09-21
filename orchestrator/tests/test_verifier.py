"""Unit tests for the deterministic verifier (CLAUDE.md section 6.4, D1-T4).

No LLM, no network, no database. These rules are the structural guarantee that
the tutor cannot hand over the answer, so they get tested properly.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

from app.verifier import (
    GENERIC_CODE_FALLBACK,
    GENERIC_LOGIC_FALLBACK,
    code_fallback,
    find_forbidden_terms,
    logic_fallback,
    verify_code_draft,
    verify_logic_draft,
)

# The real rubric, read from the generator so the tests cannot drift from what
# is actually seeded into the database.
_GEN = pathlib.Path(__file__).resolve().parents[2] / "db" / "seed" / "generate_two_sum.py"


@pytest.fixture(scope="module")
def rubric() -> dict:
    # import the generator as a module (it only defines things at import time;
    # main() is guarded), so the tests always see the rubric that is seeded
    spec = importlib.util.spec_from_file_location("generate_two_sum", _GEN)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.RUBRIC


# --------------------------------------------------------------------- logic


def test_clean_socratic_question_passes(rubric):
    draft = ("Agar array mein 20,000 numbers hon, toh tumhara approach kitne pairs "
             "check karega? Kya har pair ko dekhna sach mein zaroori hai?")
    result = verify_logic_draft(draft, rubric)
    assert result.ok, result.reasons


def test_english_socratic_question_passes(rubric):
    draft = "What do you already know by the time you reach the third number?"
    assert verify_logic_draft(draft, rubric).ok


def test_forbidden_term_hashmap_is_rejected(rubric):
    result = verify_logic_draft("Try using a hashmap to store what you have seen.", rubric)
    assert not result.ok
    assert any("hashmap" in r for r in result.reasons)


@pytest.mark.parametrize(
    "term",
    ["hashmap", "hash map", "hash table", "dictionary", "dict",
     "complement", "two pointer", "two pointers", "two-pointer"],
)
def test_every_rubric_forbidden_term_is_caught(rubric, term):
    result = verify_logic_draft(f"Maybe a {term} would help here?", rubric)
    assert not result.ok, f"{term!r} was not caught"


def test_forbidden_terms_are_case_insensitive(rubric):
    assert not verify_logic_draft("What about a HashMap?", rubric).ok
    assert not verify_logic_draft("Consider the COMPLEMENT.", rubric).ok


def test_forbidden_terms_respect_word_boundaries(rubric):
    # "dict" is forbidden; "contradictory" and "predict" must not trip it
    assert find_forbidden_terms("that is contradictory", rubric["forbidden_terms_logic_tutor"]) == []
    assert find_forbidden_terms("can you predict it", rubric["forbidden_terms_logic_tutor"]) == []
    assert find_forbidden_terms("use a dict", rubric["forbidden_terms_logic_tutor"]) == ["dict"]


def test_code_fence_is_rejected(rubric):
    draft = "Think about this:\n```\nseen = {}\n```\nWhat does it give you?"
    result = verify_logic_draft(draft, rubric)
    assert not result.ok
    assert any("code fence" in r for r in result.reasons)


@pytest.mark.parametrize(
    "line",
    ["for i in range(len(nums)):",
     "if target - x in seen:",
     "def two_sum(nums, target):",
     "while left < right:",
     "elif left > right:",
     "class Solution:"],
)
def test_code_like_lines_are_rejected(rubric, line):
    result = verify_logic_draft(f"Consider this:\n{line}\nWhat happens?", rubric)
    assert not result.ok, f"{line!r} slipped through"


@pytest.mark.parametrize("line", ["return [i, j]", "return (i, j)", "import json", "import sys"])
def test_colonless_code_lines_are_caught(rubric, line):
    """The section 6.4 gap, closed with human approval on 2026-09-21.

    The specified regex requires a trailing colon, so a bare ``return [i, j]`` or
    ``import json`` used to slip through. Two narrow patterns now close it:
    ``^\\s*return\\s*[\\[\\(]`` and ``^\\s*import\\s+\\w+\\s*$``.
    """
    result = verify_logic_draft(f"Consider this:\n{line}\nWhat happens?", rubric)
    assert not result.ok, f"{line!r} slipped through"


@pytest.mark.parametrize(
    "prose",
    [
        "Return the indices, not the values.",
        "What should your function return when it finds the pair?",
        "Tumhe return karna hai positions, numbers nahi.",
        "Think about what is important to remember as you go.",
        "The order you return them in does not matter.",
    ],
)
def test_new_patterns_do_not_fire_on_prose(rubric, prose):
    """The whole point of making the two new patterns narrow.

    A verifier that rejects ordinary tutoring language burns regenerations and
    pushes the tutor onto its canned fallback mid-demo, which is worse than the
    gap it closes.
    """
    result = verify_logic_draft(prose, rubric)
    assert result.ok, f"false positive on prose: {result.reasons}"


def test_the_same_colonless_lines_are_caught_inside_a_fence(rubric):
    # why the gap above is tolerable: the realistic delivery vehicle is caught
    for line in ("return [i, j]", "import json"):
        assert not verify_logic_draft(f"```\n{line}\n```", rubric).ok


def test_empty_container_assignment_is_rejected(rubric):
    assert not verify_logic_draft("Start with seen = {} and go from there.", rubric).ok
    assert not verify_logic_draft("What if results = [] at the start?", rubric).ok
    assert not verify_logic_draft("Try store = dict() first.", rubric).ok


def test_in_range_and_dot_get_are_rejected(rubric):
    assert not verify_logic_draft("What if you loop in range(n)?", rubric).ok
    assert not verify_logic_draft("Could you call .get(x) there?", rubric).ok


def test_over_long_draft_is_rejected(rubric):
    draft = "word " * 121
    result = verify_logic_draft(draft, rubric)
    assert not result.ok
    assert any("121 words" in r for r in result.reasons)


def test_draft_at_the_word_limit_passes(rubric):
    assert verify_logic_draft("word " * 120, rubric).ok


def test_empty_draft_is_rejected(rubric):
    assert not verify_logic_draft("", rubric).ok
    assert not verify_logic_draft("   \n  ", rubric).ok


def test_multiple_violations_are_all_reported(rubric):
    draft = "Use a hashmap:\n```\nseen = {}\n```\n" + "word " * 130
    result = verify_logic_draft(draft, rubric)
    assert not result.ok
    assert len(result.rejections) >= 3


def test_prose_that_merely_sounds_like_code_passes(rubric):
    # ordinary Hinglish tutoring language must not trip the code heuristics
    draft = ("Tum har number ke liye kya check kar rahe ho? Jo number tumne pehle "
             "dekha, kya woh yaad rehta hai?")
    assert verify_logic_draft(draft, rubric).ok


# ---------------------------------------------------------------------- code


def test_code_tutor_may_name_the_construct(rubric):
    draft = ("Your lookup assumes the value is already there. What does python do "
             "when you index a container with a key that was never stored?")
    assert verify_code_draft(draft, rubric).ok


def test_code_tutor_may_quote_a_short_snippet(rubric):
    draft = "Look at this line:\n```\nj = seen[target - x]\n```\nWhat if it is missing?"
    assert verify_code_draft(draft, rubric).ok, verify_code_draft(draft, rubric).reasons


def test_code_tutor_may_not_define_the_entrypoint(rubric):
    draft = "Here you go:\ndef two_sum(nums, target):\n    ..."
    result = verify_code_draft(draft, rubric)
    assert not result.ok
    assert any("entrypoint" in r for r in result.reasons)


def test_code_tutor_may_not_paste_a_long_block(rubric):
    draft = ("Try:\n```\nseen = {}\nfor i, x in enumerate(nums):\n"
             "    if target - x in seen:\n        return [seen[target - x], i]\n"
             "    seen[x] = i\n```")
    result = verify_code_draft(draft, rubric)
    assert not result.ok
    assert any("code block" in r for r in result.reasons)


def test_code_draft_word_limit(rubric):
    assert verify_code_draft("word " * 160, rubric).ok
    assert not verify_code_draft("word " * 161, rubric).ok


def test_code_phase_does_not_apply_logic_forbidden_terms(rubric):
    # by the code phase the student has already earned the concept
    assert verify_code_draft("Your dictionary lookup is unguarded.", rubric).ok


# ----------------------------------------------------------------- fallbacks


def test_logic_fallback_prefers_the_rubric_counter(rubric):
    text = logic_fallback(rubric, "nested-loop")
    assert "20,000" in text
    assert verify_logic_draft(text, rubric).ok, "the fallback must itself pass verification"


def test_every_rubric_counter_passes_verification(rubric):
    for m in rubric["misconceptions"]:
        result = verify_logic_draft(m["socratic_counter"], rubric)
        assert result.ok, f"{m['id']}: {result.reasons}"


def test_logic_fallback_falls_back_to_generic(rubric):
    assert logic_fallback(rubric, None) == GENERIC_LOGIC_FALLBACK
    assert logic_fallback(rubric, "no-such-misconception") == GENERIC_LOGIC_FALLBACK
    assert verify_logic_draft(GENERIC_LOGIC_FALLBACK, rubric).ok


def test_code_fallback_passes_verification(rubric):
    assert code_fallback() == GENERIC_CODE_FALLBACK
    assert verify_code_draft(GENERIC_CODE_FALLBACK, rubric).ok


def test_rubric_loaded_is_the_real_one(rubric):
    assert rubric["problem_id"] == "two-sum"
    assert rubric["entrypoint"] == "two_sum"
    assert len(rubric["forbidden_terms_logic_tutor"]) == 9
    json.dumps(rubric)  # must stay JSON-serialisable for the DB column
