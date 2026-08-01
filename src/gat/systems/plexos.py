"""Plexos system implementation for GAT v1.0.0.

Wraps the existing PlexosParser to implement the BaseSystem interface and
provide default generator→area / generator→technology category maps for use
with GATDatabase.query_grouped.

POC scope: only the relations needed to support generator aggregation are
exposed today. Full system metadata (lines, loads, buses) will follow in the
broader migration.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

import pandas as pd
from loguru import logger

from ..categories import CategoryMap
from ..datasets import DatasetInfo
from ..interfaces import BaseSystem


class PlexosSystem(BaseSystem):
    """Plexos system wrapping PlexosParser.

    Provides default category maps derived from plexos h5 metadata relations
    (regions_generators) so that generation can be aggregated by area in
    DuckDB.

    Args:
        solution_dir: Directory containing .h5 solution files.
        solution_files: Explicit list of .h5 file paths.
        tech_map: Optional generator→technology dict (generator name → tech).
            Sourced from the legacy PlexosScenario._tech_simple if not provided.
    """

    def __init__(
        self,
        solution_dir: Optional[Union[str, Path]] = None,
        solution_files: Optional[List[str]] = None,
        tech_map: Optional[dict] = None,
    ) -> None:
        from ..datahelpers.h5Parsers import PlexosParser

        if solution_dir is not None:
            from glob import glob

            solution_files = sorted(glob(str(Path(solution_dir) / "*.h5")))
        if not solution_files:
            raise ValueError("PlexosSystem requires solution_dir or solution_files")

        self._parser = PlexosParser(solution_files=solution_files)
        self._tech_map = tech_map
        logger.info("PlexosSystem loaded with {} solution file(s)", len(solution_files))

    @property
    def parser(self) -> object:
        return self._parser

    def list_datasets(self) -> list[DatasetInfo]:
        # POC: no system datasets exposed yet — relation maps alone are
        # sufficient to drive query_grouped with the migrated dispatch path.
        return []

    def get_dataset(self, name: str) -> pd.DataFrame:
        raise KeyError(f"PlexosSystem currently exposes no datasets (got '{name}')")

    def get_default_category_maps(self) -> list[CategoryMap]:
        """Return generator→area and (if tech_map provided) generator→tech maps."""
        maps: list[CategoryMap] = []

        # Generator → area (region) from h5 metadata relations. Batteries are
        # a separate h5 group/relation from generators, so their area mapping
        # must be unioned in explicitly (mirrors legacy
        # PlexosScenario.generate_gen_area_map) or battery entities fall
        # through query_grouped's "other" bucket / get dropped entirely.
        try:
            gen_area = self._parser.get_metadata(
                "metadata/relations/regions_generators", reverse=True
            )
            if "batteries" in self._parser.list_groups("ST", "interval"):
                battery_area = self._parser.get_metadata(
                    "metadata/relations/regions_batteries", reverse=True
                )
                gen_area = {**gen_area, **battery_area}
            if gen_area:
                maps.append(
                    CategoryMap(
                        name="gen_area",
                        description="Generator → region/area mapping (from plexos h5 relations)",
                        mapping={str(k): str(v) for k, v in gen_area.items()},
                    )
                )
        except Exception as e:
            logger.debug("Could not extract regions_generators: {}", e)

        # Generator → simplified tech, if a tech_map was supplied.
        if self._tech_map:
            maps.append(
                CategoryMap(
                    name="gen_tech",
                    description="Generator → simplified technology",
                    mapping={str(k): str(v) for k, v in self._tech_map.items()},
                )
            )

        return maps
