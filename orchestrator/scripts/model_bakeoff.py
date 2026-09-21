#!/usr/bin/env python3
"""Pick an LLM by evidence rather than by guessing (CLAUDE.md trap 12).

The slug named in .env (google/gemini-2.0-flash-exp:free) no longer exists on
OpenRouter, and we are on a strict zero-budget constraint, so the model has to
come from the free tier. Free models vary wildly in whether they can hold a JSON
contract and whether they read Hinglish, and those are exactly the two things the
evaluator depends on.

This runs each candidate against the real fixtures and prints a scoreboard:

    uv run python scripts/model_bakeoff.py
    uv run python scripts/model_bakeoff.py --models a,b,c

Talks to OpenRouter directly so it can be run before LiteLLM is up.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.llm import LLMError, extract_json  # noqa: E402
from app.prompts.evaluator import EVALUATOR_SYSTEM, build_evaluator_user  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]

DEFAULT_CANDIDATES = [
    "z-ai/glm-5.2:free",
    "qwen/qwen3.8-27b:free",
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "thinkingmachines/inkling:free",
]

# (fixture file, expected verdict, expected approach, expected misconception)
CASES = [
    ("logic_f1.txt",  "FAIL", None,                   "nested-loop"),
    ("logic_f3.txt",  "PASS", "lookup-single-pass",   None),
    ("logic_f3b.txt", "PASS", "sort-two-pointer",     None),
    ("logic_f6.txt",  "FAIL", None,                   None),
]


def load_rubric_and_problem() -> tuple[dict, str, str]:
    gen = ROOT / "db" / "seed" / "generate_two_sum.py"
    spec = importlib.util.spec_from_file_location("generate_two_sum", gen)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.RUBRIC, mod.TITLE, mod.DESCRIPTION


def _call_with_backoff(client, model: str, user: str, attempts: int = 3) -> str:
    """One evaluator call, retrying through free-tier 429s.

    Free OpenRouter models are heavily contended, so a first-shot 429 says
    nothing about whether the model is usable. Only a model that 429s through
    all the backoff is genuinely unavailable to us.
    """
    last: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0,
                messages=[
                    {"role": "system", "content": EVALUATOR_SYSTEM},
                    {"role": "user", "content": user},
                ],
            )
            # an error payload can arrive with choices=None, which used to blow
            # up as "'NoneType' object is not subscriptable" and look like a
            # model failure rather than the transport failure it is
            if not getattr(resp, "choices", None):
                raise LLMError(f"no choices in response: {str(resp)[:200]}")
            return (resp.choices[0].message.content or "").strip()
        except Exception as e:                       # noqa: BLE001 - reported, not swallowed
            last = e
            if attempt < attempts and "429" in str(e):
                time.sleep(5 * attempt)
                continue
            raise
    raise last                                        # pragma: no cover


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", help="comma-separated slugs (default: a free-tier shortlist)")
    ap.add_argument("--base-url", default="https://openrouter.ai/api/v1")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        print("STOP: OPENROUTER_API_KEY is not set (source .env first)")
        return 2

    from openai import OpenAI
    client = OpenAI(base_url=args.base_url, api_key=key, timeout=120.0, max_retries=0)

    rubric, title, description = load_rubric_and_problem()
    candidates = args.models.split(",") if args.models else DEFAULT_CANDIDATES

    fixtures = ROOT / "demo" / "fixtures"
    scoreboard = []

    for model in candidates:
        print(f"\n=== {model} ===")
        correct = 0
        json_ok = 0
        total_time = 0.0
        notes = []

        for fname, want_verdict, want_approach, want_misconception in CASES:
            student_text = (fixtures / fname).read_text(encoding="utf-8")
            user = build_evaluator_user(
                title=title, description=description, rubric=rubric, student_text=student_text
            )

            t0 = time.perf_counter()
            try:
                raw = _call_with_backoff(client, model, user)
                took = time.perf_counter() - t0
                total_time += took
                data = json.loads(extract_json(raw))
                json_ok += 1
            except (LLMError, json.JSONDecodeError) as e:
                took = time.perf_counter() - t0
                total_time += took
                print(f"  {fname:<16} JSON FAIL after {took:5.1f}s  {type(e).__name__}")
                notes.append(f"{fname}: bad json")
                continue
            except Exception as e:                       # network / 404 / rate limit
                took = time.perf_counter() - t0
                total_time += took
                msg = str(e).replace("\n", " ")[:110]
                print(f"  {fname:<16} ERROR after {took:5.1f}s  {msg}")
                notes.append(f"{fname}: {type(e).__name__}")
                continue

            got_verdict = data.get("verdict")
            got_approach = data.get("matched_approach")
            got_misc = data.get("misconception_id")
            conf = data.get("confidence")

            hits = [got_verdict == want_verdict]
            if want_approach is not None:
                hits.append(got_approach == want_approach)
            if want_misconception is not None:
                hits.append(got_misc == want_misconception)
            good = all(hits)
            correct += 1 if good else 0

            print(f"  {fname:<16} {'OK ' if good else 'BAD'} {took:5.1f}s  "
                  f"verdict={got_verdict} approach={got_approach} "
                  f"misconception={got_misc} conf={conf}")
            if not good:
                notes.append(f"{fname}: wanted {want_verdict}/{want_approach}/{want_misconception}")

        scoreboard.append({
            "model": model,
            "correct": correct,
            "of": len(CASES),
            "json_ok": json_ok,
            "avg_s": total_time / len(CASES),
            "notes": notes,
        })

    print("\n\n=== SCOREBOARD ===")
    print(f"{'model':<46} {'correct':>8} {'json':>6} {'avg s':>7}")
    for row in sorted(scoreboard, key=lambda r: (-r["correct"], -r["json_ok"], r["avg_s"])):
        print(f"{row['model']:<46} {row['correct']}/{row['of']:<6} "
              f"{row['json_ok']}/{len(CASES):<4} {row['avg_s']:>6.1f}")
    print("\nPick the top row that also has json == %d/%d." % (len(CASES), len(CASES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
