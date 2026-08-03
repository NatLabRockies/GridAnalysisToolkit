"""Smoke coverage for the PJM 5-bus long-horizon fixture (issue #18).

No dataframe-regression baselines here on purpose: the fixture is
best-effort in CI (built on cache-miss by the docs workflow), so these
tests assert structure — zones, technologies, horizon — rather than
exact solve values, and skip when the fixture is absent.
"""

import pytest


@pytest.fixture(scope="module")
def pjm5_scenario(sienna_pjm5_fixture_root):
    from gat.scenariohandlers import SiennaScenario

    root = sienna_pjm5_fixture_root
    s = SiennaScenario(
        simulation_files=str(root / "simulation_store.h5"),
        system_file=str(root / "sys.json"),
    )
    s._use_cache = False
    return s


def test_pjm5_two_zones(pjm5_scenario):
    d = pjm5_scenario.get_area_dispatch(include_charging=False, include_use=False)
    areas = sorted(d.columns.get_level_values("Area").unique())
    assert areas == ["Z1", "Z2"]


def test_pjm5_technology_mapping(pjm5_scenario):
    d = pjm5_scenario.get_area_dispatch(include_charging=False, include_use=False)
    techs = set(d.columns.get_level_values("Technology").unique())
    # Thermal + both renewables must map to standard display groups —
    # no fuzzy-match fallbacks for this fixture.
    assert {"Coal", "PV", "Land-based Wind", "Native Demand"} <= techs


def test_pjm5_long_horizon(pjm5_scenario):
    d = pjm5_scenario.get_area_dispatch(include_charging=False, include_use=False)
    # The CI/annual build covers a year (8760h); local smoke builds may be
    # shorter. Either way the data must aggregate monthly without gaps.
    monthly = d.resample("MS").sum()
    assert len(monthly) >= 1
    if len(d) >= 8760:
        assert len(monthly) == 12
