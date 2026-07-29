"""
Example demonstrating unified dataset configuration in GAT.

This example shows how to:
1. Configure both raw and aggregate datasets in a unified way
2. Save dataset configurations to YAML (part of ScenarioConfig)
3. Use parser.get_dataset() for both raw and aggregate datasets seamlessly
4. Validate configurations against simulation data
"""

from pathlib import Path

from gat.models.base import AggregateDataset, DatasetConfig, RawDataset
from gat.models.scenario import ScenarioConfig
from gat.models.sienna import initialize_sienna_config
from gat.simulations.sienna import SiennaSimulationParser


def example_1_basic_unified_approach():
    """
    Example 1: Using unified dataset configuration
    """
    print("=" * 80)
    print("Example 1: Basic Unified Dataset Configuration")
    print("=" * 80)

    # Assume we have a Sienna simulation file
    sim_file = "path/to/simulation.h5"

    # Create parser
    parser = SiennaSimulationParser(sim_file)

    # Create unified dataset configuration
    dataset_config = DatasetConfig(
        dataset_configs={
            # Aggregate datasets - combine multiple raw datasets
            "generation": AggregateDataset(
                patterns=["ActivePowerVariable__*", "ActivePowerOutVariable__*"],
                scale_by_base_power=True,
            ),
            "flow": AggregateDataset(
                patterns=["FlowActivePowerVariable__Line"],
                scale_by_base_power=True,
            ),
            "load": AggregateDataset(
                patterns=["ActivePowerTimeSeriesParameter__StandardLoad"],
                scale_by_base_power=True,
            ),
            # Raw dataset - direct reference to a specific dataset
            "thermal_gen_1": RawDataset(
                h5_path="/simulation/decision_models/UC/variables/ActivePowerVariable__ThermalStandard_1",
                scale_by_base_power=True,
            ),
        }
    )

    # Set configuration on parser (validates automatically)
    parser.dataset_config = dataset_config

    # Now use get_dataset() for everything - both raw and aggregate!
    print("\nRetrieving datasets using unified get_dataset() method:")

    # Get aggregate dataset (combines multiple raw datasets)
    gen_df = parser.get_dataset("generation")
    if gen_df is not None:
        print(f"  generation: {gen_df.shape} (aggregate of multiple datasets)")

    # Get another aggregate dataset
    flow_df = parser.get_dataset("flow")
    if flow_df is not None:
        print(f"  flow: {flow_df.shape}")

    # Get raw dataset (single dataset, but same API!)
    thermal_df = parser.get_dataset("thermal_gen_1")
    if thermal_df is not None:
        print(f"  thermal_gen_1: {thermal_df.shape} (raw dataset)")

    # List all configured datasets
    print("\nConfigured datasets:")
    for name, desc in parser.list_datasets().items():
        print(f"  {name}: {desc}")


def example_2_scenario_config_with_datasets():
    """
    Example 2: Dataset configuration as part of ScenarioConfig (YAML)
    """
    print("\n" + "=" * 80)
    print("Example 2: Dataset Config in ScenarioConfig (YAML)")
    print("=" * 80)

    # Create a scenario configuration with dataset configs
    scenario_config = ScenarioConfig(
        model_type="Sienna",
        display_name="MyScenario",
        simulation_paths="path/to/simulation.h5",
        system_path="path/to/system.json",
        # Dataset configuration included in scenario config
        dataset_config=DatasetConfig(
            dataset_configs={
                "generation": AggregateDataset(
                    patterns=["ActivePowerVariable__*"],
                    scale_by_base_power=True,
                ),
                "thermal_generation": AggregateDataset(
                    patterns=["ActivePowerVariable__Thermal*"],
                    scale_by_base_power=True,
                ),
                "renewable_generation": AggregateDataset(
                    patterns=["ActivePowerVariable__Renewable*"],
                    scale_by_base_power=True,
                ),
                "flow": AggregateDataset(
                    patterns=["FlowActivePowerVariable__Line"],
                    scale_by_base_power=True,
                ),
                "load": AggregateDataset(
                    patterns=["ActivePowerTimeSeriesParameter__StandardLoad"],
                    scale_by_base_power=True,
                ),
            }
        ),
    )

    # Save to YAML - dataset configs are preserved!
    scenario_config.save("my_scenario.yaml")
    print("\nSaved scenario config to my_scenario.yaml")
    print("Dataset configurations are saved in YAML format!")

    # Example YAML output:
    print("\nYAML structure includes:")
    print("""
    dataset_config:
      dataset_configs:
        generation:
          patterns:
            - ActivePowerVariable__*
          scale_by_base_power: true
          scale_factor: 1.0
          combination_method: concat
        thermal_generation:
          patterns:
            - ActivePowerVariable__Thermal*
          scale_by_base_power: true
        ...
    """)


