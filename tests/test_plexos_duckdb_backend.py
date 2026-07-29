"""Tests for the plexos2duckdb-backed GAT v1 backend.

Builds small synthetic ``.duckdb`` files shaped like plexos2duckdb output
(``report`` / ``processed`` schemas) so these tests exercise
``PlexosDuckDBSystem`` / ``PlexosDuckDBSimulation`` / ``PlexosDuckDBSource``
without requiring a real PLEXOS solution file or the ``plexos2duckdb``
package itself (only the .zip -> .duckdb conversion step needs that; these
tests operate on already-"converted" files).
"""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from gat.backends.duckdb_backend import GATDatabase
from gat.datahelpers.plexos_duckdb import PlexosDuckDBSource
from gat.scenario import Scenario
from gat.simulations.plexos_duckdb import PlexosDuckDBSimulation
from gat.simulations.utils import resolve_compositions
from gat.systems.plexos_duckdb import PlexosDuckDBSystem

GEN_TABLE = "ST__Interval__Generators__Generation"


def _build_synthetic_solution(
    path: Path,
    generators: dict[str, str],
    timestamps: list[str],
    values: dict[str, list[float]],
) -> None:
    """Create a .duckdb file shaped like a plexos2duckdb conversion.

    Args:
        path: Output .duckdb path.
        generators: {generator_name: region_name}.
        timestamps: ISO timestamp strings, one row per timestamp.
        values: {generator_name: [value_per_timestamp]}.
    """
    conn = duckdb.connect(str(path))
    conn.execute("CREATE SCHEMA report")
    conn.execute("CREATE SCHEMA processed")

    rows = []
    for gen_name, vals in values.items():
        for ts, v in zip(timestamps, vals):
            rows.append((0, "base", gen_name, "Gas", ts, 60, v, "MW"))
    gen_df = pd.DataFrame(
        rows,
        columns=[
            "band", "sample_name", "name", "category",
            "timestamp", "interval_length", "Generation", "unit",
        ],
    )
    # Real plexos2duckdb report views store a native TIMESTAMP column.
    gen_df["timestamp"] = pd.to_datetime(gen_df["timestamp"])
    conn.execute(
        f'CREATE TABLE report."{GEN_TABLE}" AS SELECT * FROM gen_df'
    )

    objects_rows = []
    for i, (gen_name, region) in enumerate(generators.items()):
        objects_rows.append((i, gen_name, "Gas", "Generator", "Generator"))
    for i, region in enumerate(sorted(set(generators.values())), start=100):
        objects_rows.append((i, region, "Region", "Region", "Region"))
    objects_df = pd.DataFrame(
        objects_rows, columns=["id", "name", "category", "class_group", "class"]
    )
    conn.execute("CREATE TABLE processed.objects AS SELECT * FROM objects_df")

    membership_rows = []
    for i, (gen_name, region) in enumerate(generators.items()):
        membership_rows.append((
            i, region, "Generators", region, "Region", "Region", "Region",
            gen_name, "Generator", "Generator", "Gas", "Generator",
        ))
    membership_df = pd.DataFrame(
        membership_rows,
        columns=[
            "membership_id", "parent_id", "collection", "parent_name",
            "parent_class", "parent_group", "parent_category",
            "child_name", "child_class", "child_group", "child_category", "kind",
        ],
    )
    conn.execute(
        "CREATE TABLE processed.memberships AS SELECT * FROM membership_df"
    )
    conn.close()


@pytest.fixture()
def single_solution(tmp_path) -> Path:
    path = tmp_path / "sol.duckdb"
    _build_synthetic_solution(
        path,
        generators={"Gen1": "North", "Gen2": "South"},
        timestamps=["2030-01-01T00:00:00", "2030-01-01T01:00:00", "2030-01-01T02:00:00"],
        values={"Gen1": [10.0, 20.0, 30.0], "Gen2": [1.0, 2.0, 3.0]},
    )
    return path


