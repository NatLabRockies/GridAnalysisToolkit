"""Single locked code path for DuckDB access from this extension.

DuckDB Python connections are not thread-safe: concurrent ``execute``
calls can race inside the C++ result machinery and crash the process
with ``InternalException: Attempted to dereference unique_ptr that is
NULL`` (which arrives as a SIGSEGV that takes the container down).

Every site in the extension that touches the shared connection must go
through ``_DuckDBGateway`` so the lock is held for both ``execute`` and
the follow-up fetch. The lock is the same RLock used by the server's
``DuckDBEngine`` (``ExtensionContext.duckdb_lock``), so chart queries
and extension reads serialize against each other on the same handle.

Lives in its own module so the contract can be tested without the
gridsight-sdk import chain.
"""

from __future__ import annotations

import threading
from typing import Any


class _DuckDBGateway:
    def __init__(self, conn: Any, lock: threading.RLock) -> None:
        self._conn = conn
        self._lock = lock

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    @property
    def raw(self) -> Any:
        """Escape hatch — only for code that must pass the underlying
        connection to a third party. Callers MUST wrap their use in
        ``with gateway.transaction():`` if they execute statements."""
        return self._conn

    def fetchall(self, sql: str, params: list | tuple | None = None) -> list:
        with self._lock:
            return self._conn.execute(sql, params or []).fetchall()

    def fetchone(self, sql: str, params: list | tuple | None = None):
        with self._lock:
            return self._conn.execute(sql, params or []).fetchone()

    def fetch_arrow(self, sql: str, params: list | tuple | None = None):
        with self._lock:
            result = self._conn.execute(sql, params or [])
            # DuckDB 2.x renamed fetch_arrow_table() to to_arrow_table().
            if hasattr(result, "to_arrow_table"):
                return result.to_arrow_table()
            return result.fetch_arrow_table()

    def execute(self, sql: str, params: list | tuple | None = None) -> None:
        """For DDL and statements with no result. Discards the cursor so
        no follow-up fetch can race outside the lock."""
        with self._lock:
            self._conn.execute(sql, params or [])

    def execute_silent(self, sql: str) -> None:
        """Like ``execute`` but swallows exceptions. For idempotent
        DETACH calls where the table may already be detached."""
        with self._lock:
            try:
                self._conn.execute(sql)
            except Exception:
                pass

    def transaction(self):
        """Context manager that holds the lock across multiple statements.

        Use for sequences that must not be interleaved with other queries
        (the ATTACH / write / DETACH dance, or any read that depends on
        a prior DDL). Yields the raw connection — callers use
        ``conn.execute(...)`` directly inside the ``with`` block."""
        gateway = self

        class _Txn:
            def __enter__(self):
                gateway._lock.acquire()
                return gateway._conn

            def __exit__(self, *exc):
                gateway._lock.release()
                return False

        return _Txn()
