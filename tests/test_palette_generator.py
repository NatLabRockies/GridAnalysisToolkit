# tests/test_palette_generator.py
"""
Tests for palette generation from system files.

Tests the BaseSystem abstraction, SiennaSystem implementation,
and PaletteGenerator functionality.
"""

import json
import tempfile
from pathlib import Path

import pytest

from gat.datahelpers.base_system import GeneratorCategory, SystemInfo
from gat.datahelpers.sienna_system import SiennaSystem
from gat.models.palette import Palette
from gat.palette_generator import PaletteGenerator


@pytest.fixture
def sample_sienna_system():
    """Create a sample Sienna system JSON file for testing."""
    system_data = {
        "data_format_version": "3.0.0",
        "data": {
            "name": "Test System",
            "description": "A test power system",
            "base_power": 100.0,
            "components": [
                # Solar PV generator
                {
                    "__metadata__": {"type": "RenewableNonDispatch"},
                    "name": "Solar_PV_1",
                    "fuel": "Solar",
                    "prime_mover": "PV",
                    "technology_type": "Photovoltaic",
                    "available": True,
                    "active_power_limits": {"min": 0.0, "max": 100.0},
                    "bus": {"value": "bus1"},
                },
                {
                    "__metadata__": {"type": "RenewableNonDispatch"},
                    "name": "Solar_PV_2",
                    "fuel": "Solar",
                    "prime_mover": "PV",
                    "technology_type": "Photovoltaic",
                    "available": True,
                    "active_power_limits": {"min": 0.0, "max": 150.0},
                    "bus": {"value": "bus2"},
                },
                # Wind generator
                {
                    "__metadata__": {"type": "RenewableNonDispatch"},
                    "name": "Wind_1",
                    "fuel": "Wind",
                    "prime_mover": "WT",
                    "technology_type": "Onshore",
                    "available": True,
                    "active_power_limits": {"min": 0.0, "max": 200.0},
                    "bus": {"value": "bus1"},
                },
                # Natural gas CT
                {
                    "__metadata__": {"type": "ThermalStandard"},
                    "name": "Gas_CT_1",
                    "fuel": "NaturalGas",
                    "prime_mover": "CT",
                    "technology_type": "CombustionTurbine",
                    "available": True,
                    "active_power_limits": {"min": 0.0, "max": 50.0},
                    "bus": {"value": "bus1"},
                },
                # Natural gas CC
                {
                    "__metadata__": {"type": "ThermalStandard"},
                    "name": "Gas_CC_1",
                    "fuel": "NaturalGas",
                    "prime_mover": "CC",
                    "technology_type": "CombinedCycle",
                    "available": True,
                    "active_power_limits": {"min": 0.0, "max": 300.0},
                    "bus": {"value": "bus2"},
                },
                # Coal
                {
                    "__metadata__": {"type": "ThermalStandard"},
                    "name": "Coal_1",
                    "fuel": "Coal",
                    "prime_mover": "ST",
                    "technology_type": "Steam",
                    "available": True,
                    "active_power_limits": {"min": 50.0, "max": 400.0},
                    "bus": {"value": "bus3"},
                },
                # Battery storage
                {
                    "__metadata__": {"type": "GenericBattery"},
                    "name": "Battery_1",
                    "technology_type": "LithiumIon",
                    "available": True,
                    "rating": 50.0,
                    "bus": {"value": "bus1"},
                },
                # Hydro
                {
                    "__metadata__": {"type": "HydroDispatch"},
                    "name": "Hydro_1",
                    "technology_type": "Conventional",
                    "available": True,
                    "active_power_limits": {"min": 0.0, "max": 100.0},
                    "bus": {"value": "bus2"},
                },
                # Buses
                {"__metadata__": {"type": "ACBus"}, "name": "bus1", "number": 1},
                {"__metadata__": {"type": "ACBus"}, "name": "bus2", "number": 2},
                {"__metadata__": {"type": "ACBus"}, "name": "bus3", "number": 3},
                # Load
                {
                    "__metadata__": {"type": "PowerLoad"},
                    "name": "Load_1",
                    "max_active_power": 500.0,
                    "bus": {"value": "bus1"},
                },
            ],
        },
    }

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(system_data, f)
        temp_path = f.name

    yield temp_path

    # Cleanup
    Path(temp_path).unlink()


