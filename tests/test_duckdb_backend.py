"""Tests for the GAT v1.0.0 DuckDB analytical backend.

Exercises the full pipeline:
  BaseSystem + BaseSimulation → GATDatabase → Scenario → grouped queries
"""

import numpy as np
import pandas as pd
import pytest

from gat.backends.duckdb_backend import GATDatabase
from gat.categories import CategoryMap, CategoryMapRegistry
from gat.datasets import DatasetComposition, DatasetInfo, DatasetKind
from gat.interfaces import BaseSimulation, BaseSystem
from gat.scenario import Scenario


# ------------------------------------------------------------------ #
# Mock implementations
# ------------------------------------------------------------------ #


class MockSystem(BaseSystem):
    """Mock system with 5 generators across 2 areas."""

    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name="ThermalStandard",
                description="Thermal generators",
                kind=DatasetKind.RAW_SYSTEM,
                entity_column="name",
                columns=["name", "bus", "area", "fuel", "capacity_mw"],
            ),
            DatasetInfo(
                name="RenewableDispatch",
                description="Renewable generators",
                kind=DatasetKind.RAW_SYSTEM,
                entity_column="name",
                columns=["name", "bus", "area", "fuel", "capacity_mw"],
            ),
            DatasetInfo(
                name="generators",
                description="All generators",
                kind=DatasetKind.COMPOSED,
                entity_column="name",
                source_datasets=["ThermalStandard", "RenewableDispatch"],
            ),
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name == "ThermalStandard":
            return pd.DataFrame({
                "name": ["gen_101", "gen_102", "gen_103"],
                "bus": ["bus_A", "bus_B", "bus_A"],
                "area": ["East", "West", "East"],
                "fuel": ["Gas", "Gas", "Coal"],
                "capacity_mw": np.array([400.0, 150.0, 600.0], dtype=np.float32),
            })
        elif name == "RenewableDispatch":
            return pd.DataFrame({
                "name": ["solar_01", "wind_01"],
                "bus": ["bus_B", "bus_A"],
                "area": ["West", "East"],
                "fuel": ["Solar", "Wind"],
                "capacity_mw": np.array([200.0, 300.0], dtype=np.float32),
            })
        elif name == "generators":
            return pd.concat(
                [self.get_dataset("ThermalStandard"),
                 self.get_dataset("RenewableDispatch")],
                ignore_index=True,
            )
        raise KeyError(name)

    def get_default_category_maps(self) -> list[CategoryMap]:
        return [
            CategoryMap(
                name="technology_simple",
                description="Simplified tech groups",
                mapping={
                    "gen_101": "Gas",
                    "gen_102": "Gas",
                    "gen_103": "Coal",
                    "solar_01": "Solar",
                    "wind_01": "Wind",
                },
                applies_to=["generation"],
            ),
            CategoryMap(
                name="native_area",
                description="Native model areas",
                mapping={
                    "gen_101": "East",
                    "gen_102": "West",
                    "gen_103": "East",
                    "solar_01": "West",
                    "wind_01": "East",
                },
            ),
        ]


