"""
Example demonstrating aggregate dataset functionality in GAT.

This example shows how to:
1. Configure aggregate datasets using the new pydantic models
2. Validate aggregate datasets against available raw datasets
3. Retrieve aggregate datasets from a simulation
4. Use both legacy path-based and new aggregate dataset approaches
"""

from pathlib import Path

from gat.models.base import AggregateDatasetConfig, DatasetConfig
from gat.models.sienna import initialize_sienna_config
from gat.simulations.sienna import SiennaSimulationParser


def example_basic_aggregate_dataset():
    """
    Example 1: Basic usage with pre-configured aggregate datasets
    """
    print("=" * 80)
    print("Example 1: Basic Aggregate Dataset Usage")
    print("=" * 80)

    # Assume we have a Sienna simulation file
    sim_file = "path/to/simulation.h5"

    # Create parser
    parser = SiennaSimulationParser(sim_file)

    # Initialize Sienna configuration with default aggregate datasets
    config = initialize_sienna_config(data_format_version="4.0.0")

    # Set the configuration on the parser
    # This will validate aggregate datasets against available raw datasets
    parser.dataset_config = config

    # List available aggregate datasets
    print("\nAvailable aggregate datasets:")
    for name in parser.list_aggregate_datasets():
        print(f"  - {name}")

    # Retrieve an aggregate dataset by name
    print("\nRetrieving 'generation' aggregate dataset...")
    generation_df = parser.get_aggregate_dataset_by_name("generation")

    if generation_df is not None:
        print(f"Shape: {generation_df.shape}")
        print(f"Columns: {list(generation_df.columns)[:5]}...")  # First 5 columns
        print(f"Date range: {generation_df.index[0]} to {generation_df.index[-1]}")

    # Retrieve flow data
    print("\nRetrieving 'flow' aggregate dataset...")
    flow_df = parser.get_aggregate_dataset_by_name("flow")

    if flow_df is not None:
        print(f"Shape: {flow_df.shape}")


def example_custom_aggregate_dataset():
    """
    Example 2: Creating custom aggregate datasets
    """
    print("\n" + "=" * 80)
    print("Example 2: Custom Aggregate Dataset Configuration")
    print("=" * 80)

    sim_file = "path/to/simulation.h5"
    parser = SiennaSimulationParser(sim_file)

    # Create a custom configuration with specific aggregate datasets
    custom_config = DatasetConfig(
        aggregate_datasets=[
            AggregateDatasetConfig(
                name="thermal_generation",
                patterns=[
                    "ActivePowerVariable__ThermalStandard",
                    "ActivePowerVariable__ThermalMultiStart",
                ],
                scale_by_base_power=True,
            ),
            AggregateDatasetConfig(
                name="renewable_generation",
                patterns=[
                    "ActivePowerVariable__RenewableDispatch",
                    "ActivePowerVariable__RenewableNonDispatch",
                ],
                scale_by_base_power=True,
            ),
            AggregateDatasetConfig(
                name="storage",
                patterns=[
                    "ActivePowerOutVariable__*Storage*",
                    "ActivePowerInVariable__*Storage*",
                ],
                scale_by_base_power=True,
            ),
            AggregateDatasetConfig(
                name="all_power_variables",
                patterns=["*PowerVariable__*"],
                scale_by_base_power=True,
            ),
        ]
    )

    # Set configuration (will validate)
    try:
        parser.dataset_config = custom_config
        print("\nCustom aggregate datasets configured successfully!")

        print("\nAvailable aggregate datasets:")
        for name in parser.list_aggregate_datasets():
            print(f"  - {name}")

        # Retrieve thermal generation
        thermal_df = parser.get_aggregate_dataset_by_name("thermal_generation")
        if thermal_df is not None:
            print(f"\nThermal generation shape: {thermal_df.shape}")

        # Retrieve renewable generation
        renewable_df = parser.get_aggregate_dataset_by_name("renewable_generation")
        if renewable_df is not None:
            print(f"Renewable generation shape: {renewable_df.shape}")

    except ValueError as e:
        print(f"\nValidation failed: {e}")


def example_pattern_matching():
    """
    Example 3: Using pattern matching directly
    """
    print("\n" + "=" * 80)
    print("Example 3: Direct Pattern Matching")
    print("=" * 80)

    sim_file = "path/to/simulation.h5"
    parser = SiennaSimulationParser(sim_file)

    # Match datasets using glob patterns
    print("\nMatching datasets with pattern 'ActivePowerVariable__*':")
    matches = parser.match_datasets_by_patterns(["ActivePowerVariable__*"])
    for match in matches[:5]:  # Show first 5
        print(f"  - {match}")
    print(f"  ... ({len(matches)} total matches)")

    # Retrieve aggregate data directly with patterns
    print("\nRetrieving data directly with patterns...")
    df = parser.get_aggregate_dataset(
        patterns=["ActivePowerVariable__Thermal*"], scale_by_base_power=True
    )

    if df is not None:
        print(f"Shape: {df.shape}")


