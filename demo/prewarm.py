#!/usr/bin/env python3
"""Warm the caches before the demo (CLAUDE.md D3-T4).

    cd orchestrator && uv run python ../demo/prewarm.py
    ...                                 ../demo/prewarm.py --check

Runs every logic fixture through the gateway, then resets the session so the
demo starts clean. Afterwards the scripted logic beats hit cache instead of the
LLM, which on the free tier turns a 30-90s wait into about a second.

Two things are warmed, not one. Caching only the verdict still left F3 -- the
"editor unlocks" beat -- paying for its own summarizer call, so summaries are
cached too. Both are filled by simply replaying the fixtures.

What is NOT cached, and cannot be: the tutor's replies. Those are generated
fresh every time and verified before delivery, so F1 still costs a live call.
That is the point of the product, so it stays live.

MUST be run AFTER the D3-T3 cold-start test: `docker compose down -v` destroys
the volume this fills (CLAUDE.md trap 10).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "demo" / "fixtures"
GATEWAY = os.environ.get("GATEWAY_URL", "http://localhost:8000")
PROBLEM = "two-sum"

# Only logic fixtures: they are what the evaluator and summariser cache on.
# F1 and F6 fail (verdict cached); F3 and F3b pass (verdict AND summary cached).
LOGIC_FIXTURES = [
    ("F1", "logic_f1.txt"),
    ("F6", "logic_f6.txt"),
    ("F3", "logic_f3.txt"),
    ("F3b", "logic_f3b.txt"),
]

GREEN = "\033[32m"; RED = "\033[31m"; DIM = "\033[2m"; BOLD = "\033[1m"; RESET = "\033[0m"


def call(path: str, payload: dict | None = None, timeout: float = 300.0) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        f"{GATEWAY}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.loads(res.read().decode("utf-8"))


def warm_one(label: str, fixture: str) -> tuple[bool, float, str]:
    text = (FIXTURES / fixture).read_text(encoding="utf-8")
    # each fixture needs its own clean session, or F3 would move the session to
    # the CODE phase and the later logic events would be rejected with 409
    call("/api/sessions/reset", {"problem_id": PROBLEM})
    call("/api/sessions/start", {"problem_id": PROBLEM})

    t0 = time.perf_counter()
    try:
        view = call(
            "/api/sessions/event",
            {"problem_id": PROBLEM, "type": "logic", "text": text},
        )
    except urllib.error.HTTPError as e:
        return False, time.perf_counter() - t0, f"HTTP {e.code}: {e.read()[:120]!r}"
    except Exception as e:                         # noqa: BLE001
        return False, time.perf_counter() - t0, str(e)[:120]

    took = time.perf_counter() - t0
    ev = view.get("last_eval") or {}
    note = (f"verdict={ev.get('verdict')} approach={ev.get('matched_approach')} "
            f"cache_hit={ev.get('cache_hit')}")
    return True, took, note


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="replay the fixtures and assert every one is a cache hit")
    args = ap.parse_args()

    mode = "CHECK" if args.check else "WARM"
    print(f"{BOLD}prewarm ({mode}){RESET}  gateway={GATEWAY}")

    try:
        call("/api/sessions/start", {"problem_id": PROBLEM})
    except Exception as e:                         # noqa: BLE001
        print(f"{RED}STOP: cannot reach the gateway at {GATEWAY}: {e}{RESET}")
        return 2

    failures = 0
    total = 0.0
    for label, fixture in LOGIC_FIXTURES:
        okay, took, note = warm_one(label, fixture)
        total += took
        if not okay:
            print(f"  {RED}FAIL{RESET} {label:<4} {took:5.1f}s  {note}")
            failures += 1
            continue

        hit = "cache_hit=True" in note
        if args.check and not hit:
            print(f"  {RED}MISS{RESET} {label:<4} {took:5.1f}s  {note}")
            failures += 1
        else:
            tag = f"{GREEN}hit {RESET}" if hit else f"{DIM}warm{RESET}"
            print(f"  {tag} {label:<4} {took:5.1f}s  {note}")

    # leave the demo session clean, whatever happened above
    try:
        call("/api/sessions/reset", {"problem_id": PROBLEM})
        call("/api/sessions/start", {"problem_id": PROBLEM})
        print(f"{DIM}  session reset - the UI will open on a fresh LOGIC phase{RESET}")
    except Exception as e:                         # noqa: BLE001
        print(f"{RED}  could not reset the session: {e}{RESET}")

    print()
    if failures:
        print(f"{RED}{BOLD}{failures} fixture(s) failed{RESET}  (total {total:.1f}s)")
        return 1

    if args.check:
        print(f"{GREEN}{BOLD}all fixtures served from cache{RESET}  (total {total:.1f}s)")
    else:
        print(f"{GREEN}{BOLD}caches warm{RESET}  (total {total:.1f}s)")
        print(f"{DIM}  verify with: uv run python ../demo/prewarm.py --check{RESET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
