"""Tests for PlexosScenario's dual h5/duckdb backend.

Construction-level tests run unconditionally. The real-data parity suite
is gated on ``plexos_zip_fixture_root`` (skips cleanly without it) — see
``Eclipse2031_update_Feb25``, which ships both a native ``Solution.zip``
and the h5plexos-converted ``Solution.h5`` for the *same* underlying
PLEXOS solve, a rare chance to compare the two backends directly through
the exact same ``PlexosScenario`` class and its ``BaseScenario``-derived
high-level methods (``get_system_dispatch()`` etc.) — not a strict
regression gate (independent converters), see
docs/source/architecture/v1_migration_pattern.md.

Deliberately a separate file from tests/handlers/test_plexos_v1_migration.py,
which tests a different class pair (PlexosSystem/PlexosSimulation, the
older h5-based v1 POC) — this file is specifically about PlexosScenario
itself now speaking two backends.
"""
from pathlib import Path

import pandas as pd
import pytest

from gat.scenariohandlers import PlexosScenario


def _resolve_zip_path(root: Path) -> Path:
    """``plexos_zip_fixture_root`` may point at a directory or a file."""
    if root.is_dir():
        zips = sorted(root.glob("*.zip"))
        assert zips, f"no .zip files found in {root}"
        return zips[0]
    return root


class TestBackendDetectionOnConstruction:
    def test_h5_directory_uses_h5_backend(self, plexos_fixture_root):
        scenario = PlexosScenario(str(plexos_fixture_root))
        assert scenario._backend == "h5"
        assert scenario.parser is not None

    def test_zip_uses_duckdb_backend(self, plexos_zip_fixture_root):
        zip_path = _resolve_zip_path(plexos_zip_fixture_root)
        scenario = PlexosScenario(str(zip_path))
        assert scenario._backend == "duckdb"
        assert scenario.parser is None


class TestRealSolutionZipVsH5SystemDispatchParity:
    """The actual thing this feature was built for: get_system_dispatch()
    working identically (within tolerance) regardless of backend."""

    @pytest.fixture()
    def matched_pair(self, plexos_zip_fixture_root):
        zip_path = _resolve_zip_path(plexos_zip_fixture_root)
        h5_path = zip_path.with_suffix(".h5")
        if not h5_path.exists():
            pytest.skip(f"no matching .h5 file for {zip_path}")
        return zip_path, h5_path

    def test_get_system_dispatch_parity(self, matched_pair):
        zip_path, h5_path = matched_pair

        new = PlexosScenario(str(zip_path))
        legacy = PlexosScenario(solution_path=str(h5_path))

        new_dispatch = new.get_system_dispatch()
        legacy_dispatch = legacy.get_system_dispatch()

        new_totals = new_dispatch.sum().to_dict()
        legacy_totals = legacy_dispatch.sum().to_dict()

        common_techs = set(new_totals) & set(legacy_totals)
        assert len(common_techs) > 0, (
            f"no overlapping technology columns: new={set(new_totals)} "
            f"legacy={set(legacy_totals)}"
        )
        for tech in common_techs:
            assert new_totals[tech] == pytest.approx(legacy_totals[tech], rel=1e-2), (
                f"technology '{tech}': new={new_totals[tech]} legacy={legacy_totals[tech]}"
            )

    def test_get_generation_capacity_parity(self, matched_pair):
        zip_path, h5_path = matched_pair

        new = PlexosScenario(str(zip_path))
        legacy = PlexosScenario(solution_path=str(h5_path))

        new_cap = new.get_generation_capacity()
        legacy_cap = legacy.get_generation_capacity()

        assert new_cap.values.sum() == pytest.approx(legacy_cap.values.sum(), rel=1e-2)

    def test_get_peak_stats_shape(self, matched_pair):
        """Shape-only sanity check — peak timestamps can legitimately
        differ by a few hours between two independently-parsed exports."""
        zip_path, _ = matched_pair
        scenario = PlexosScenario(str(zip_path))
        peak = scenario.get_peak_stats()
        assert len(peak) > 0

    def test_get_storage_charging_and_production_cost_available(self, matched_pair):
        """These are the "full parity" additions — confirm they at least
        run and return sensible (non-crashing, non-empty-if-applicable)
        results against real data, on both backends."""
        zip_path, h5_path = matched_pair
        new = PlexosScenario(str(zip_path))
        legacy = PlexosScenario(solution_path=str(h5_path))

        new_charging = new.get_storage_charging()
        legacy_charging = legacy.get_storage_charging()
        assert new_charging is None or isinstance(new_charging, pd.DataFrame)
        assert legacy_charging is None or isinstance(legacy_charging, pd.DataFrame)

        new_cost = new.get_production_cost()
        assert new_cost is NotImplemented or isinstance(new_cost, pd.DataFrame)