def example_validation():
    """
    Example 4: Dataset validation
    """
    print("\n" + "=" * 80)
    print("Example 4: Aggregate Dataset Validation")
    print("=" * 80)

    sim_file = "path/to/simulation.h5"
    parser = SiennaSimulationParser(sim_file)

    # Get list of available raw datasets
    raw_datasets = list(parser.list_datasets().keys())
    print(f"\nFound {len(raw_datasets)} raw datasets in simulation")
    print("First 5 raw datasets:")
    for ds in raw_datasets[:5]:
        print(f"  - {ds}")

    # Create configuration with validation
    config = DatasetConfig(
        aggregate_datasets=[
            AggregateDatasetConfig(
                name="generation",
                patterns=["ActivePowerVariable__*"],
                scale_by_base_power=True,
            ),
            AggregateDatasetConfig(
                name="flow",
                patterns=["FlowActivePowerVariable__Line"],
                scale_by_base_power=True,
            ),
        ]
    )

    # Validate without setting on parser
    print("\nValidating aggregate datasets...")
    try:
        validation_results = config.validate_aggregate_datasets(raw_datasets)
        print("Validation successful!")
        for agg_name, matched_datasets in validation_results.items():
            print(f"\n  {agg_name}:")
            print(f"    Matched {len(matched_datasets)} datasets")
            for ds in matched_datasets[:3]:  # Show first 3
                print(f"      - {ds}")
            if len(matched_datasets) > 3:
                print(f"      ... and {len(matched_datasets) - 3} more")

    except ValueError as e:
        print(f"Validation failed: {e}")


def example_legacy_vs_new():
    """
    Example 5: Comparing legacy path-based and new aggregate dataset approaches
    """
    print("\n" + "=" * 80)
    print("Example 5: Legacy vs New Approach")
    print("=" * 80)

    # Initialize with both legacy and new configurations
    config = initialize_sienna_config(data_format_version="4.0.0")

    # Show that both approaches are available
    print("\nLegacy path-based configuration:")
    print(f"  generation_paths: {config.generation_paths}")
    print(f"  flow_paths: {config.flow_paths}")

    print("\nNew aggregate dataset configuration:")
    gen_agg = config.get_aggregate_dataset("generation")
    if gen_agg:
        print(
            f"  generation: patterns={gen_agg.patterns}, "
            f"scale={gen_agg.scale_by_base_power}"
        )

    flow_agg = config.get_aggregate_dataset("flow")
    if flow_agg:
        print(
            f"  flow: patterns={flow_agg.patterns}, "
            f"scale={flow_agg.scale_by_base_power}"
        )

    print("\nBoth approaches are supported for backward compatibility!")
    print("New code should prefer aggregate_datasets for better flexibility.")


def example_multi_model_simulation():
    """
    Example 6: Working with multiple simulation models
    """
    print("\n" + "=" * 80)
    print("Example 6: Multi-Model Simulation")
    print("=" * 80)

    sim_file = "path/to/simulation.h5"
    parser = SiennaSimulationParser(sim_file)

    # List available simulation models
    print("\nAvailable simulation models:")
    for model in parser.simulation_models:
        print(f"  - {model}")

    # Set configuration
    config = initialize_sienna_config(data_format_version="4.0.0")
    parser.dataset_config = config

    # Select first decision model
    if parser.simulation_models:
        first_model = parser.simulation_models[0]
        parser.selected_model = first_model
        print(f"\nSelected model: {first_model}")
        print(f"Base power: {parser.base_power} MW")

        # Retrieve aggregate dataset for this model
        gen_df = parser.get_aggregate_dataset_by_name("generation")
        if gen_df is not None:
            print(f"Generation data shape: {gen_df.shape}")
            print(
                f"Values are automatically scaled by base_power ({parser.base_power} MW)"
            )


if __name__ == "__main__":
    print("\n")
    print("*" * 80)
    print("GAT Aggregate Dataset Examples")
    print("*" * 80)

    # Note: These examples assume you have a valid Sienna simulation file
    # Replace "path/to/simulation.h5" with an actual file path

    try:
        # Uncomment the examples you want to run:

        # example_basic_aggregate_dataset()
        # example_custom_aggregate_dataset()
        # example_pattern_matching()
        # example_validation()
        example_legacy_vs_new()
        # example_multi_model_simulation()

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