class TestSiennaSystem:
    """Tests for SiennaSystem implementation."""

    def test_load_system(self, sample_sienna_system):
        """Test loading a Sienna system file."""
        system = SiennaSystem(sample_sienna_system)
        assert system._system_data is not None
        assert system._system_data["data_format_version"] == "3.0.0"

    def test_system_info(self, sample_sienna_system):
        """Test extracting system info."""
        system = SiennaSystem(sample_sienna_system)
        info = system.get_system_info()

        assert isinstance(info, SystemInfo)
        assert info.name == "Test System"
        assert info.base_power == 100.0
        assert (
            info.num_generators == 8
        )  # 2 solar, 1 wind, 2 gas, 1 coal, 1 battery, 1 hydro
        assert info.num_buses == 3
        assert info.num_loads == 1

    def test_list_component_types(self, sample_sienna_system):
        """Test listing component types."""
        system = SiennaSystem(sample_sienna_system)
        types = system.list_component_types()

        assert "RenewableNonDispatch" in types
        assert "ThermalStandard" in types
        assert "GenericBattery" in types
        assert "HydroDispatch" in types
        assert "ACBus" in types
        assert "PowerLoad" in types

    def test_list_generator_categories(self, sample_sienna_system):
        """Test listing generator categories."""
        system = SiennaSystem(sample_sienna_system)
        categories = system.list_generator_categories()

        assert len(categories) > 0
        assert all(isinstance(cat, GeneratorCategory) for cat in categories)

        # Check we have expected categories
        category_names = [cat.name for cat in categories]
        assert any("Solar" in name or "PV" in name for name in category_names)
        assert any("Wind" in name for name in category_names)
        assert any("Gas" in name or "NaturalGas" in name for name in category_names)
        assert any("Coal" in name for name in category_names)
        assert any("Battery" in name for name in category_names)
        assert any("Hydro" in name for name in category_names)

    def test_vre_classification(self, sample_sienna_system):
        """Test VRE classification."""
        system = SiennaSystem(sample_sienna_system)
        categories = system.list_generator_categories()

        # Solar and wind should be VRE
        solar_cats = [
            cat for cat in categories if "Solar" in cat.name or "PV" in cat.name
        ]
        wind_cats = [cat for cat in categories if "Wind" in cat.name]

        assert any(cat.is_vre for cat in solar_cats)
        assert any(cat.is_vre for cat in wind_cats)

        # Coal and gas should not be VRE
        coal_cats = [cat for cat in categories if "Coal" in cat.name]
        gas_cats = [
            cat for cat in categories if "Gas" in cat.name or "NaturalGas" in cat.name
        ]

        assert all(not cat.is_vre for cat in coal_cats)
        assert all(not cat.is_vre for cat in gas_cats)

    def test_storage_classification(self, sample_sienna_system):
        """Test storage classification."""
        system = SiennaSystem(sample_sienna_system)
        categories = system.list_generator_categories()

        # Battery should be storage
        battery_cats = [cat for cat in categories if "Battery" in cat.name]
        assert any(cat.is_storage for cat in battery_cats)

        # Solar should not be storage
        solar_cats = [
            cat for cat in categories if "Solar" in cat.name or "PV" in cat.name
        ]
        assert all(not cat.is_storage for cat in solar_cats)

    def test_get_generator_data(self, sample_sienna_system):
        """Test getting generator data as DataFrame."""
        system = SiennaSystem(sample_sienna_system)
        df = system.get_generator_data()

        assert not df.empty
        assert "name" in df.columns
        assert "category" in df.columns
        assert "capacity" in df.columns
        assert "is_vre" in df.columns
        assert "is_storage" in df.columns

        # Check we have 8 generators
        assert len(df) == 8

        # Check capacity values
        assert df["capacity"].sum() > 0

    def test_get_load_data(self, sample_sienna_system):
        """Test getting load data as DataFrame."""
        system = SiennaSystem(sample_sienna_system)
        df = system.get_load_data()

        assert not df.empty
        assert "name" in df.columns
        assert "category" in df.columns
        assert "demand" in df.columns

        # Check we have 1 load
        assert len(df) == 1

    def test_validate(self, sample_sienna_system):
        """Test system validation."""
        system = SiennaSystem(sample_sienna_system)
        warnings = system.validate()

        # Should have no critical warnings
        assert isinstance(warnings, list)
        # May have some warnings but shouldn't be empty system
        assert not any("no generators" in w.lower() for w in warnings)


