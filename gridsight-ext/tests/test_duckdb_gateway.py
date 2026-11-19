"""Concurrency and correctness tests for ``_DuckDBGateway``.

Why these exist: a prior version of this extension touched the shared
DuckDB connection from many call sites, only some of which held the
serialization lock. Under concurrent FastAPI requests this raced inside
DuckDB's C++ result machinery and crashed the container with
``InternalException: Attempted to dereference unique_ptr that is NULL``
(SIGSEGV). The gateway makes that impossible by routing every read and
write through one locked code path. These tests pin that contract.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

# Load _gateway directly by file path so the test doesn't have to drag
# in gridsight-sdk just to verify locking semantics. The gateway is
# self-contained — only depends on threading + the duckdb conn passed
# at construction time.
_GATEWAY_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "gridsight_gat" / "_gateway.py"
)
_spec = importlib.util.spec_from_file_location("_gateway_under_test", _GATEWAY_PATH)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["_gateway_under_test"] = _mod
_spec.loader.exec_module(_mod)
_DuckDBGateway = _mod._DuckDBGateway


@pytest.fixture
def gateway():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE t (id INTEGER, val DOUBLE)")
    conn.execute(
        "INSERT INTO t SELECT i AS id, i * 1.5 AS val " "FROM range(0, 10000) AS r(i)"
    )
    gw = _DuckDBGateway(conn, threading.RLock())
    yield gw
    conn.close()


def test_fetchall_returns_rows(gateway):
    rows = gateway.fetchall("SELECT id, val FROM t WHERE id < 5 ORDER BY id")
    assert rows == [(0, 0.0), (1, 1.5), (2, 3.0), (3, 4.5), (4, 6.0)]


def test_fetchone_returns_single_row(gateway):
    row = gateway.fetchone("SELECT COUNT(*) FROM t")
    assert row == (10000,)


def test_fetch_arrow_returns_table(gateway):
    table = gateway.fetch_arrow("SELECT id, val FROM t ORDER BY id")
    assert table.num_rows == 10000
    assert table.column_names == ["id", "val"]


def test_execute_runs_ddl(gateway):
    gateway.execute("CREATE TABLE t2 (x INTEGER)")
    gateway.execute("INSERT INTO t2 VALUES (1), (2), (3)")
    assert gateway.fetchone("SELECT SUM(x) FROM t2") == (6,)


def test_execute_silent_swallows_errors(gateway):
    # DETACH of a non-attached schema would normally raise; execute_silent
    # is the replacement for the previous try/except idiom around DETACH.
    gateway.execute_silent("DETACH does_not_exist")  # must not raise


def test_parametrized_query(gateway):
    rows = gateway.fetchall("SELECT id FROM t WHERE id = ?", [42])
    assert rows == [(42,)]


def test_transaction_yields_raw_conn_under_lock(gateway):
    with gateway.transaction() as conn:
        conn.execute("CREATE TABLE in_txn (n INTEGER)")
        conn.execute("INSERT INTO in_txn VALUES (1)")
        # Lock is reentrant — a nested gateway call must work.
        n = gateway.fetchone("SELECT n FROM in_txn")
        assert n == (1,)


# ──────────────────────────────────────────────────────────────────────
# Concurrency tests — these are the regression bar for the segfault.
#
# Without the gateway, hammering a single DuckDB connection with
# concurrent execute() calls crashes the process. With the gateway every
# call serializes on the shared lock, so all N workers must complete
# without exception and all results must be correct.
# ──────────────────────────────────────────────────────────────────────


def _hammer(gateway, n_threads, n_iters_per_thread, query_fn):
    """Run query_fn(gateway, i) on n_threads workers, n_iters_per_thread
    times each. Return (results, errors)."""
    results: list = []
    errors: list[BaseException] = []
    results_lock = threading.Lock()

    def worker(thread_idx: int):
        for i in range(n_iters_per_thread):
            try:
                r = query_fn(gateway, thread_idx, i)
                with results_lock:
                    results.append(r)
            except BaseException as e:  # noqa: BLE001
                with results_lock:
                    errors.append(e)
                raise

    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        futures = [ex.submit(worker, t) for t in range(n_threads)]
        for f in as_completed(futures):
            # Re-raise the first per-thread exception so pytest sees it.
            f.result()

    return results, errors


def test_concurrent_fetchall_no_races(gateway):
    """16 threads × 50 iterations = 800 concurrent SELECTs.

    Pre-gateway, this reliably segfaulted on a multi-core box. With the
    gateway, every result must equal the canonical answer.
    """
    expected_count = 10000

    def q(gw, _t, _i):
        return gw.fetchone("SELECT COUNT(*) FROM t")[0]

    results, errors = _hammer(gateway, n_threads=16, n_iters_per_thread=50, query_fn=q)
    assert errors == []
    assert len(results) == 16 * 50
    assert all(r == expected_count for r in results)


def test_concurrent_fetch_arrow_no_races(gateway):
    """Arrow fetch is the dataset-streaming hot path — same one that
    crashed in production. Replays it under heavy concurrency."""

    def q(gw, t, i):
        # Vary the predicate per call so the planner does real work
        # rather than serving from a result cache.
        cutoff = (t * 100 + i) % 9999
        tbl = gw.fetch_arrow("SELECT id, val FROM t WHERE id < ?", [cutoff])
        return (cutoff, tbl.num_rows)

    results, errors = _hammer(gateway, n_threads=8, n_iters_per_thread=40, query_fn=q)
    assert errors == []
    for cutoff, rows in results:
        assert rows == cutoff


def test_concurrent_mixed_read_write(gateway):
    """Writers create per-thread tables while readers query the base
    table. Mirrors the production pattern of catmap materialization
    racing with chart queries on the same connection."""
    gateway.execute("CREATE SCHEMA scratch")

    def op(gw, t, i):
        if i % 2 == 0:
            tbl_name = f"scratch.t_{t}_{i}"
            gw.execute(
                f"CREATE OR REPLACE TABLE {tbl_name} AS SELECT * FROM t LIMIT 10"
            )
            return ("write", tbl_name)
        else:
            return ("read", gw.fetchone("SELECT COUNT(*) FROM t")[0])

    results, errors = _hammer(gateway, n_threads=8, n_iters_per_thread=20, query_fn=op)
    assert errors == []
    reads = [v for kind, v in results if kind == "read"]
    assert all(r == 10000 for r in reads)


def test_transaction_is_atomic_under_concurrency(gateway):
    """Multi-statement transaction blocks must not interleave with
    other queries. Tag each row with (owner, iter) and verify that
    inside the transaction, after inserting both this iter's rows, the
    count for this exact (owner, iter) is 2 — never 1 (would mean an
    outside reader saw the half-written state) and never >2 (would mean
    another writer wrote against our key, which we don't do)."""
    gateway.execute("CREATE TABLE txn_test (owner INTEGER, iter INTEGER, n INTEGER)")

    def op(gw, t, i):
        with gw.transaction() as conn:
            # Insert this iter's two rows. If another worker's
            # statements interleaved, an outside-the-txn reader thread
            # would see (t, i, 1) without (t, i, 2) — but no such
            # reader exists; instead we verify the inside view is
            # exactly the two rows we just inserted.
            conn.execute("INSERT INTO txn_test VALUES (?, ?, 1)", [t, i])
            mid = conn.execute(
                "SELECT COUNT(*) FROM txn_test WHERE owner = ? AND iter = ?",
                [t, i],
            ).fetchone()[0]
            conn.execute("INSERT INTO txn_test VALUES (?, ?, 2)", [t, i])
            after = conn.execute(
                "SELECT COUNT(*) FROM txn_test WHERE owner = ? AND iter = ?",
                [t, i],
            ).fetchone()[0]
            assert mid == 1, f"thread {t} iter {i} saw {mid} mid-txn rows"
            assert after == 2, f"thread {t} iter {i} saw {after} post-txn rows"
        return t

    _results, errors = _hammer(gateway, n_threads=8, n_iters_per_thread=10, query_fn=op)
    assert errors == []
    rows = gateway.fetchall(
        "SELECT owner, COUNT(*) FROM txn_test GROUP BY owner ORDER BY owner"
    )
    assert rows == [(t, 20) for t in range(8)]
