"""Phase 11a — unit tests for `combine_frames_skip_prev`.

`gat.datahelpers.parsers.combine_frames_skip_prev` is the load-bearing
overlap-dedup function for the plexos multi-file path
(`agg_plexos_parallel`). It had zero direct tests before this module —
only indirect coverage via the existing 2-file plexos fixture.

Semantics (probed against the implementation):

- Frames are sorted internally by their max(index).
- For each non-first frame, rows where ``index <= prev_frame.max()``
  are dropped (strict ``>`` filter).
- A single-frame input is returned unchanged (same object).
- A no-overlap case is just a sorted concat.
"""

import pandas as pd
import pytest

from gat.datahelpers.parsers import combine_frames_skip_prev


def _ts_frame(timestamps, value=None):
    """Helper: build a one-column DataFrame indexed by the given dates."""
    idx = pd.DatetimeIndex(timestamps)
    if value is None:
        value = list(range(len(idx)))
    return pd.DataFrame({"v": value}, index=idx)


def test_single_frame_passthrough():
    df = _ts_frame(["2020-01-01", "2020-01-02"])
    out = combine_frames_skip_prev([df])
    # Implementation returns the input frame as-is for the single-frame case.
    assert out is df


def test_two_disjoint_frames():
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    out = combine_frames_skip_prev([a, b])
    assert list(out.index) == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2020-01-03"),
        pd.Timestamp("2020-01-04"),
    ]
    assert out["v"].tolist() == [1, 2, 3, 4]


def test_two_frames_one_row_overlap():
    """Frame B starts at frame A's last timestamp — earlier frame wins."""
    a = _ts_frame(["2020-01-01", "2020-01-02", "2020-01-03"], [1, 2, 3])
    b = _ts_frame(["2020-01-03", "2020-01-04", "2020-01-05"], [99, 4, 5])
    out = combine_frames_skip_prev([a, b])
    # The 2020-01-03 row from A is kept (value 3); B's overlapping row dropped.
    assert out.loc[pd.Timestamp("2020-01-03"), "v"] == 3
    assert list(out.index) == [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2020-01-03"),
        pd.Timestamp("2020-01-04"),
        pd.Timestamp("2020-01-05"),
    ]


def test_three_frames_time_ordered_with_overlap():
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-02", "2020-01-03"], [99, 3])  # overlaps with A
    c = _ts_frame(["2020-01-03", "2020-01-04"], [99, 4])  # overlaps with B
    out = combine_frames_skip_prev([a, b, c])
    assert out["v"].tolist() == [1, 2, 3, 4]


def test_three_frames_unsorted_input_is_NOT_time_sorted():
    """**Documented quirk.** The function uses max(index) only to compute
    dedup boundaries; the final ``pd.concat`` walks ``frame_dict.items()``
    in insertion order, so the *output* row order matches the input list
    order, not chronological order.

    Plexos's `agg_plexos_parallel` happens to feed frames in chronological
    order (file paths are sorted upstream), so this quirk doesn't bite in
    production today. It would bite a caller who passes frames in arbitrary
    order. Worth a follow-up to sort the final concat — until then, the
    contract is "caller is responsible for chronological input order."
    """
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    c = _ts_frame(["2020-01-05", "2020-01-06"], [5, 6])
    out = combine_frames_skip_prev([c, a, b])
    # Output is in INPUT order (c, a, b), not time order.
    assert out["v"].tolist() == [5, 6, 1, 2, 3, 4]


def test_three_frames_chronological_input():
    """Caller-sorted chronological input (the production path) gives a
    chronologically-sorted output."""
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-03", "2020-01-04"], [3, 4])
    c = _ts_frame(["2020-01-05", "2020-01-06"], [5, 6])
    out = combine_frames_skip_prev([a, b, c])
    assert out["v"].tolist() == [1, 2, 3, 4, 5, 6]


def test_two_frames_full_overlap_smaller_inside_larger():
    """If B is fully inside A's range, B contributes nothing (its max < A's max).

    The implementation orders by max(index), so A (later max) is processed
    second and only keeps timestamps strictly after B's max. Since A starts
    before B's max but contains rows beyond it, A keeps those rows and B
    keeps everything (B is "first" in time-sorted order, processed first).
    """
    a = _ts_frame(
        ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04"], [1, 2, 3, 4]
    )
    b = _ts_frame(["2020-01-02", "2020-01-03"], [99, 99])
    out = combine_frames_skip_prev([a, b])
    # A's max (01-04) > B's max (01-03), so A is processed second and filtered
    # to index > 01-03 → only 01-04 remains. B keeps all its rows.
    assert pd.Timestamp("2020-01-04") in out.index
    # The 2020-01-04 row from A survives.
    assert out.loc[pd.Timestamp("2020-01-04"), "v"] == 4


def test_two_frames_identical_max_collapse_into_one():
    """Two frames with the same max(index) — the second clobbers the first
    in the internal `frame_dict[last_idx] = df`, so only one survives.

    This is a sharp edge of the current implementation. Documenting it as
    a test pins the contract; if the implementation later changes to
    handle this case differently, the test will flag it.
    """
    a = _ts_frame(["2020-01-01", "2020-01-02"], [1, 2])
    b = _ts_frame(["2020-01-01", "2020-01-02"], [10, 20])  # same max as A
    out = combine_frames_skip_prev([a, b])
    # Whichever was inserted last to frame_dict wins; with len==1 after
    # dedup the single-frame branch returns frames[0] directly.
    # The implementation hits the `len(frame_dict) == 1` branch with
    # frames[0] (= a). So a's values come through.
    assert out["v"].tolist() == [1, 2]
