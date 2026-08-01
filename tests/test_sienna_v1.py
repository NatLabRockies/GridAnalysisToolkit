"""Tests for SiennaSystem and SiennaSimulation v1.0 wrappers.

Uses real ExtremeEvents data files in ./data/ExtremeEvents/.
"""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from gat.backends.duckdb_backend import GATDatabase
from gat.categories import CategoryMap
from gat.datasets import DatasetInfo, DatasetKind
from gat.scenario import Scenario
from gat.systems.sienna import SiennaSystem
from gat.simulations.sienna_v1 import SiennaSimulation

DATA_DIR = Path(__file__).parent.parent / "data" / "ExtremeEvents"
SYSTEM_PATH = DATA_DIR / "sys.json"
SIM_PATH = DATA_DIR / "simulation_store.h5"

pytestmark = pytest.mark.skipif(
    not SYSTEM_PATH.exists() or not SIM_PATH.exists(),
    reason="ExtremeEvents test data not available",
)


# ------------------------------------------------------------------ #
# Fixtures
# ------------------------------------------------------------------ #


@pytest.fixture(scope="module")
def sienna_system():
    return SiennaSystem(SYSTEM_PATH)


@pytest.fixture(scope="module")
def sienna_sim():
    return SiennaSimulation(SIM_PATH)


@pytest.fixture(scope="module")
def scenario(sienna_system, sienna_sim):
    db = GATDatabase()
    s = Scenario(
        system=sienna_system,
        simulation=sienna_sim,
        db=db,
        project="ee",
        name="test",
    )
    s.ingest()
    yield s
    db.close()


# ------------------------------------------------------------------ #
# SiennaSystem tests
# ------------------------------------------------------------------ #


class TestSiennaSystem:
    def test_list_datasets(self, sienna_system):
        datasets = sienna_system.list_datasets()
        names = {ds.name for ds in datasets}

        # Raw component types
        assert "ThermalStandard" in names
        assert "RenewableDispatch" in names
        assert "ACBus" in names
        assert "Line" in names

        # Composed datasets
        assert "generators" in names
        assert "loads" in names
        assert "branches" in names

    def test_dataset_kinds(self, sienna_system):
        datasets = sienna_system.list_datasets()

        thermal = next(ds for ds in datasets if ds.name == "ThermalStandard")
        assert thermal.kind == DatasetKind.RAW_SYSTEM

        gen = next(ds for ds in datasets if ds.name == "generators")
        assert gen.kind == DatasetKind.COMPOSED
        assert "ThermalStandard" in gen.source_datasets
        assert "RenewableDispatch" in gen.source_datasets

    def test_get_raw_dataset(self, sienna_system):
        df = sienna_system.get_dataset("ThermalStandard")
        assert len(df) > 0
        assert "name" in df.columns

    def test_get_composed_generators(self, sienna_system):
        df = sienna_system.get_dataset("generators")
        assert len(df) > 0
        assert "name" in df.columns

        # Should include generators from multiple types
        thermal = sienna_system.get_dataset("ThermalStandard")
        renewable = sienna_system.get_dataset("RenewableDispatch")
        assert len(df) >= len(thermal) + len(renewable)

    def test_default_category_maps(self, sienna_system):
        maps = sienna_system.get_default_category_maps()
        map_names = {m.name for m in maps}

        assert "native_area" in map_names
        assert "fuel" in map_names
        assert "prime_mover" in map_names

    def test_area_map_has_real_names(self, sienna_system):
        maps = sienna_system.get_default_category_maps()
        area_map = next(m for m in maps if m.name == "native_area")

        # Should have area names, not UUIDs
        areas = set(area_map.mapping.values())
        assert len(areas) > 1
        # Check it's not UUIDs
        for area in areas:
            assert not area.startswith("{"), f"Got UUID instead of name: {area}"

    def test_fuel_map(self, sienna_system):
        maps = sienna_system.get_default_category_maps()
        fuel_map = next(m for m in maps if m.name == "fuel")

        fuels = set(fuel_map.mapping.values())
        assert "NATURAL_GAS" in fuels or "Gas" in fuels or len(fuels) > 1

    def test_missing_dataset_raises(self, sienna_system):
        with pytest.raises(KeyError):
            sienna_system.get_dataset("nonexistent_dataset")


