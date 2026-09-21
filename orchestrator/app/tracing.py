"""Trace id propagation (CLAUDE.md section 1.7).

Every service logs the trace id on every request, and Python additionally logs
every graph node transition. Those logs are part of the demo: the examiner sees
one id travel browser -> Rust -> Python -> Java.

A ContextVar carries it, so node code does not have to thread a parameter
through every function just to log it.
"""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

HEADER = "X-Trace-Id"

_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace_id(value: str | None) -> str:
    tid = value or f"orch-{uuid.uuid4()}"
    _trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    return _trace_id.get()


class TraceIdFilter(logging.Filter):
    """Injects trace_id into every record so the format string can use it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id()
        return True


LOG_FORMAT = "%(asctime)s %(levelname)-5s [trace=%(trace_id)s] %(name)-26s %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    handler.addFilter(TraceIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn keeps its own handlers otherwise, and those lines would have no id
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True

    logging.getLogger("httpx").setLevel(logging.WARNING)
