import pytest
import warnings
from gat.models.scenario import TechnologyMapping, _fuzzy_match_technology
from gat.quickplots.utils import standard_color_dict
from gat.config import config as gc


@pytest.fixture(autouse=True)
def _mock_curtailable_tech():
    """Override gc.curtailable_tech for tests in this module without leaking
    the change to other modules' tests (e.g. handler regression snapshots)."""
    saved = getattr(gc, "curtailable_tech", None)
    gc.curtailable_tech = ["PV", "Wind", "Offshore Wind", "Onshore Wind"]
    try:
        yield
    finally:
        if saved is None:
            delattr(gc, "curtailable_tech")
        else:
            gc.curtailable_tech = saved


def test_standard_technology_mapping():
    """Test mapping with standard technology names that exist in standard_color_dict"""
    # Test with a standard technology
    tech_map = TechnologyMapping.new("PV")

    # Check the values are set correctly
    assert tech_map.display_group == "PV"
    assert tech_map.display_color == standard_color_dict["PV"]
    assert tech_map.display_order == list(standard_color_dict.keys()).index("PV")
    assert tech_map.curtailable == True  # PV is in curtailable_tech

    # Test with another standard technology that's not curtailable
    tech_map = TechnologyMapping.new("Nuclear")
    assert tech_map.display_group == "Nuclear"
    assert tech_map.display_color == standard_color_dict["Nuclear"]
    assert tech_map.display_order == list(standard_color_dict.keys()).index("Nuclear")
    assert tech_map.curtailable == False  # Nuclear isn't in curtailable_tech


def test_normalized_technology_mapping():
    """Test mapping with technologies that need normalization"""
    # Test with dashes
    tech_map = TechnologyMapping.new("off-shore-wind")
    assert tech_map.display_group == "Offshore Wind"
    assert tech_map.display_color == standard_color_dict["Offshore Wind"]

    # Test with underscores
    tech_map = TechnologyMapping.new("onshore_wind")
    assert tech_map.display_group == "Onshore Wind"
    assert tech_map.display_color == standard_color_dict["Onshore Wind"]

    # Test with spaces and case differences
    tech_map = TechnologyMapping.new("gas cc")
    assert tech_map.display_group == "Gas-CC"
    assert tech_map.display_color == standard_color_dict["Gas-CC"]


def test_random_color_assignment():
    """Test mapping with unknown technology names"""
    # Test with warning capture
    with pytest.warns(
        UserWarning, match="Technology 'UnknownTech' not found in standard mappings"
    ):
        tech_map = TechnologyMapping.new("UnknownTech")

    # Check that display group is the original technology
    assert tech_map.display_group == "UnknownTech"
    # Color should be assigned, but we can't check the exact value
    assert tech_map.display_color is not None
    # Default to bottom
    assert tech_map.display_order == 0
    # Should not be curtailable if not in the list
    assert tech_map.curtailable == False


def test_curtailable_technologies():
    """Test curtailable flag assignment"""
    # Wind technologies should be curtailable
    tech_map = TechnologyMapping.new("Wind")
    assert tech_map.curtailable == True

    # Coal should not be curtailable
    tech_map = TechnologyMapping.new("Coal")
    assert tech_map.curtailable == False

    # Even an unknown technology that matches a curtailable name should be marked
    gc.curtailable_tech.append("UnknownCurtailableTech")
    tech_map = TechnologyMapping.new("UnknownCurtailableTech")
    assert tech_map.curtailable == True


class TestFuzzyTechnologyMapping:
    """Model technology naming is arbitrary and backend-specific (PLEXOS
    categories in particular are user-defined in the PLEXOS GUI, not a fixed
    convention), so TechnologyMapping.new() falls back to a token-overlap
    fuzzy match against standard_color_dict before giving up and assigning a
    random color. These technology strings mirror the real PLEXOS Eclipse
    fixture's categories.
    """

    def test_compound_underscore_codes_resolve_to_display_group(self):
        with pytest.warns(UserWarning, match="Fuzzy-matched to 'PV'"):
            tech_map = TechnologyMapping.new("Solar_PV")
        assert tech_map.display_group == "PV"
        assert tech_map.display_color == standard_color_dict["PV"]

    def test_fuzzy_match_does_not_confuse_solar_pv_with_storage(self):
        """Regression guard: whole-string similarity (difflib) ranks
        "storage" above "pv" for "Solar_PV" purely from shared letters.
        Token-overlap scoring must not repeat that mistake."""
        tech_map = TechnologyMapping.new("Solar_PV")
        assert tech_map.display_group != "Storage"

    def test_fuel_and_prime_mover_code_resolves_to_coal(self):
        tech_map = TechnologyMapping.new("COAL_CT")
        assert tech_map.display_group == "Coal"
        assert tech_map.display_color == standard_color_dict["Coal"]

    def test_fuel_and_prime_mover_code_resolves_to_gas_cc(self):
        tech_map = TechnologyMapping.new("NATURAL_GAS_CC")
        assert tech_map.display_group == "Gas-CC"

    def test_no_shared_tokens_falls_back_to_random_color(self):
        """A technology with zero token overlap against every standard
        display group must fall through to the original random-color
        behavior, not a spurious fuzzy match."""
        with pytest.warns(UserWarning, match="Assigning a random color"):
            tech_map = TechnologyMapping.new("MUNICIPAL_WASTE_OT")
        assert tech_map.display_group == "MUNICIPAL_WASTE_OT"

    def test_exact_match_takes_precedence_over_fuzzy_match(self):
        """A technology already exactly present in standard_color_dict must
        never be routed through fuzzy matching."""
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            tech_map = TechnologyMapping.new("Coal")
        assert tech_map.display_group == "Coal"

    def test_config_override_bypasses_fuzzy_matching_entirely(self):
        """The YAML-configurable technology_mappings override in
        ScenarioConfig is resolved before create_tech_mappings() (and thus
        TechnologyMapping.new()) is ever called for a given technology --
        fuzzy matching only ever runs for technologies left unmapped after
        the config override, so it can't clobber a user's explicit choice."""
        from gat.models.scenario import ScenarioConfig

        config = ScenarioConfig(model_type="Plexos")
        config.technology_mappings["Solar_PV"] = TechnologyMapping(
            display_group="Storage", display_color="#000000"
        )
        assert config.technology_mappings["Solar_PV"].display_group == "Storage"


class TestFuzzyMatchTechnologyHelper:
    """Direct tests of the _fuzzy_match_technology token-overlap scorer."""

    def test_prefers_smaller_more_specific_candidate_over_generic_abbreviation(self):
        """ "COAL_CT" shares a token with both "Coal" and generic "*-CT"
        entries (e.g. "NG-CT"/"RE-CT"), but the tighter, more specific
        candidate ("Coal") must win on Jaccard overlap."""
        result = _fuzzy_match_technology("COAL_CT", list(standard_color_dict.keys()))
        assert result == "Coal"

    def test_no_overlap_returns_none(self):
        assert (
            _fuzzy_match_technology("Xyzzy123", list(standard_color_dict.keys()))
            is None
        )

    def test_empty_technology_string_returns_none(self):
        assert _fuzzy_match_technology("", list(standard_color_dict.keys())) is None
