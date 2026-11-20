"""``transpose_day`` must give the same partition as the PIVOT query it
replaced (one ``datetime`` row per hour, one float64 column per entity,
entities sorted, first row wins for duplicate ids), without the PIVOT's
memory cost on wide tables."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import duckdb
import pytest

_PATH = Path(__file__).resolve().parents[1] / "src" / "gridsight_gat" / "_partitions.py"
_spec = importlib.util.spec_from_file_location("_partitions", _PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
transpose_day = _mod.transpose_day

DATE = "2019-08-15"
HOURS = [f"{DATE}T{h:02d}:00:00" for h in range(3)]


@pytest.fixture()
def con():
    c = duckdb.connect()
    cols = ", ".join(f'"{h}" FLOAT' for h in HOURS + ["2019-08-16T00:00:00"])
    c.execute(f"CREATE TABLE flows (entity_id VARCHAR, {cols})")
    rows = [
        ("line-b", 1.5, None, -2.0, 9.0),
        ("line-a", 0.0, 3.25, 4.0, 9.0),
        ("line-c", -1.0, -1.0, None, 9.0),
        ("line-a", 99.0, 99.0, 99.0, 9.0),  # duplicate id: first row wins
    ]
    c.executemany("INSERT INTO flows VALUES (?, ?, ?, ?, ?)", rows)
    return c


def _arrow(c, sql):
    res = c.execute(sql)
    return (
        res.to_arrow_table()
        if hasattr(res, "to_arrow_table")
        else res.fetch_arrow_table()
    )


def test_matches_pivot(con):
    up = ", ".join(f'"{h}"' for h in HOURS)
    old = _arrow(
        con,
        f"WITH u AS (SELECT entity_id, ts AS datetime, CAST(val AS DOUBLE) AS val "
        f"FROM flows UNPIVOT INCLUDE NULLS (val FOR ts IN ({up}))) "
        f"PIVOT u ON entity_id USING first(val) ORDER BY datetime",
    )
    sel = ", ".join(f'CAST("{h}" AS DOUBLE) AS "{h}"' for h in HOURS)
    wide = _arrow(
        con, f"SELECT CAST(entity_id AS VARCHAR) AS entity_id, {sel} FROM flows"
    )
    new = transpose_day(wide, HOURS)

    assert new.column_names == ["datetime", "line-a", "line-b", "line-c"]
    assert new.column_names == old.column_names
    assert new.column("datetime").to_pylist() == HOURS
    assert new.column("line-a").to_pylist() == [0.0, 3.25, 4.0]
    assert new.column("line-b").to_pylist() == [1.5, None, -2.0]
    assert new.column("line-c").to_pylist() == [-1.0, -1.0, None]
    for name in ("line-b", "line-c"):
        assert new.column(name).to_pylist() == old.column(name).to_pylist()


def test_empty_table(con):
    con.execute("DELETE FROM flows")
    sel = ", ".join(f'CAST("{h}" AS DOUBLE) AS "{h}"' for h in HOURS)
    wide = _arrow(
        con, f"SELECT CAST(entity_id AS VARCHAR) AS entity_id, {sel} FROM flows"
    )
    new = transpose_day(wide, HOURS)
    assert new.column_names == ["datetime"]
    assert new.num_rows == len(HOURS)
