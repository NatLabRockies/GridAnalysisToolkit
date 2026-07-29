"""
This file contains utility functions common to all simulation parsers

* combining multiple time series
* deduplicating overlapping time blocks

For detailed merge strategy examples, see SiennaSimulationParser._get_decision_data()

"left" strategy: ignore_previous=True - prioritize REALIZED data, remove future overlap
"right" strategy: ignore_previous=False - prioritize FORECASTED data, remove previous overlap

x - ignored or skipped
left: |-----|xxxxx|
            |-----|xxxxx|
                  |-----|-----| <=== last blocks are kept

right: |-----|-----|  <=== first blocks are kept
             |xxxxx|------|
                   |xxxxx|------|

"""

from __future__ import annotations

import fnmatch

import pandas as pd
from typing import TYPE_CHECKING, Iterable, Literal, Union

if TYPE_CHECKING:
    import polars as pl


block_combination_strategy = Literal['left', 'right']


def resolve_compositions(
    raw_names: Iterable[str], compositions: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Match raw dataset names against glob patterns to build composed datasets.

    Shared by any ``BaseSimulation``/``BaseSystem`` implementation that
    defines composed datasets (e.g. "generation") as a union of raw dataset
    names matched via glob patterns (e.g. "ActivePowerVariable__*").

    Args:
        raw_names: Names of raw datasets available from the parser/source.
        compositions: Mapping of composed dataset name to a list of glob
            patterns to match against ``raw_names``.

    Returns:
        Mapping of composed dataset name to the sorted list of matched raw
        dataset names. Compositions with no matches are omitted.
    """
    raw_names = list(raw_names)
    resolved: dict[str, list[str]] = {}
    for comp_name, patterns in compositions.items():
        matched = set()
        for pattern in patterns:
            for name in raw_names:
                if fnmatch.fnmatch(name, pattern):
                    matched.add(name)
        if matched:
            resolved[comp_name] = sorted(matched)
    return resolved


def dedup_slices(
    blocks: Union[list[pl.Series], list[pd.Series]],
    ignore_previous: bool = False
) -> list[tuple[int, int]]:
    """
    Determine non-overlapping slices for datetime blocks.

    Args:
        blocks: List of datetime series representing time blocks
        ignore_previous: If True ("left" strategy), remove overlap with future blocks.
                        If False ("right" strategy), remove overlap with previous blocks.

    Returns:
        List of (start_idx, end_idx) tuples for each block in original order

    See SiennaSimulationParser._get_decision_data() for detailed strategy examples.
    """
    # Create mapping of block start time to (original_index, block)
    block_mapping = {}
    for i, block in enumerate(blocks):
        start_time = block.min()
        block_mapping[start_time] = (i, block)

    # Sort blocks by start time
    sorted_start_times = sorted(block_mapping.keys())

    # Create result list in original order
    result = [None] * len(blocks)

    for j, start_time in enumerate(sorted_start_times):
        original_idx, current_block = block_mapping[start_time]

        if ignore_previous:
            # LEFT strategy: Keep data from current time forward, remove overlap with next block
            if j < len(sorted_start_times) - 1:
                # Not the last block - find overlap with next block
                next_start_time = sorted_start_times[j + 1]

                # Find where next block starts in current block
                try:
                    overlap_idx = current_block.search_sorted(next_start_time)
                    end_idx = overlap_idx - 1 if overlap_idx > 0 else len(current_block) - 1
                except:
                    # Fallback if search_sorted not available
                    overlap_idx = None
                    for idx, dt in enumerate(current_block):
                        if dt >= next_start_time:
                            overlap_idx = idx
                            break
                    end_idx = overlap_idx - 1 if overlap_idx is not None and overlap_idx > 0 else len(current_block) - 1

                result[original_idx] = (0, end_idx)
            else:
                # Last block - keep all data
                result[original_idx] = (0, len(current_block) - 1)

        else:
            # RIGHT strategy: Remove overlap with previous block, keep data forward
            if j > 0:
                # Not the first block - find overlap with previous block
                prev_start_time = sorted_start_times[j - 1]
                prev_original_idx, prev_block = block_mapping[prev_start_time]
                prev_end_time = prev_block.max()

                # Find where previous block ends in current block
                try:
                    start_idx = current_block.search_sorted(prev_end_time, side='right')
                except:
                    # Fallback if search_sorted not available
                    start_idx = 0
                    for idx, dt in enumerate(current_block):
                        if dt > prev_end_time:
                            start_idx = idx
                            break

                result[original_idx] = (start_idx, len(current_block) - 1)
            else:
                # First block - keep all data
                result[original_idx] = (0, len(current_block) - 1)

    return result


def combine_overlapping_frames(
    frames: list[pd.DataFrame],
    merge_strategy: block_combination_strategy = "right",
) -> pd.DataFrame:
    """Combine time-indexed DataFrames using GAT's standard multi-file/
    multi-block overlap convention, built on ``dedup_slices``.

    This is the canonical entry point for "parse each file/block on its
    own, then let GAT combine them" — plugin authors implementing a new
    backend should only need to produce one DataFrame per file/block and
    hand the list here, rather than reimplementing overlap logic.
    ``gat.simulations.generic_aggregator.SimulationAggregator._combine_frames``
    (Sienna) and ``gat.datahelpers.plexos_duckdb.PlexosDuckDBSource.
    pivot_wide`` (plexos2duckdb) both delegate to this function.

    ``merge_strategy="right"`` (default) drops the overlap from the
    *later* frame — the earlier frame wins at the seam. This matches
    the convention PLEXOS rolling-horizon solves use (each file's warm-up
    overlap with the next file is discarded in favor of the earlier
    file's already-solved values) — see ``gat.datahelpers.parsers.
    combine_frames_skip_prev`` for the legacy h5-based Plexos path, which
    implements the same "earlier wins" direction with a separate (and
    less robust — it doesn't sort unsorted input, see
    tests/datahelpers/test_combine_frames.py) implementation.
    ``merge_strategy="left"`` drops the overlap from the earlier frame
    instead (later frame wins) — Sienna's decision-model default.

    Unlike ``combine_frames_skip_prev``, input order doesn't matter:
    frames are sorted by their first timestamp before combining, and the
    result is always chronologically sorted.

    Args:
        frames: DataFrames to combine, each with a sortable time index.
        merge_strategy: "right" (earlier wins, default) or "left" (later
            wins) — see the module docstring for the visual explanation.

    Returns:
        A single combined, chronologically-sorted DataFrame.
    """
    if not frames:
        return pd.DataFrame()
    if len(frames) == 1:
        return frames[0]

    sorted_frames = sorted(frames, key=lambda df: df.index.min())
    ignore_previous = merge_strategy == "left"

    try:
        blocks = [pd.Series(df.index) for df in sorted_frames]
        slices = dedup_slices(blocks, ignore_previous=ignore_previous)
        kept = [
            sorted_frames[i].iloc[start_idx:end_idx + 1]
            for i, (start_idx, end_idx) in enumerate(slices)
            if start_idx is not None and end_idx is not None
        ]
        combined = pd.concat(kept, axis=0) if kept else pd.concat(sorted_frames, axis=0)
    except Exception:
        combined = pd.concat(sorted_frames, axis=0)
        combined = combined[~combined.index.duplicated(keep="first")]

    return combined.sort_index()


