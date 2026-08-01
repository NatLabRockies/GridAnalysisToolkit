"""Plexos-DuckDB simulation implementation for GAT v1.0.0.

Wraps ``PlexosDuckDBSource`` (a plexos2duckdb-converted PLEXOS solution) to
implement the BaseSimulation interface, exposing ``report`` schema views as
named datasets. This is a second Plexos backend alongside
``gat.simulations.plexos_v1.PlexosSimulation`` — that one wraps the legacy
h5plexos-converted ``.h5`` files; this one wraps native PLEXOS
``Solution.zip`` files converted in-process via the optional
``plexos2duckdb`` dependency (``pip install nlr-gat[plexos-duckdb]``).

POC scope, matching ``gat.simulations.plexos_v1.PlexosSimulation``: only the
generation timeseries is currently exposed as a composed dataset; load,
flow, and other groups will follow in the broader migration. Unlike the
legacy POC, adding another property is a one-line addition to
``_DEFAULT_COMPOSITIONS`` — every plexos2duckdb report view is addressed the
same way (Phase/Period/Collection/Property), so no new parsing code is
needed per property.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

import numpy as np
import pandas as pd
from loguru import logger

from ..datahelpers.plexos_duckdb import PlexosDuckDBSource
from ..datasets import DatasetInfo, DatasetKind
from ..interfaces import BaseSimulation
from .utils import resolve_compositions

# Default compositions mapping composed dataset names to report-view name
# patterns (Phase__Period__Collection__Property), matched with fnmatch —
# same shape as gat.simulations.sienna_v1._DEFAULT_COMPOSITIONS.
#
# "generation" is intentionally NOT unioned with Storage report tables —
# verified against a real converted solution that PLEXOS Storage objects
# (head/tail reservoir bookkeeping for battery-capable generators) report
# "Generation" that's bit-identical to their parent Generator's own
# Generation; unioning would double-count. See gat/systems/plexos_duckdb.py
# for the full explanation. Storage charging (Pump_Load) is genuinely
# separate information and is composed below.
_DEFAULT_COMPOSITIONS: Dict[str, List[str]] = {
    "generation": ["ST__Interval__Generators__Generation"],
    "availability": ["ST__Interval__Generators__Available_Capacity"],
    "load": ["ST__Interval__Regions__Load"],
    "unserved": ["ST__Interval__Regions__Unserved_Energy"],
    "line_flow": ["ST__Interval__Lines__Flow"],
    "storage_charging": ["ST__Interval__Storages__Pump_Load"],
    "production_cost": ["ST__Interval__Generators__Total_Generation_Cost"],
}


class PlexosDuckDBSimulation(BaseSimulation):
    """Plexos simulation wrapping a plexos2duckdb-converted solution.

    Exposes each ``report`` schema view as a raw dataset and provides a
    default ``generation`` composed dataset.

    Args:
        solution_paths: One or more PLEXOS solution ``.zip`` files (or
            already-converted ``.duckdb`` files).
        compositions: Override the default composition patterns. Keys are
            composed dataset names, values are lists of glob patterns
            matched against report view names.
        force_convert: Reconvert every ``.zip`` input even if a fresh
            ``.duckdb`` cache already exists.
    """

    def __init__(
        self,
        solution_paths: Union[str, Path, Sequence[Union[str, Path]]],
        compositions: Optional[Dict[str, List[str]]] = None,
        force_convert: bool = False,
    ) -> None:
        self._source = PlexosDuckDBSource(solution_paths, force_convert=force_convert)
        self._compositions = compositions or _DEFAULT_COMPOSITIONS
        self._raw_tables: Optional[list[str]] = None
        self._resolved_compositions: Optional[dict[str, list[str]]] = None
        self._cache: dict[str, pd.DataFrame] = {}
        logger.info(
            "PlexosDuckDBSimulation loaded, {} report tables discovered",
            len(self._get_raw_tables()),
        )

    @property
    def source(self) -> PlexosDuckDBSource:
        """Access the underlying PlexosDuckDBSource for advanced use."""
        return self._source

    def _get_raw_tables(self) -> list[str]:
        if self._raw_tables is None:
            self._raw_tables = self._source.report_tables()
        return self._raw_tables

    def _resolve_compositions(self) -> dict[str, list[str]]:
        if self._resolved_compositions is None:
            self._resolved_compositions = resolve_compositions(
                self._get_raw_tables(), self._compositions
            )
        return self._resolved_compositions

    def list_datasets(self) -> list[DatasetInfo]:
        result: list[DatasetInfo] = []

        for table in sorted(self._get_raw_tables()):
            result.append(DatasetInfo(
                name=table,
                description="Plexos report dataset",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="entity_id",
            ))

        for comp_name, source_tables in self._resolve_compositions().items():
            result.append(DatasetInfo(
                name=comp_name,
                description=f"Composed dataset ({len(source_tables)} sources)",
                kind=DatasetKind.COMPOSED,
                entity_column="entity_id",
                source_datasets=source_tables,
            ))

        return result

    def get_dataset(self, name: str) -> pd.DataFrame:
        raw_tables = self._get_raw_tables()
        compositions = self._resolve_compositions()

        if name in compositions:
            frames = [self._get_raw_df(t) for t in compositions[name]]
            return pd.concat(frames, axis=1)

        if name in raw_tables:
            return self._get_raw_df(name)

        available = sorted(raw_tables) + sorted(compositions.keys())
        raise KeyError(f"Dataset '{name}' not found. Available: {available}")

    def _get_raw_df(self, table: str) -> pd.DataFrame:
        """Return a report table pivoted to timestamp-rows x entity-cols."""
        if table in self._cache:
            return self._cache[table]

        # Table name is "<Phase>__<Period>__<Collection>__<Property>"; the
        # value column in the report view is named after the property.
        property_col = table.split("__")[-1]
        df = self._source.pivot_wide(table, property_col)
        df = df.set_index("timestamp")
        df.index = pd.to_datetime(df.index)
        df.index.name = "DATETIME"
        df.columns = [str(c) for c in df.columns]

        float_cols = df.select_dtypes(include=[np.float64]).columns
        if len(float_cols) > 0:
            df[float_cols] = df[float_cols].astype(np.float32)

        self._cache[table] = df
        return df
