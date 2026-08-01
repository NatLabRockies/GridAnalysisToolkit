"""Shared source for the plexos2duckdb-backed GAT v1 backend.

Wraps one or more converted (or convertible) PLEXOS solution files and
exposes them as a single logical source over an in-process DuckDB
connection. Used by both ``gat.systems.plexos_duckdb.PlexosDuckDBSystem``
and ``gat.simulations.plexos_duckdb.PlexosDuckDBSimulation`` — mirrors how
``gat.datahelpers.h5Parsers.PlexosParser`` is shared by the legacy
H5-based ``PlexosSystem``/``PlexosSimulation`` pair.

Conversion (PLEXOS ``Solution.zip`` -> ``.duckdb``) is done by shelling out
to the `plexos2duckdb <https://github.com/epri-dev/plexos2duckdb>`_ CLI via
its Python wrapper (an optional dependency — install with
``pip install nlr-gat[plexos-duckdb]``). Once converted, everything else is
plain DuckDB SQL against the tool's own ``raw`` / ``processed`` / ``report``
schemas — see that project's source for the schema, it isn't otherwise
documented:

- ``report."<Phase>__<Period>__<Collection>__<Property>"`` — one view per
  reported property, columns: band, sample_name, name, category, timestamp,
  interval_length, "<Property>" (value), unit.
- ``processed.objects`` — id, name, category, class_group, class.
- ``processed.memberships`` — membership_id, parent_id, child_id,
  collection, parent_name, parent_class, parent_group, parent_category,
  child_name, child_class, child_group, child_category, kind.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence, Union

import pandas as pd
from loguru import logger

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]

try:
    from plexos2duckdb import PLEXOS2DuckDB
except ImportError:
    PLEXOS2DuckDB = None  # type: ignore[assignment]


def _require_duckdb() -> None:
    if duckdb is None:
        raise ImportError(
            "duckdb is required for PlexosDuckDBSystem/PlexosDuckDBSimulation. "
            "Install it with: pip install duckdb"
        )


def _require_plexos2duckdb() -> None:
    if PLEXOS2DuckDB is None:
        raise ImportError(
            "plexos2duckdb is required to convert PLEXOS solution .zip files "
            "to DuckDB. Install it with: pip install nlr-gat[plexos-duckdb]"
        )


def _resolve_duckdb_path(input_path: Union[str, Path], force_convert: bool) -> Path:
    """Return the .duckdb path for a single input, converting if needed.

    If ``input_path`` already has a .duckdb suffix, it is used as-is (no
    conversion attempted — assumed already converted). Otherwise it is
    treated as a PLEXOS solution .zip and converted via plexos2duckdb,
    writing a sibling ``<name>.duckdb`` next to it. Conversion is skipped
    if that sibling already exists and is newer than the .zip, unless
    ``force_convert`` is set — mirrors the cache-unless-stale convention
    used for parquet in ``gat.backends.duckdb_backend``.
    """
    path = Path(input_path)
    if path.suffix.lower() == ".duckdb":
        if not path.exists():
            raise FileNotFoundError(f"DuckDB file not found: {path}")
        return path

    _require_plexos2duckdb()
    client = PLEXOS2DuckDB(str(path))
    duckdb_path = client.output_path

    needs_convert = (
        force_convert
        or duckdb_path is None
        or not duckdb_path.exists()
        or duckdb_path.stat().st_mtime < path.stat().st_mtime
    )
    if needs_convert:
        logger.info("Converting PLEXOS solution '{}' -> '{}'", path, duckdb_path)
        duckdb_path = client.convert(force=True)
    else:
        logger.debug("Using cached DuckDB conversion: {}", duckdb_path)

    return duckdb_path


class PlexosDuckDBSource:
    """Attaches one or more plexos2duckdb-converted files as one source.

    Args:
        solution_paths: One or more paths, each either a PLEXOS solution
            ``.zip`` file (converted on demand) or an already-converted
            ``.duckdb`` file (used as-is).
        force_convert: Reconvert every ``.zip`` input even if a fresh
            ``.duckdb`` cache already exists.
    """

    def __init__(
        self,
        solution_paths: Union[str, Path, Sequence[Union[str, Path]]],
        force_convert: bool = False,
    ) -> None:
        _require_duckdb()

        if isinstance(solution_paths, (str, Path)):
            solution_paths = [solution_paths]
        if not solution_paths:
            raise ValueError("PlexosDuckDBSource requires at least one solution path")

        self._conn = duckdb.connect()
        self._aliases: list[str] = []
        for i, raw_path in enumerate(solution_paths):
            duckdb_path = _resolve_duckdb_path(raw_path, force_convert)
            alias = f"sol{i}"
            self._conn.execute(f"ATTACH '{duckdb_path}' AS {alias} (READ_ONLY)")
            self._aliases.append(alias)

        logger.info(
            "PlexosDuckDBSource attached {} solution file(s)", len(self._aliases)
        )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PlexosDuckDBSource":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def report_tables(self) -> list[str]:
        """Return the union of ``report`` schema view names across all
        attached files."""
        names: set[str] = set()
        for alias in self._aliases:
            rows = self._conn.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = ? AND table_schema = 'report'",
                [alias],
            ).fetchall()
            names.update(r[0] for r in rows)
        return sorted(names)

    def objects(self, class_name: str) -> pd.DataFrame:
        """Return ``processed.objects`` rows for a given PLEXOS class,
        unioned across attached files and deduplicated by name."""
        frames = []
        for alias in self._aliases:
            df = self._conn.execute(
                f"SELECT id, name, category, class_group, class "
                f"FROM {alias}.processed.objects WHERE class = ?",
                [class_name],
            ).fetchdf()
            frames.append(df)
        combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        if len(combined) == 0:
            return combined
        return combined.drop_duplicates(subset=["name"]).reset_index(drop=True)

    # ------------------------------------------------------------------ #
    # Category maps
    # ------------------------------------------------------------------ #

    def membership_map(
        self, parent_class: str, child_class: str
    ) -> dict[str, str]:
        """Build a ``{child_name: parent_name}`` map from ``processed.
        memberships`` (e.g. generator -> region), unioned across attached
        files."""
        mapping: dict[str, str] = {}
        for alias in self._aliases:
            rows = self._conn.execute(
                f"SELECT child_name, parent_name FROM {alias}.processed.memberships "
                "WHERE parent_class = ? AND child_class = ?",
                [parent_class, child_class],
            ).fetchall()
            for child_name, parent_name in rows:
                mapping[str(child_name)] = str(parent_name)
        return mapping

    # ------------------------------------------------------------------ #
    # Timeseries
    # ------------------------------------------------------------------ #

    def _pivot_one_file(self, alias: str, table: str, property_col: str) -> pd.DataFrame:
        """PIVOT a single attached file's report view into timestamp-rows x
        entity-columns — the "parse one file" half of the standard
        multi-file contract (see ``pivot_wide``)."""
        quoted_table = table.replace('"', '""')
        quoted_prop = property_col.replace('"', '""')
        sql = (
            f'PIVOT (SELECT timestamp, name, "{quoted_prop}" AS value '
            f'FROM {alias}.report."{quoted_table}") '
            "ON name USING FIRST(value) GROUP BY timestamp ORDER BY timestamp"
        )
        return self._conn.execute(sql).fetchdf().set_index("timestamp")

    def pivot_wide(self, table: str, property_col: str) -> pd.DataFrame:
        """Pivot a ``report`` view into timestamp-rows x entity-columns,
        combined across every attached file.

        Each attached file is pivoted independently (``_pivot_one_file``
        — "parse a single file"), then combined via ``gat.simulations.
        utils.combine_overlapping_frames`` — the same standard multi-file
        overlap primitive used by Sienna's ``SimulationAggregator``. This
        keeps file-specific parsing and cross-file overlap handling
        separate, so a plugin author (or this class) never needs its own
        bespoke dedup logic.
        """
        # Imported lazily to avoid a circular import: gat.simulations
        # eagerly imports PlexosDuckDBSimulation, which imports this module.
        from ..simulations.utils import combine_overlapping_frames

        frames = [
            self._pivot_one_file(alias, table, property_col)
            for alias in self._aliases
        ]
        frames = [f for f in frames if len(f) > 0]
        if not frames:
            raise KeyError(f"No data found for report table '{table}'")

        # "right": earlier files win at the overlap — matches the PLEXOS
        # rolling-horizon convention (gat.datahelpers.parsers.
        # combine_frames_skip_prev).
        combined = combine_overlapping_frames(frames, merge_strategy="right")
        return combined.reset_index()

    def query(self, sql: str, parameters: Iterable[Any] | None = None) -> pd.DataFrame:
        """Execute arbitrary SQL against the attached connection."""
        return self._conn.execute(sql, list(parameters) if parameters else []).fetchdf()