# ------------------------------------------------------------------ #
# SiennaSimulation tests
# ------------------------------------------------------------------ #


class TestSiennaSimulation:
    def test_list_datasets(self, sienna_sim):
        datasets = sienna_sim.list_datasets()
        names = {ds.name for ds in datasets}

        # Raw simulation datasets
        assert "ActivePowerVariable__ThermalStandard" in names
        assert "ActivePowerVariable__RenewableDispatch" in names

        # Composed datasets
        assert "generation" in names

    def test_composed_generation_sources(self, sienna_sim):
        datasets = sienna_sim.list_datasets()
        gen = next(ds for ds in datasets if ds.name == "generation")
        assert gen.kind == DatasetKind.COMPOSED
        assert "ActivePowerVariable__ThermalStandard" in gen.source_datasets
        assert "ActivePowerVariable__RenewableDispatch" in gen.source_datasets

    def test_get_raw_dataset(self, sienna_sim):
        df = sienna_sim.get_dataset("ActivePowerVariable__ThermalStandard")
        assert isinstance(df.index, pd.DatetimeIndex)
        assert len(df) > 0
        assert len(df.columns) > 0

    def test_get_composed_generation(self, sienna_sim):
        df = sienna_sim.get_dataset("generation")
        assert isinstance(df.index, pd.DatetimeIndex)

        # Should combine columns from multiple raw datasets
        thermal = sienna_sim.get_dataset("ActivePowerVariable__ThermalStandard")
        renewable = sienna_sim.get_dataset("ActivePowerVariable__RenewableDispatch")
        assert len(df.columns) >= len(thermal.columns) + len(renewable.columns)

    def test_missing_dataset_raises(self, sienna_sim):
        with pytest.raises(KeyError):
            sienna_sim.get_dataset("nonexistent_dataset")


# ------------------------------------------------------------------ #
# Full Scenario integration tests
# ------------------------------------------------------------------ #


class TestScenarioIntegration:
    def test_ingest_creates_tables(self, scenario):
        tables = scenario.db.list_tables(scenario.schema)
        assert "generation" in tables
        assert "sys__ThermalStandard" in tables

    def test_list_datasets(self, scenario):
        datasets = scenario.list_datasets()
        names = {ds.name for ds in datasets}
        assert "ThermalStandard" in names
        assert "generation" in names

    def test_ungrouped_query(self, scenario):
        gen = scenario.query("generation")
        assert "entity_id" in gen.columns
        assert len(gen) > 0

    def test_group_by_fuel(self, scenario):
        result = scenario.query("generation", group_by=["fuel"])
        assert "fuel" in result.columns
        fuels = set(result["fuel"])
        assert len(fuels) > 1
        assert "NATURAL_GAS" in fuels or "NUCLEAR" in fuels

    def test_group_by_area(self, scenario):
        result = scenario.query("generation", group_by=["native_area"])
        assert "native_area" in result.columns
        areas = set(result["native_area"])
        assert len(areas) > 1
        # Verify real area names
        for area in areas:
            assert not area.startswith("{")

    def test_multi_group(self, scenario):
        result = scenario.query("generation", group_by=["native_area", "fuel"])
        assert "native_area" in result.columns
        assert "fuel" in result.columns
        # Multiple area×fuel combinations
        assert len(result) > 6

    def test_sql_escape_hatch(self, scenario):
        result = scenario.sql(
            f"SELECT COUNT(*) as cnt FROM {scenario.schema}.generation"
        )
        assert result["cnt"].iloc[0] > 0

    def test_category_maps_list(self, scenario):
        maps = scenario.list_category_maps()
        assert "native_area" in maps
        assert "fuel" in maps
        assert "prime_mover" in maps

    def test_add_custom_category_map(self, scenario):
        # Get some entity IDs from generation
        gen = scenario.query("generation")
        entities = list(gen["entity_id"][:10])

        scenario.add_category_map(
            CategoryMap(
                name="test_group",
                description="Test grouping",
                mapping={
                    e: "GroupA" if i < 5 else "GroupB" for i, e in enumerate(entities)
                },
            )
        )
        assert "test_group" in scenario.list_category_maps()