class MockSimulation(BaseSimulation):
    """Mock simulation with 4 timestamps and 5 entities."""

    TIMESTAMPS = [
        "2025-01-01T00:00:00",
        "2025-01-01T01:00:00",
        "2025-01-01T02:00:00",
        "2025-01-01T03:00:00",
    ]

    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name="ActivePowerVariable__ThermalStandard",
                description="Thermal generation",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="entity_id",
            ),
            DatasetInfo(
                name="ActivePowerVariable__RenewableDispatch",
                description="Renewable generation",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="entity_id",
            ),
            DatasetInfo(
                name="generation",
                description="All generation",
                kind=DatasetKind.COMPOSED,
                entity_column="entity_id",
                source_datasets=[
                    "ActivePowerVariable__ThermalStandard",
                    "ActivePowerVariable__RenewableDispatch",
                ],
            ),
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        idx = pd.DatetimeIndex(self.TIMESTAMPS, name="datetime")

        if name == "ActivePowerVariable__ThermalStandard":
            return pd.DataFrame(
                {
                    "gen_101": np.array([380.5, 395.2, 400.0, 390.0], dtype=np.float32),
                    "gen_102": np.array([120.0, 145.8, 130.0, 125.0], dtype=np.float32),
                    "gen_103": np.array([580.0, 575.0, 590.0, 585.0], dtype=np.float32),
                },
                index=idx,
            )
        elif name == "ActivePowerVariable__RenewableDispatch":
            return pd.DataFrame(
                {
                    "solar_01": np.array([0.0, 0.0, 50.0, 150.0], dtype=np.float32),
                    "wind_01": np.array([45.2, 52.1, 48.0, 42.0], dtype=np.float32),
                },
                index=idx,
            )
        elif name == "generation":
            return pd.concat(
                [
                    self.get_dataset("ActivePowerVariable__ThermalStandard"),
                    self.get_dataset("ActivePowerVariable__RenewableDispatch"),
                ],
                axis=1,
            )
        raise KeyError(name)


class SpecialCharSystem(BaseSystem):
    """Mock system with a dataset name containing "&", mirroring real
    PLEXOS property names like "Start & Shutdown Cost"."""

    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name="Start & Shutdown Cost",
                description="Startup/shutdown cost",
                kind=DatasetKind.RAW_SYSTEM,
                entity_column="name",
                columns=["name", "value"],
            ),
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name == "Start & Shutdown Cost":
            return pd.DataFrame({
                "name": ["gen_101", "gen_102"],
                "value": np.array([10.0, 20.0], dtype=np.float32),
            })
        raise KeyError(name)

    def get_default_category_maps(self) -> list[CategoryMap]:
        return []


class SpecialCharSimulation(BaseSimulation):
    """Mock simulation with a raw dataset name containing "&"."""

    TIMESTAMPS = MockSimulation.TIMESTAMPS

    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name="Start & Shutdown Cost",
                description="Startup/shutdown cost over time",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="entity_id",
            ),
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        if name == "Start & Shutdown Cost":
            idx = pd.DatetimeIndex(self.TIMESTAMPS, name="datetime")
            return pd.DataFrame(
                {
                    "gen_101": np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32),
                },
                index=idx,
            )
        raise KeyError(name)


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


@pytest.fixture
def scenario():
    """Create a fully ingested mock scenario."""
    db = GATDatabase()  # in-memory
    s = Scenario(
        system=MockSystem(),
        simulation=MockSimulation(),
        db=db,
        project="test",
        name="base",
    )
    s.ingest()
    return s


