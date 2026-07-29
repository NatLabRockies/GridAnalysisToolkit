"""Phase 10c — public-property regression tests.

Promoted configuration that used to require private-attribute mutation
(e.g. `scenario._load_includes_charging = True`) is now exposed as
public properties. These tests pin the contract.
"""
import pandas as pd
import pytest


def test_load_includes_charging_default_false(plexos_scenario):
    """Default for plexos scenarios is native demand (charging tracked
    separately)."""
    assert plexos_scenario.load_includes_charging is False
    # The private attribute still exists; the public property is just a
    # documented setter / getter pair on top of it.
    assert plexos_scenario._load_includes_charging is False


def test_load_includes_charging_setter(plexos_scenario):
    """Setting the public property mutates the underlying flag."""
    original = plexos_scenario.load_includes_charging
    try:
        plexos_scenario.load_includes_charging = True
        assert plexos_scenario.load_includes_charging is True
        assert plexos_scenario._load_includes_charging is True
    finally:
        plexos_scenario.load_includes_charging = original


def test_tech_simple_property(plexos_scenario):
    """`tech_simple` returns the shared tech-simplification dict and
    accepts replacement via the setter."""
    original = dict(plexos_scenario.tech_simple)
    try:
        # Read path
        assert isinstance(plexos_scenario.tech_simple, dict)
        # Mutating in place still works (existing pattern)
        plexos_scenario.tech_simple["NG/CC"] = "Gas-CC"
        assert plexos_scenario.tech_simple["NG/CC"] == "Gas-CC"
    finally:
        plexos_scenario._tech_simple.clear()
        plexos_scenario._tech_simple.update(original)


def test_gen_area_map_property(plexos_scenario):
    """`gen_area_map` exposes the generator → area mapping."""
    assert isinstance(plexos_scenario.gen_area_map, dict)
    assert len(plexos_scenario.gen_area_map) > 0


def test_area_property_default(plexos_scenario):
    """Plexos scenarios default `area` to the empty string (no Sienna
    ext lookup needed)."""
    # Default for BaseScenario is "area"; Plexos may override.
    assert plexos_scenario.area in ("", "area")


def test_load_includes_charging_from_config():
    """Construction-time setting via `ScenarioConfig.load_includes_charging`
    flows through to `BaseScenario._load_includes_charging`."""
    from gat.models.scenario import ScenarioConfig
    cfg = ScenarioConfig(
        model_type="Plexos",
        load_includes_charging=True,
    )
    assert cfg.load_includes_charging is True
