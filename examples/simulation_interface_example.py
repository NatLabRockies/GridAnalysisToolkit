"""
GAT Simulation Interface Examples
==================================

This script demonstrates the new unified simulation interface and
automatic multi-file aggregation capabilities.

Key Features Shown:
-------------------
1. Single file parsing
2. Multi-file aggregation with parallel loading
3. Dataset discovery and retrieval
4. Model selection
5. Merge strategy control
6. System dataset interface

Run this example:
    python examples/simulation_interface_example.py
"""

from pathlib import Path

import pandas as pd
from loguru import logger

# Import system interfaces
from gat.datahelpers import SiennaSystem

# Import simulation interfaces
from gat.simulations import (
    BaseSimulationParser,
    SiennaSimulationParser,
    SimulationAggregator,
)


def example_1_single_file():
    """Example 1: Working with a single simulation file."""
    print("\n" + "=" * 70)
    print("Example 1: Single File Parser")
    print("=" * 70)

    # Create parser for single file
    parser = SiennaSimulationParser("path/to/simulation.h5")

    # Discover available models
    models = parser.simulation_models
    print(f"\nAvailable models: {models}")

    # Select a model (if multiple exist)
    if len(models) > 1:
        parser.selected_model = models[0]
        print(f"Selected model: {parser.selected_model}")

    # List available datasets
    datasets = parser.list_datasets()
    print(f"\nAvailable datasets ({len(datasets)}):")
    for name, path in list(datasets.items())[:5]:
        print(f"  - {name}: {path}")

    # Get a specific dataset
    if "ActivePowerVariable__ThermalStandard" in datasets:
        data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
        print(f"\nDataset shape: {data.shape}")
        print(f"Date range: {data.index.min()} to {data.index.max()}")
        print(f"Columns: {list(data.columns[:5])}")


def example_2_multi_file_sequential():
    """Example 2: Aggregating multiple files sequentially."""
    print("\n" + "=" * 70)
    print("Example 2: Multi-File Aggregation (Sequential)")
    print("=" * 70)

    # List of simulation files (e.g., from multi-day simulation)
    file_paths = [
        "path/to/day_1.h5",
        "path/to/day_2.h5",
        "path/to/day_3.h5",
    ]

    # Create aggregator - loads files sequentially
    aggregator = SimulationAggregator(
        file_paths=file_paths,
        parser_class=SiennaSimulationParser,
        parallel=False,  # Sequential loading
    )

    print(f"\nLoaded {len(aggregator.parsers)} files")

    # Same interface as single parser!
    models = aggregator.simulation_models
    print(f"Common models across files: {models}")

    # Set model for all parsers
    aggregator.selected_model = models[0]

    # Get combined dataset
    datasets = aggregator.list_datasets()
    print(f"\nDatasets available: {len(datasets)}")

    # Get data - automatically combined across all files
    if datasets:
        first_key = list(datasets.keys())[0]
        combined_data = aggregator.get_dataset(first_key)
        print(f"\nCombined dataset '{first_key}':")
        print(f"  Shape: {combined_data.shape}")
        print(
            f"  Date range: {combined_data.index.min()} to {combined_data.index.max()}"
        )


def example_3_multi_file_parallel():
    """Example 3: Parallel loading for faster performance."""
    print("\n" + "=" * 70)
    print("Example 3: Multi-File Aggregation (Parallel)")
    print("=" * 70)

    # Larger set of files
    file_paths = [f"path/to/hour_{i:03d}.h5" for i in range(24)]

    # Create aggregator with parallel loading
    aggregator = SimulationAggregator(
        file_paths=file_paths,
        parser_class=SiennaSimulationParser,
        parallel=True,  # Enable parallel loading
        max_workers=4,  # Use 4 processes
    )

    print(f"\nLoaded {len(aggregator.parsers)} files in parallel")

    # Set model and get data
    aggregator.selected_model = "UC"
    datasets = aggregator.list_datasets()

    if "generator_commit" in datasets:
        data = aggregator.get_dataset("generator_commit")
        print(f"\nCombined commitment data:")
        print(f"  Files: {len(file_paths)}")
        print(f"  Total hours: {len(data)}")
        print(f"  Generators: {len(data.columns)}")


def example_4_merge_strategies():
    """Example 4: Controlling overlap handling with merge strategies."""
    print("\n" + "=" * 70)
    print("Example 4: Merge Strategies for Overlapping Time Periods")
    print("=" * 70)

    file_paths = ["path/to/forecast_1.h5", "path/to/forecast_2.h5"]

    aggregator = SimulationAggregator(
        file_paths=file_paths,
        parser_class=SiennaSimulationParser,
        parallel=True,
    )

    aggregator.selected_model = "ED"

    # Strategy 1: "left" - keep earlier timestamps, remove future overlap
    # Typical for multi-stage simulations where earlier data is "realized"
    data_left = aggregator.get_dataset("generator_dispatch", merge_strategy="left")

    print("\nMerge strategy: 'left' (keep earlier timestamps)")
    print(f"  Shape: {data_left.shape}")
    print(f"  Range: {data_left.index.min()} to {data_left.index.max()}")

    # Strategy 2: "right" - keep later timestamps, remove previous overlap
    # Typical for rolling forecasts where later data is more accurate
    data_right = aggregator.get_dataset("generator_dispatch", merge_strategy="right")

    print("\nMerge strategy: 'right' (keep later timestamps)")
    print(f"  Shape: {data_right.shape}")
    print(f"  Range: {data_right.index.min()} to {data_right.index.max()}")


