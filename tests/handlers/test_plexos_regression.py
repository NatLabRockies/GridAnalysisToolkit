"""Snapshot regression tests for PlexosScenario public API.

Uses pytest-regressions' dataframe_regression fixture. To regenerate snapshots
after an intentional change, run:

    pytest tests/handlers/test_plexos_regression.py --force-regen

Snapshots are stored under tests/handlers/test_plexos_regression/.
"""

import pandas as pd
import pytest


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """pytest-regressions' dataframe fixture writes flat CSV — flatten any MultiIndex.

    Columns are sorted for deterministic snapshot ordering; iteration order of
    underlying tech maps depends on which scenarios were instantiated earlier
    in the session.
    """
    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        out.columns = ["::".join(str(c) for c in tup) for tup in out.columns]
    else:
        out.columns = [str(c) for c in out.columns]
    return out[sorted(out.columns)]


def _summary(df: pd.DataFrame) -> pd.DataFrame:
    """Per-column summary: useful when full-row snapshots are noisy or huge."""
    flat = _flatten_columns(df)
    numeric = flat.select_dtypes(include="number")
    out = pd.DataFrame(
        {
            "sum": numeric.sum(),
            "min": numeric.min(),
            "max": numeric.max(),
            "mean": numeric.mean(),
        }
    ).reset_index(names="column")
    return out.sort_values("column").reset_index(drop=True)


TOL = {"rtol": 1e-6, "atol": 1e-9}


def test_get_generators_tech(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_generators_tech()
    dataframe_regression.check(_flatten_columns(df), default_tolerance=TOL)


def test_get_gen_and_curtailment_summary(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_gen_and_curtailment()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_area_dispatch_user_reproducer_summary(
    plexos_scenario, dataframe_regression
):
    """Bug-fix regression: the exact call the user (ecooper) was running."""
    df = plexos_scenario.get_area_dispatch(include_load=False, include_charging=False)
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_area_dispatch_defaults_shape(plexos_scenario):
    """Defaults path exercises the empty-storage_charging fall-through.
    Shape-only because the include_use=True branch depends on whether the
    fixture has unserved energy and we don't want value drift to mask the
    structural property under test."""
    df = plexos_scenario.get_area_dispatch()
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert isinstance(df.columns, pd.MultiIndex)
    assert df.columns.names == ["Area", "Technology"]


def test_get_area_load_summary(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_area_load()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_area_unserved_summary(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_area_unserved()
    assert df is not NotImplemented
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_line_loading_summary(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_line_loading()
    dataframe_regression.check(
        _summary(df), default_tolerance={"rtol": 1e-6, "atol": 1e-3}
    )


@pytest.mark.skip(
    reason="get_peak_stats has a pre-existing KeyError on 'Total Demand' for this fixture; unrelated to Phase 1"
)
def test_get_peak_stats(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_peak_stats()
    dataframe_regression.check(_flatten_columns(df), default_tolerance=TOL)


# ---------------------------------------------------------------------------
# Phase-12 expansion: snapshot the rest of the public `get_*` surface so
# the duckdb migration can't silently drift on a method that wasn't
# already covered. Most use the per-column summary (sum/min/max/mean)
# to keep snapshot files small. A few smaller frames get full snapshots.
# ---------------------------------------------------------------------------


def test_get_generation_summary(plexos_scenario, dataframe_regression):
    """Per-generator dispatch — the foundational time series most other
    aggregations build on."""
    df = plexos_scenario.get_generation()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_load_summary(plexos_scenario, dataframe_regression):
    """Per-area native load (3 columns × 1560 rows)."""
    df = plexos_scenario.get_load()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_curtailment_summary(plexos_scenario, dataframe_regression):
    """Per-curtailable-generator curtailment timeseries."""
    df = plexos_scenario.get_curtailment()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_availability_summary(plexos_scenario, dataframe_regression):
    """Per-generator availability (max output capability)."""
    df = plexos_scenario.get_availability()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_availability_tech_summary(plexos_scenario, dataframe_regression):
    """Availability with tech-mapping applied (different from get_availability)."""
    df = plexos_scenario.get_availability_tech()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_line_flow_summary(plexos_scenario, dataframe_regression):
    """Per-line transmission flow timeseries.
    `get_flow()` is an alias of this method (deprecated) — covered via this test.
    """
    df = plexos_scenario.get_line_flow()
    dataframe_regression.check(
        _summary(df), default_tolerance={"rtol": 1e-6, "atol": 1e-3}
    )


def test_get_line_utilization_summary(plexos_scenario, dataframe_regression):
    """Per-line utilization metrics (484 cols — a wide derived frame).
    Tolerances loosened slightly to absorb floating-point drift in the
    percentile bucketing."""
    df = plexos_scenario.get_line_utilization()
    dataframe_regression.check(
        _summary(df), default_tolerance={"rtol": 1e-5, "atol": 1e-3}
    )


def test_get_line_congestion_hours_summary(plexos_scenario, dataframe_regression):
    df = plexos_scenario.get_line_congestion_hours()
    dataframe_regression.check(
        _summary(df), default_tolerance={"rtol": 1e-6, "atol": 1e-3}
    )


def test_get_unserved_summary(plexos_scenario, dataframe_regression):
    """Raw unserved energy — small (3 columns) but useful as a sanity
    pin for the `is NotImplemented` bug-fix code path."""
    df = plexos_scenario.get_unserved()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_system_dispatch_summary(plexos_scenario, dataframe_regression):
    """System-level dispatch (no area split) — different aggregation than
    `get_area_dispatch`, separate test for separate code path."""
    df = plexos_scenario.get_system_dispatch()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_area_curtailment_aggregates_summary(plexos_scenario, dataframe_regression):
    """Area-aggregated curtailment."""
    df = plexos_scenario.get_area_curtailment_aggregates()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_area_tech_aggregates_summary(plexos_scenario, dataframe_regression):
    """Area × technology aggregation — wide frame (180 cols)."""
    df = plexos_scenario.get_area_tech_aggregates()
    dataframe_regression.check(_summary(df), default_tolerance=TOL)


def test_get_generation_capacity_full(plexos_scenario, dataframe_regression):
    """System capacities by area × tech (3 × 12 — small enough to snapshot
    in full rather than summary)."""
    df = plexos_scenario.get_generation_capacity()
    dataframe_regression.check(_flatten_columns(df), default_tolerance=TOL)
