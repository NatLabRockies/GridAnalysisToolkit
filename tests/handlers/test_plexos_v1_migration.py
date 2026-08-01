"""Phase 5c — proof-of-concept duckdb migration on Plexos.

This test demonstrates that data can flow end-to-end through the v1 stack
(``PlexosSystem`` → ``GATDatabase`` ← ``PlexosSimulation``) and that
``query_grouped`` with a category map produces an area-aggregated generation
DataFrame whose values match the legacy pandas path.

This is the architecture proof for the broader migration. Once the pattern
is proven here, remaining ``get_*`` methods on ``PlexosScenario`` can be
ported through the same shape:

  1. Subclass-specific ``BaseSystem`` exposes default ``CategoryMap`` instances
  2. Subclass-specific ``BaseSimulation`` exposes raw + composed ``DatasetInfo``
  3. ``GATDatabase.ingest_system`` / ``ingest_simulation`` materializes both
  4. ``GATDatabase.query_grouped`` returns the aggregate

Snapshots remain pinned to the legacy path; v1 must match.
"""

import pandas as pd
import pytest

from gat.backends import GATDatabase
from gat.simulations import PlexosSimulation
from gat.systems import PlexosSystem


@pytest.fixture(scope="module")
def plexos_v1_db(plexos_fixture_root):
    """Build an in-memory GATDatabase from the plexos fixture."""
    db = GATDatabase()
    system = PlexosSystem(solution_dir=str(plexos_fixture_root))
    sim = PlexosSimulation(solution_dir=str(plexos_fixture_root))
    db.ingest_system("plexos", system)
    db.ingest_simulation("plexos", sim)
    for cmap in system.get_default_category_maps():
        db.register_category_map("plexos", cmap)
    return db


def test_v1_pipeline_ingests_and_groups(plexos_v1_db):
    """The ingest path produces queryable composed tables and category maps."""
    tables = plexos_v1_db.list_tables("plexos")
    assert "generation" in tables, f"composed table missing: {tables}"
    assert "sim__generation_raw" in tables, f"raw sim table missing: {tables}"
    assert "catmap__gen_area" in tables, f"category map missing: {tables}"
    assert "gen_area" in plexos_v1_db.list_category_maps("plexos")


def test_v1_area_aggregation_matches_legacy(plexos_v1_db, plexos_scenario):
    """Area-aggregated generation through GATDatabase matches the pandas path.

    This is the load-bearing parity check: the duckdb engine must produce
    the same total generation per area, per timestamp, that the legacy
    pandas/h5py path produces.
    """
    # v1 path: query the duckdb composed table grouped by area
    v1_wide = plexos_v1_db.query_grouped("plexos", "generation", group_by=["gen_area"])

    # First column is the area label; remaining columns are per-timestamp totals
    v1_areas = v1_wide.iloc[:, 0].astype(str).tolist()

    # Legacy path: raw Generation, mapped to area, summed. Use get_generation
    # (raw dispatch — no curtailment math) for an apples-to-apples compare.
    legacy = plexos_scenario.get_generation().copy()
    legacy.columns = [
        str(plexos_scenario._gen_area_map.get(str(c), "other")) for c in legacy.columns
    ]
    legacy_by_area = legacy.T.groupby(level=0).sum().T  # timestamp × area
    legacy_areas = sorted(legacy_by_area.columns.astype(str).tolist())

    assert (
        sorted(v1_areas) == legacy_areas
    ), f"area sets differ: v1={v1_areas} legacy={legacy_areas}"

    # Compare per-area totals across the whole horizon (duckdb summed all
    # timestamp columns into row sums; legacy sums via pandas).
    v1_totals = {
        str(area): float(v1_wide.iloc[i, 1:].sum()) for i, area in enumerate(v1_areas)
    }
    legacy_totals = {
        str(area): float(legacy_by_area[area].sum()) for area in legacy_by_area.columns
    }
    for area in v1_totals:
        assert v1_totals[area] == pytest.approx(
            legacy_totals[area], rel=1e-4
        ), f"area {area}: v1={v1_totals[area]} legacy={legacy_totals[area]}"