class TestGATDatabase:
    def test_in_memory(self):
        db = GATDatabase()
        assert db.get_connection() is not None
        db.close()

    def test_file_backed(self, tmp_path):
        db_path = tmp_path / "test.duckdb"
        db = GATDatabase(db_path)
        assert db_path.exists()
        db.close()

    def test_ingest_system(self):
        db = GATDatabase()
        db.ingest_system("test", MockSystem())
        tables = db.list_tables("test")
        assert "sys__ThermalStandard" in tables
        assert "sys__RenewableDispatch" in tables
        assert "sys__generators" in tables

        # Verify data
        df = db.query("SELECT * FROM test.sys__ThermalStandard")
        assert len(df) == 3
        assert "name" in df.columns
        assert "capacity_mw" in df.columns
        db.close()

    def test_ingest_simulation_raw(self):
        db = GATDatabase()
        db._ensure_schema("test")
        sim = MockSimulation()

        # Ingest just raw datasets
        for ds in sim.list_datasets():
            if ds.kind == DatasetKind.RAW_SIMULATION:
                df = sim.get_dataset(ds.name)
                from gat.backends.duckdb_backend import _prepare_sim_dataframe, _sanitize_table_name
                df = _prepare_sim_dataframe(df)
                table_name = f"test.sim__{_sanitize_table_name(ds.name)}"
                db._conn.execute(
                    f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df"
                )

        # Check raw table shape (timestamp rows × entity cols)
        df = db.query("SELECT * FROM test.sim__ActivePowerVariable__ThermalStandard")
        assert len(df) == 4  # 4 timestamps
        assert "datetime" in df.columns
        assert "gen_101" in df.columns
        assert "gen_102" in df.columns
        assert "gen_103" in df.columns
        db.close()

    def test_ingest_simulation_composed(self):
        db = GATDatabase()
        db.ingest_simulation("test", MockSimulation())

        # Check composed table shape (entity rows × timestamp cols)
        df = db.query("SELECT * FROM test.generation")
        assert len(df) == 5  # 5 entities
        assert "entity_id" in df.columns
        entities = set(df["entity_id"])
        assert entities == {"gen_101", "gen_102", "gen_103", "solar_01", "wind_01"}

        # Timestamp columns
        ts_cols = [c for c in df.columns if c != "entity_id"]
        assert len(ts_cols) == 4  # 4 timestamps
        db.close()

    def test_ingest_system_with_special_char_dataset_name(self):
        """Dataset names sourced from PLEXOS properties (e.g. "Start &
        Shutdown Cost") can contain characters invalid in a bare SQL
        identifier. Sanitization alone doesn't strip "&", so the view/
        table registration must quote the identifier."""
        db = GATDatabase()
        db.ingest_system("test", SpecialCharSystem())
        tables = db.list_tables("test")
        assert "sys__Start_&_Shutdown_Cost" in tables

        df = db.query('SELECT * FROM test."sys__Start_&_Shutdown_Cost"')
        assert len(df) == 2
        assert "value" in df.columns
        db.close()

    def test_ingest_simulation_with_special_char_dataset_name(self):
        db = GATDatabase()
        db.ingest_simulation("test", SpecialCharSimulation())

        df = db.query('SELECT * FROM test."sim__Start_&_Shutdown_Cost"')
        assert len(df) == 4
        assert "gen_101" in df.columns
        db.close()


class TestCategoryMaps:
    def test_dict_map(self):
        db = GATDatabase()
        db._ensure_schema("test")
        cat = CategoryMap(
            name="tech",
            description="Tech groups",
            mapping={"gen_101": "Gas", "gen_102": "Gas", "gen_103": "Coal"},
        )
        db.register_category_map("test", cat)

        df = db.query("SELECT * FROM test.catmap__tech")
        assert len(df) == 3
        assert set(df.columns) == {"entity_id", "category"}
        db.close()

    def test_list_category_maps(self):
        db = GATDatabase()
        db._ensure_schema("test")
        db.register_category_map("test", CategoryMap(
            name="tech", description="", mapping={"a": "b"},
        ))
        db.register_category_map("test", CategoryMap(
            name="area", description="", mapping={"a": "c"},
        ))
        assert set(db.list_category_maps("test")) == {"tech", "area"}
        db.close()


class TestCategoryMapRegistry:
    def test_register_and_list(self):
        reg = CategoryMapRegistry()
        reg.register(CategoryMap(name="tech", description="", mapping={}))
        reg.register(CategoryMap(
            name="area", description="", mapping={}, applies_to=["generation"],
        ))

        assert reg.list_maps() == ["tech", "area"]
        assert reg.list_for_dataset("generation") == ["tech", "area"]
        assert reg.list_for_dataset("load") == ["tech"]  # area doesn't apply

    def test_get_missing(self):
        reg = CategoryMapRegistry()
        with pytest.raises(KeyError):
            reg.get("nonexistent")


