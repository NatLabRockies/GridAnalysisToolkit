"""Partition layout helpers (no GridSight SDK import, so tests can load
this file on its own)."""

from __future__ import annotations


def transpose_day(wide, ts_cols: list[str]):
    """Turn entity rows x hour columns into the partition layout the web
    client reads: a ``datetime`` column (one row per hour) plus one float64
    column per entity, entities sorted by id. Duplicate entity ids keep the
    first row (as PIVOT ... USING first(val) did)."""
    import numpy as np
    import pyarrow as pa

    ids = wide.column("entity_id").to_pylist()
    first: dict[str, int] = {}
    for i, e in enumerate(ids):
        if e is not None and e not in first:
            first[e] = i
    order = sorted(first)
    rows = np.fromiter((first[e] for e in order), dtype=np.int64, count=len(order))
    mat = np.column_stack(
        [
            wide.column(c).to_numpy(zero_copy_only=False).astype("float64")
            for c in ts_cols
        ]
    )[
        rows
    ]  # entities x hours; NaN where the stored value is NULL
    arrays = [pa.array(ts_cols, type=pa.string())]
    arrays += [
        pa.array(mat[j], type=pa.float64(), from_pandas=True) for j in range(len(order))
    ]
    return pa.Table.from_arrays(arrays, names=["datetime", *order])
