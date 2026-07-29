"""Plexos-DuckDB system implementation for GAT v1.0.0.

Wraps ``PlexosDuckDBSource`` (a plexos2duckdb-converted PLEXOS solution) to
implement the BaseSystem interface. This is a second Plexos backend
alongside ``gat.systems.plexos.PlexosSystem`` — that one wraps the legacy
h5plexos-converted ``.h5`` files via ``PlexosParser``; this one wraps native
PLEXOS ``Solution.zip`` files converted in-process via the optional
``plexos2duckdb`` dependency (``pip install nlr-gat[plexos-duckdb]``).

POC scope, matching ``gat.systems.plexos.PlexosSystem``: only the classes
needed to support generator area aggregation (Generator, Region) are
exposed as raw datasets today. Full system metadata (lines, loads, buses)
will follow in the broader migration.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Sequence, Union

import pandas as pd
from loguru import logger

from ..categories import CategoryMap
from ..datahelpers.plexos_duckdb import PlexosDuckDBSource
from ..datasets import DatasetInfo, DatasetKind
from ..interfaces import BaseSystem

# PLEXOS classes exposed as raw system datasets (POC scope).
#
# "Storage" is exposed for discoverability only — it is NOT unioned into
# gen_area or any generation dataset. Verified against a real converted
# solution: PLEXOS Storage objects are internal head/tail reservoir
# bookkeeping for battery-capable generators (named
# "<generator_name>_head"/"_tail", children of that Generator via the
# "Head Storage"/"Tail Storage" membership collections — never children of
# Region). Their "Generation" is bit-identical to the parent Generator's
# own Generation ("_tail" is always 0) — unioning it would double-count.
# This differs from h5plexos's "batteries" group, which is a separate,
# non-overlapping group at conversion time (see gat/systems/plexos.py's
# battery union for that legacy path).
_DEFAULT_CLASSES = ["Generator", "Region", "Storage"]


class PlexosDuckDBSystem(BaseSystem):
    """Plexos system wrapping a plexos2duckdb-converted solution.

    Provides a default generator -> area category map derived from
    ``processed.memberships`` (Region parent / Generator child) so that
    generation can be aggregated by area in DuckDB — the same map
    ``gat.systems.plexos.PlexosSystem`` derives from h5 metadata relations,
    just SQL-derived instead.

    Args:
        solution_paths: One or more PLEXOS solution ``.zip`` files (or
            already-converted ``.duckdb`` files).
        classes: Override the set of PLEXOS classes exposed as raw datasets.
        force_convert: Reconvert every ``.zip`` input even if a fresh
            ``.duckdb`` cache already exists.
    """

    def __init__(
        self,
        solution_paths: Union[str, Path, Sequence[Union[str, Path]]],
        classes: Optional[List[str]] = None,
        force_convert: bool = False,
    ) -> None:
        self._source = PlexosDuckDBSource(solution_paths, force_convert=force_convert)
        self._classes = classes or list(_DEFAULT_CLASSES)
        logger.info(
            "PlexosDuckDBSystem loaded, exposing classes: {}", self._classes
        )

    @property
    def source(self) -> PlexosDuckDBSource:
        """Access the underlying PlexosDuckDBSource for advanced use."""
        return self._source

    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name=class_name,
                description=f"Plexos {class_name} objects",
                kind=DatasetKind.RAW_SYSTEM,
                entity_column="name",
            )
            for class_name in self._classes
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name not in self._classes:
            raise KeyError(
                f"Dataset '{name}' not found. Available: {self._classes}"
            )
        return self._source.objects(name)

    def get_default_category_maps(self) -> list[CategoryMap]:
        """Return the generator -> area (region) category map."""
        maps: list[CategoryMap] = []
        try:
            gen_area = self._source.membership_map(
                parent_class="Region", child_class="Generator"
            )
            if gen_area:
                maps.append(CategoryMap(
                    name="gen_area",
                    description="Generator -> region/area mapping (from plexos2duckdb memberships)",
                    mapping=gen_area,
                ))
        except Exception as e:
            logger.debug("Could not extract Region/Generator memberships: {}", e)
        return maps

    def _first_row_map(self, table: str, property_col: str) -> dict[str, float]:
        """Read a single-row (annual/template) report table as {name: value}.

        Used for rating-style properties (installed capacity, line export
        limits) that don't vary by timestamp within a solution year.
        """
        try:
            if table not in self._source.report_tables():
                return {}
            df = self._source.pivot_wide(table, property_col)
            if len(df) == 0:
                return {}
            row = df.set_index("timestamp").iloc[0]
            return {str(k): float(v) for k, v in row.items() if pd.notna(v)}
        except Exception as e:
            logger.debug("Could not read '{}': {}", table, e)
            return {}

    def get_generator_ratings(self) -> dict[str, float]:
        """Return a mapping of generator entity names to installed capacity (MW)."""
        return self._first_row_map(
            "ST__Year__Generators__Installed_Capacity", "Installed_Capacity"
        )

    def get_branch_ratings(self, base_power: Optional[float] = None) -> dict[str, float]:
        """Return a mapping of branch/line entity names to MW ratings.

        ``base_power`` is accepted for interface parity with
        ``SiennaSystem.get_branch_ratings`` but unused — plexos2duckdb's
        Export Limit is already reported in MW, not per-unit.
        """
        return self._first_row_map("ST__Year__Lines__Export_Limit", "Export_Limit")
