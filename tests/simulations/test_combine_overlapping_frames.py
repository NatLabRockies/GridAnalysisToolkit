"""Unit tests for `gat.simulations.utils.combine_overlapping_frames`.

The canonical multi-file/multi-block overlap-combination primitive shared
by `SimulationAggregator._combine_frames` (Sienna) and
`PlexosDuckDBSource.pivot_wide` (plexos2duckdb) — see
tests/simulations/test_combine_frames_aggregator.py and
tests/datahelpers/test_combine_frames.py for the pre-unification behavior
this preserves (for the aggregator) or improves on (for legacy Plexos,
which doesn't sort unsorted input — see its own quirk tests).
"""
import pandas as pd
import pytest

from gat.simulations.utils import combine_overlapping_frames


def _ts_frame(timestamps, value=None):
    idx = pd.DatetimeIndex(timestamps)
    if value is None:
        value = list(range(len(idx)))
    return pd.DataFrame({"v": value}, index=idx)


def test_single_frame_passthrough():
    df = _ts_frame(["2020-01-01", "2020-01-02"])
    out = combine_overlapping_frames([df])
    assert out is df


def test_empty_list_returns_empty_frame():
    out = combine_overlapping_frames([])
    assert len(out) == 0


def test_two_disjoint_frames():
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    out = combine_overlapping_frames([a, b])
    assert out["v"].tolist() == [1, 2, 3, 4]


def test_overlap_right_earlier_wins():
    """Default strategy: earlier frame wins at the seam — matches the
    PLEXOS rolling-horizon convention (combine_frames_skip_prev)."""
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [99, 4, 5])
    out = combine_overlapping_frames([a, b], merge_strategy="right")
    assert out.loc[pd.Timestamp("2020-01-03"), "v"] == 3
    assert out["v"].tolist() == [1, 2, 3, 4, 5]


def test_overlap_left_later_wins():
    """"left" strategy: later frame wins at the seam — Sienna's default."""
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [99, 4, 5])
    out = combine_overlapping_frames([a, b], merge_strategy="left")
    assert out.loc[pd.Timestamp("2020-01-03"), "v"] == 99
    assert out["v"].tolist() == [1, 2, 99, 4, 5]


def test_unsorted_input_still_chronological():
    """Unlike combine_frames_skip_prev, input order never matters — output
    is always sorted by timestamp."""
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    c = _ts_frame(["2020-01-05", "2020-01-06"], [5, 6])
    out = combine_overlapping_frames([c, a, b], merge_strategy="right")
    assert out["v"].tolist() == [1, 2, 3, 4, 5, 6]


def test_three_frames_chained_overlap_right():
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [97, 4, 98])
    c = _ts_frame(["2020-01-05", "2020-01-06", "2020-01-07"], [99, 6, 7])
    out = combine_overlapping_frames([a, b, c], merge_strategy="right")
    # Earlier frame wins at each seam: 01-03 from a, 01-05 from b.
    assert out["v"].tolist() == [1, 2, 3, 4, 98, 6, 7]
