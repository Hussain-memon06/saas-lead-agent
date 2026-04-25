"""Async Postgres checkpointer factory for LangGraph state persistence."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def postgres_checkpointer(
    url: str | None = None,
) -> AsyncIterator[AsyncPostgresSaver]:
    """Async context manager that yields a ready-to-use AsyncPostgresSaver.

    Opens a psycopg3 connection pool, runs idempotent DDL (setup()), yields
    the checkpointer, then closes the pool on exit.

    Args:
        url: PostgreSQL DSN.  Defaults to the ``POSTGRES_URL`` env var.
             Format: ``postgresql://user:pass@host:5432/dbname``

    Raises:
        KeyError: if ``url`` is None and ``POSTGRES_URL`` is not set.
    """
    conn_url = url or os.environ["POSTGRES_URL"]
    async with AsyncPostgresSaver.from_conn_string(conn_url) as checkpointer:
        await checkpointer.setup()
        yield checkpointer
