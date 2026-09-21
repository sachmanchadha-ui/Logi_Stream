#!/usr/bin/env python3
"""Drive the graph from a terminal, with no HTTP in the way (D1-T4).

    uv run python scripts/cli_harness.py                 # interactive
    uv run python scripts/cli_harness.py --fixtures       # run the golden set

Interactive commands:
    logic: <text>     submit an algorithm description
    chat:  <text>     ask the tutor something
    state             dump the current state
    reset             start a fresh thread
    quit

Prints the node path, the verdict fields and the delivered tutor message for
every turn, which is what makes interrupt/resume bugs visible before Postgres
and FastAPI are added on Day 2.
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
import time
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from langgraph.types import Command  # noqa: E402

from app import config, domain_client, llm  # noqa: E402
from app.graph import build_graph  # noqa: E402
from app.state import initial_state  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "demo" / "fixtures"

DIM = "\033[2m"; BOLD = "\033[1m"; RED = "\033[31m"; GREEN = "\033[32m"
YELLOW = "\033[33m"; CYAN = "\033[36m"; RESET = "\033[0m"


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)-5s %(name)-28s %(message)s",
        datefmt="%H:%M:%S",
    )


def show_turn(state: dict, elapsed: float, seen_messages: int) -> int:
    path = state.get("node_path") or []
    print(f"{DIM}  node path : {' -> '.join(path)}{RESET}")

    ev = state.get("last_eval")
    if ev:
        colour = GREEN if ev["verdict"] == "PASS" else (YELLOW if ev["verdict"] == "FLAGGED" else RED)
        print(f"  verdict   : {colour}{ev['verdict']}{RESET}"
              f"   approach={ev.get('matched_approach')}"
              f"   misconception={ev.get('misconception_id')}"
              f"   confidence={ev.get('confidence')}"
              f"   cache_hit={ev.get('cache_hit')}")
        if ev.get("missing_steps"):
            print(f"{DIM}  missing   : {'; '.join(ev['missing_steps'])}{RESET}")
        if ev.get("violated_invariants"):
            print(f"{DIM}  violated  : {'; '.join(ev['violated_invariants'])}{RESET}")

    rejections = state.get("verifier_rejections") or []
    if rejections:
        print(f"{YELLOW}  verifier  : {len(rejections)} rejection(s){RESET}")
        for r in rejections:
            print(f"{DIM}              - {r['reason']}{RESET}")
    if state.get("fallback_used"):
        print(f"{YELLOW}  fallback  : canned reply used (regenerations exhausted){RESET}")

    messages = state.get("messages") or []
    for m in messages[seen_messages:]:
        if m["role"] == "student":
            continue
        tag = f"{CYAN}tutor{RESET}" if m["role"] == "tutor" else f"{DIM}system{RESET}"
        print(f"\n  {tag}: {m['text']}\n")

    print(f"{DIM}  phase={state.get('phase')} status={state.get('status')} "
          f"attempts={state.get('attempts')} took={elapsed:.1f}s{RESET}")
    return len(messages)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", default="two-sum")
    ap.add_argument("--fixtures", action="store_true", help="run the golden set and exit")
    ap.add_argument("--verbose", "-v", action="store_true")
    args = ap.parse_args()
    setup_logging(args.verbose)

    print(f"{BOLD}LogiStream CLI harness{RESET}")
    print(f"  llm       : {json.dumps(llm.describe())}")
    print(f"  domain    : {config.DOMAIN_URL} (healthy={domain_client.health()})")

    if not domain_client.health():
        print(f"{RED}STOP: the Java domain service is not reachable. Start it first.{RESET}")
        return 2

    try:
        ctx = domain_client.get_problem_context(args.problem)
        print(f"  problem   : {ctx['title']} (rubric v{ctx.get('rubric_version')})\n")
    except Exception as e:
        print(f"{RED}STOP: {e}{RESET}")
        return 2

    if args.fixtures:
        return run_fixtures(args.problem)
    return interactive(args.problem)


def new_session(problem_id: str, thread_id: str | None = None):
    graph = build_graph()
    thread_id = thread_id or f"cli-{uuid.uuid4().hex[:12]}"
    cfg = {"configurable": {"thread_id": thread_id}}
    graph.invoke(initial_state(problem_id, "demo-user", thread_id), cfg)
    return graph, cfg, thread_id


def send(graph, cfg, etype: str, text: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    graph.invoke(Command(resume={"type": etype, "text": text}), cfg)
    # build the view from get_state, never from invoke's return shape (section 5.3)
    return graph.get_state(cfg).values, time.perf_counter() - t0


def interactive(problem_id: str) -> int:
    graph, cfg, thread_id = new_session(problem_id)
    print(f"{DIM}thread {thread_id}{RESET}")
    seen = 0

    while True:
        try:
            line = input(f"{BOLD}> {RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line:
            continue
        if line in ("quit", "exit"):
            return 0
        if line == "state":
            print(json.dumps(graph.get_state(cfg).values, indent=2, default=str))
            continue
        if line == "reset":
            graph, cfg, thread_id = new_session(problem_id)
            seen = 0
            print(f"{DIM}new thread {thread_id}{RESET}")
            continue

        if ":" not in line:
            print(f"{DIM}use 'logic: ...' or 'chat: ...'{RESET}")
            continue
        etype, text = line.split(":", 1)
        etype, text = etype.strip(), text.strip()
        if etype not in ("logic", "chat"):
            print(f"{DIM}unknown command {etype!r}{RESET}")
            continue

        try:
            state, elapsed = send(graph, cfg, etype, text)
            seen = show_turn(state, elapsed, seen)
        except Exception as e:                   # noqa: BLE001 - surfaced, not hidden
            print(f"{RED}  ERROR: {type(e).__name__}: {e}{RESET}")


# --------------------------------------------------------------------------
# golden set (D1-T4 verify)
# --------------------------------------------------------------------------

CASES = [
    ("F1",  "logic", "logic_f1.txt",  {"verdict": "FAIL", "misconception_id": "nested-loop"}),
    ("F2",  "chat",  "chat_f2.txt",   {"tutor_reply": True}),
    ("F3",  "logic", "logic_f3.txt",  {"verdict": "PASS", "matched_approach": "lookup-single-pass",
                                       "phase": "CODE"}),
    ("F3b", "logic", "logic_f3b.txt", {"verdict": "PASS", "matched_approach": "sort-two-pointer",
                                       "phase": "CODE"}, "fresh"),
    ("F6",  "logic", "logic_f6.txt",  {"verdict": "FAIL"}, "fresh"),
    ("F3c", "logic", "logic_f3.txt",  {"verdict": "PASS", "cache_hit": True}, "fresh"),
]


def run_fixtures(problem_id: str) -> int:
    import importlib.util
    gen = ROOT / "db" / "seed" / "generate_two_sum.py"
    spec = importlib.util.spec_from_file_location("generate_two_sum", gen)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    forbidden = mod.RUBRIC["forbidden_terms_logic_tutor"]

    from app.verifier import find_forbidden_terms

    graph, cfg, thread_id = new_session(problem_id)
    seen = 0
    rows = []
    failures = 0

    for case in CASES:
        cid, etype, fixture, expect = case[0], case[1], case[2], case[3]
        if len(case) > 4 and case[4] == "fresh":
            graph, cfg, thread_id = new_session(problem_id)
            seen = 0

        text = (FIXTURES / fixture).read_text(encoding="utf-8")
        print(f"\n{BOLD}=== {cid}  ({etype}: {fixture}){RESET}")
        print(f"{DIM}  {text[:110]}{'...' if len(text) > 110 else ''}{RESET}")

        try:
            state, elapsed = send(graph, cfg, etype, text)
        except Exception as e:                   # noqa: BLE001
            print(f"{RED}  ERROR: {type(e).__name__}: {e}{RESET}")
            rows.append((cid, "ERROR", "-", "-", "-", f"{type(e).__name__}"))
            failures += 1
            continue

        seen = show_turn(state, elapsed, seen)

        ev = state.get("last_eval") or {}
        problems = []
        for field, want in expect.items():
            if field == "tutor_reply":
                got = any(m["role"] == "tutor" for m in (state.get("messages") or []))
                if not got:
                    problems.append("no tutor reply")
            elif field == "phase":
                if state.get("phase") != want:
                    problems.append(f"phase={state.get('phase')} wanted {want}")
            else:
                if ev.get(field) != want:
                    problems.append(f"{field}={ev.get(field)!r} wanted {want!r}")

        # every delivered tutor turn must be free of forbidden terms
        for m in (state.get("messages") or []):
            if m["role"] == "tutor":
                hits = find_forbidden_terms(m["text"], forbidden)
                if hits:
                    problems.append(f"tutor said forbidden term(s): {hits}")

        if problems:
            failures += 1
            print(f"{RED}  FAIL: {'; '.join(problems)}{RESET}")
        else:
            print(f"{GREEN}  OK{RESET}")

        rows.append((
            cid,
            ev.get("verdict", "-"),
            str(ev.get("matched_approach")),
            str(ev.get("misconception_id")),
            str(ev.get("cache_hit")),
            "OK" if not problems else "; ".join(problems),
        ))

    print(f"\n\n{BOLD}=== FIXTURE VERDICT TABLE ==={RESET}")
    print(f"| {'Id':<4} | {'Verdict':<8} | {'Approach':<20} | {'Misconception':<14} | {'Cache':<5} | Result |")
    print(f"|{'-'*6}|{'-'*10}|{'-'*22}|{'-'*16}|{'-'*7}|--------|")
    for r in rows:
        print(f"| {r[0]:<4} | {r[1]:<8} | {r[2]:<20} | {r[3]:<14} | {r[4]:<5} | {r[5]} |")

    print()
    if failures:
        print(f"{RED}{failures} fixture(s) FAILED{RESET}")
    else:
        print(f"{GREEN}all fixtures passed{RESET}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
