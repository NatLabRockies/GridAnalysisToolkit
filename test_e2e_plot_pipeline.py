"""End-to-end test: Sienna data → DuckDB ingest → query → plot via backend.

Exercises the full GAT pipeline from raw ExtremeEvents data through to
rendered matplotlib figures using the new multi-backend plotting system.

Uses real ExtremeEvents data files in ./data/ExtremeEvents/.
Saves output plots to a temp directory for visual inspection.

Run from the repo root::

    python -m pytest test_e2e_plot_pipeline.py -v

(Lives at repo root to avoid the legacy tests/__init__.py import issue.)
"""

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from gat.backends.duckdb_backend import GATDatabase
from gat.categories import CategoryMap
from gat.scenario import Scenario
from gat.systems.sienna import SiennaSystem
from gat.simulations.sienna_v1 import SiennaSimulation
from gat.quickplots.core import (
    plot_stacked_component_area,
    plot_stacked_component_bar,
    plot_component_donut,
)
from gat.quickplots.backends import get_backend, list_backends
from gat.models.palette import Palette, DisplayCategory, CategoryMapping


DATA_DIR = Path(__file__).parent / "data" / "ExtremeEvents"
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
def scenario():
    system = SiennaSystem(SYSTEM_PATH)
    sim = SiennaSimulation(SIM_PATH)
    db = GATDatabase()
    s = Scenario(system=system, simulation=sim, db=db, project="ee", name="e2e")
    s.ingest()
    yield s
    db.close()


@pytest.fixture(scope="module")
def output_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("e2e_plots")


def _pivot_grouped(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Pivot a grouped query result into plot-ready form.

    DuckDB grouped queries return:
        group_col | ts_0 | ts_1 | ...

    Plot functions expect:
        DatetimeIndex | Category_A | Category_B | ...
    """
    ts_cols = [c for c in df.columns if c != group_col]
    pivoted = df.set_index(group_col)[ts_cols].T
    pivoted.index = pd.to_datetime(pivoted.index)
    pivoted.index.name = "datetime"
    # Ensure numeric
    pivoted = pivoted.apply(pd.to_numeric, errors="coerce").fillna(0)
    return pivoted


# ------------------------------------------------------------------ #
# Backend infrastructure tests
# ------------------------------------------------------------------ #


class TestBackendInfrastructure:
    def test_static_backend_registered(self):
        assert "static" in list_backends()

    def test_get_default_backend(self):
        be = get_backend()
        assert be.name == "static"

    def test_get_named_backend(self):
        be = get_backend("static")
        assert be.name == "static"

    def test_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            get_backend("nonexistent_backend")


# ------------------------------------------------------------------ #
# Stacked area: generation by fuel
# ------------------------------------------------------------------ #


class TestStackedAreaPlot:
    def test_generation_by_fuel(self, scenario, output_dir):
        """Full pipeline: query generation grouped by fuel → stacked area."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        assert len(df) > 0
        assert len(df.columns) > 1

        fig, ax = plt.subplots(figsize=(12, 6))
        result = plot_stacked_component_area(df, ax=ax, legend=True)

        assert result is not None
        fig.savefig(output_dir / "generation_by_fuel_area.png", bbox_inches="tight")
        plt.close(fig)

    def test_generation_by_fuel_explicit_backend(self, scenario, output_dir):
        """Same plot but with explicit backend='static'."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        fig, ax = plt.subplots(figsize=(12, 6))
        result = plot_stacked_component_area(df, ax=ax, backend="static")

        assert result is not None
        fig.savefig(
            output_dir / "generation_by_fuel_area_explicit.png", bbox_inches="tight"
        )
        plt.close(fig)

    def test_generation_by_area(self, scenario, output_dir):
        """Query generation grouped by native_area → stacked area."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", group_by=["native_area"])
        df = _pivot_grouped(gen, "native_area")

        assert len(df.columns) > 1  # multiple areas

        fig, ax = plt.subplots(figsize=(12, 6))
        result = plot_stacked_component_area(df, ax=ax, legend=True)

        assert result is not None
        fig.savefig(output_dir / "generation_by_area_area.png", bbox_inches="tight")
        plt.close(fig)


# ------------------------------------------------------------------ #
# Stacked bar: generation by fuel
# ------------------------------------------------------------------ #


