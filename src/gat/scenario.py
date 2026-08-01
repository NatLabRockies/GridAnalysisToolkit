"""Scenario — the user-facing composition of system + simulation + DuckDB.

A Scenario is what users interact with. It composes:
- A BaseSystem (parsed power system definition)
- A BaseSimulation (parsed simulation results)
- A GATDatabase (DuckDB analytical engine)

It provides escape hatches at every level:
- Level 0: Raw DataFrames via system.get_dataset() / simulation.get_dataset()
- Level 1: All datasets (raw + composed) via list_datasets() / get_dataset()
- Level 2: Category-grouped queries via query(dataset, group_by=[...])
- Level 3: Common analytics (net_load, curtailment, ramp_rate, line_loading)
- Level 4: Plots via gat.quickplots (not implemented here)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

import numpy as np
import pandas as pd
from loguru import logger

from .backends.duckdb_backend import GATDatabase
from .categories import CategoryMap, CategoryMapRegistry
from .datasets import DatasetComposition, DatasetInfo, DatasetKind
from .interfaces import BaseSimulation, BaseSystem
from .models.palette import Palette


class Scenario:
    """High-level object composing system + simulation + DuckDB.

    Example usage::

        from gat import Scenario, GATDatabase
        from gat.systems.sienna import SiennaSystem
        from gat.simulations.sienna import SiennaSimulation

        system = SiennaSystem("/path/to/system.json")
        simulation = SiennaSimulation("/path/to/sim.h5")
        db = GATDatabase()  # in-memory

        scenario = Scenario(
            system=system,
            simulation=simulation,
            db=db,
            project="rts-gmlc",
            name="base-case",
        )
        scenario.ingest()

        # Level 0: raw DataFrames
        thermal = scenario.system.get_dataset("ThermalStandard")

        # Level 1: list everything
        for ds in scenario.list_datasets():
            print(ds.name, ds.kind)

        # Level 2: grouped query
        gen_by_tech = scenario.query("generation", group_by=["technology_simple"])

        # Level 3: analytics
        net = scenario.net_load()
    """

    def __init__(
        self,
        system: BaseSystem,
        simulation: BaseSimulation,
        db: GATDatabase,
        project: str,
        name: str,
        schema_name: str | None = None,
    ) -> None:
        self.system = system
        self.simulation = simulation
        self.db = db
        self.project = project
        self.name = name
        # Sienna H5 files contain multiple optimization stages; the server
        # ingests each into its own schema (``{project}__{scenario}__{model}``).
        # The server-side ingest_scenario passes the model-aware name in;
        # direct callers (notebooks, REPL) get the legacy single-schema
        # behavior if they don't specify one.
        self._schema = schema_name or f"{project}__{name}".replace("-", "_")
        self._ingested = False
        self._palettes: dict[str, Palette] = {}

    @classmethod
    def from_plexos_duckdb(
        cls,
        solution_paths: str | Path | list[str | Path],
        project: str = "plexos",
        name: str = "duckdb",
        force_convert: bool = False,
        db: GATDatabase | None = None,
        full_ingest: bool = False,
    ) -> Scenario:
        """Build and ingest a Scenario from PLEXOS solution ``.zip`` file(s).

        Convenience one-liner over ``PlexosDuckDBSystem`` +
        ``PlexosDuckDBSimulation`` + ``GATDatabase`` + ``Scenario.ingest()``
        for the plexos2duckdb-backed backend (optional dependency —
        ``pip install nlr-gat[plexos-duckdb]``). Each path may be a PLEXOS
        solution ``.zip`` (converted on demand, cached next to it) or an
        already-converted ``.duckdb`` file; pass a list for multiple
        rolling-horizon solution files.

        Example::

            from gat import Scenario
            scenario = Scenario.from_plexos_duckdb("/path/to/Solution.zip")
            scenario.query("generation", group_by=["gen_area"])

        Args:
            solution_paths: One or more PLEXOS solution ``.zip``/``.duckdb`` paths.
            project: Project name for the DuckDB schema (default "plexos").
            name: Scenario name for the DuckDB schema (default "duckdb").
            force_convert: Reconvert every ``.zip`` even if a fresh
                ``.duckdb`` cache already exists.
            db: Optional pre-existing ``GATDatabase`` to ingest into.
                Defaults to a new in-memory instance.
            full_ingest: If True, ingest every report table the solution
                exposes (there can be 100+, covering every PLEXOS
                property) instead of just what the "generation"
                composition needs. Slow (minutes, not seconds, on a
                real multi-thousand-generator solution) and can crash on
                properties with special characters in their name (e.g.
                PLEXOS's "Start & Shutdown Cost") — see
                docs/source/architecture/v1_migration_pattern.md. Off by
                default; this backend's dataset coverage is generation-only
                today (see that doc for the composition-based extension
                pattern if you need more).

        Returns:
            An already-ingested ``Scenario``, ready to query.
        """
        from .backends.duckdb_backend import GATDatabase as _GATDatabase
        from .datasets import DatasetKind
        from .simulations.plexos_duckdb import PlexosDuckDBSimulation
        from .systems.plexos_duckdb import PlexosDuckDBSystem

        system = PlexosDuckDBSystem(solution_paths, force_convert=force_convert)
        simulation = PlexosDuckDBSimulation(solution_paths, force_convert=force_convert)
        scenario = cls(
            system=system, simulation=simulation, db=db or _GATDatabase(),
            project=project, name=name,
        )

        dataset_filter = None
        if not full_ingest:
            needed: set[str] = set()
            for ds in simulation.list_datasets():
                if ds.kind == DatasetKind.COMPOSED:
                    needed.add(ds.name)
                    needed.update(ds.source_datasets or [])
            dataset_filter = lambda ds: ds.name in needed  # noqa: E731

        scenario.ingest(dataset_filter=dataset_filter)
        return scenario

    @property
    def schema(self) -> str:
        """DuckDB schema name for this scenario."""
        return self._schema

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def ingest(self, dataset_filter=None, include_system: bool = True) -> None:
        """Parse source data into DuckDB.

        1. Ingest raw system datasets (entity_id | properties) — skipped
           if ``include_system=False`` (tier-2 background re-ingest;
           system tables already wrote in tier-1).
        2. Ingest raw simulation datasets passing ``dataset_filter``.
        3. Build composed tables whose sources are all in this tier.
        4. Register default category maps (system + simulation).

        ``dataset_filter`` selects which simulation datasets are
        included. None = everything.
        """
        import time as _time
        logger.info(
            "Ingesting scenario '{}/{}' into schema '{}'",
            self.project, self.name, self._schema,
        )

        _t0 = _time.perf_counter()
        if include_system:
            self.db.ingest_system(self._schema, self.system)
        _t1 = _time.perf_counter()
        self.db.ingest_simulation(self._schema, self.simulation, dataset_filter=dataset_filter)
        _t2 = _time.perf_counter()

        # Register default category maps
        for cat_map in self.system.get_default_category_maps():
            self.db.register_category_map(self._schema, cat_map)
        for cat_map in self.simulation.get_default_category_maps():
            self.db.register_category_map(self._schema, cat_map)
        _t3 = _time.perf_counter()

        # Store branch ratings + generator ratings in MW for downstream
        # consumers (server clients, notebooks). Both writes share one
        # ``with_write_conn`` window so the server's per-call lock /
        # detach overhead is paid once, not twice.
        base_power = getattr(self.simulation, "base_power", None)
        try:
            branch_ratings = self.system.get_branch_ratings(base_power=base_power)
        except Exception as e:
            logger.warning("Could not read branch ratings: {}", e)
            branch_ratings = None
        try:
            gen_ratings = self.system.get_generator_ratings()
        except Exception as e:
            logger.warning("Could not read generator ratings: {}", e)
            gen_ratings = None

        if branch_ratings or gen_ratings:
            import pandas as pd
            branch_df = (
                pd.DataFrame([
                    {"name": k, "rating_mw": v} for k, v in branch_ratings.items()
                ]) if branch_ratings else None
            )
            gen_df = (
                pd.DataFrame([
                    {"name": k, "rating_mw": v} for k, v in gen_ratings.items()
                ]) if gen_ratings else None
            )

            def _write_ratings(conn):
                if branch_df is not None:
                    tn = f"{self._schema}.branch_ratings"
                    conn.execute(
                        f"CREATE OR REPLACE TABLE {tn} AS SELECT * FROM branch_df"
                    )
                    logger.info("Stored {} branch ratings (MW) in {}", len(branch_df), tn)
                if gen_df is not None:
                    tn = f"{self._schema}.generator_ratings"
                    conn.execute(
                        f"CREATE OR REPLACE TABLE {tn} AS SELECT * FROM gen_df"
                    )
                    logger.info("Stored {} generator ratings (MW) in {}", len(gen_df), tn)

            try:
                self.db.with_write_conn(_write_ratings)
            except Exception as e:
                logger.warning("Could not store ratings: {}", e)

        _t4 = _time.perf_counter()
        self._ingested = True
        logger.info(
            "[ingest-timing] system={:.1f}s sim={:.1f}s catmaps={:.1f}s "
            "ratings={:.1f}s total={:.1f}s",
            _t1 - _t0, _t2 - _t1, _t3 - _t2, _t4 - _t3, _t4 - _t0,
        )
        logger.info("Ingestion complete for '{}/{}'", self.project, self.name)

    # ------------------------------------------------------------------ #
    # Level 1: Dataset discovery
    # ------------------------------------------------------------------ #

    def list_datasets(self) -> list[DatasetInfo]:
        """Return a unified list of all datasets (system + simulation + composed).

        Each entry's `kind` field indicates whether it's RAW_SYSTEM,
        RAW_SIMULATION, or COMPOSED.
        """
        result: list[DatasetInfo] = []
        result.extend(self.system.list_datasets())
        result.extend(self.simulation.list_datasets())
        return result

    def get_dataset(self, name: str) -> pd.DataFrame:
        """Get any dataset by name.

        Checks system datasets first, then simulation datasets.
        For raw datasets, delegates to the parser (Level 0).
        For composed datasets at Level 0, returns concatenated columns.
        """
        # Try system first
        sys_names = {ds.name for ds in self.system.list_datasets()}
        if name in sys_names:
            return self.system.get_dataset(name)

        # Then simulation
        sim_names = {ds.name for ds in self.simulation.list_datasets()}
        if name in sim_names:
            return self.simulation.get_dataset(name)

        raise KeyError(
            f"Dataset '{name}' not found. Available: "
            f"{sorted(sys_names | sim_names)}"
        )

    # ------------------------------------------------------------------ #
    # Level 2: Category-grouped queries
    # ------------------------------------------------------------------ #

    def list_category_maps(self, dataset: str | None = None) -> list[str]:
        """List available category maps.

        Args:
            dataset: If given, filter to maps applicable to this dataset.
        """
        registry = self.db.get_category_registry(self._schema)
        if dataset is None:
            return registry.list_maps()
        return registry.list_for_dataset(dataset)

    def query(
        self,
        dataset: str,
        group_by: list[str] | None = None,
        palette: Union[str, Palette, None] = None,
    ) -> pd.DataFrame:
        """Query a dataset with optional category map grouping or palette.

        When ``palette`` is provided the palette's ``category_map`` is used
        for the GROUP BY, then simulation categories are re-aggregated into
        display categories and columns are ordered per ``stack_order``.

        ``palette`` and ``group_by`` are mutually exclusive.

        Args:
            dataset: Dataset name (raw or composed).
            group_by: List of category map names to GROUP BY.
                If None, returns the raw table from DuckDB.
            palette: A :class:`Palette` object or the name of a registered
                palette.  If given, takes precedence over *group_by*.

        Returns:
            Wide DataFrame. For grouped/palette queries on composed simulation
            tables: category rows × timestamp columns.
        """
        if palette is not None:
            pal = self._resolve_palette(palette)
            return self._apply_palette(dataset, pal)
        if group_by:
            return self.db.query_grouped(self._schema, dataset, group_by)
        # Return the table directly
        table = f"{self._schema}.{dataset.replace('-', '_')}"
        return self.db.query(f"SELECT * FROM {table}")

    def sql(self, query: str) -> pd.DataFrame:
        """Direct SQL escape hatch against DuckDB."""
        return self.db.query(query)

    # ------------------------------------------------------------------ #
    # Level 3: Common analytics
    # ------------------------------------------------------------------ #

    def net_load(
        self,
        load_dataset: str = "load",
        generation_dataset: str = "generation",
        vre_categories: list[str] | None = None,
        area_map: str = "native_area",
        tech_map: str | None = None,
    ) -> pd.DataFrame:
        """Compute net load = total load - VRE generation, grouped by area.

        Net load per area per timestamp:
            net_load[area, t] = sum(load[area, t]) - sum(vre_gen[area, t])

        Args:
            load_dataset: Composed dataset name for load (default "load").
            generation_dataset: Composed dataset name for generation
                (default "generation").
            vre_categories: Technology categories considered VRE/curtailable.
                If None, no VRE subtraction is performed and the result is
                simply total load by area.
            area_map: Category map name for area grouping.
            tech_map: Category map name for technology (required if
                vre_categories is provided, to identify VRE generators).

        Returns:
            Wide DataFrame: area rows × timestamp columns (MW).
        """
        s = self._schema

        # Total load by area
        load_by_area = self.query(load_dataset, group_by=[area_map])

        if vre_categories is None or tech_map is None:
            return load_by_area

        # VRE generation by area — filter to vre categories in SQL
        vre_cat_list = ", ".join(f"'{c}'" for c in vre_categories)
        cat_table = f"{s}.catmap__{tech_map}"
        area_table = f"{s}.catmap__{area_map}"
        gen_table = f"{s}.{generation_dataset}"

        ts_cols = self.db.get_timestamp_columns(s, generation_dataset)
        sum_exprs = ", ".join(f'SUM("{c}") AS "{c}"' for c in ts_cols)

        sql = f"""
            SELECT a.category AS {area_map}, {sum_exprs}
            FROM {gen_table} g
            JOIN {cat_table} t ON g.entity_id = t.entity_id
            JOIN {area_table} a ON g.entity_id = a.entity_id
            WHERE t.category IN ({vre_cat_list})
            GROUP BY a.category
            ORDER BY a.category
        """
        vre_by_area = self.db.query(sql)

        # Subtract VRE from load, aligning on area
        load_by_area = load_by_area.set_index(area_map)
        vre_by_area = vre_by_area.set_index(area_map)

        # Align — areas without VRE keep full load
        net = load_by_area.sub(vre_by_area.reindex(load_by_area.index, fill_value=0.0))
        return net.reset_index()

    def curtailment(
        self,
        generation_dataset: str = "generation",
        availability_dataset: str = "availability",
        vre_categories: list[str] | None = None,
        tech_map: str | None = None,
    ) -> pd.DataFrame:
        """Compute curtailment = availability - generation for VRE techs.

        curtailment[entity, t] = max(0, availability[entity, t] - generation[entity, t])

        Args:
            generation_dataset: Composed dataset for actual generation.
            availability_dataset: Composed dataset for max available power
                (e.g. from ActivePowerTimeSeriesParameter datasets).
            vre_categories: If provided with tech_map, only compute
                curtailment for entities in these technology categories.
            tech_map: Category map for technology filtering.

        Returns:
            Wide DataFrame: entity_id rows × timestamp columns (MW).
            Values are clamped to >= 0.
        """
        s = self._schema
        gen_table = f"{s}.{generation_dataset}"
        avail_table = f"{s}.{availability_dataset}"

        ts_cols = self.db.get_timestamp_columns(s, generation_dataset)

        if vre_categories and tech_map:
            # Filter to VRE entities only
            vre_cat_list = ", ".join(f"'{c}'" for c in vre_categories)
            cat_table = f"{s}.catmap__{tech_map}"

            diff_exprs = ", ".join(
                f'GREATEST(0, a."{c}" - g."{c}") AS "{c}"' for c in ts_cols
            )
            sql = f"""
                SELECT g.entity_id, {diff_exprs}
                FROM {gen_table} g
                JOIN {avail_table} a ON g.entity_id = a.entity_id
                JOIN {cat_table} t ON g.entity_id = t.entity_id
                WHERE t.category IN ({vre_cat_list})
                ORDER BY g.entity_id
            """
        else:
            # All entities that appear in both tables
            diff_exprs = ", ".join(
                f'GREATEST(0, a."{c}" - g."{c}") AS "{c}"' for c in ts_cols
            )
            sql = f"""
                SELECT g.entity_id, {diff_exprs}
                FROM {gen_table} g
                JOIN {avail_table} a ON g.entity_id = a.entity_id
                ORDER BY g.entity_id
            """

        return self.db.query(sql)

    def ramp_rate(
        self,
        dataset: str = "generation",
        group_by: list[str] | None = None,
    ) -> pd.DataFrame:
        """Compute ramp rate (MW/min) between consecutive timestamps.

        ramp_rate[t] = (value[t] - value[t-1]) / minutes_between_timestamps

        Args:
            dataset: Composed dataset to compute ramp rate on.
                Can be "generation", "load", or any composed timeseries.
            group_by: Optional category maps to group by before computing
                ramp rate. For example, ["native_area"] computes ramp rate
                of total generation per area.

        Returns:
            Wide DataFrame with same shape as the grouped query, but values
            are MW/min. First timestamp column will be NaN (no prior value).
        """
        if group_by:
            df = self.query(dataset, group_by=group_by)
            group_cols = list(group_by)
        else:
            df = self.query(dataset)
            group_cols = ["entity_id"]

        ts_cols = [c for c in df.columns if c not in group_cols]
        if len(ts_cols) < 2:
            raise ValueError("Need at least 2 timestamps to compute ramp rate")

        # Infer time delta from ISO timestamp column names
        t0 = pd.Timestamp(ts_cols[0])
        t1 = pd.Timestamp(ts_cols[1])
        minutes = (t1 - t0).total_seconds() / 60.0
        if minutes <= 0:
            raise ValueError(
                f"Timestamps not in ascending order: {ts_cols[0]}, {ts_cols[1]}"
            )

        values = df[ts_cols].values.astype(np.float64)
        ramp = np.diff(values, axis=1) / minutes

        # Prepend NaN column for first timestamp
        nan_col = np.full((ramp.shape[0], 1), np.nan)
        ramp = np.hstack([nan_col, ramp])

        result = df[group_cols].copy()
        for i, col in enumerate(ts_cols):
            result[col] = ramp[:, i].astype(np.float32)

        return result

    def line_loading(
        self,
        flow_dataset: str = "line_flow",
        rating_map: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Compute line loading as percentage of line rating.

        loading[line, t] = |flow[line, t]| / rating[line] * 100

        Uses numpy for the core computation (vectorized divide + abs),
        which is critical for performance with 80k+ lines.

        Args:
            flow_dataset: Composed simulation dataset with line flows.
            rating_map: Mapping of entity names to MW ratings. If None,
                auto-builds from system.get_branch_ratings() which handles
                Line, MonitoredLine, TwoTerminalHVDCLine, AreaInterchange, etc.

        Returns:
            Wide DataFrame: entity_id rows × timestamp columns.
            Values are loading as a percentage (0-100+).
        """
        # Get flow data from composed table
        flow_df = self.query(flow_dataset)
        entity_ids = flow_df["entity_id"].values
        ts_cols = [c for c in flow_df.columns if c != "entity_id"]
        flow_matrix = flow_df[ts_cols].values

        # Build or use provided rating map
        if rating_map is None:
            # Pass base_power so per-unit ratings are scaled to MW
            base_power = getattr(self.simulation, "base_power", None)
            rating_map = self.system.get_branch_ratings(base_power=base_power)

        # Build ratings vector aligned to flow entities
        ratings = np.array(
            [rating_map.get(eid, np.nan) for eid in entity_ids],
            dtype=np.float32,
        )

        missing = np.isnan(ratings)
        zero = ratings == 0
        invalid = missing | zero

        if missing.any():
            logger.warning(
                "{} of {} flow entities have no rating — loading will be NaN",
                int(missing.sum()), len(ratings),
            )
        if zero.any():
            logger.warning(
                "{} of {} flow entities have zero rating — loading will be NaN",
                int(zero.sum()), len(ratings),
            )

        # Vectorized loading computation (same as compute.calc_loading)
        out = np.full_like(flow_matrix, np.nan, dtype=np.float32)
        loading_matrix = np.abs(
            np.divide(
                flow_matrix,
                ratings[:, np.newaxis],
                out=out,
                where=(~invalid)[:, np.newaxis],
            )
            * 100.0
        ).astype(np.float32)

        result = pd.DataFrame({"entity_id": entity_ids})
        for i, col in enumerate(ts_cols):
            result[col] = loading_matrix[:, i]

        return result

    def line_utilization(
        self,
        thresholds: list[float] | None = None,
        flow_dataset: str = "line_flow",
        rating_map: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Compute line utilization flags at various loading thresholds.

        For each threshold, returns 1 if loading >= threshold, else 0.

        Args:
            thresholds: Loading percentage thresholds (default [99, 95, 90, 75]).
            flow_dataset: Composed dataset with line flows.
            rating_map: Mapping of entity names to MW ratings (passed to
                line_loading). If None, auto-built from system.

        Returns:
            DataFrame with MultiIndex columns (threshold_label, timestamp)
            and entity_id rows. Values are 0 or 1.
        """
        if thresholds is None:
            thresholds = [99, 95, 90, 75]

        loading = self.line_loading(flow_dataset, rating_map=rating_map)
        entity_ids = loading["entity_id"]
        ts_cols = [c for c in loading.columns if c != "entity_id"]
        loading_matrix = loading[ts_cols].values

        frames = []
        for t in thresholds:
            congestion = (loading_matrix >= t).astype(np.int8)
            cols = pd.MultiIndex.from_tuples(
                [(f"U{t}", c) for c in ts_cols],
                names=["Utilization", "Timestamp"],
            )
            frames.append(
                pd.DataFrame(congestion, columns=cols, index=entity_ids.index)
            )

        result = pd.concat(
            [entity_ids.reset_index(drop=True)] + frames, axis=1
        )
        return result

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #

    def add_category_map(self, cat_map: CategoryMap) -> None:
        """Register a user-provided category map."""
        self.db.register_category_map(self._schema, cat_map)

    # ------------------------------------------------------------------ #
    # Palette management
    # ------------------------------------------------------------------ #

    def register_palette(self, palette: Palette) -> None:
        """Register a palette by name so it can be referenced in queries.

        Args:
            palette: A :class:`Palette` instance.
        """
        self._palettes[palette.name] = palette
        logger.debug("Registered palette '{}'", palette.name)

    def list_palettes(self) -> list[str]:
        """Return names of all registered palettes."""
        return list(self._palettes.keys())

    def _resolve_palette(self, palette: Union[str, Palette]) -> Palette:
        """Resolve a palette argument to a Palette object.

        Accepts either a Palette instance (used directly) or a string name
        (looked up in the scenario's registered palettes).
        """
        if isinstance(palette, Palette):
            return palette
        if palette in self._palettes:
            return self._palettes[palette]
        raise ValueError(
            f"Palette '{palette}' not found. "
            f"Available: {list(self._palettes.keys())}"
        )

    def _apply_palette(self, dataset: str, palette: Palette) -> pd.DataFrame:
        """Query *dataset* using the palette's category map, then re-aggregate.

        Steps:
            1. Use ``palette.category_map`` for GROUP BY
            2. Re-aggregate simulation categories → display categories
            3. Order columns per ``palette.stack_order``

        Returns:
            Wide DataFrame: display category rows × timestamp columns,
            with a leading column named after the palette's category_map.
        """
        cat_map_name = palette.category_map
        if cat_map_name is None:
            raise ValueError(
                f"Palette '{palette.name}' has no category_map set — "
                "cannot determine which category map to use for grouping."
            )

        # Step 1: GROUP BY the palette's category map
        raw = self.db.query_grouped(self._schema, dataset, [cat_map_name])

        # Step 2: Re-aggregate simulation categories → display categories
        agg_map = palette.get_aggregation_map()
        group_col = cat_map_name
        ts_cols = [c for c in raw.columns if c != group_col]

        # Map each row's category to a display name (unmapped → keep original)
        raw[group_col] = raw[group_col].map(
            lambda x: agg_map.get(x, x)
        )

        # Sum rows that now share the same display category
        result = raw.groupby(group_col, as_index=False)[ts_cols].sum()

        # Step 3: Order rows per stack_order
        ordered_names = palette.get_ordered_display_names()
        present = set(result[group_col].values)
        order = [n for n in ordered_names if n in present]
        # Append any categories not in the palette's ordering
        order += [n for n in result[group_col].values if n not in set(order)]

        result = result.set_index(group_col).loc[order].reset_index()
        return result

    def add_composition(self, comp: DatasetComposition) -> None:
        """Add a new composed dataset and materialize it."""
        ds_info = DatasetInfo(
            name=comp.name,
            description=comp.description,
            kind=DatasetKind.COMPOSED,
            entity_column=comp.entity_column,
            source_datasets=comp.source_datasets,
        )
        self.db._build_composed_simulation(self._schema, ds_info)

    def edit_composition(
        self,
        name: str,
        add: list[str] | None = None,
        remove: list[str] | None = None,
    ) -> None:
        """Modify an existing composition and rebuild the table.

        Args:
            name: Composition name (e.g. "generation")
            add: Raw dataset names to add to the composition
            remove: Raw dataset names to remove from the composition
        """
        # Find the existing composition
        all_datasets = self.list_datasets()
        existing = None
        for ds in all_datasets:
            if ds.name == name and ds.kind == DatasetKind.COMPOSED:
                existing = ds
                break

        if existing is None:
            raise KeyError(f"Composed dataset '{name}' not found")

        sources = list(existing.source_datasets or [])
        if add:
            sources.extend(s for s in add if s not in sources)
        if remove:
            sources = [s for s in sources if s not in remove]

        updated = DatasetInfo(
            name=name,
            description=existing.description,
            kind=DatasetKind.COMPOSED,
            entity_column=existing.entity_column,
            source_datasets=sources,
        )
        self.db._build_composed_simulation(self._schema, updated)
        logger.info("Rebuilt composed dataset '{}' with sources: {}", name, sources)