# ------------------------------------------------------------------ #
# Level 3: Analytics tests
# ------------------------------------------------------------------ #


class TestAnalytics:
    def test_net_load_returns_areas(self, scenario):
        net = scenario.net_load()
        assert "native_area" in net.columns
        areas = set(net["native_area"])
        assert len(areas) > 1

    def test_net_load_has_values(self, scenario):
        net = scenario.net_load()
        ts_cols = [c for c in net.columns if c != "native_area"]
        assert len(ts_cols) > 0
        # All areas should have non-zero load
        assert (net[ts_cols].abs().sum(axis=1) > 0).all()

    def test_ramp_rate_shape(self, scenario):
        ramp = scenario.ramp_rate(group_by=["native_area"])
        assert "native_area" in ramp.columns
        ts_cols = [c for c in ramp.columns if c != "native_area"]
        assert len(ts_cols) >= 2
        # First timestamp should be NaN (no prior)
        assert ramp[ts_cols[0]].isna().all()
        # Subsequent timestamps should have values
        assert ramp[ts_cols[1]].notna().all()

    def test_ramp_rate_ungrouped(self, scenario):
        ramp = scenario.ramp_rate(dataset="generation")
        assert "entity_id" in ramp.columns
        assert len(ramp) > 0

    def test_line_loading_shape(self, scenario):
        loading = scenario.line_loading()
        assert "entity_id" in loading.columns
        ts_cols = [c for c in loading.columns if c != "entity_id"]
        assert len(ts_cols) > 0
        assert len(loading) > 0

    def test_line_loading_no_inf(self, scenario):
        loading = scenario.line_loading()
        ts_cols = [c for c in loading.columns if c != "entity_id"]
        values = loading[ts_cols].values
        assert not np.isinf(values).any()

    def test_line_loading_percentage_range(self, scenario):
        loading = scenario.line_loading()
        ts_cols = [c for c in loading.columns if c != "entity_id"]
        values = loading[ts_cols].values
        # Non-NaN values should be >= 0
        valid = values[~np.isnan(values)]
        assert (valid >= 0).all()

    def test_line_loading_custom_rating_map(self, scenario):
        flow_df = scenario.query("line_flow")
        entities = list(flow_df["entity_id"])
        custom_ratings = {e: 1000.0 for e in entities}
        loading = scenario.line_loading(rating_map=custom_ratings)
        ts_cols = [c for c in loading.columns if c != "entity_id"]
        # No NaN since all entities have ratings
        assert not np.isnan(loading[ts_cols].values).any()

    def test_branch_ratings_from_system(self, sienna_system):
        ratings = sienna_system.get_branch_ratings()
        assert len(ratings) > 0
        # All ratings should be numeric and non-negative
        for name, rating in list(ratings.items())[:100]:
            assert isinstance(rating, float)
            assert rating >= 0

    def test_line_utilization_shape(self, scenario):
        util = scenario.line_utilization()
        assert "entity_id" in util.columns
        assert len(util) > 0

    def test_line_utilization_binary(self, scenario):
        util = scenario.line_utilization()
        # All non-entity_id columns should be 0 or 1
        data_cols = [c for c in util.columns if c != "entity_id"]
        values = util[data_cols].values
        assert set(np.unique(values[~np.isnan(values)])).issubset({0, 1})