class TestPaletteGenerator:
    """Tests for PaletteGenerator."""

    def test_generate_palette(self, sample_sienna_system):
        """Test generating a palette from system file."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)

        palette = generator.generate(
            name="Test Palette",
            simulation_type="sienna",
            description="Test palette from sample system",
        )

        assert isinstance(palette, Palette)
        assert palette.name == "Test Palette"
        assert palette.simulation_type == "sienna"
        assert len(palette.display_categories) > 0
        assert len(palette.category_mappings) > 0
        assert len(palette.stack_order) == len(palette.display_categories)

    def test_display_categories(self, sample_sienna_system):
        """Test display category generation."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        # Check we have expected display categories
        display_names = [cat.name for cat in palette.display_categories]

        # Should have simplified names
        assert any("Solar" in name for name in display_names)
        assert any("Wind" in name for name in display_names)
        assert any("Gas" in name or "Natural Gas" in name for name in display_names)
        assert any("Coal" in name for name in display_names)
        assert any("Battery" in name or "Storage" in name for name in display_names)
        assert any("Hydro" in name for name in display_names)

        # Each display category should have a color
        for cat in palette.display_categories:
            assert cat.color is not None
            assert cat.color.startswith("#") or cat.color.isalpha()

    def test_category_mappings(self, sample_sienna_system):
        """Test category mappings generation."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        # Each simulation category should map to a display category
        assert len(palette.category_mappings) >= len(system.list_generator_categories())

        # All display categories in mappings should exist
        display_names = {cat.name for cat in palette.display_categories}
        for mapping in palette.category_mappings:
            assert mapping.display_category in display_names

    def test_stack_order(self, sample_sienna_system):
        """Test stack order generation."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        # Stack order should include all display categories
        assert len(palette.stack_order) == len(palette.display_categories)

        display_names = {cat.name for cat in palette.display_categories}
        for name in palette.stack_order:
            assert name in display_names

        # Check typical ordering: baseload at bottom, VRE/storage at top
        stack_lower = [name.lower() for name in palette.stack_order]

        # Solar should be higher than coal if both exist
        if any("solar" in name for name in stack_lower) and any(
            "coal" in name for name in stack_lower
        ):
            solar_idx = next(i for i, name in enumerate(stack_lower) if "solar" in name)
            coal_idx = next(i for i, name in enumerate(stack_lower) if "coal" in name)
            assert solar_idx > coal_idx, "Solar should stack above coal"

    def test_vre_classification(self, sample_sienna_system):
        """Test VRE classification in palette."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        assert palette.vre_classification is not None
        assert len(palette.vre_classification.vre_technologies) > 0

        # Should include VRE types
        vre_techs_lower = [
            tech.lower() for tech in palette.vre_classification.vre_technologies
        ]
        assert any("solar" in tech or "pv" in tech for tech in vre_techs_lower)
        assert any("wind" in tech for tech in vre_techs_lower)

    def test_load_classification(self, sample_sienna_system):
        """Test load classification in palette."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        assert palette.load_classification is not None

        # Battery should be in storage charging
        if palette.load_classification.storage_charging_categories:
            storage_cats_lower = [
                cat.lower()
                for cat in palette.load_classification.storage_charging_categories
            ]
            assert any("battery" in cat for cat in storage_cats_lower)

    def test_validate_palette(self, sample_sienna_system):
        """Test palette validation."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        # Validate should pass
        warnings = palette.validate_stack_order()
        assert isinstance(warnings, list)
        # Should have no warnings for auto-generated palette
        assert len(warnings) == 0

    def test_color_assignment(self, sample_sienna_system):
        """Test that colors are assigned appropriately."""
        system = SiennaSystem(sample_sienna_system)
        generator = PaletteGenerator(system)
        palette = generator.generate(name="Test", simulation_type="sienna")

        # Check that different categories have different colors (mostly)
        colors = [cat.color for cat in palette.display_categories]
        unique_colors = set(colors)

        # Should have good color diversity (allow some overlap for large systems)
        assert len(unique_colors) >= min(len(colors), 5)


class TestPaletteGeneratorEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_system(self):
        """Test handling of system with no generators."""
        system_data = {
            "data_format_version": "3.0.0",
            "data": {
                "name": "Empty System",
                "base_power": 100.0,
                "components": [
                    {"__metadata__": {"type": "ACBus"}, "name": "bus1", "number": 1}
                ],
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(system_data, f)
            temp_path = f.name

        try:
            system = SiennaSystem(temp_path)
            generator = PaletteGenerator(system)

            with pytest.raises(ValueError, match="no generators"):
                palette = generator.generate(name="Test", simulation_type="sienna")
        finally:
            Path(temp_path).unlink()

    def test_invalid_system_file(self):
        """Test handling of invalid system file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json{")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="Failed to parse"):
                system = SiennaSystem(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_nonexistent_file(self):
        """Test handling of nonexistent file."""
        with pytest.raises(FileNotFoundError):
            system = SiennaSystem("/nonexistent/path/to/system.json")
