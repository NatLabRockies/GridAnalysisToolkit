"""End-to-end integration tests for `gat.reports.scenario_single`.

The reporting framework's entry point (`run(SystemReportConfig)`) was
0% covered before this module — same for `gat.utils.scenario_from_config`
and `gat.registry.utils.execute_plot`, both called transitively. A
single happy-path run against the plexos fixture exercises ~500 lines.

We don't assert on plot correctness (that's what the gallery + snapshots
do); we just confirm the run produces output files and doesn't raise on
the discovery / execute / save flow.
"""

import os
import warnings
from pathlib import Path

import pytest


@pytest.fixture
def report_output_dir(tmp_path):
    """Per-test scratch directory for report artifacts."""
    out = tmp_path / "report_out"
    out.mkdir(parents=True, exist_ok=True)
    return out


def test_scenario_single_run_produces_output_files(
    plexos_fixture_root, report_output_dir
):
    """Drive `gat.reports.scenario_single.run` end-to-end with the plexos
    fixture. Verify it discovers plots, executes some of them, and writes
    PNG files. Catches regressions in:

    - `gat.utils.scenario_from_config` (factory wiring)
    - `gat.registry.discover_all_plots` (decorator + entry-point discovery)
    - `gat.registry.utils.execute_plot` (per-plot save loop)
    - `gat.reports.scenario_single.discover_available_plots` (filtering)
    - `gat.reports.scenario_single.run` (top-level orchestration)
    """
    # Reporter uses `print` and `logger` extensively for status; suppress to
    # keep test output readable.
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from gat.models.scenario import ScenarioConfig
    from gat.reports.scenario_single import SystemReportConfig, run

    scenario_config = ScenarioConfig(
        model_type="Plexos",
        display_name="plexos-test-fixture",
        simulation_paths=str(plexos_fixture_root),
    )
    report_config = SystemReportConfig(
        model_type="Plexos",
        scenario=scenario_config,
        output_path=str(report_output_dir),
        output_fmt="png",  # skip pptx bundling — tested separately by `make fixture-deck`
    )

    run(report_config)

    # The reporter writes per-plot PNGs under <output_path>/<subpath>/<name>.png.
    # Some plots fail individually (pre-existing 'Total Demand' bugs etc.);
    # `run` catches per-plot exceptions and continues. We just need *some*
    # PNGs to land — proves the discovery + execute loop wired up.
    pngs = list(report_output_dir.rglob("*.png"))
    assert len(pngs) > 0, (
        f"reporter produced no PNGs in {report_output_dir}; "
        f"discovery or execute_plot is broken"
    )


def test_scenario_single_run_with_explicit_plot_list(
    plexos_fixture_root, report_output_dir
):
    """`run` with `output_plots` explicitly populated runs only the named
    plots — avoids the discovery+filter path. Useful for pinning a known
    subset of plots when the auto-discovery is broken."""
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from gat.models.scenario import ScenarioConfig
    from gat.reports.scenario_single import SystemReportConfig, run

    scenario_config = ScenarioConfig(
        model_type="Plexos",
        display_name="plexos-explicit",
        simulation_paths=str(plexos_fixture_root),
    )
    report_config = SystemReportConfig(
        model_type="Plexos",
        scenario=scenario_config,
        output_path=str(report_output_dir),
        output_fmt="png",
        output_plots=[
            {"name": "plot_total_system_dispatch", "options": {}},
            {"name": "plot_monthly_system_dispatch", "options": {}},
        ],
    )

    run(report_config)

    # At least one of the two named plots should produce output. (If both
    # blow up internally, run() doesn't raise — but no PNGs land.)
    pngs = list(report_output_dir.rglob("*.png"))
    assert (
        len(pngs) > 0
    ), f"explicit-plot-list run produced no PNGs in {report_output_dir}"


def test_scenario_from_config_returns_handler(plexos_fixture_root):
    """Direct test for `gat.utils.scenario_from_config` (the factory the
    reporter uses)."""
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from gat.models.scenario import ScenarioConfig
    from gat.utils import scenario_from_config

    cfg = ScenarioConfig(
        model_type="Plexos",
        simulation_paths=str(plexos_fixture_root),
    )
    scenario = scenario_from_config(cfg)
    # The factory returns a concrete BaseScenario subclass; verify the type
    # routing worked (model_type="Plexos" → PlexosScenario).
    from gat.scenariohandlers import PlexosScenario

    assert isinstance(scenario, PlexosScenario)
    # And the scenario actually loaded the data — quick sanity check.
    assert scenario.parser is not None
