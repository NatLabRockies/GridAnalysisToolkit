"""
Tests for default_palette field in scenario configurations.

Tests that all scenario config types (Sienna, ReEDS, Plexos) support
the default_palette field.
"""

from datetime import datetime

import pytest

from gat.models.project import (
    PlexosScenarioConfig,
    ReedsScenarioConfig,
    SiennaScenarioConfig,
)


class TestSiennaScenarioDefaultPalette:
    """Tests for default_palette field in SiennaScenarioConfig."""

    def test_sienna_scenario_with_default_palette(self):
        """Test creating Sienna scenario with default_palette."""
        config = SiennaScenarioConfig(
            name="Test Scenario",
            system_path="/path/to/system.json",
            simulation_paths="/path/to/simulation.h5",
            default_palette="my_palette",
        )

        assert config.default_palette == "my_palette"
        assert config.name == "Test Scenario"
        assert config.type == "sienna"

    def test_sienna_scenario_without_default_palette(self):
        """Test creating Sienna scenario without default_palette (None)."""
        config = SiennaScenarioConfig(
            name="Test Scenario",
            system_path="/path/to/system.json",
            simulation_paths="/path/to/simulation.h5",
        )

        assert config.default_palette is None
        assert config.name == "Test Scenario"

    def test_sienna_scenario_default_palette_serialization(self):
        """Test that default_palette is included in serialization."""
        config = SiennaScenarioConfig(
            name="Test Scenario",
            system_path="/path/to/system.json",
            simulation_paths="/path/to/simulation.h5",
            default_palette="test_palette",
        )

        data = config.model_dump()
        assert "default_palette" in data
        assert data["default_palette"] == "test_palette"

    def test_sienna_scenario_default_palette_exclude_none(self):
        """Test that default_palette is excluded when None."""
        config = SiennaScenarioConfig(
            name="Test Scenario",
            system_path="/path/to/system.json",
            simulation_paths="/path/to/simulation.h5",
            default_palette=None,
        )

        data = config.model_dump(exclude_none=True)
        assert "default_palette" not in data


class TestReedsScenarioDefaultPalette:
    """Tests for default_palette field in ReedsScenarioConfig."""

    def test_reeds_scenario_with_default_palette(self):
        """Test creating ReEDS scenario with default_palette."""
        config = ReedsScenarioConfig(
            name="ReEDS Test",
            path="/path/to/reeds/output",
            solve_year=2035,
            default_palette="reeds_palette",
        )

        assert config.default_palette == "reeds_palette"
        assert config.name == "ReEDS Test"
        assert config.type == "reeds"
        assert config.solve_year == 2035

    def test_reeds_scenario_without_default_palette(self):
        """Test creating ReEDS scenario without default_palette."""
        config = ReedsScenarioConfig(
            name="ReEDS Test",
            path="/path/to/reeds/output",
        )

        assert config.default_palette is None

    def test_reeds_scenario_default_palette_serialization(self):
        """Test that default_palette is included in serialization."""
        config = ReedsScenarioConfig(
            name="ReEDS Test",
            path="/path/to/reeds/output",
            default_palette="my_reeds_palette",
        )

        data = config.model_dump()
        assert "default_palette" in data
        assert data["default_palette"] == "my_reeds_palette"


class TestPlexosScenarioDefaultPalette:
    """Tests for default_palette field in PlexosScenarioConfig."""

    def test_plexos_scenario_with_default_palette(self):
        """Test creating Plexos scenario with default_palette."""
        config = PlexosScenarioConfig(
            name="Plexos Test",
            solution_path="/path/to/solution.xml",
            default_palette="plexos_palette",
        )

        assert config.default_palette == "plexos_palette"
        assert config.name == "Plexos Test"
        assert config.type == "plexos"

    def test_plexos_scenario_without_default_palette(self):
        """Test creating Plexos scenario without default_palette."""
        config = PlexosScenarioConfig(
            name="Plexos Test",
            solution_path="/path/to/solution.xml",
        )

        assert config.default_palette is None

    def test_plexos_scenario_default_palette_serialization(self):
        """Test that default_palette is included in serialization."""
        config = PlexosScenarioConfig(
            name="Plexos Test",
            solution_path="/path/to/solution.xml",
            default_palette="plexos_viz",
        )

        data = config.model_dump()
        assert "default_palette" in data
        assert data["default_palette"] == "plexos_viz"


class TestScenarioDefaultPaletteIntegration:
    """Integration tests for default_palette across scenario types."""

    def test_all_scenario_types_support_default_palette(self):
        """Test that all scenario types have default_palette field."""
        sienna_config = SiennaScenarioConfig(
            name="Sienna",
            system_path="/sys.json",
            simulation_paths="/sim.h5",
            default_palette="palette1",
        )

        reeds_config = ReedsScenarioConfig(
            name="ReEDS",
            path="/reeds",
            default_palette="palette2",
        )

        plexos_config = PlexosScenarioConfig(
            name="Plexos",
            solution_path="/solution.xml",
            default_palette="palette3",
        )

        assert sienna_config.default_palette == "palette1"
        assert reeds_config.default_palette == "palette2"
        assert plexos_config.default_palette == "palette3"

    def test_default_palette_with_other_fields(self):
        """Test default_palette works alongside other optional fields."""
        config = SiennaScenarioConfig(
            name="Full Config",
            description="A complete scenario config",
            system_path="/system.json",
            simulation_paths=["/sim1.h5", "/sim2.h5"],
            metadata_path="/metadata.json",
            default_palette="comprehensive_palette",
            tags=["test", "full"],
            created_at=datetime(2024, 1, 1),
        )

        assert config.default_palette == "comprehensive_palette"
        assert config.description == "A complete scenario config"
        assert config.metadata_path == "/metadata.json"
        assert "test" in config.tags
        assert config.created_at is not None

    def test_default_palette_yaml_roundtrip(self):
        """Test that default_palette survives YAML serialization."""
        import yaml

        config = SiennaScenarioConfig(
            name="YAML Test",
            system_path="/system.json",
            simulation_paths="/sim.h5",
            default_palette="yaml_palette",
        )

        # Serialize to YAML
        yaml_str = yaml.dump(config.model_dump(exclude_none=True))

        # Deserialize from YAML
        data = yaml.safe_load(yaml_str)
        restored_config = SiennaScenarioConfig(**data)

        assert restored_config.default_palette == "yaml_palette"
        assert restored_config.name == "YAML Test"
