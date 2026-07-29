"""Phase 11c — unit tests for `SimulationAggregator._combine_frames`.

The v1 multi-file aggregation path. Internally calls `dedup_slices`
(`gat/simulations/utils.py:33`) for overlap detection, then applies
the resulting (start, end) tuples to slice each frame, then
``pd.concat`` + ``sort_index`` for deterministic chronological output.

The method doesn't use ``self`` — we bypass ``__init__`` (which would
require real files) by constructing the instance via ``__new__`` and
calling the method directly. This is a unit test of the combine logic,
not an integration test of the full aggregator.
"""
import pandas as pd
import pytest

from gat.simulations.generic_aggregator import SimulationAggregator


@pytest.fixture
def aggregator():
    """Bare aggregator instance for testing _combine_frames in isolation.

    Skips __init__ (which would require real h5 files + a parser class) —
    `_combine_frames` doesn't depend on any instance state.
    """
    return SimulationAggregator.__new__(SimulationAggregator)


def _ts_frame(timestamps, value=None):
    idx = pd.DatetimeIndex(timestamps)
    if value is None:
        value = list(range(len(idx)))
    return pd.DataFrame({"v": value}, index=idx)


def test_combine_single_frame_passthrough(aggregator):
    df = _ts_frame(["2020-01-01", "2020-01-02"])
    out = aggregator._combine_frames([df], merge_strategy="left")
    assert out is df  # single-frame path returns the input directly


def test_combine_disjoint_left(aggregator):
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    out = aggregator._combine_frames([a, b], merge_strategy="left")
    assert out["v"].tolist() == [1, 2, 3, 4]


def test_combine_overlap_left(aggregator):
    """Left strategy: ``ignore_previous=True`` — the *earlier* block drops
    overlap with the next block, so the **later** frame wins at the seam.

    This is the inverse of ``combine_frames_skip_prev`` (used by plexos),
    which keeps the earlier frame's data on overlap. The naming is
    counterintuitive — "left" refers to the side of the dedup operation,
    not which frame survives.
    """
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [99, 4, 5])
    out = aggregator._combine_frames([a, b], merge_strategy="left")
    # B's 2020-01-03 row wins (value 99); A's overlapping row dropped.
    assert out.loc[pd.Timestamp("2020-01-03"), "v"] == 99
    assert out["v"].tolist() == [1, 2, 99, 4, 5]


def test_combine_overlap_right(aggregator):
    """Right strategy: ``ignore_previous=False`` — the *later* block drops
    overlap with the previous block, so the **earlier** frame wins at
    the seam (same behavior as ``combine_frames_skip_prev``)."""
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [99, 4, 5])
    out = aggregator._combine_frames([a, b], merge_strategy="right")
    # A's 2020-01-03 row wins (value 3); B's overlapping row dropped.
    assert out.loc[pd.Timestamp("2020-01-03"), "v"] == 3
    assert out["v"].tolist() == [1, 2, 3, 4, 5]


def test_combine_unsorted_input_left(aggregator):
    """Aggregator sorts by frame.index.min() before deduping; output is
    chronological regardless of input order."""
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    c = _ts_frame(["2020-01-05", "2020-01-06"], [5, 6])
    out = aggregator._combine_frames([c, a, b], merge_strategy="left")
    # Unlike combine_frames_skip_prev, this method's final sort_index()
    # gives chronological order even when input is unsorted.
    assert out["v"].tolist() == [1, 2, 3, 4, 5, 6]


def test_combine_three_overlapping_chained_left(aggregator):
    """Chained A→B→C, each overlapping by 1 timestamp. Left strategy:
    later frame wins at every seam, so each boundary timestamp comes from
    the second frame at that seam."""
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [97, 4, 5])
    c = _ts_frame(["2020-01-05", "2020-01-06", "2020-01-07"], [98, 6, 7])
    out = aggregator._combine_frames([a, b, c], merge_strategy="left")
    # 01-03 from B (97), 01-05 from C (98).
    assert out["v"].tolist() == [1, 2, 97, 4, 98, 6, 7]
