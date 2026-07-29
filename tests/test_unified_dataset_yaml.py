"""
Test unified dataset configuration YAML serialization.

Verifies that DatasetConfig with RawDataset and AggregateDataset
can be properly serialized to and from YAML in ScenarioConfig.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from gat.models.base import AggregateDataset, DatasetConfig, RawDataset
from gat.models.project import SiennaScenarioConfig


def test_dataset_config_yaml_serialization():
    """Test that DatasetConfig serializes to YAML correctly"""
    config = DatasetConfig(
        aggregates={
            "generation": AggregateDataset(
                patterns=["ActivePowerVariable__*"],
                scale_factor=1.0,
                combination_method="concat",
            ),
            "flow": AggregateDataset(
                patterns=["FlowActivePowerVariable__Line"],
                scale_factor=1.0,
            ),
            "specific_gen": RawDataset(
                h5_path="/simulation/decision_models/UC/variables/ActivePowerVariable__Gen1",
                scale_factor=1.0,
            ),
        }
    )

    # Serialize to dict
    config_dict = config.model_dump()

    # Verify structure
    assert "aggregates" in config_dict
    assert "generation" in config_dict["aggregates"]
    assert "flow" in config_dict["aggregates"]
    assert "specific_gen" in config_dict["aggregates"]

    # Verify generation aggregate
    gen_config = config_dict["aggregates"]["generation"]
    assert "patterns" in gen_config
    assert gen_config["patterns"] == ["ActivePowerVariable__*"]
    assert gen_config["scale_factor"] == 1.0

    # Verify raw dataset
    raw_config = config_dict["aggregates"]["specific_gen"]
    assert "h5_path" in raw_config
    assert "patterns" not in raw_config  # RawDataset doesn't have patterns

    # Deserialize back
    reconstructed = DatasetConfig(**config_dict)
    assert len(reconstructed.aggregates) == 3
    assert "generation" in reconstructed.aggregates


def test_scenario_config_with_dataset_config_yaml():
    """Test that SiennaScenarioConfig with DatasetConfig serializes correctly"""
    from gat.models.project import SimulationConfig, SystemConfig

    dataset_config = DatasetConfig(
        aggregates={
            "generation": AggregateDataset(
                patterns=["ActivePowerVariable__*", "ActivePowerOutVariable__*"],
                scale_factor=1.0,
            ),
            "thermal_gen": AggregateDataset(
                patterns=["ActivePowerVariable__Thermal*"],
                scale_factor=1.0,
            ),
            "flow": AggregateDataset(
                patterns=["FlowActivePowerVariable__Line"],
                scale_factor=1.0,
            ),
        }
    )

    scenario = SiennaScenarioConfig(
        name="Test Scenario",
        simulation=SimulationConfig(paths="/path/to/simulation.h5", type="UC"),
        system=SystemConfig(path="/path/to/system.json"),
    )

    # Set dataset config
    scenario.set_dataset_config_from_object(dataset_config)

    # Serialize to dict
    scenario_dict = scenario.model_dump()

    # Verify dataset config is present in simulation section
    assert "simulation" in scenario_dict
    assert scenario_dict["simulation"]["datasets"] is not None
    assert "aggregates" in scenario_dict["simulation"]["datasets"]

    # Verify datasets are present
    datasets = scenario_dict["simulation"]["datasets"]["aggregates"]
    assert "generation" in datasets
    assert "thermal_gen" in datasets
    assert "flow" in datasets

    # Deserialize back
    reconstructed = SiennaScenarioConfig(**scenario_dict)
    assert reconstructed.simulation.datasets is not None

    # Get back as DatasetConfig object
    dataset_config_obj = reconstructed.get_dataset_config()
    assert dataset_config_obj is not None
    assert len(dataset_config_obj.aggregates) == 3


def test_scenario_config_yaml_file_roundtrip():
    """Test full YAML file write and read roundtrip"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yaml_path = Path(tmpdir) / "test_scenario.yaml"

        from gat.models.project import SimulationConfig, SystemConfig

        # Create scenario with dataset config
        dataset_config = DatasetConfig(
            aggregates={
                "generation": AggregateDataset(
                    patterns=["ActivePowerVariable__*"],
                    scale_factor=1.0,
                ),
                "flow": AggregateDataset(
                    patterns=["FlowActivePowerVariable__Line"],
                    scale_factor=1.0,
                    combination_method="concat",
                ),
                "gen1": RawDataset(
                    h5_path="/simulation/decision_models/UC/variables/ActivePowerVariable__Gen1",
                    scale_factor=1.0,
                ),
            }
        )

        scenario = SiennaScenarioConfig(
            name="Test Scenario",
            description="Test scenario with dataset configs",
            simulation=SimulationConfig(paths="/path/to/simulation.h5", type="UC"),
            system=SystemConfig(path="/path/to/system.json"),
            tags=["test", "sample"],
        )
        scenario.set_dataset_config_from_object(dataset_config)

        # Write to YAML
        with open(yaml_path, "w") as f:
            yaml.dump(scenario.model_dump(), f, sort_keys=False)

        # Read back from YAML
        with open(yaml_path, "r") as f:
            loaded_dict = yaml.safe_load(f)

        # Reconstruct
        loaded_scenario = SiennaScenarioConfig(**loaded_dict)

        # Verify
        assert loaded_scenario.name == "Test Scenario"
        assert loaded_scenario.simulation.type == "UC"
        assert loaded_scenario.simulation.datasets is not None

        # Get dataset config object
        loaded_dataset_config = loaded_scenario.get_dataset_config()
        assert loaded_dataset_config is not None
        assert len(loaded_dataset_config.aggregates) == 3

        # Verify generation aggregate
        gen_def = loaded_dataset_config.get_dataset_config("generation")
        assert gen_def is not None
        assert isinstance(gen_def, AggregateDataset)
        assert gen_def.patterns == ["ActivePowerVariable__*"]
        assert gen_def.scale_factor == 1.0

        # Verify flow aggregate
        flow_def = loaded_dataset_config.get_dataset_config("flow")
        assert flow_def is not None
        assert isinstance(flow_def, AggregateDataset)
        assert flow_def.combination_method == "concat"

        # Verify raw dataset
        gen1_def = loaded_dataset_config.get_dataset_config("gen1")
        assert gen1_def is not None
        assert isinstance(gen1_def, RawDataset)
        assert (
            gen1_def.h5_path
            == "/simulation/decision_models/UC/variables/ActivePowerVariable__Gen1"
        )


