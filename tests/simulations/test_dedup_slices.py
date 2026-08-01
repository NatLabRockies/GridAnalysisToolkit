"""Phase 11b — unit tests for `dedup_slices`.

`gat.simulations.utils.dedup_slices` is the building block under the v1
`SimulationAggregator._combine_frames` path. It returns
``(start_idx, end_idx)`` tuples for each block in the **original input
order**, computed against time-sorted overlap detection.

Strategy semantics:
- `ignore_previous=True` ("left"): keep the earlier block's data;
  truncate any block that overlaps its successor's start.
- `ignore_previous=False` ("right"): keep the later block's data;
  truncate any block that overlaps its predecessor's end.
"""

import polars as pl
import pytest

from gat.simulations.utils import dedup_slices


def _series(*timestamps):
    return pl.Series("t", list(timestamps)).str.to_datetime()


def test_single_block_returns_full_range():
    b = _series("2020-01-01", "2020-01-02")
    assert dedup_slices([b], ignore_previous=True) == [(0, 1)]
    assert dedup_slices([b], ignore_previous=False) == [(0, 1)]


def test_two_disjoint_blocks_both_kept():
    b1 = _series("2020-01-01", "2020-01-02")
    b2 = _series("2020-01-03", "2020-01-04")
    assert dedup_slices([b1, b2], ignore_previous=True) == [(0, 1), (0, 1)]
    assert dedup_slices([b1, b2], ignore_previous=False) == [(0, 1), (0, 1)]


def test_two_overlapping_blocks_left_strategy():
    """Left: earlier block (b1) gets truncated up to where later block (b2) starts."""
    b1 = _series("2020-01-01", "2020-01-02", "2020-01-03")
    b2 = _series("2020-01-03", "2020-01-04", "2020-01-05")
    # b1 keeps indices 0..1 (drops 01-03 because b2 starts at 01-03);
    # b2 keeps everything.
    assert dedup_slices([b1, b2], ignore_previous=True) == [(0, 1), (0, 2)]


def test_two_overlapping_blocks_right_strategy():
    """Right: later block (b2) gets truncated to start after b1's max."""
    b1 = _series("2020-01-01", "2020-01-02", "2020-01-03")
    b2 = _series("2020-01-03", "2020-01-04", "2020-01-05")
    # b1 keeps everything; b2 keeps indices 1..2 (drops 01-03).
    assert dedup_slices([b1, b2], ignore_previous=False) == [(0, 2), (1, 2)]


def test_three_blocks_unsorted_input_preserves_input_order():
    """Output indices are returned in INPUT order even though overlap
    computation is done in time-sorted order. Caller's responsibility
    to map slices back to their original block."""
    a = _series("2020-01-01", "2020-01-02")
    b = _series("2020-01-03", "2020-01-04")
    c = _series("2020-01-05", "2020-01-06")
    # All disjoint, so all kept in full regardless of input order.
    assert dedup_slices([c, a, b], ignore_previous=True) == [
        (0, 1),  # c
        (0, 1),  # a
        (0, 1),  # b
    ]


def test_overlap_dedup_for_chained_blocks_left():
    """Chained overlap: A→B→C each overlapping by 1 timestamp."""
    a = _series("2020-01-01", "2020-01-02", "2020-01-03")
    b = _series("2020-01-03", "2020-01-04", "2020-01-05")
    c = _series("2020-01-05", "2020-01-06", "2020-01-07")
    out = dedup_slices([a, b, c], ignore_previous=True)
    # a truncated up to b's start (drops 01-03 → keeps 0..1)
    # b truncated up to c's start (drops 01-05 → keeps 0..1)
    # c kept fully
    assert out == [(0, 1), (0, 1), (0, 2)]
