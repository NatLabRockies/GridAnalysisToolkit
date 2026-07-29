"""
Unit tests for aggregate dataset functionality.

Tests the pattern matching, validation, and retrieval logic for aggregate datasets.
"""

from unittest.mock import MagicMock, Mock

import pandas as pd
import pytest

from gat.models.base import AggregateDatasetConfig, DatasetConfig


class TestAggregateDatasetConfig:
    """Tests for AggregateDatasetConfig pydantic model"""

    def test_valid_config(self):
        """Test creating a valid aggregate dataset config"""
        config = AggregateDatasetConfig(
            name="generation",
            patterns=["ActivePowerVariable__*"],
            scale_by_base_power=True,
        )
        assert config.name == "generation"
        assert config.patterns == ["ActivePowerVariable__*"]
        assert config.scale_by_base_power is True

    def test_default_scaling(self):
        """Test default value for scale_by_base_power"""
        config = AggregateDatasetConfig(name="test", patterns=["Pattern*"])
        assert config.scale_by_base_power is True

    def test_empty_patterns_rejected(self):
        """Test that empty patterns list is rejected"""
        with pytest.raises(ValueError):
            AggregateDatasetConfig(name="test", patterns=[])


class TestDatasetConfig:
    """Tests for DatasetConfig with aggregate dataset support"""

    def test_get_aggregate_dataset_found(self):
        """Test retrieving an existing aggregate dataset by name"""
        config = DatasetConfig(
            aggregate_datasets=[
                AggregateDatasetConfig(
                    name="generation", patterns=["ActivePowerVariable__*"]
                ),
                AggregateDatasetConfig(
                    name="flow", patterns=["FlowActivePowerVariable__*"]
                ),
            ]
        )

        agg = config.get_aggregate_dataset("generation")
        assert agg is not None
        assert agg.name == "generation"
        assert agg.patterns == ["ActivePowerVariable__*"]

    def test_get_aggregate_dataset_not_found(self):
        """Test retrieving non-existent aggregate dataset returns None"""
        config = DatasetConfig(
            aggregate_datasets=[
                AggregateDatasetConfig(name="generation", patterns=["Pattern*"])
            ]
        )

        agg = config.get_aggregate_dataset("nonexistent")
        assert agg is None

    def test_validate_aggregate_datasets_success(self):
        """Test successful validation of aggregate datasets"""
        config = DatasetConfig(
            aggregate_datasets=[
                AggregateDatasetConfig(
                    name="generation",
                    patterns=["ActivePowerVariable__*", "Other__*"],
                ),
            ]
        )

        available = [
            "ActivePowerVariable__Gen1",
            "ActivePowerVariable__Gen2",
            "Other__Thing",
            "Unmatched__Dataset",
        ]

        results = config.validate_aggregate_datasets(available)

        assert "generation" in results
        assert len(results["generation"]) == 3
        assert "ActivePowerVariable__Gen1" in results["generation"]
        assert "ActivePowerVariable__Gen2" in results["generation"]
        assert "Other__Thing" in results["generation"]

    def test_validate_aggregate_datasets_pattern_no_match(self):
        """Test validation fails when a pattern has no matches"""
        config = DatasetConfig(
            aggregate_datasets=[
                AggregateDatasetConfig(
                    name="generation",
                    patterns=["NonExistent__*"],
                ),
            ]
        )

        available = ["ActivePowerVariable__Gen1"]

        with pytest.raises(ValueError) as exc_info:
            config.validate_aggregate_datasets(available)

        assert "pattern 'NonExistent__*' matched no raw datasets" in str(exc_info.value)

    def test_validate_aggregate_datasets_aggregate_no_match(self):
        """Test validation fails when aggregate dataset has no matches at all"""
        config = DatasetConfig(
            aggregate_datasets=[
                AggregateDatasetConfig(
                    name="generation",
                    patterns=["NonExistent1__*", "NonExistent2__*"],
                ),
            ]
        )

        available = ["SomeOther__Dataset"]

        with pytest.raises(ValueError) as exc_info:
            config.validate_aggregate_datasets(available)

        assert "has no matching raw datasets" in str(exc_info.value)

    def test_get_legacy_patterns(self):
        """Test accessing legacy path-based patterns"""
        config = DatasetConfig(
            generation_paths=["ActivePowerVariable*"],
            flow_paths=["FlowActivePowerVariable__Line"],
        )

        gen_patterns = config.get_legacy_patterns("generation")
        assert gen_patterns == ["ActivePowerVariable*"]

        flow_patterns = config.get_legacy_patterns("flow")
        assert flow_patterns == ["FlowActivePowerVariable__Line"]

        none_patterns = config.get_legacy_patterns("nonexistent")
        assert none_patterns is None