def example_3_loading_from_yaml():
    """
    Example 3: Load dataset configuration from YAML
    """
    print("\n" + "=" * 80)
    print("Example 3: Load Dataset Config from YAML")
    print("=" * 80)

    # Load scenario config from YAML
    from gat.models.scenario import load_config

    scenario_config = load_config("my_scenario.yaml")
    print(f"Loaded scenario: {scenario_config.display_name}")

    # Create parser and apply loaded dataset config
    parser = SiennaSimulationParser(scenario_config.simulation_paths)
    parser.dataset_config = scenario_config.dataset_config

    # Now use the configured datasets
    print("\nConfigured datasets from YAML:")
    for name in scenario_config.dataset_config.list_dataset_names():
        print(f"  - {name}")

    # Retrieve data using names from YAML config
    gen_df = parser.get_dataset("generation")
    thermal_df = parser.get_dataset("thermal_generation")
    print(
        f"\nRetrieved generation data: {gen_df.shape if gen_df is not None else 'N/A'}"
    )
    print(
        f"Retrieved thermal generation data: {thermal_df.shape if thermal_df is not None else 'N/A'}"
    )


def example_4_custom_combinations():
    """
    Example 4: Custom dataset combinations
    """
    print("\n" + "=" * 80)
    print("Example 4: Custom Dataset Combinations")
    print("=" * 80)

    dataset_config = DatasetConfig(
        dataset_configs={
            # Sum total generation across all generators
            "total_generation": AggregateDataset(
                patterns=["ActivePowerVariable__*"],
                scale_by_base_power=True,
                combination_method="sum",  # Sum instead of concat!
            ),
            # Concatenate for detailed view
            "generation_by_unit": AggregateDataset(
                patterns=["ActivePowerVariable__*"],
                scale_by_base_power=True,
                combination_method="concat",  # Keep separate columns (default)
            ),
            # Storage net flow (custom scaling)
            "storage_discharge": AggregateDataset(
                patterns=["ActivePowerOutVariable__*Storage*"],
                scale_by_base_power=True,
            ),
            "storage_charge": AggregateDataset(
                patterns=["ActivePowerInVariable__*Storage*"],
                scale_by_base_power=True,
            ),
        }
    )

    parser = SiennaSimulationParser("path/to/simulation.h5")
    parser.dataset_config = dataset_config

    # Get total generation as a single time series
    total_gen = parser.get_dataset("total_generation")
    if total_gen is not None:
        print(f"Total generation shape: {total_gen.shape} (single column)")

    # Get generation by unit as separate columns
    gen_by_unit = parser.get_dataset("generation_by_unit")
    if gen_by_unit is not None:
        print(f"Generation by unit shape: {gen_by_unit.shape} (multiple columns)")

    # Calculate storage net flow
    discharge = parser.get_dataset("storage_discharge")
    charge = parser.get_dataset("storage_charge")
    if discharge is not None and charge is not None:
        net_storage = discharge - charge
        print(f"Storage net flow calculated: {net_storage.shape}")


def example_5_mixing_raw_and_aggregate():
    """
    Example 5: Mix raw and aggregate datasets in same configuration
    """
    print("\n" + "=" * 80)
    print("Example 5: Mixing Raw and Aggregate Datasets")
    print("=" * 80)

    dataset_config = DatasetConfig(
        dataset_configs={
            # Aggregate dataset for all generation
            "all_generation": AggregateDataset(
                patterns=["ActivePowerVariable__*"],
                scale_by_base_power=True,
            ),
            # Specific raw datasets for key units
            "nuke_plant_1": RawDataset(
                h5_path="/simulation/decision_models/UC/variables/ActivePowerVariable__Nuclear_1",
                scale_by_base_power=True,
            ),
            "wind_farm_1": RawDataset(
                h5_path="/simulation/decision_models/UC/variables/ActivePowerVariable__Wind_1",
                scale_by_base_power=True,
            ),
            # Aggregate for all wind
            "all_wind": AggregateDataset(
                patterns=["ActivePowerVariable__Wind*"],
                scale_by_base_power=True,
            ),
        }
    )

    parser = SiennaSimulationParser("path/to/simulation.h5")
    parser.dataset_config = dataset_config

    print("\nSame API for both raw and aggregate datasets:")

    # All use the same get_dataset() method!
    all_gen = parser.get_dataset("all_generation")  # Aggregate
    nuke = parser.get_dataset("nuke_plant_1")  # Raw
    wind1 = parser.get_dataset("wind_farm_1")  # Raw
    all_wind = parser.get_dataset("all_wind")  # Aggregate

    print(f"  all_generation (aggregate): {all_gen.shape if all_gen else 'N/A'}")
    print(f"  nuke_plant_1 (raw): {nuke.shape if nuke else 'N/A'}")
    print(f"  wind_farm_1 (raw): {wind1.shape if wind1 else 'N/A'}")
    print(f"  all_wind (aggregate): {all_wind.shape if all_wind else 'N/A'}")


