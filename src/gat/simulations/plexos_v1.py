"""Plexos simulation implementation for GAT v1.0.0.

Wraps the existing PlexosParser to implement the BaseSimulation interface,
exposing Plexos H5 solution files as a single named "generation" dataset
suitable for ingestion into GATDatabase.

This is a POC scope — only the generation timeseries is currently exposed;
load, flow, and other groups will follow in the broader migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import pandas as pd
from loguru import logger

from ..datasets import DatasetInfo, DatasetKind
from ..interfaces import BaseSimulation

_GENERATION_RAW = "generation_raw"  # raw H5 dataset name in DuckDB sim__ table
_GENERATION_COMPOSED = "generation"  # composed (transposed) name


class PlexosSimulation(BaseSimulation):
    """Plexos simulation wrapping PlexosParser.

    Exposes a single ``generation`` composed dataset built from
    ``ST/interval/generators/Generation`` aggregated across solution files.

    Args:
        solution_dir: Directory containing .h5 solution files (preferred).
        solution_files: Explicit list of .h5 file paths.
    """

    def __init__(
        self,
        solution_dir: Optional[Union[str, Path]] = None,
        solution_files: Optional[List[str]] = None,
    ) -> None:
        from ..datahelpers.h5Parsers import PlexosParser

        if solution_dir is not None:
            from glob import glob

            solution_files = sorted(glob(str(Path(solution_dir) / "*.h5")))
        if not solution_files:
            raise ValueError("PlexosSimulation requires solution_dir or solution_files")

        self._parser = PlexosParser(solution_files=solution_files)
        self._cache: dict[str, pd.DataFrame] = {}
        logger.info(
            "PlexosSimulation loaded with {} solution file(s)", len(solution_files)
        )

    @property
    def parser(self) -> object:
        return self._parser

    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name=_GENERATION_RAW,
                description="Generator dispatch (ST interval) — raw timeseries",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="entity_id",
            ),
            DatasetInfo(
                name=_GENERATION_COMPOSED,
                description="Generation composed (entity-rows × timestamp-cols)",
                kind=DatasetKind.COMPOSED,
                entity_column="entity_id",
                source_datasets=[_GENERATION_RAW],
            ),
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name in self._cache:
            return self._cache[name]
        if name in (_GENERATION_RAW, _GENERATION_COMPOSED):
            # PlexosParser returns entity-rows × timestamp-columns with a
            # MultiIndex (generators, category) on the rows. The v1 BaseSimulation
            # contract is timestamp-rows × entity-cols (DatetimeIndex + str cols),
            # so transpose and flatten the index to just the generator name.
            raw = self._parser.get_h5dataset(
                "ST", "interval", "generators", "Generation"
            )
            if isinstance(raw.index, pd.MultiIndex):
                raw = raw.copy()
                raw.index = raw.index.get_level_values(0)
            # Batteries are a separate h5 group from generators but are still
            # generation entities (discharge); the legacy path
            # (PlexosScenario.get_generation) unions them in when present, so
            # v1 must too or area/system totals under-count wherever storage
            # discharges.
            if "batteries" in self._parser.list_groups("ST", "interval"):
                battery_raw = self._parser.get_h5dataset(
                    "ST", "interval", "batteries", "Generation"
                )
                if isinstance(battery_raw.index, pd.MultiIndex):
                    battery_raw = battery_raw.copy()
                    battery_raw.index = battery_raw.index.get_level_values(0)
                raw = pd.concat([raw, battery_raw]).drop_duplicates()
            df = raw.T
            df.index = pd.to_datetime(df.index)
            df.index.name = "DATETIME"
            df.columns = [str(c) for c in df.columns]
            float_cols = df.select_dtypes(include=[np.float64]).columns
            if len(float_cols) > 0:
                df[float_cols] = df[float_cols].astype(np.float32)
            self._cache[name] = df
            return df
        raise KeyError(f"Dataset '{name}' not found in PlexosSimulation")