def example_5_multiple_datasets():
    """Example 5: Retrieving multiple datasets efficiently."""
    print("\n" + "=" * 70)
    print("Example 5: Multiple Dataset Retrieval")
    print("=" * 70)

    parser = SiennaSimulationParser("path/to/simulation.h5")
    parser.selected_model = "UC"

    # Get multiple datasets at once
    datasets = parser.get_datasets(
        "generator_dispatch",
        "generator_commit",
        "curtailment",
    )

    print(f"\nRetrieved {len(datasets)} datasets:")
    for name, data in datasets.items():
        print(f"  - {name}: {data.shape}")


def example_6_system_interface():
    """Example 6: Using the unified system dataset interface."""
    print("\n" + "=" * 70)
    print("Example 6: System Dataset Interface")
    print("=" * 70)

    # Load system
    system = SiennaSystem("path/to/system.json")

    # New unified interface - list available datasets
    datasets = system.list_datasets()
    print(f"\nAvailable system datasets:")
    for name, type_ in datasets.items():
        print(f"  - {name}: {type_}")

    # Get single dataset
    generators = system.get_dataset("generators")
    print(f"\nGenerator data:")
    print(f"  Count: {len(generators)}")
    print(f"  Columns: {list(generators.columns)}")

    # Get filtered dataset
    solar_gens = system.get_dataset("generators", category="Solar_PV")
    print(f"\nSolar PV generators: {len(solar_gens)}")

    # Get multiple datasets at once
    data = system.get_datasets("generators", "loads", "system_info")
    print(f"\nRetrieved {len(data)} datasets:")
    for name, df in data.items():
        print(f"  - {name}: {df.shape}")


def example_7_context_managers():
    """Example 7: Using context managers for automatic cleanup."""
    print("\n" + "=" * 70)
    print("Example 7: Context Managers (Automatic Cleanup)")
    print("=" * 70)

    # Single parser with context manager
    with SiennaSimulationParser("path/to/simulation.h5") as parser:
        parser.selected_model = "ED"
        data = parser.get_dataset("generator_dispatch")
        print(f"\nSingle file data shape: {data.shape}")
    # File handle automatically closed

    # Aggregator with context manager
    with SimulationAggregator(
        file_paths=["sim1.h5", "sim2.h5"],
        parser_class=SiennaSimulationParser,
        parallel=True,
    ) as aggregator:
        aggregator.selected_model = "UC"
        data = aggregator.get_dataset("generator_commit")
        print(f"Combined data shape: {data.shape}")
    # All parsers automatically closed


def example_8_custom_parser():
    """Example 8: Creating a custom parser (plugin development)."""
    print("\n" + "=" * 70)
    print("Example 8: Custom Parser Implementation")
    print("=" * 70)

    class CSVSimulationParser(BaseSimulationParser):
        """Simple CSV-based simulation parser."""

        def __init__(self, directory_path: str):
            super().__init__()
            self.directory = Path(directory_path)

            # Find all CSV files
            self.csv_files = {f.stem: f for f in self.directory.glob("*.csv")}

        @property
        def simulation_models(self) -> list[str]:
            return ["default"]

        def list_datasets(self) -> dict[str, str]:
            return {name: str(path) for name, path in self.csv_files.items()}

        def get_dataset(self, key: str) -> pd.DataFrame:
            if key not in self.csv_files:
                raise KeyError(f"Dataset '{key}' not found")

            df = pd.read_csv(self.csv_files[key], index_col=0, parse_dates=True)
            return df

    # Use custom parser with aggregator
    csv_parser = CSVSimulationParser("path/to/csv_results")
    datasets = csv_parser.list_datasets()
    print(f"\nCSV datasets found: {list(datasets.keys())}")

    # Works with generic aggregator!
    aggregator = SimulationAggregator(
        file_paths=["results_day1/", "results_day2/", "results_day3/"],
        parser_class=CSVSimulationParser,
        parallel=True,
    )
    print(f"Aggregated {len(aggregator.parsers)} CSV result directories")


def example_9_metadata_and_validation():
    """Example 9: Accessing metadata and validation."""
    print("\n" + "=" * 70)
    print("Example 9: Metadata and Validation")
    print("=" * 70)

    parser = SiennaSimulationParser("path/to/simulation.h5")

    # Get metadata
    metadata = parser.get_metadata()
    print("\nSimulation metadata:")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    # Validate file
    warnings = parser.validate()
    if warnings:
        print("\nValidation warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    else:
        print("\nNo validation issues found")

    # Aggregator metadata (from first file)
    aggregator = SimulationAggregator(
        file_paths=["sim1.h5", "sim2.h5"],
        parser_class=SiennaSimulationParser,
    )

    metadata = aggregator.get_metadata()
    print(f"\nAggregator metadata (from first file):")
    for key, value in metadata.items():
        print(f"  {key}: {value}")

    # Validate all files
    all_warnings = aggregator.validate()
    print(f"\nTotal warnings across all files: {len(all_warnings)}")


def main():
    """Run all examples."""
    logger.info("Starting GAT Simulation Interface Examples")

    try:
        # Note: These examples use placeholder paths
        # Replace with actual file paths to run

        print("\n" + "=" * 70)
        print("GAT SIMULATION INTERFACE EXAMPLES")
        print("=" * 70)
        print("\nNote: Update file paths in the examples to run with real data")

        # Uncomment to run individual examples:
        # example_1_single_file()
        # example_2_multi_file_sequential()
        # example_3_multi_file_parallel()
        # example_4_merge_strategies()
        # example_5_multiple_datasets()
        # example_6_system_interface()
        # example_7_context_managers()
        # example_8_custom_parser()
        # example_9_metadata_and_validation()

        print("\n" + "=" * 70)
        print("Examples complete!")
        print("=" * 70)

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    main()