@pytest.fixture()
def two_solutions(tmp_path) -> list[Path]:
    """Two overlapping solution files simulating a rolling PLEXOS horizon."""
    p0 = tmp_path / "sol0.duckdb"
    p1 = tmp_path / "sol1.duckdb"
    _build_synthetic_solution(
        p0,
        generators={"Gen1": "North"},
        timestamps=[
            "2030-01-01T00:00:00", "2030-01-01T01:00:00",
            "2030-01-01T02:00:00", "2030-01-01T03:00:00",
        ],
        values={"Gen1": [1.0, 2.0, 3.0, 4.0]},
    )
    # Overlaps at hours 2-3 with different (stale) values, then extends to 4-5.
    _build_synthetic_solution(
        p1,
        generators={"Gen1": "North"},
        timestamps=[
            "2030-01-01T02:00:00", "2030-01-01T03:00:00",
            "2030-01-01T04:00:00", "2030-01-01T05:00:00",
        ],
        values={"Gen1": [999.0, 999.0, 5.0, 6.0]},
    )
    return [p0, p1]


def _add_full_dataset_tables(path: Path, timestamps: list[str]) -> None:
    """Extend a `_build_synthetic_solution`-built file with the additional
    classes/report tables needed for "full parity" coverage: a
    storage-capable generator (Gen1, with head/tail Storage sub-objects
    mirroring its own Generation — the real-data pattern confirmed this
    session, see gat/systems/plexos_duckdb.py), a Line, and the
    availability/load/unserved/line_flow/storage_charging/production_cost/
    rating report tables.
    """
    conn = duckdb.connect(str(path))
    ts = pd.to_datetime(timestamps)
    n = len(ts)

    # Storage: Gen1_head mirrors Gen1's own Generation exactly (real-data
    # convention); Gen1_tail is always 0. Same for Pump_Load (charging).
    storage_objects = pd.DataFrame([
        (200, "Gen1_head", "-", "Electric", "Storage"),
        (201, "Gen1_tail", "-", "Electric", "Storage"),
    ], columns=["id", "name", "category", "class_group", "class"])
    conn.execute("INSERT INTO processed.objects SELECT * FROM storage_objects")

    line_objects = pd.DataFrame([(300, "Line1", "-", "Electric", "Line")],
                                 columns=["id", "name", "category", "class_group", "class"])
    conn.execute("INSERT INTO processed.objects SELECT * FROM line_objects")

    storage_memberships = pd.DataFrame([
        (100, "Gen1", "Head Storage", "Gen1", "Generator", "Generator", "Gas",
         "Gen1_head", "Storage", "Storage", "-", "Generator"),
        (101, "Gen1", "Tail Storage", "Gen1", "Generator", "Generator", "Gas",
         "Gen1_tail", "Storage", "Storage", "-", "Generator"),
    ], columns=[
        "membership_id", "parent_id", "collection", "parent_name",
        "parent_class", "parent_group", "parent_category",
        "child_name", "child_class", "child_group", "child_category", "kind",
    ])
    conn.execute("INSERT INTO processed.memberships SELECT * FROM storage_memberships")

    def _report_table(table: str, prop: str, entity_values: dict[str, list[float]]) -> None:
        rows = []
        for name, vals in entity_values.items():
            for t, v in zip(ts, vals):
                rows.append((0, "base", name, "cat", t, 60, v, "MW"))
        df = pd.DataFrame(rows, columns=[
            "band", "sample_name", "name", "category",
            "timestamp", "interval_length", prop, "unit",
        ])
        conn.execute(f'CREATE TABLE report."{table}" AS SELECT * FROM df')

    _report_table("ST__Interval__Generators__Available_Capacity", "Available_Capacity",
                   {"Gen1": [100.0] * n, "Gen2": [50.0] * n})
    _report_table("ST__Interval__Regions__Load", "Load",
                   {"North": [15.0] * n, "South": [8.0] * n})
    _report_table("ST__Interval__Regions__Unserved_Energy", "Unserved_Energy",
                   {"North": [0.0] * n, "South": [0.0] * n})
    _report_table("ST__Interval__Lines__Flow", "Flow", {"Line1": [42.0] * n})
    _report_table("ST__Interval__Generators__Total_Generation_Cost", "Total_Generation_Cost",
                   {"Gen1": [5.0] * n, "Gen2": [3.0] * n})
    # Gen1_head mirrors Gen1 exactly (real-data convention); tail is 0.
    _report_table("ST__Interval__Storages__Generation", "Generation",
                   {"Gen1_head": [10.0, 20.0, 30.0][:n], "Gen1_tail": [0.0] * n})
    _report_table("ST__Interval__Storages__Pump_Load", "Pump_Load",
                   {"Gen1_head": [5.0] * n, "Gen1_tail": [0.0] * n})

    _report_table("ST__Year__Generators__Installed_Capacity", "Installed_Capacity",
                   {"Gen1": [100.0], "Gen2": [50.0]})
    _report_table("ST__Year__Lines__Export_Limit", "Export_Limit", {"Line1": [500.0]})

    conn.close()