class TestStackedBarPlot:
    def test_generation_by_fuel_bar(self, scenario, output_dir):
        """Query generation grouped by fuel → stacked bar (vertical)."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        # Resample to daily totals for a cleaner bar chart
        daily = df.resample("D").sum()

        fig, ax = plt.subplots(figsize=(10, 6))
        result = plot_stacked_component_bar(daily, ax=ax, legend=True)

        assert result is not None
        fig.savefig(output_dir / "generation_by_fuel_bar.png", bbox_inches="tight")
        plt.close(fig)

    def test_generation_by_fuel_barh(self, scenario, output_dir):
        """Query generation grouped by fuel → horizontal stacked bar."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        # Sum to single total per fuel for a summary bar
        totals = df.sum().to_frame("Total").T

        fig, ax = plt.subplots(figsize=(10, 6))
        result = plot_stacked_component_bar(totals, horizontal=True, ax=ax)

        assert result is not None
        fig.savefig(output_dir / "generation_by_fuel_barh.png", bbox_inches="tight")
        plt.close(fig)


# ------------------------------------------------------------------ #
# Donut chart: capacity by fuel
# ------------------------------------------------------------------ #


class TestDonutPlot:
    def test_capacity_donut(self, scenario, output_dir):
        """Query generation, sum across time → donut chart of total energy."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        # Total energy per fuel (sum of all hours)
        energy_by_fuel = df.sum()

        fig, ax = plt.subplots(figsize=(8, 8))
        result = plot_component_donut(energy_by_fuel, unit=" MWh", ax=ax)

        assert result is not None
        fig.savefig(output_dir / "energy_by_fuel_donut.png", bbox_inches="tight")
        plt.close(fig)


# ------------------------------------------------------------------ #
# Backend chart methods directly
# ------------------------------------------------------------------ #


class TestBackendChartMethods:
    def test_backend_line(self, scenario, output_dir):
        """Use the backend line method directly on net_load data."""
        import matplotlib.pyplot as plt

        be = get_backend("static")
        net = scenario.net_load()

        # Pick the first area's timeseries
        ts_cols = [c for c in net.columns if c != "native_area"]
        first_area = net.iloc[0]
        area_name = first_area["native_area"]
        line_df = pd.DataFrame(
            {area_name: first_area[ts_cols].values.astype(float)},
            index=pd.to_datetime(ts_cols),
        )

        fig, ax = plt.subplots(figsize=(10, 4))
        result = be.line(line_df, ax=ax)
        be.set_title(result, f"Net Load — {area_name}")
        be.set_ylabel(result, "MW")

        assert result is not None
        fig.savefig(output_dir / "net_load_line.png", bbox_inches="tight")
        plt.close(fig)

    def test_backend_boxplot(self, scenario, output_dir):
        """Use the backend boxplot method on generation data."""
        import matplotlib.pyplot as plt

        be = get_backend("static")
        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        fig, ax = plt.subplots(figsize=(10, 6))
        result = be.boxplot(df, ax=ax)
        be.set_title(result, "Generation Distribution by Fuel")
        be.set_ylabel(result, "MW")

        assert result is not None
        fig.savefig(output_dir / "generation_boxplot.png", bbox_inches="tight")
        plt.close(fig)

    def test_backend_create_subplots(self, scenario, output_dir):
        """Create a multi-panel figure using backend.create_subplots."""
        import matplotlib.pyplot as plt

        be = get_backend("static")
        gen = scenario.query("generation", group_by=["native_area"])
        df = _pivot_grouped(gen, "native_area")

        n_areas = len(df.columns)
        fig, axs = be.create_subplots(n_areas, 1, figsize=(12, 3 * n_areas))

        if not hasattr(axs, "__len__"):
            axs = [axs]

        for i, area in enumerate(df.columns):
            area_df = df[[area]]
            be.line(area_df, ax=axs[i])
            be.set_title(axs[i], f"Generation — {area}")
            be.set_ylabel(axs[i], "MW")

        fig.tight_layout()
        fig.savefig(output_dir / "generation_by_area_panels.png", bbox_inches="tight")
        plt.close(fig)


# ------------------------------------------------------------------ #
# Analytics → Plot integration
# ------------------------------------------------------------------ #


class TestAnalyticsToPlot:
    def test_ramp_rate_line(self, scenario, output_dir):
        """Compute ramp rate grouped by fuel → line plot."""
        import matplotlib.pyplot as plt

        be = get_backend("static")
        ramp = scenario.ramp_rate(group_by=["fuel"])

        ts_cols = [c for c in ramp.columns if c != "fuel"]
        # Drop first timestamp (NaN for ramp)
        ts_cols = ts_cols[1:]

        ramp_df = ramp.set_index("fuel")[ts_cols].T
        ramp_df.index = pd.to_datetime(ramp_df.index)

        fig, ax = plt.subplots(figsize=(12, 6))
        be.line(ramp_df, ax=ax)
        be.set_title(ax, "Ramp Rate by Fuel")
        be.set_ylabel(ax, "MW/interval")

        fig.savefig(output_dir / "ramp_rate_by_fuel.png", bbox_inches="tight")
        plt.close(fig)

    def test_line_loading_area(self, scenario, output_dir):
        """Compute line loading → stacked area of top loaded lines."""
        import matplotlib.pyplot as plt

        loading = scenario.line_loading()
        ts_cols = [c for c in loading.columns if c != "entity_id"]

        # Pick top 5 lines by mean loading
        means = loading[ts_cols].mean(axis=1)
        top5_idx = means.nlargest(5).index
        top5 = loading.loc[top5_idx].copy()

        plot_df = top5.set_index("entity_id")[ts_cols].T
        plot_df.index = pd.to_datetime(plot_df.index)
        plot_df = plot_df.fillna(0)

        fig, ax = plt.subplots(figsize=(12, 6))
        result = plot_stacked_component_area(plot_df, ax=ax, legend=True)

        assert result is not None
        fig.savefig(output_dir / "line_loading_top5.png", bbox_inches="tight")
        plt.close(fig)


# ------------------------------------------------------------------ #
# Plotly (interactive) backend
# ------------------------------------------------------------------ #

plotly_available = "interactive" in list_backends()


@pytest.mark.skipif(not plotly_available, reason="plotly not installed")
class TestPlotlyBackend:
    def test_plotly_registered(self):
        assert "interactive" in list_backends()
        be = get_backend("interactive")
        assert be.name == "interactive"

    def test_stacked_area_interactive(self, scenario):
        """Plotly stacked area from generation by fuel."""
        import plotly.graph_objects as go

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        fig = plot_stacked_component_area(df, backend="interactive")

        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0
        # Should have one trace per fuel category (pos stack)
        assert len(fig.data) >= len(df.columns)

    def test_stacked_bar_interactive(self, scenario):
        """Plotly stacked bar."""
        import plotly.graph_objects as go

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")
        daily = df.resample("D").sum()

        fig = plot_stacked_component_bar(daily, backend="interactive")

        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_stacked_bar_horizontal(self, scenario):
        """Plotly horizontal stacked bar."""
        import plotly.graph_objects as go

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")
        totals = df.sum().to_frame("Total").T

        fig = plot_stacked_component_bar(totals, horizontal=True, backend="interactive")

        assert isinstance(fig, go.Figure)
        # Check orientation
        assert fig.data[0].orientation == "h"

    def test_donut_interactive(self, scenario):
        """Plotly donut chart."""
        import plotly.graph_objects as go

        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")
        energy = df.sum()

        fig = plot_component_donut(energy, unit=" MWh", backend="interactive")

        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Pie)

    def test_line_interactive(self, scenario):
        """Plotly line chart via backend directly."""
        import plotly.graph_objects as go

        be = get_backend("interactive")
        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        fig = be.line(df)

        assert isinstance(fig, go.Figure)
        assert len(fig.data) == len(df.columns)

    def test_boxplot_interactive(self, scenario):
        """Plotly boxplot via backend directly."""
        import plotly.graph_objects as go

        be = get_backend("interactive")
        gen = scenario.query("generation", group_by=["fuel"])
        df = _pivot_grouped(gen, "fuel")

        fig = be.boxplot(df)

        assert isinstance(fig, go.Figure)
        assert len(fig.data) == len(df.columns)

    def test_subplots_interactive(self, scenario):
        """Plotly subplots creation."""
        be = get_backend("interactive")
        fig, cells = be.create_subplots(2, 1)

        assert len(cells) == 2
        assert cells[0] == (1, 1)
        assert cells[1] == (2, 1)

    def test_formatting_helpers(self, scenario):
        """Plotly formatting helpers mutate the figure."""
        import plotly.graph_objects as go

        be = get_backend("interactive")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2], y=[3, 4], name="test"))

        be.set_title(fig, "Test Title")
        assert fig.layout.title.text == "Test Title"

        be.set_ylabel(fig, "Y Label")
        be.set_xlabel(fig, "X Label")
        be.set_xlim(fig, 0, 10)
        be.set_ylim(fig, 0, 100)
        be.remove_legend(fig)
        assert fig.layout.showlegend is False

    def test_palette_with_plotly(self, scenario, fuel_palette):
        """Full palette pipeline through plotly backend."""
        import plotly.graph_objects as go

        gen = scenario.query("generation", palette=fuel_palette)
        df = _pivot_grouped(gen, "fuel")

        fig = plot_stacked_component_area(
            df, palette=fuel_palette, backend="interactive"
        )

        assert isinstance(fig, go.Figure)
        # Should have 4 display categories as traces
        trace_names = [t.name for t in fig.data]
        assert "Nuclear" in trace_names
        assert "Coal" in trace_names
        assert "Gas" in trace_names
        assert "Other" in trace_names


# ------------------------------------------------------------------ #
# Colors integration
# ------------------------------------------------------------------ #


class TestColorsIntegration:
    def test_standard_colors_accessible(self):
        from gat.colors import standard

        assert standard.PV == "#FFC903"
        assert standard.WIND == "#00B6EF"
        assert standard.NUCLEAR == "#820000"
        assert len(standard) > 50

    def test_colors_iterable(self):
        from gat.colors import standard

        items = list(standard)
        assert len(items) > 50
        # Each item is (name, hex_color)
        for name, color in items:
            assert color.startswith("#")

    def test_colors_subscript(self):
        from gat.colors import standard

        assert standard["GAS_CC"] == "#52216B"


# ------------------------------------------------------------------ #
# Palette-driven query + plot
# ------------------------------------------------------------------ #


@pytest.fixture(scope="module")
def fuel_palette():
    """A test palette that re-aggregates fuel categories."""
    return Palette(
        name="test_fuel",
        simulation_type="sienna",
        category_map="fuel",
        dimension="technology",
        display_categories=[
            DisplayCategory(name="Gas", color="#C2A1DB"),
            DisplayCategory(name="Coal", color="#222222"),
            DisplayCategory(name="Nuclear", color="#820000"),
            DisplayCategory(name="Other", color="#808080"),
        ],
        category_mappings=[
            CategoryMapping(simulation_category="NATURAL_GAS", display_category="Gas"),
            CategoryMapping(simulation_category="COAL", display_category="Coal"),
            CategoryMapping(simulation_category="WASTE_COAL", display_category="Coal"),
            CategoryMapping(simulation_category="NUCLEAR", display_category="Nuclear"),
            CategoryMapping(simulation_category="DISTILLATE_FUEL_OIL", display_category="Other"),
            CategoryMapping(simulation_category="MUNICIPAL_WASTE", display_category="Other"),
            CategoryMapping(simulation_category="RESIDUAL_FUEL_OIL", display_category="Other"),
            CategoryMapping(simulation_category="OTHER", display_category="Other"),
        ],
        stack_order=["Nuclear", "Coal", "Gas", "Other"],
    )


class TestPaletteIntegration:
    def test_palette_query_re_aggregates(self, scenario, fuel_palette):
        """Palette query merges simulation categories into display categories."""
        result = scenario.query("generation", palette=fuel_palette)
        categories = list(result["fuel"].values)
        assert categories == ["Nuclear", "Coal", "Gas", "Other"]
        assert result.shape[0] == 4  # 4 display categories

    def test_palette_query_sums_match(self, scenario, fuel_palette):
        """Re-aggregated sums should match the raw grouped sums."""
        raw = scenario.query("generation", group_by=["fuel"])
        pal = scenario.query("generation", palette=fuel_palette)

        ts_cols_raw = [c for c in raw.columns if c != "fuel"]
        ts_cols_pal = [c for c in pal.columns if c != "fuel"]

        raw_total = raw[ts_cols_raw].sum().sum()
        pal_total = pal[ts_cols_pal].sum().sum()
        assert abs(raw_total - pal_total) < 1.0

    def test_palette_query_coal_merge(self, scenario, fuel_palette):
        """COAL + WASTE_COAL should merge into 'Coal' display category."""
        raw = scenario.query("generation", group_by=["fuel"])
        pal = scenario.query("generation", palette=fuel_palette)

        ts_cols = [c for c in raw.columns if c != "fuel"]
        raw_coal = raw[raw["fuel"] == "COAL"][ts_cols].values.sum()
        raw_waste = raw[raw["fuel"] == "WASTE_COAL"][ts_cols].values.sum()

        ts_cols_pal = [c for c in pal.columns if c != "fuel"]
        pal_coal = pal[pal["fuel"] == "Coal"][ts_cols_pal].values.sum()

        assert abs(pal_coal - (raw_coal + raw_waste)) < 0.1

    def test_palette_register_and_lookup(self, scenario, fuel_palette):
        """Register palette on scenario and query by name."""
        scenario.register_palette(fuel_palette)
        assert "test_fuel" in scenario.list_palettes()

        result = scenario.query("generation", palette="test_fuel")
        assert list(result["fuel"].values) == ["Nuclear", "Coal", "Gas", "Other"]

    def test_palette_stacked_area_plot(self, scenario, fuel_palette, output_dir):
        """Full pipeline: palette query → pivot → palette-driven area plot."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", palette=fuel_palette)
        df = _pivot_grouped(gen, "fuel")

        fig, ax = plt.subplots(figsize=(12, 6))
        result = plot_stacked_component_area(df, palette=fuel_palette, ax=ax)

        assert result is not None
        fig.savefig(output_dir / "palette_area.png", bbox_inches="tight")
        plt.close(fig)

    def test_palette_bar_plot(self, scenario, fuel_palette, output_dir):
        """Palette-driven stacked bar chart."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", palette=fuel_palette)
        df = _pivot_grouped(gen, "fuel")
        daily = df.resample("D").sum()

        fig, ax = plt.subplots(figsize=(10, 6))
        result = plot_stacked_component_bar(daily, palette=fuel_palette, ax=ax)

        assert result is not None
        fig.savefig(output_dir / "palette_bar.png", bbox_inches="tight")
        plt.close(fig)

    def test_palette_donut_plot(self, scenario, fuel_palette, output_dir):
        """Palette-driven donut chart."""
        import matplotlib.pyplot as plt

        gen = scenario.query("generation", palette=fuel_palette)
        df = _pivot_grouped(gen, "fuel")
        energy = df.sum()

        fig, ax = plt.subplots(figsize=(8, 8))
        result = plot_component_donut(energy, unit=" MWh", palette=fuel_palette, ax=ax)

        assert result is not None
        fig.savefig(output_dir / "palette_donut.png", bbox_inches="tight")
        plt.close(fig)

    def test_palette_model_fields(self, fuel_palette):
        """Palette has category_map and dimension fields."""
        assert fuel_palette.category_map == "fuel"
        assert fuel_palette.dimension == "technology"

    def test_palette_color_map(self, fuel_palette):
        """get_color_map returns display category → color mapping."""
        cmap = fuel_palette.get_color_map()
        assert cmap["Gas"] == "#C2A1DB"
        assert cmap["Nuclear"] == "#820000"

    def test_palette_aggregation_map(self, fuel_palette):
        """get_aggregation_map returns simulation → display mapping."""
        amap = fuel_palette.get_aggregation_map()
        assert amap["NATURAL_GAS"] == "Gas"
        assert amap["COAL"] == "Coal"
        assert amap["WASTE_COAL"] == "Coal"

    def test_palette_ordered_display_names(self, fuel_palette):
        """get_ordered_display_names follows stack_order."""
        names = fuel_palette.get_ordered_display_names()
        assert names == ["Nuclear", "Coal", "Gas", "Other"]

    def test_palette_missing_raises(self, scenario):
        """Querying with an unregistered palette name raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            scenario.query("generation", palette="nonexistent_palette")
