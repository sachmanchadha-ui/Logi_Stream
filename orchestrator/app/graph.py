"""Graph wiring (CLAUDE.md section 6.1).

One long-running graph per session. Every student action is a resume of the
interrupt in await_input, which is why the whole conversation survives a service
restart once PostgresSaver goes in on Day 2.

    START -> await_input --(logic)--> evaluate_logic --PASS/FLAGGED--> summarize_logic -> await_input
                 |                          '--FAIL--> logic_tutor <=> verify_logic ---> await_input
                 '--(chat, LOGIC)--------------------> logic_tutor <=> verify_logic ---> await_input

The CODE-phase branch (execute_code, code_tutor, verify_code, finish) lands in
D2-T1; until then a code event routes harmlessly back to await_input.
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.nodes.await_input import await_input, route_after_input
from app.nodes.evaluate_logic import evaluate_logic, route_after_eval
from app.nodes.logic_tutor import logic_tutor, route_after_verify_logic, verify_logic
from app.nodes.summarize_logic import summarize_logic
from app.state import SessionState

log = logging.getLogger(__name__)


def build_graph(checkpointer=None):
    g = StateGraph(SessionState)

    g.add_node("await_input", await_input)
    g.add_node("evaluate_logic", evaluate_logic)
    g.add_node("logic_tutor", logic_tutor)
    g.add_node("verify_logic", verify_logic)
    g.add_node("summarize_logic", summarize_logic)

    g.add_edge(START, "await_input")

    g.add_conditional_edges(
        "await_input",
        route_after_input,
        {
            "evaluate_logic": "evaluate_logic",
            "logic_tutor": "logic_tutor",
            # D2-T1 replaces these two with the real code-phase nodes
            "execute_code": "await_input",
            "code_tutor": "await_input",
            "await_input": "await_input",
        },
    )

    g.add_conditional_edges(
        "evaluate_logic",
        route_after_eval,
        {"summarize_logic": "summarize_logic", "logic_tutor": "logic_tutor"},
    )

    # the verify loop: tutor -> verify -> (regenerate | deliver)
    g.add_edge("logic_tutor", "verify_logic")
    g.add_conditional_edges(
        "verify_logic",
        route_after_verify_logic,
        {"logic_tutor": "logic_tutor", "await_input": "await_input"},
    )

    g.add_edge("summarize_logic", "await_input")

    if checkpointer is None:
        # Day 1 runs on MemorySaver so that interrupt/resume bugs surface in the
        # CLI harness, separated from HTTP and Postgres (section 12).
        checkpointer = MemorySaver()

    return g.compile(checkpointer=checkpointer)


__all__ = ["build_graph", "END"]
