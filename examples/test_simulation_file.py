#!/usr/bin/env python
"""
Quick test script for exploring a single simulation file.

Usage:
    python examples/test_simulation_file.py <path_to_simulation.h5>

    # With specific model
    python examples/test_simulation_file.py <path_to_simulation.h5> --model UC

    # Load specific datasets
    python examples/test_simulation_file.py <path_to_simulation.h5> --datasets dispatch commit

Example:
    python examples/test_simulation_file.py results/simulation_1.h5
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from gat.simulations import SiennaSimulationParser


def explore_file(file_path: str, model_name: str = None, dataset_keys: list = None):
    """
    Load and explore a simulation file.

    Args:
        file_path: Path to simulation file
        model_name: Optional specific model to test
        dataset_keys: Optional list of specific datasets to load
    """
    print("\n" + "=" * 70)
    print(f"Testing Simulation File: {file_path}")
    print("=" * 70)

    # Check file exists
    if not Path(file_path).exists():
        print(f"❌ Error: File not found: {file_path}")
        return False

    try:
        # Load the file
        print("\n📂 Loading file...")
        parser = SiennaSimulationParser(file_path)
        print("✅ File loaded successfully")

        # Show available models
        models = parser.simulation_models
        print(f"\n🔧 Available models ({len(models)}):")
        for i, model in enumerate(models, 1):
            print(f"  {i}. {model}")

        # Determine which models to test
        if model_name:
            if model_name not in models:
                print(f"\n❌ Error: Model '{model_name}' not found")
                print(f"   Available: {', '.join(models)}")
                return False
            test_models = [model_name]
        else:
            test_models = models

        # Test each model
        for model in test_models:
            print(f"\n{'=' * 70}")
            print(f"📊 Testing Model: {model}")
            print("=" * 70)

            parser.selected_model = model

            # List datasets
            datasets = parser.list_datasets()
            print(f"\n📋 Found {len(datasets)} datasets")

            if not datasets:
                print("   No datasets found in this model")
                continue

            # Show sample of datasets
            print("\n   Sample datasets (showing first 15):")
            for i, name in enumerate(list(datasets.keys())[:15], 1):
                print(f"   {i:2d}. {name}")

            if len(datasets) > 15:
                print(f"   ... and {len(datasets) - 15} more")

            # Load specific datasets if requested
            if dataset_keys:
                print(f"\n📦 Loading requested datasets...")
                for key in dataset_keys:
                    # Try to find matching datasets
                    matches = [k for k in datasets.keys() if key.lower() in k.lower()]

                    if not matches:
                        print(f"   ⚠️  No datasets matching '{key}'")
                        continue

                    for match in matches[:3]:  # Load up to 3 matches
                        try:
                            df = parser.get_dataset(match)
                            print(f"\n   ✅ {match}")
                            print(f"      Shape: {df.shape}")
                            print(
                                f"      Time range: {df.index.min()} to {df.index.max()}"
                            )
                            print(f"      Columns: {len(df.columns)}")
                            if len(df.columns) > 0:
                                print(f"      Sample columns: {list(df.columns[:5])}")
                        except Exception as e:
                            print(f"   ❌ Error loading {match}: {e}")

            else:
                # Just load first dataset as a test
                first_key = list(datasets.keys())[0]
                print(f"\n🔍 Test loading first dataset: {first_key}")
                try:
                    df = parser.get_dataset(first_key)
                    print(f"   ✅ Successfully loaded")
                    print(f"   Shape: {df.shape}")
                    print(f"   Time range: {df.index.min()} to {df.index.max()}")
                    print(f"   Columns: {len(df.columns)}")
                    if len(df.columns) > 0:
                        print(f"   Sample columns: {list(df.columns[:5])}")

                    # Show basic statistics
                    print(f"\n   📈 Basic Statistics:")
                    print(f"   Mean: {df.mean().mean():.2f}")
                    print(f"   Max: {df.max().max():.2f}")
                    print(f"   Min: {df.min().min():.2f}")

                except Exception as e:
                    print(f"   ❌ Error loading: {e}")

        # Show metadata if available
        print(f"\n{'=' * 70}")
        print("ℹ️  Metadata")
        print("=" * 70)
        try:
            metadata = parser.get_metadata()
            if metadata:
                for key, value in metadata.items():
                    print(f"   {key}: {value}")
            else:
                print("   No metadata available")
        except Exception as e:
            print(f"   Error getting metadata: {e}")

        # Validate file
        print(f"\n{'=' * 70}")
        print("✓ Validation")
        print("=" * 70)
        try:
            warnings = parser.validate()
            if warnings:
                print(f"   ⚠️  Found {len(warnings)} warnings:")
                for warning in warnings:
                    print(f"   - {warning}")
            else:
                print("   ✅ No validation issues found")
        except Exception as e:
            print(f"   Error during validation: {e}")

        print("\n" + "=" * 70)
        print("✅ Test Complete")
        print("=" * 70)
        return True

    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.exception("Full error:")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test and explore a GAT simulation file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic exploration
  python test_simulation_file.py simulation.h5

  # Test specific model
  python test_simulation_file.py simulation.h5 --model UC

  # Load specific datasets
  python test_simulation_file.py simulation.h5 --datasets dispatch commit power

  # Combine options
  python test_simulation_file.py simulation.h5 --model ED --datasets thermal renewable
        """,
    )

    parser.add_argument(
        "file_path", help="Path to simulation file (e.g., simulation.h5)"
    )

    parser.add_argument(
        "--model", "-m", help="Specific model to test (e.g., UC, ED, emulation_model)"
    )

    parser.add_argument(
        "--datasets",
        "-d",
        nargs="+",
        help="Specific datasets to load (will match partial names)",
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Reduce logging output"
    )

    args = parser.parse_args()

    # Configure logging
    if args.quiet:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")

    # Run exploration
    success = explore_file(
        args.file_path, model_name=args.model, dataset_keys=args.datasets
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