def example_6_default_sienna_config():
    """
    Example 6: Use default Sienna configuration
    """
    print("\n" + "=" * 80)
    print("Example 6: Default Sienna Configuration")
    print("=" * 80)

    # Initialize with default Sienna dataset configs
    sienna_config = initialize_sienna_config("4.0.0")

    parser = SiennaSimulationParser("path/to/simulation.h5")
    parser.dataset_config = sienna_config

    print("\nDefault Sienna datasets available:")
    for name in sienna_config.list_dataset_names():
        print(f"  - {name}")

    # Use standard dataset names
    gen_df = parser.get_dataset("generation")
    flow_df = parser.get_dataset("flow")
    load_df = parser.get_dataset("load")
    cost_df = parser.get_dataset("cost")

    print("\nAll standard Sienna datasets accessible via get_dataset()!")


def example_7_validation():
    """
    Example 7: Validation of dataset configurations
    """
    print("\n" + "=" * 80)
    print("Example 7: Dataset Configuration Validation")
    print("=" * 80)

    parser = SiennaSimulationParser("path/to/simulation.h5")

    # Get available raw datasets
    raw_datasets = list(parser.list_raw_datasets().keys())
    print(f"\nFound {len(raw_datasets)} raw datasets in simulation")
    print("First 5 raw datasets:")
    for ds in raw_datasets[:5]:
        print(f"  - {ds}")

    # Create configuration
    dataset_config = DatasetConfig(
        dataset_configs={
            "generation": AggregateDataset(
                patterns=["ActivePowerVariable__*"],
                scale_by_base_power=True,
            ),
            "flow": AggregateDataset(
                patterns=["FlowActivePowerVariable__Line"],
                scale_by_base_power=True,
            ),
        }
    )

    # Validation happens automatically when setting config
    try:
        parser.dataset_config = dataset_config
        print("\n✓ Validation passed!")
    except ValueError as e:
        print(f"\n✗ Validation failed: {e}")

    # Manual validation
    print("\nManual validation results:")
    results = dataset_config.validate_datasets(raw_datasets)
    for name, matches in results.items():
        print(f"  {name}: {len(matches)} datasets matched")
        for match in matches[:3]:  # Show first 3
            print(f"    - {match}")


def example_8_fallback_to_raw():
    """
    Example 8: Fallback to raw datasets when no config is set
    """
    print("\n" + "=" * 80)
    print("Example 8: Fallback to Raw Datasets")
    print("=" * 80)

    parser = SiennaSimulationParser("path/to/simulation.h5")

    # Without setting dataset_config, can still access raw datasets
    print("\nWithout dataset_config, get_dataset() falls back to raw datasets:")

    # This will retrieve the raw dataset directly
    raw_df = parser.get_dataset("ActivePowerVariable__ThermalStandard")
    if raw_df is not None:
        print(f"  Retrieved raw dataset: {raw_df.shape}")

    # list_datasets() shows raw datasets
    print("\nlist_datasets() returns raw datasets:")
    raw_list = parser.list_datasets()
    for name in list(raw_list.keys())[:5]:
        print(f"  - {name}")

    # But with dataset_config, we get configured view
    print("\nWith dataset_config, get_dataset() uses configured datasets:")
    parser.dataset_config = initialize_sienna_config("4.0.0")

    # Now this uses the configuration
    gen_df = parser.get_dataset("generation")
    if gen_df is not None:
        print(f"  Retrieved configured dataset 'generation': {gen_df.shape}")

    # list_datasets() shows configured datasets
    print("\nlist_datasets() returns configured datasets:")
    for name, desc in parser.list_datasets().items():
        print(f"  - {name}: {desc}")


if __name__ == "__main__":
    print("\n")
    print("*" * 80)
    print("GAT Unified Dataset Configuration Examples")
    print("*" * 80)

    # Note: These examples assume you have a valid Sienna simulation file
    # Replace "path/to/simulation.h5" with an actual file path

    try:
        # Uncomment the examples you want to run:

        # example_1_basic_unified_approach()
        # example_2_scenario_config_with_datasets()
        # example_3_loading_from_yaml()
        # example_4_custom_combinations()
        # example_5_mixing_raw_and_aggregate()
        example_6_default_sienna_config()
        # example_7_validation()
        # example_8_fallback_to_raw()

        print("\n" + "=" * 80)
        print("Examples completed!")
        print("=" * 80 + "\n")

    except FileNotFoundError:
        print("\nNote: These examples require a valid Sienna simulation file.")
        print("Please update the 'sim_file' path in the examples.")
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback

        traceback.print_exc()