@pytest.fixture()
def full_solution(tmp_path) -> Path:
    """A synthetic solution extended with Storage/Line objects and the
    full set of report tables needed for "full parity" coverage."""
    path = tmp_path / "full_sol.duckdb"
    timestamps = ["2030-01-01T00:00:00", "2030-01-01T01:00:00", "2030-01-01T02:00:00"]
    _build_synthetic_solution(
        path,
        generators={"Gen1": "North", "Gen2": "South"},
        timestamps=timestamps,
        values={"Gen1": [10.0, 20.0, 30.0], "Gen2": [1.0, 2.0, 3.0]},
    )
    _add_full_dataset_tables(path, timestamps)
    return path


# ------------------------------------------------------------------ #
# PlexosDuckDBSource
# ------------------------------------------------------------------ #


class TestPlexosDuckDBSource:
    def test_report_tables(self, single_solution):
        with PlexosDuckDBSource(single_solution) as source:
            assert GEN_TABLE in source.report_tables()

    def test_objects(self, single_solution):
        with PlexosDuckDBSource(single_solution) as source:
            gens = source.objects("Generator")
            assert sorted(gens["name"]) == ["Gen1", "Gen2"]
            regions = source.objects("Region")
            assert sorted(regions["name"]) == ["North", "South"]

    def test_membership_map(self, single_solution):
        with PlexosDuckDBSource(single_solution) as source:
            mapping = source.membership_map(
                parent_class="Region", child_class="Generator"
            )
            assert mapping == {"Gen1": "North", "Gen2": "South"}

    def test_pivot_wide_single_file(self, single_solution):
        with PlexosDuckDBSource(single_solution) as source:
            df = source.pivot_wide(GEN_TABLE, "Generation")
            assert list(df["timestamp"]) == list(
                pd.to_datetime([
                    "2030-01-01T00:00:00", "2030-01-01T01:00:00", "2030-01-01T02:00:00",
                ])
            )
            assert df.set_index("timestamp")["Gen1"].tolist() == [10.0, 20.0, 30.0]
            assert df.set_index("timestamp")["Gen2"].tolist() == [1.0, 2.0, 3.0]

    def test_pivot_wide_multi_file_dedup(self, two_solutions):
        """Overlapping timestamps: the earlier file wins (dedup_slices 'right')."""
        with PlexosDuckDBSource(two_solutions) as source:
            df = source.pivot_wide(GEN_TABLE, "Generation").set_index("timestamp")
            expected_index = pd.to_datetime([
                "2030-01-01T00:00:00", "2030-01-01T01:00:00",
                "2030-01-01T02:00:00", "2030-01-01T03:00:00",
                "2030-01-01T04:00:00", "2030-01-01T05:00:00",
            ])
            assert list(df.index) == list(expected_index)
            # Hours 2-3 come from the first (earlier-start) file, not the
            # overlapping 999.0 stand-in values in the second file.
            assert df["Gen1"].tolist() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


# ------------------------------------------------------------------ #
# PlexosDuckDBSystem
# ------------------------------------------------------------------ #