class TestGroupedQueries:
    def test_single_category_group(self, scenario):
        """GROUP BY technology_simple on generation."""
        result = scenario.query("generation", group_by=["technology_simple"])
        assert "technology_simple" in result.columns

        # Should have 4 categories: Gas, Coal, Solar, Wind
        cats = set(result["technology_simple"])
        assert cats == {"Gas", "Coal", "Solar", "Wind"}

        # Gas = gen_101 + gen_102 at t=0: 380.5 + 120.0 = 500.5
        gas_row = result[result["technology_simple"] == "Gas"].iloc[0]
        ts_cols = [c for c in result.columns if c != "technology_simple"]
        gas_t0 = gas_row[ts_cols[0]]
        assert abs(gas_t0 - 500.5) < 0.1

    def test_multi_category_group(self, scenario):
        """GROUP BY native_area AND technology_simple on generation."""
        result = scenario.query(
            "generation", group_by=["native_area", "technology_simple"]
        )
        assert "native_area" in result.columns
        assert "technology_simple" in result.columns

        # East + Gas = gen_101 at t=0: 380.5
        east_gas = result[
            (result["native_area"] == "East")
            & (result["technology_simple"] == "Gas")
        ]
        assert len(east_gas) == 1
        ts_cols = [
            c for c in result.columns
            if c not in ("native_area", "technology_simple")
        ]
        val = east_gas.iloc[0][ts_cols[0]]
        assert abs(val - 380.5) < 0.1

    def test_ungrouped_query(self, scenario):
        """Query without grouping returns raw composed table."""
        result = scenario.query("generation")
        assert "entity_id" in result.columns
        assert len(result) == 5


class TestScenario:
    def test_list_datasets(self, scenario):
        datasets = scenario.list_datasets()
        names = [ds.name for ds in datasets]
        assert "ThermalStandard" in names
        assert "generation" in names
        assert "ActivePowerVariable__ThermalStandard" in names

        # Check kinds
        gen = next(ds for ds in datasets if ds.name == "generation")
        assert gen.kind == DatasetKind.COMPOSED

    def test_get_dataset_raw(self, scenario):
        """Level 0: raw DataFrame access."""
        df = scenario.get_dataset("ThermalStandard")
        assert len(df) == 3
        assert "name" in df.columns

    def test_get_dataset_simulation(self, scenario):
        """Level 0: raw simulation DataFrame."""
        df = scenario.get_dataset("ActivePowerVariable__ThermalStandard")
        assert isinstance(df.index, pd.DatetimeIndex)
        assert "gen_101" in df.columns

    def test_list_category_maps(self, scenario):
        maps = scenario.list_category_maps()
        assert "technology_simple" in maps
        assert "native_area" in maps

    def test_list_category_maps_for_dataset(self, scenario):
        maps = scenario.list_category_maps(dataset="generation")
        assert "technology_simple" in maps
        # native_area has applies_to=None so it applies to all
        assert "native_area" in maps

    def test_sql_escape_hatch(self, scenario):
        """Direct SQL access."""
        result = scenario.sql(
            f"SELECT COUNT(*) as cnt FROM {scenario.schema}.generation"
        )
        assert result["cnt"].iloc[0] == 5

    def test_add_category_map(self, scenario):
        """User can add a new category map after ingestion."""
        scenario.add_category_map(CategoryMap(
            name="custom_group",
            description="User-defined grouping",
            mapping={
                "gen_101": "GroupA",
                "gen_102": "GroupA",
                "gen_103": "GroupB",
                "solar_01": "GroupB",
                "wind_01": "GroupA",
            },
        ))
        assert "custom_group" in scenario.list_category_maps()
        result = scenario.query("generation", group_by=["custom_group"])
        cats = set(result["custom_group"])
        assert cats == {"GroupA", "GroupB"}

    def test_float32_precision(self, scenario):
        """Verify float32 values round-trip through DuckDB."""
        result = scenario.query("generation")
        gen_101 = result[result["entity_id"] == "gen_101"]
        ts_cols = [c for c in result.columns if c != "entity_id"]
        val = gen_101.iloc[0][ts_cols[0]]
        # float32 precision: 380.5 should be exact (representable in float32)
        assert abs(val - 380.5) < 0.01
