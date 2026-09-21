"""PostgresSaver wiring (CLAUDE.md section 6.5, trap 4).

The four settings below are not optional and are the whole of trap 4:

    autocommit=True        LangGraph manages its own transaction boundaries;
                           leaving this False deadlocks on the first write
    prepare_threshold=0    psycopg 3 otherwise creates server-side prepared
                           statements that break across pooled connections
    row_factory=dict_row   PostgresSaver indexes rows by column name
    checkpointer.setup()   creates the checkpoint tables; called once at startup

Getting any of them wrong produces a failure that looks like a LangGraph bug
rather than a configuration one, which is exactly why it is a listed trap.
"""
from __future__ import annotations

import logging

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app import config

log = logging.getLogger(__name__)

_pool: ConnectionPool | None = None


def build_checkpointer() -> PostgresSaver:
    global _pool

    _pool = ConnectionPool(
        conninfo=config.DATABASE_URL,
        max_size=10,
        open=True,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )

    checkpointer = PostgresSaver(_pool)
    checkpointer.setup()

    log.info("PostgresSaver ready (pool max_size=10)")
    return checkpointer


def close_checkpointer() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
        log.info("checkpointer pool closed")