class TestPlexosDuckDBSystem:
    def test_list_datasets(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        names = {ds.name for ds in system.list_datasets()}
        assert names == {"Generator", "Region", "Storage"}

    def test_get_dataset_storage_empty_when_absent(self, single_solution):
        """single_solution has no Storage objects — should return an
        empty (not erroring) frame, matching "absent gracefully"."""
        system = PlexosDuckDBSystem(single_solution)
        storages = system.get_dataset("Storage")
        assert len(storages) == 0

    def test_get_dataset(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        gens = system.get_dataset("Generator")
        assert sorted(gens["name"]) == ["Gen1", "Gen2"]

    def test_get_dataset_unknown_raises(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        with pytest.raises(KeyError):
            system.get_dataset("NotAClass")

    def test_default_category_maps(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        maps = {m.name: m for m in system.get_default_category_maps()}
        assert maps["gen_area"].mapping == {"Gen1": "North", "Gen2": "South"}

    def test_default_category_maps_unaffected_by_storage_presence(self, full_solution):
        """Storage objects exist in full_solution (Gen1_head/Gen1_tail),
        but gen_area must NOT include them — they're not separate
        generation entities, see module docstring / real-data findings."""
        system = PlexosDuckDBSystem(full_solution)
        maps = {m.name: m for m in system.get_default_category_maps()}
        assert maps["gen_area"].mapping == {"Gen1": "North", "Gen2": "South"}

    def test_get_generator_ratings(self, full_solution):
        system = PlexosDuckDBSystem(full_solution)
        ratings = system.get_generator_ratings()
        assert ratings == {"Gen1": 100.0, "Gen2": 50.0}

    def test_get_generator_ratings_absent_returns_empty(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        assert system.get_generator_ratings() == {}

    def test_get_branch_ratings(self, full_solution):
        system = PlexosDuckDBSystem(full_solution)
        ratings = system.get_branch_ratings(base_power=100.0)
        assert ratings == {"Line1": 500.0}

    def test_get_branch_ratings_absent_returns_empty(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        assert system.get_branch_ratings() == {}


# ------------------------------------------------------------------ #
# PlexosDuckDBSimulation
# ------------------------------------------------------------------ #


class TestPlexosDuckDBSimulation:
    def test_list_datasets(self, single_solution):
        sim = PlexosDuckDBSimulation(single_solution)
        names = {ds.name for ds in sim.list_datasets()}
        assert GEN_TABLE in names
        assert "generation" in names

    def test_get_raw_dataset(self, single_solution):
        sim = PlexosDuckDBSimulation(single_solution)
        df = sim.get_dataset(GEN_TABLE)
        assert isinstance(df.index, pd.DatetimeIndex)
        assert df["Gen1"].tolist() == [10.0, 20.0, 30.0]

    def test_get_composed_generation_dataset(self, single_solution):
        sim = PlexosDuckDBSimulation(single_solution)
        df = sim.get_dataset("generation")
        assert set(df.columns) == {"Gen1", "Gen2"}

    def test_unknown_dataset_raises(self, single_solution):
        sim = PlexosDuckDBSimulation(single_solution)
        with pytest.raises(KeyError):
            sim.get_dataset("not_a_dataset")

    def test_composition_override(self, single_solution):
        sim = PlexosDuckDBSimulation(
            single_solution, compositions={"custom": [GEN_TABLE]}
        )
        names = {ds.name for ds in sim.list_datasets()}
        assert "custom" in names
        assert "generation" not in names

    def test_generation_excludes_storage(self, full_solution):
        """generation must stay generator-only — Storage's mirrored
        Generation would double-count if unioned in."""
        sim = PlexosDuckDBSimulation(full_solution)
        df = sim.get_dataset("generation")
        assert set(df.columns) == {"Gen1", "Gen2"}
        assert df["Gen1"].tolist() == [10.0, 20.0, 30.0]

    def test_new_default_compositions_resolve(self, full_solution):
        sim = PlexosDuckDBSimulation(full_solution)
        names = {ds.name for ds in sim.list_datasets()}
        for comp in ["availability", "load", "unserved", "line_flow",
                     "storage_charging", "production_cost"]:
            assert comp in names, f"{comp} missing from {names}"

    def test_storage_charging_raw_has_both_head_and_tail(self, full_solution):
        """The raw composed dataset exposes both columns — filtering to
        _head-only is BaseScenario/PlexosScenario's job, not this class's."""
        sim = PlexosDuckDBSimulation(full_solution)
        df = sim.get_dataset("storage_charging")
        assert set(df.columns) == {"Gen1_head", "Gen1_tail"}
        assert df["Gen1_head"].tolist() == [5.0, 5.0, 5.0]
        assert df["Gen1_tail"].tolist() == [0.0, 0.0, 0.0]

    def test_load_and_unserved_compositions(self, full_solution):
        sim = PlexosDuckDBSimulation(full_solution)
        load = sim.get_dataset("load")
        assert set(load.columns) == {"North", "South"}
        unserved = sim.get_dataset("unserved")
        assert set(unserved.columns) == {"North", "South"}

    def test_line_flow_composition(self, full_solution):
        sim = PlexosDuckDBSimulation(full_solution)
        flow = sim.get_dataset("line_flow")
        assert list(flow.columns) == ["Line1"]
        assert flow["Line1"].tolist() == [42.0, 42.0, 42.0]

    def test_generation_capacity_raw_table_accessible(self, full_solution):
        """generation_capacity isn't a composition — it's read by exact
        raw table name (annual/single-row), confirm that still works."""
        sim = PlexosDuckDBSimulation(full_solution)
        df = sim.get_dataset("ST__Year__Generators__Installed_Capacity")
        assert df.iloc[0].to_dict() == {"Gen1": 100.0, "Gen2": 50.0}


def test_resolve_compositions_matches_plexos_table_shape():
    """Sanity check that the shared helper matches plexos2duckdb's naming."""
    resolved = resolve_compositions(
        [GEN_TABLE, "ST__interval__Regions__Load"],
        {"generation": [GEN_TABLE]},
    )
    assert resolved == {"generation": [GEN_TABLE]}


# ------------------------------------------------------------------ #
# End-to-end via Scenario (System + Simulation + GATDatabase)
# ------------------------------------------------------------------ #


class TestScenarioIntegration:
    def test_ingest_and_grouped_query(self, single_solution):
        system = PlexosDuckDBSystem(single_solution)
        sim = PlexosDuckDBSimulation(single_solution)
        db = GATDatabase()
        scenario = Scenario(
            system=system, simulation=sim, db=db,
            project="test", name="plexos-duckdb",
        )
        scenario.ingest()

        wide = scenario.query("generation", group_by=["gen_area"])
        totals = {
            str(row[0]): float(sum(row[1:]))
            for row in wide.itertuples(index=False)
        }
        # Gen1 (North) = 10+20+30 = 60; Gen2 (South) = 1+2+3 = 6
        assert totals == pytest.approx({"North": 60.0, "South": 6.0})

    def test_from_plexos_duckdb_one_liner(self, single_solution):
        scenario = Scenario.from_plexos_duckdb(single_solution)

        wide = scenario.query("generation", group_by=["gen_area"])
        totals = {
            str(row[0]): float(sum(row[1:]))
            for row in wide.itertuples(index=False)
        }
        assert totals == pytest.approx({"North": 60.0, "South": 6.0})

    def test_from_plexos_duckdb_default_skips_unrelated_tables(self, tmp_path):
        """Default (full_ingest=False) only ingests what "generation" needs
        — an unrelated raw table (even one with a special character in its
        name, like a real PLEXOS "Start & Shutdown Cost" property) must not
        be pulled in or crash ingestion."""
        path = tmp_path / "sol.duckdb"
        _build_synthetic_solution(
            path,
            generators={"Gen1": "North"},
            timestamps=["2030-01-01T00:00:00"],
            values={"Gen1": [10.0]},
        )
        # Add a second, unrelated report table with a special character in
        # its name — mirrors a real crash found against production data.
        conn = duckdb.connect(str(path))
        extra = pd.DataFrame(
            [(0, "base", "Gen1", "Gas", pd.Timestamp("2030-01-01"), 60, 1.0, "$")],
            columns=[
                "band", "sample_name", "name", "category",
                "timestamp", "interval_length", "Start_&_Shutdown_Cost", "unit",
            ],
        )
        conn.execute(
            'CREATE TABLE report."ST__Interval__Generators__Start_&_Shutdown_Cost" '
            "AS SELECT * FROM extra"
        )
        conn.close()

        scenario = Scenario.from_plexos_duckdb(path)
        tables = scenario.db.list_tables(scenario.schema)
        assert "sim__ST__Interval__Generators__Start_&_Shutdown_Cost" not in tables
        assert "generation" in tables


# ------------------------------------------------------------------ #
# Real solution .zip integration (skipped without GAT_PLEXOS_ZIP_FIXTURE)
# ------------------------------------------------------------------ #


def _resolve_zip_path(root: Path) -> Path:
    """``plexos_zip_fixture_root`` may point at a directory or a file."""
    if root.is_dir():
        zips = sorted(root.glob("*.zip"))
        assert zips, f"no .zip files found in {root}"
        return zips[0]
    return root


class TestRealSolutionZip:
    """Exercises the real .zip -> plexos2duckdb -> System/Simulation path.

    Skipped until a real PLEXOS solution .zip is available — see
    ``plexos_zip_fixture_root`` in tests/conftest.py. Requires the
    optional `plexos2duckdb` dependency (``pip install nlr-gat[plexos-duckdb]``).
    """

    def test_convert_and_load(self, plexos_zip_fixture_root):
        zip_path = _resolve_zip_path(plexos_zip_fixture_root)

        system = PlexosDuckDBSystem(zip_path)
        sim = PlexosDuckDBSimulation(zip_path)

        datasets = {ds.name for ds in sim.list_datasets()}
        assert "generation" in datasets

        gen = sim.get_dataset("generation")
        assert isinstance(gen.index, pd.DatetimeIndex)
        assert len(gen.columns) > 0

        area_map = {
            m.name: m for m in system.get_default_category_maps()
        }
        assert "gen_area" in area_map


class TestRealSolutionZipVsLegacyH5Parity:
    """Parity check against the legacy h5plexos-based path.

    ``Eclipse2031_update_Feb25`` (see the ``plexos_zip_fixture_root``
    fixture) ships both a native ``Solution.zip`` and the h5plexos-
    converted ``Solution.h5`` for the *same* underlying PLEXOS solve
    (same base filename, different extension) — a rare chance to compare
    the new plexos2duckdb-backed path against the legacy
    ``PlexosScenario`` path on real, non-synthetic data.

    Not a strict regression gate (the two tools are independent
    converters) — see docs/source/architecture/v1_migration_pattern.md.
    """

    def test_area_aggregated_generation_matches_legacy(self, plexos_zip_fixture_root):
        zip_path = _resolve_zip_path(plexos_zip_fixture_root)
        h5_path = zip_path.with_suffix(".h5")
        if not h5_path.exists():
            pytest.skip(f"no matching .h5 file for {zip_path}")

        # Legacy path: pandas/h5py PlexosScenario, raw generation mapped to
        # area and summed.
        from gat.scenariohandlers import PlexosScenario

        legacy = PlexosScenario(solution_path=str(h5_path))
        legacy._use_cache = False
        legacy_gen = legacy.get_generation().copy()
        legacy_gen.columns = [
            str(legacy._gen_area_map.get(str(c), "other"))
            for c in legacy_gen.columns
        ]
        legacy_by_area = legacy_gen.T.groupby(level=0).sum().T
        legacy_totals = {
            str(area): float(legacy_by_area[area].sum())
            for area in legacy_by_area.columns
        }

        # New path: plexos2duckdb-backed System/Simulation -> Scenario ->
        # grouped query.
        system = PlexosDuckDBSystem(zip_path)
        sim = PlexosDuckDBSimulation(zip_path)
        db = GATDatabase()
        scenario = Scenario(
            system=system, simulation=sim, db=db,
            project="parity", name="eclipse-da",
        )
        # Real PLEXOS property names can contain characters (e.g. "&" in
        # "Start & Shutdown Cost") that GATDatabase's view registration
        # doesn't quote as identifiers — a pre-existing engine limitation,
        # not specific to this backend. Scope ingestion to what
        # "generation" actually needs to sidestep it here.
        needed = {"generation", GEN_TABLE}
        scenario.ingest(dataset_filter=lambda ds: ds.name in needed)
        wide = scenario.query("generation", group_by=["gen_area"])
        new_totals = {
            str(row[0]): float(sum(row[1:]))
            for row in wide.itertuples(index=False)
        }

        assert set(new_totals) == set(legacy_totals), (
            f"area sets differ: new={sorted(new_totals)} "
            f"legacy={sorted(legacy_totals)}"
        )
        for area in legacy_totals:
            assert new_totals[area] == pytest.approx(
                legacy_totals[area], rel=1e-3
            ), f"area {area}: new={new_totals[area]} legacy={legacy_totals[area]}"
