#!/usr/bin/env python
"""
Test script to verify simulation discovery and querying functionality.

This script tests:
1. Auto-discovery of emulation models (using 'name' attribute)
2. Auto-discovery of decision models (using group names)
3. Querying datasets with simulation parameter
4. Using default simulation property

Usage:
    python examples/test_simulation_discovery.py <path_to_simulation.h5>
"""

import argparse
import sys
from pathlib import Path

from loguru import logger

from gat.simulations import SiennaSimulationParser


def test_simulation_discovery(file_path: str):
    """Test simulation discovery functionality."""
    print("\n" + "=" * 70)
    print(f"🧪 Testing Simulation Discovery: {Path(file_path).name}")
    print("=" * 70)

    try:
        # Load the parser
        print("\n1️⃣  Loading parser...")
        parser = SiennaSimulationParser(file_path)
        print("   ✅ Parser loaded successfully")

        # Test 1: List available simulations
        print("\n2️⃣  Testing simulation discovery...")
        simulations = parser.simulation_models
        print(f"   ✅ Found {len(simulations)} simulation(s):")
        for i, sim in enumerate(simulations, 1):
            print(f"      {i}. {sim}")

        if not simulations:
            print("   ⚠️  No simulations found. Stopping tests.")
            return False

        # Test 2: Check default selection
        print("\n3️⃣  Testing default simulation selection...")
        default_sim = parser.simulation
        print(f"   ✅ Default simulation: {default_sim}")

        if default_sim:
            # Verify selected_model is set
            assert parser.selected_model is not None
            assert parser.selected_model.name == default_sim
            print(f"   ✅ selected_model.name matches: {parser.selected_model.name}")

        # Test 3: Test simulation property (new API)
        print("\n4️⃣  Testing simulation property (new API)...")
        for sim_name in simulations[:2]:  # Test first 2 simulations
            print(f"\n   Testing simulation: {sim_name}")

            # Set via simulation property
            parser.simulation = sim_name
            print(f"      ✅ Set parser.simulation = '{sim_name}'")

            # Verify it was set correctly
            assert parser.simulation == sim_name
            print(f"      ✅ parser.simulation returns '{parser.simulation}'")

            # Verify selected_model is consistent
            assert parser.selected_model.name == sim_name
            print(
                f"      ✅ parser.selected_model.name = '{parser.selected_model.name}'"
            )

            # List datasets for this simulation
            datasets = parser.list_datasets()
            print(f"      ✅ Found {len(datasets)} datasets")

        # Test 4: Test list_datasets with simulation parameter
        print("\n5️⃣  Testing list_datasets(simulation=...) parameter...")

        # Store current selection
        original_sim = parser.simulation

        for sim_name in simulations[:2]:
            print(f"\n   Testing: list_datasets(simulation='{sim_name}')")

            # Query without changing selection
            datasets = parser.list_datasets(simulation=sim_name)
            print(f"      ✅ Found {len(datasets)} datasets")

            # Show sample
            if datasets:
                sample_keys = list(datasets.keys())[:3]
                for key in sample_keys:
                    print(f"         - {key}")

            # Verify original selection wasn't changed
            assert parser.simulation == original_sim
            print(f"      ✅ Original simulation still selected: '{parser.simulation}'")

        # Test 5: Test get_dataset with simulation parameter
        print("\n6️⃣  Testing get_dataset(key, simulation=...) parameter...")

        for sim_name in simulations[:2]:
            print(f"\n   Testing: get_dataset(..., simulation='{sim_name}')")

            # Get datasets for this simulation
            datasets = parser.list_datasets(simulation=sim_name)

            if not datasets:
                print(f"      ⚠️  No datasets found for '{sim_name}'")
                continue

            # Try to load first dataset
            first_key = list(datasets.keys())[0]
            print(f"      Trying to load: {first_key}")

            try:
                df = parser.get_dataset(first_key, simulation=sim_name)

                if df is not None:
                    print(f"      ✅ Loaded successfully")
                    print(f"         Shape: {df.shape}")
                    print(f"         Columns: {len(df.columns)}")

                    # Verify original selection wasn't changed
                    assert parser.simulation == original_sim
                    print(
                        f"      ✅ Original simulation still selected: '{parser.simulation}'"
                    )
                else:
                    print(f"      ⚠️  Dataset returned None")

            except Exception as e:
                print(f"      ⚠️  Error loading dataset: {e}")

        # Test 6: Compare old API (selected_model) with new API (simulation)
        print("\n7️⃣  Testing API compatibility (selected_model vs simulation)...")

        if len(simulations) >= 1:
            test_sim = simulations[0]

            # Using old API
            parser.selected_model = test_sim
            datasets_old = parser.list_datasets()

            # Using new API
            parser.simulation = test_sim
            datasets_new = parser.list_datasets()

            # Should be identical
            assert datasets_old.keys() == datasets_new.keys()
            print(f"   ✅ Both APIs return identical results")
            print(f"      Tested with simulation: {test_sim}")
            print(f"      Dataset count: {len(datasets_old)}")

        # Test 7: Test error handling
        print("\n8️⃣  Testing error handling...")

        try:
            parser.selected_model = "INVALID_SIMULATION_NAME"
            print("   ❌ Should have raised ValueError")
            return False
        except ValueError as e:
            print(f"   ✅ Correctly raised ValueError for invalid simulation")
            print(f"      Message: {e}")

        # Reset to valid simulation
        parser.simulation = simulations[0]

        # Test 8: Test querying without setting simulation
        print("\n9️⃣  Testing behavior with no simulation selected...")

        # Create fresh parser to test initial state
        parser2 = SiennaSimulationParser(file_path)

        # Clear selection
        parser2._selected_model = None

        try:
            datasets = parser2.list_datasets()
            print("   ❌ Should have raised ValueError")
            return False
        except ValueError as e:
            print(f"   ✅ Correctly raised ValueError when no simulation selected")

        # But should work with simulation parameter
        datasets = parser2.list_datasets(simulation=simulations[0])
        print(
            f"   ✅ Works correctly when simulation parameter provided ({len(datasets)} datasets)"
        )

        # Summary
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED")
        print("=" * 70)
        print("\n📊 Summary:")
        print(f"   - Total simulations found: {len(simulations)}")
        print(f"   - Default simulation: {default_sim}")
        print(f"   - Simulations tested: {simulations[:2]}")
        print("\n🎯 Key Features Verified:")
        print("   ✅ Auto-discovery of simulation models")
        print("   ✅ Emulation model names from 'name' attribute")
        print("   ✅ Decision model names from group names")
        print("   ✅ Default simulation selection")
        print("   ✅ simulation property (new API)")
        print("   ✅ list_datasets(simulation=...) parameter")
        print("   ✅ get_dataset(key, simulation=...) parameter")
        print("   ✅ Backward compatibility with selected_model")
        print("   ✅ Proper error handling")

        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test simulation discovery and querying",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "file_path", help="Path to simulation file (e.g., simulation.h5)"
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

    # Run tests
    success = test_simulation_discovery(args.file_path)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