def test_yaml_structure_matches_expected():
    """Test that YAML structure matches expected format for documentation"""
    from gat.models.project import SimulationConfig, SystemConfig

    dataset_config = DatasetConfig(
        aggregates={
            "generation": AggregateDataset(
                patterns=["ActivePowerVariable__*"],
                scale_factor=1.0,
                combination_method="concat",
            ),
        }
    )

    scenario = SiennaScenarioConfig(
        name="Test",
        simulation=SimulationConfig(paths="/path/to/simulation.h5", type=None),
        system=SystemConfig(path="/path/to/system.json"),
    )
    scenario.set_dataset_config_from_object(dataset_config)

    # Convert to YAML string
    yaml_str = yaml.dump(scenario.model_dump(), sort_keys=False)

    # Verify expected keys are present in YAML
    assert "simulation:" in yaml_str
    assert "datasets:" in yaml_str
    assert "aggregates:" in yaml_str
    assert "generation:" in yaml_str
    assert "patterns:" in yaml_str
    assert "- ActivePowerVariable__*" in yaml_str
    assert "scale_factor:" in yaml_str
    assert "combination_method: concat" in yaml_str


def test_empty_dataset_config():
    """Test scenario with no dataset config"""
    from gat.models.project import SimulationConfig, SystemConfig

    scenario = SiennaScenarioConfig(
        name="Test",
        simulation=SimulationConfig(paths="/path/to/simulation.h5", type=None),
        system=SystemConfig(path="/path/to/system.json"),
    )

    # Should have None datasets by default
    assert scenario.simulation.datasets is None
    assert scenario.get_dataset_config() is None

    # Should serialize/deserialize fine
    scenario_dict = scenario.model_dump()
    reconstructed = SiennaScenarioConfig(**scenario_dict)
    assert reconstructed.get_dataset_config() is None


def test_multiple_patterns_in_aggregate():
    """Test aggregate dataset with multiple patterns"""
    config = DatasetConfig(
        aggregates={
            "generation": AggregateDataset(
                patterns=[
                    "ActivePowerVariable__*",
                    "ActivePowerOutVariable__*",
                    "PowerOutput__*",
                ],
                scale_factor=1.0,
            ),
        }
    )

    # Serialize and deserialize
    config_dict = config.model_dump()
    reconstructed = DatasetConfig(**config_dict)

    # Verify patterns preserved
    gen_def = reconstructed.get_dataset_config("generation")
    assert isinstance(gen_def, AggregateDataset)
    assert len(gen_def.patterns) == 3
    assert "ActivePowerVariable__*" in gen_def.patterns
    assert "ActivePowerOutVariable__*" in gen_def.patterns
    assert "PowerOutput__*" in gen_def.patterns


def test_scale_factor_preserved():
    """Test that custom scale_factor is preserved"""
    config = DatasetConfig(
        aggregates={
            "custom_scaled": AggregateDataset(
                patterns=["SomeVariable__*"],
                scale_factor=0.001,  # Custom scaling
            ),
        }
    )

    config_dict = config.model_dump()
    reconstructed = DatasetConfig(**config_dict)

    custom_def = reconstructed.get_dataset_config("custom_scaled")
    assert isinstance(custom_def, AggregateDataset)
    assert custom_def.scale_factor == 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
