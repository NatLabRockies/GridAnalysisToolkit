#!/usr/bin/env python
"""
Example: Working with Dataset Configurations and Base Power Multiplication

This script demonstrates:
1. Auto-discovering datasets with their base_power flags
2. Viewing which datasets will have base_power applied
3. Customizing dataset configurations
4. Setting custom multipliers for specific datasets

Usage:
    python examples/dataset_base_power_example.py <path_to_simulation.h5>
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from gat.simulations import SiennaSimulationParser
from gat.simulations.sienna import SiennaSimulationDataset


def example_1_discover_datasets(file_path: str):
    """Example 1: Discover datasets and see base_power flags."""
    print("\n" + "=" * 70)
    print("Example 1: Auto-Discovering Dataset Configurations")
    print("=" * 70)

    parser = SiennaSimulationParser(file_path)

    # Select a simulation
    if parser.simulation_models:
        parser.simulation = parser.simulation_models[0]
        print(f"\nUsing simulation: {parser.simulation}")

    # Discover datasets
    print("\nDiscovering datasets...")
    dataset_configs = parser.discover_datasets()

    # Show which datasets have base_power flagged
    power_datasets = [c for c in dataset_configs if c.apply_base_power]
    other_datasets = [c for c in dataset_configs if not c.apply_base_power]

    print(f"\n✓ Found {len(dataset_configs)} total datasets")
    print(f"\nDatasets WITH base_power multiplication ({len(power_datasets)}):")
    for config in power_datasets[:10]:  # Show first 10
        print(f"  ✓ {config.name}")
    if len(power_datasets) > 10:
        print(f"  ... and {len(power_datasets) - 10} more")

    print(f"\nDatasets WITHOUT base_power multiplication ({len(other_datasets)}):")
    for config in other_datasets[:10]:  # Show first 10
        print(f"  - {config.name}")
    if len(other_datasets) > 10:
        print(f"  ... and {len(other_datasets) - 10} more")


def example_2_custom_configurations(file_path: str):
    """Example 2: Create custom dataset configurations."""
    print("\n" + "=" * 70)
    print("Example 2: Custom Dataset Configurations")
    print("=" * 70)

    parser = SiennaSimulationParser(file_path)

    if parser.simulation_models:
        parser.simulation = parser.simulation_models[0]
        print(f"\nUsing simulation: {parser.simulation}")

    # Discover datasets
    dataset_configs = parser.discover_datasets()

    print("\nModifying configurations...")

    # Example customizations:
    modified_configs = []
    for config in dataset_configs:
        # 1. Add a dataset that wasn't auto-detected
        if "Voltage" in config.name:
            config.apply_base_power = True
            print(f"  ✓ Enabled base_power for: {config.name}")

        # 2. Remove a dataset that was auto-detected
        if (
            config.name
            == "ActivePowerReserveVariable__VariableReserve__ReserveUp__Spin_Up_R2"
        ):
            config.apply_base_power = False
            print(f"  - Disabled base_power for: {config.name}")

        # 3. Add a custom multiplier
        if "ThermalStandard" in config.name and config.apply_base_power:
            config.custom_multiplier = 125.0  # Override base_power
            print(f"  ⚙ Custom multiplier (125.0) for: {config.name}")

        modified_configs.append(config)

    # Apply the custom configurations
    parser.set_dataset_configs(modified_configs)
    print(f"\n✓ Applied {len(modified_configs)} custom configurations")


def example_3_test_multiplication(file_path: str):
    """Example 3: Test base_power multiplication on actual data."""
    print("\n" + "=" * 70)
    print("Example 3: Testing Base Power Multiplication")
    print("=" * 70)

    parser = SiennaSimulationParser(file_path)

    if parser.simulation_models:
        parser.simulation = parser.simulation_models[0]
        print(f"\nUsing simulation: {parser.simulation}")

    # Get a power dataset
    datasets = parser.list_datasets()
    power_datasets = [name for name in datasets.keys() if "Power" in name]

    if not power_datasets:
        print("\n⚠️  No power datasets found")
        return

    test_dataset = power_datasets[0]
    print(f"\nTesting with dataset: {test_dataset}")

    # Check the base_power value
    base_power = parser._selected_model.base_power if parser._selected_model else 100
    print(f"Base power: {base_power} MW")

    # Load the dataset (with automatic base_power multiplication)
    print("\nLoading data with base_power multiplication...")
    data = parser.get_dataset(test_dataset)

    if data is not None:
        print(f"\n✓ Data loaded successfully")
        print(f"  Shape: {data.shape}")
        print(f"  Time range: {data.index.min()} to {data.index.max()}")
        print(f"\n  Statistics (in MW, after base_power multiplication):")
        print(f"    Min:  {data.min().min():.2f} MW")
        print(f"    Mean: {data.mean().mean():.2f} MW")
        print(f"    Max:  {data.max().max():.2f} MW")

        # Show a sample of the data
        print(f"\n  Sample values (first 5 timestamps, first 3 components):")
        print(data.iloc[:5, :3])


def example_4_scenario_integration(file_path: str):
    """Example 4: Using dataset configs with scenario configurations."""
    print("\n" + "=" * 70)
    print("Example 4: Integration with Scenario Configurations")
    print("=" * 70)

    from gat.models.project import SiennaScenarioConfig

    print("\nCreating scenario configuration...")

    # Create a scenario config
    scenario = SiennaScenarioConfig(
        name="Example Scenario",
        system_path="/path/to/system.json",
        simulation_paths=file_path,
        simulation_type=None,  # Will use default
    )

    print(f"  Scenario: {scenario.name}")

    # Discover and set dataset configurations
    print("\nDiscovering datasets for scenario...")
    scenario.discover_and_set_dataset_configs()

    # Check what was saved
    dataset_configs = scenario.get_dataset_configs()
    power_datasets = [c for c in dataset_configs if c.apply_base_power]

    print(f"\n✓ Discovered {len(dataset_configs)} datasets")
    print(f"  {len(power_datasets)} flagged for base_power multiplication")

    # Show how it would be saved to YAML
    print("\nDataset configurations in YAML format:")
    print("  dataset_configs:")
    for config in dataset_configs[:3]:
        print(f"    - name: {config.name}")
        print(f"      h5_path: {config.h5_path}")
        print(f"      apply_base_power: {config.apply_base_power}")
        if config.custom_multiplier:
            print(f"      custom_multiplier: {config.custom_multiplier}")
    print("    ...")


def example_5_compare_with_without(file_path: str):
    """Example 5: Compare data with and without base_power multiplication."""
    print("\n" + "=" * 70)
    print("Example 5: Comparing With/Without Base Power Multiplication")
    print("=" * 70)

    parser = SiennaSimulationParser(file_path)

    if parser.simulation_models:
        parser.simulation = parser.simulation_models[0]
        print(f"\nUsing simulation: {parser.simulation}")

    # Get a power dataset
    datasets = parser.list_datasets()
    power_datasets = [name for name in datasets.keys() if "Power" in name]

    if not power_datasets:
        print("\n⚠️  No power datasets found")
        return

    test_dataset = power_datasets[0]
    print(f"\nTesting with dataset: {test_dataset}")

    # Get base_power value
    base_power = parser._selected_model.base_power if parser._selected_model else 100
    print(f"Base power: {base_power} MW")

    # Load with base_power (default behavior)
    print("\n1. Loading WITH base_power multiplication...")
    data_with = parser.get_dataset(test_dataset)

    # Disable base_power for this dataset
    print("\n2. Disabling base_power for this dataset...")
    from gat.simulations.sienna import SiennaSimulationDataset

    custom_config = SiennaSimulationDataset(
        name=test_dataset.split("/")[-1],
        h5_path=test_dataset,
        apply_base_power=False,  # Disable
    )
    parser.set_dataset_configs([custom_config])

    # Load without base_power
    print("   Loading WITHOUT base_power multiplication...")
    data_without = parser.get_dataset(test_dataset)

    # Compare
    if data_with is not None and data_without is not None:
        print("\n✓ Comparison:")
        print(f"  WITH base_power:")
        print(f"    Mean: {data_with.mean().mean():.4f} MW")
        print(f"    Max:  {data_with.max().max():.4f} MW")

        print(f"\n  WITHOUT base_power (per-unit):")
        print(f"    Mean: {data_without.mean().mean():.4f} p.u.")
        print(f"    Max:  {data_without.max().max():.4f} p.u.")

        # Verify the relationship
        ratio = (
            (data_with.mean().mean() / data_without.mean().mean())
            if data_without.mean().mean() != 0
            else 0
        )
        print(f"\n  Ratio (should equal base_power): {ratio:.2f}")
        print(f"  Base power setting: {base_power}")
        print(f"  Match: {'✓' if abs(ratio - base_power) < 0.1 else '✗'}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Demonstrate dataset configuration and base_power multiplication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "file_path", help="Path to simulation file (e.g., simulation.h5)"
    )

    parser.add_argument(
        "--example",
        type=int,
        choices=[1, 2, 3, 4, 5],
        help="Run specific example (1-5). If not specified, runs all examples.",
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Reduce logging output"
    )

    args = parser.parse_args()

    # Configure logging
    if args.quiet:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")

    # Check file exists
    if not Path(args.file_path).exists():
        print(f"❌ Error: File not found: {args.file_path}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("Dataset Configuration and Base Power Multiplication Examples")
    print("=" * 70)
    print(f"\nFile: {args.file_path}")

    try:
        if args.example:
            # Run specific example
            examples = {
                1: example_1_discover_datasets,
                2: example_2_custom_configurations,
                3: example_3_test_multiplication,
                4: example_4_scenario_integration,
                5: example_5_compare_with_without,
            }
            examples[args.example](args.file_path)
        else:
            # Run all examples
            example_1_discover_datasets(args.file_path)
            example_2_custom_configurations(args.file_path)
            example_3_test_multiplication(args.file_path)
            example_4_scenario_integration(args.file_path)
            example_5_compare_with_without(args.file_path)

        print("\n" + "=" * 70)
        print("✅ Examples Complete")
        print("=" * 70)

        print("\n📚 Key Takeaways:")
        print(
            "  1. Datasets with 'Power' are auto-flagged for base_power multiplication"
        )
        print("  2. You can customize which datasets get multiplied")
        print("  3. Custom multipliers can override the base_power value")
        print("  4. Dataset configs can be saved to scenario YAML files")
        print(
            "  5. Use CLI: gat project scenario discover-datasets <scenario_id> --save"
        )

    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.exception("Example failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
