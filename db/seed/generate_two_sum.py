#!/usr/bin/env python3
"""Generate db/init/02_seed.sql for the Two Sum problem (CLAUDE.md section 7.2).

Run:  python db/seed/generate_two_sum.py

Everything here is deterministic: the same input always produces the same SQL,
so the seed can be regenerated and diffed. The large test is constructed so
that exactly one pair sums to the target, and the generator asserts it.
"""
from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

PROBLEM_ID = "two-sum"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "db" / "init" / "02_seed.sql"

TITLE = "Two Sum"

DESCRIPTION = """\
Given an array of integers `nums` and an integer `target`, return the indices of
the two numbers that add up to `target`.

Exactly one valid answer exists. You may not use the same element twice. Return
the indices in any order.

**Constraints**

- `2 <= n <= 20,000`
- Your solution must be faster than checking every pair.
"""

EXAMPLES = [
    {
        "input": "nums = [2, 7, 11, 15], target = 9",
        "output": "[0, 1]",
        "explanation": "nums[0] + nums[1] == 2 + 7 == 9, so the answer is [0, 1].",
    },
    {
        "input": "nums = [3, 2, 4], target = 6",
        "output": "[1, 2]",
        "explanation": "nums[1] + nums[2] == 2 + 4 == 6. The same element may not "
                       "be used twice.",
    },
]

STARTER_CODE = """\
def two_sum(nums, target):
    pass
"""

# Appended by Java after the student's code. Reads one JSON object from stdin
# and prints the sorted index pair as JSON.
HARNESS_PYTHON = """\
import sys as _sys, json as _json
_data = _json.loads(_sys.stdin.read())
print(_json.dumps(sorted(list(two_sum(_data["nums"], _data["target"])))))
"""

RUBRIC = {
    "problem_id": "two-sum",
    "rubric_version": 1,
    "entrypoint": "two_sum",
    "approaches": [
        {
            "id": "lookup-single-pass",
            "label": "Single pass with a lookup of previously seen values",
            "steps": [
                "go through the array once",
                "for each element, compute the value still needed to reach the target",
                "check whether that needed value was already seen",
                "if seen, return its stored index together with the current index",
                "otherwise remember the current value with its index",
            ],
            "complexity": "O(n) time",
        },
        {
            "id": "sort-two-pointer",
            "label": "Sort value-index pairs, then move two pointers inward",
            "steps": [
                "pair each value with its original index",
                "sort the pairs by value",
                "start one pointer at each end",
                "if the sum is too small move the left pointer right; if too large move the right pointer left",
                "when the sum equals the target return the two ORIGINAL indices",
            ],
            "complexity": "O(n log n) time",
        },
    ],
    "invariants": [
        "returns indices, not values",
        "never uses the same element twice",
        "is faster than checking every pair (better than O(n^2))",
        "describes when the search stops",
    ],
    "misconceptions": [
        {
            "id": "nested-loop",
            "pattern": "checks every pair with two nested loops",
            "socratic_counter": "Agar array mein 20,000 numbers hon, toh tumhara approach kitne pairs check karega? Kya har pair ko dekhna sach mein zaroori hai?",
        },
        {
            "id": "returns-values",
            "pattern": "returns the numbers instead of their positions",
            "socratic_counter": "Question dhyan se padho — woh numbers maang raha hai, ya unki positions?",
        },
        {
            "id": "same-element-twice",
            "pattern": "may pair an element with itself",
            "socratic_counter": "Agar target 6 hai aur array mein sirf ek 3 hai, kya tumhara logic galti se 3 + 3 bana dega?",
        },
        {
            "id": "sort-loses-indices",
            "pattern": "sorts and then returns indices from the sorted array",
            "socratic_counter": "Sort karne ke baad, kya har number ki position wahi rehti hai jo original array mein thi?",
        },
    ],
    "forbidden_terms_logic_tutor": [
        "hashmap", "hash map", "hash table", "dictionary", "dict",
        "complement", "two pointer", "two pointers", "two-pointer",
    ],
}

CPU_TIME_LIMIT = 2
WALL_TIME_LIMIT = 5
MEMORY_LIMIT_KB = 128000


# --------------------------------------------------------------------------
# test construction
# --------------------------------------------------------------------------

def stdin_for(nums, target):
    return json.dumps({"nums": nums, "target": target})


def expected_for(indices):
    # must match the harness byte for byte: json.dumps(sorted(...))
    return json.dumps(sorted(indices))


def build_large_test(n=20_000, seed=1337):
    """Build an n-element array with exactly one pair summing to target.

    Uniqueness comes from residues mod 4, which is cheap to reason about and
    cheap to verify:

      * every filler value is  == 1 (mod 4)  ->  filler + filler == 2 (mod 4)
      * a == 1 (mod 4), b == 3 (mod 4)       ->  target = a + b  == 0 (mod 4)

    So no filler pair can hit the target. A filler could only pair with b if it
    equalled target - b == a, and a is deliberately excluded from the fillers.
    The answer sits at the last two positions, which forces a nested-loop
    solution to do the full ~2*10^8 iteration scan before it finds anything.
    """
    rng = random.Random(seed)

    pool = [1 + 4 * k for k in range(60_000)]      # all == 1 (mod 4)
    rng.shuffle(pool)

    fillers = pool[: n - 2]
    a = pool[n - 2]                                # == 1 (mod 4), not among fillers
    b = 1_000_003                                  # == 3 (mod 4), far outside the pool
    target = a + b                                 # == 0 (mod 4)

    nums = fillers + [a, b]
    answer = [n - 2, n - 1]

    assert len(nums) == n
    assert a % 4 == 1 and b % 4 == 3 and target % 4 == 0
    assert nums[answer[0]] + nums[answer[1]] == target
    return nums, target, answer