class TestPatternMatching:
    """Tests for pattern matching logic"""

    def test_simple_wildcard(self):
        """Test simple wildcard pattern matching"""
        import fnmatch

        datasets = [
            "ActivePowerVariable__Gen1",
            "ActivePowerVariable__Gen2",
            "OtherVariable__Gen1",
        ]

        pattern = "ActivePowerVariable__*"
        matches = [d for d in datasets if fnmatch.fnmatch(d, pattern)]

        assert len(matches) == 2
        assert "ActivePowerVariable__Gen1" in matches
        assert "ActivePowerVariable__Gen2" in matches

    def test_multiple_patterns(self):
        """Test matching with multiple patterns"""
        import fnmatch

        datasets = [
            "ActivePowerVariable__Gen1",
            "ActivePowerOutVariable__Gen2",
            "OtherVariable__Gen1",
        ]

        patterns = ["ActivePowerVariable__*", "ActivePowerOutVariable__*"]
        matches = set()
        for pattern in patterns:
            for dataset in datasets:
                if fnmatch.fnmatch(dataset, pattern):
                    matches.add(dataset)

        assert len(matches) == 2
        assert "ActivePowerVariable__Gen1" in matches
        assert "ActivePowerOutVariable__Gen2" in matches

    def test_question_mark_wildcard(self):
        """Test single character wildcard"""
        import fnmatch

        datasets = ["Gen1", "Gen2", "Gen10"]
        pattern = "Gen?"
        matches = [d for d in datasets if fnmatch.fnmatch(d, pattern)]

        assert len(matches) == 2
        assert "Gen1" in matches
        assert "Gen2" in matches
        assert "Gen10" not in matches


class TestBackwardCompatibility:
    """Tests for backward compatibility with legacy configuration"""

    def test_legacy_and_new_config_coexist(self):
        """Test that legacy and new configs can coexist"""
        config = DatasetConfig(
            # Legacy
            generation_paths=["ActivePowerVariable*"],
            flow_paths=["FlowActivePowerVariable__Line"],
            # New
            aggregate_datasets=[
                AggregateDatasetConfig(
                    name="generation_new",
                    patterns=["ActivePowerVariable__*"],
                )
            ],
        )

        # Both should be accessible
        assert config.generation_paths == ["ActivePowerVariable*"]
        assert config.get_legacy_patterns("generation") == ["ActivePowerVariable*"]

        agg = config.get_aggregate_dataset("generation_new")
        assert agg is not None
        assert agg.patterns == ["ActivePowerVariable__*"]


class TestIntegrationScenarios:
    """Integration-level tests for common usage scenarios"""

    def test_default_sienna_config(self):
        """Test that default Sienna configuration is valid"""
        from gat.models.sienna import initialize_sienna_config

        config = initialize_sienna_config("4.0.0")

        # Should have aggregate datasets
        assert config.aggregate_datasets is not None
        assert len(config.aggregate_datasets) > 0

        # Check specific defaults
        gen_agg = config.get_aggregate_dataset("generation")
        assert gen_agg is not None
        assert "ActivePowerVariable*" in gen_agg.patterns
        assert gen_agg.scale_by_base_power is True

        flow_agg = config.get_aggregate_dataset("flow")
        assert flow_agg is not None
        assert "FlowActivePowerVariable__Line" in flow_agg.patterns

    def test_custom_config_workflow(self):
        """Test typical custom configuration workflow"""
        # Create custom config
        config = DatasetConfig(
            aggregate_datasets=[
                AggregateDatasetConfig(
                    name="thermal",
                    patterns=["ActivePowerVariable__Thermal*"],
                    scale_by_base_power=True,
                ),
                AggregateDatasetConfig(
                    name="renewable",
                    patterns=["ActivePowerVariable__Renewable*"],
                    scale_by_base_power=True,
                ),
            ]
        )

        # Simulate available datasets
        available = [
            "ActivePowerVariable__ThermalStandard",
            "ActivePowerVariable__ThermalMultiStart",
            "ActivePowerVariable__RenewableDispatch",
            "ActivePowerVariable__RenewableNonDispatch",
            "OtherVariable__Something",
        ]

        # Validate
        results = config.validate_aggregate_datasets(available)

        # Check results
        assert len(results["thermal"]) == 2
        assert len(results["renewable"]) == 2

        # Retrieve configs
        thermal_config = config.get_aggregate_dataset("thermal")
        assert thermal_config.name == "thermal"
        assert thermal_config.scale_by_base_power is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
