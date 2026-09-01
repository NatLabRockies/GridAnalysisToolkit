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
    """ "left" strategy: later frame wins at the seam — Sienna's default."""
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


def test_earlier_wins_later_wins_aliases_match_right_left():
    """ "earlier_wins"/"later_wins" are the canonical names for "right"/
    "left" -- same result either way."""
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [99, 4, 5])
    assert combine_overlapping_frames([a, b], merge_strategy="earlier_wins").equals(
        combine_overlapping_frames([a, b], merge_strategy="right")
    )
    assert combine_overlapping_frames([a, b], merge_strategy="later_wins").equals(
        combine_overlapping_frames([a, b], merge_strategy="left")
    )


def test_gap_between_partitions_passes_through_untouched():
    """A real gap (not just non-overlapping/adjacent) between partitions
    isn't synthesized or filled -- it just passes through in the index."""
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-10", "2020-01-11"], [10, 11])
    out = combine_overlapping_frames([a, b])
    assert out["v"].tolist() == [1, 2, 10, 11]
    assert out.index.tolist() == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2020-01-10"),
        pd.Timestamp("2020-01-11"),
    ]


def test_differing_columns_unions_with_nan_fill():
    """Frames with different column sets union (outer join) rather than
    silently dropping a column or raising."""
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    b["w"] = [30, 40]
    out = combine_overlapping_frames([a, b])
    assert set(out.columns) == {"v", "w"}
    assert out["v"].tolist() == [1, 2, 3, 4]
    assert pd.isna(out.loc[pd.Timestamp("2020-01-01"), "w"])
    assert out.loc[pd.Timestamp("2020-01-03"), "w"] == 30


def test_timezone_mismatch_raises_clearly():
    """Combining a tz-naive frame with a tz-aware one raises a clear error
    rather than silently misbehaving -- the comparison during sorting
    fails before the broad except-and-fallback in the try block below it
    ever gets a chance to swallow it."""
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b_idx = pd.DatetimeIndex(["2020-01-03", "2020-01-04"], tz="UTC")
    b = pd.DataFrame({"v": [3, 4]}, index=b_idx)
    with pytest.raises(TypeError):
        combine_overlapping_frames([a, b])