def count_pairs(nums, target):
    """Number of index pairs i < j with nums[i] + nums[j] == target. O(n)."""
    counts = Counter(nums)
    total = 0
    for v, cv in counts.items():
        w = target - v
        if w not in counts:
            continue
        if w == v:
            total += cv * (cv - 1) // 2
        elif v < w:
            total += cv * counts[w]
    return total


def build_tests():
    tests = []

    def add(idx, label, is_public, nums, target, answer):
        assert count_pairs(nums, target) == 1, (
            "test %d (%s) has a non-unique answer" % (idx, label))
        assert nums[answer[0]] + nums[answer[1]] == target
        assert answer[0] != answer[1], (
            "test %d uses the same element twice" % idx)
        tests.append({
            "idx": idx,
            "label": label,
            "is_public": is_public,
            "stdin": stdin_for(nums, target),
            "expected_output": expected_for(answer),
        })

    add(1, "basic",       True,  [2, 7, 11, 15], 9, [0, 1])
    add(2, "middle pair", True,  [3, 2, 4],      6, [1, 2])
    add(3, "duplicates",  False, [3, 3],         6, [0, 1])
    add(4, "negatives",   False, [-3, 4, 3, 90], 0, [0, 2])

    nums, target, answer = build_large_test()
    add(5, "large input (n=20,000)", False, nums, target, answer)

    return tests


# --------------------------------------------------------------------------
# SQL emission
# --------------------------------------------------------------------------

def dollar_quote(value, tag):
    """Dollar-quote a literal. Avoids backslash/quote escaping entirely."""
    marker = "$" + tag + "$"
    assert marker not in value, "dollar-quote tag %s collides with the value" % marker
    return marker + value + marker


def main():
    tests = build_tests()

    rows = []
    for t in tests:
        rows.append(
            "  (%s, %d, %s, %s, %s, %s)" % (
                dollar_quote(PROBLEM_ID, "pid"),
                t["idx"],
                dollar_quote(t["label"], "lbl"),
                "TRUE" if t["is_public"] else "FALSE",
                dollar_quote(t["stdin"], "sin"),
                dollar_quote(t["expected_output"], "exp"),
            )
        )
    rows_sql = ",\n".join(rows)

    sql = """\
-- GENERATED FILE - do not edit by hand.
-- Regenerate with:  python db/seed/generate_two_sum.py
-- Source of truth:  db/seed/generate_two_sum.py  (CLAUDE.md section 7.2)

INSERT INTO app.users (id, display_name) VALUES
  ('demo-user', 'Demo Student')
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.problems (
  id, title, description, examples, starter_code, harness_python,
  rubric, rubric_version, cpu_time_limit, wall_time_limit, memory_limit_kb
) VALUES (
  {pid},
  {title},
  {description},
  {examples}::jsonb,
  {starter},
  {harness},
  {rubric}::jsonb,
  {rubric_version},
  {cpu},
  {wall},
  {mem}
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO app.hidden_tests (problem_id, idx, label, is_public, stdin, expected_output) VALUES
{rows}
ON CONFLICT (problem_id, idx) DO NOTHING;
""".format(
        pid=dollar_quote(PROBLEM_ID, "pid"),
        title=dollar_quote(TITLE, "ttl"),
        description=dollar_quote(DESCRIPTION, "desc"),
        examples=dollar_quote(json.dumps(EXAMPLES, indent=2), "ex"),
        starter=dollar_quote(STARTER_CODE, "starter"),
        harness=dollar_quote(HARNESS_PYTHON, "harness"),
        rubric=dollar_quote(json.dumps(RUBRIC, indent=2, ensure_ascii=False), "rub"),
        rubric_version=RUBRIC["rubric_version"],
        cpu=CPU_TIME_LIMIT,
        wall=WALL_TIME_LIMIT,
        mem=MEMORY_LIMIT_KB,
        rows=rows_sql,
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(sql)

    print("wrote %s  (%s bytes)" % (OUT.relative_to(ROOT), format(len(sql), ",")))
    print("  problem   : %s (rubric_version %d)" % (PROBLEM_ID, RUBRIC["rubric_version"]))
    print("  tests     : %d  (public: %d)" % (
        len(tests), sum(1 for t in tests if t["is_public"])))
    for t in tests:
        print("    %d  %-26s public=%-5s expected=%-16s stdin=%sB" % (
            t["idx"], t["label"], t["is_public"], t["expected_output"],
            format(len(t["stdin"]), ",")))
    print("  assertions: unique answer verified for every test (count_pairs == 1)")


if __name__ == "__main__":
    main()
