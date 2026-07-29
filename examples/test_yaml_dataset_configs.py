#!/usr/bin/env python
"""
Test script to verify dataset configurations are properly saved to YAML.

This script demonstrates:
1. Creating a scenario with dataset configurations
2. Saving to YAML
3. Loading from YAML
4. Verifying the configurations are preserved

Usage:
    python examples/test_yaml_dataset_configs.py <path_to_simulation.h5>
"""

import argparse
import sys
import tempfile
from pathlib import Path

import yaml
from loguru import logger

from gat.models.project import SiennaScenarioConfig
from gat.simulations import SiennaSimulationParser
from gat.simulations.sienna import SiennaSimulationDataset


def test_yaml_serialization(file_path: str):
    """Test that dataset configs are properly saved to and loaded from YAML."""
    print("\n" + "=" * 70)
    print("Testing Dataset Configuration YAML Serialization")
    print("=" * 70)

    # Step 1: Create a scenario with dataset configurations
    print("\n1️⃣  Creating scenario configuration...")
    scenario = SiennaScenarioConfig(
        name="Test Scenario",
        system_path="/path/to/system.json",
        simulation_paths=file_path,
        simulation_type=None,
    )
    print(f"   ✓ Created scenario: {scenario.name}")

    # Step 2: Discover datasets
    print("\n2️⃣  Discovering datasets from simulation file...")
    scenario.discover_and_set_dataset_configs()

    dataset_configs = scenario.get_dataset_configs()
    power_datasets = [c for c in dataset_configs if c.apply_base_power]

    print(f"   ✓ Discovered {len(dataset_configs)} datasets")
    print(f"   ✓ {len(power_datasets)} flagged for base_power multiplication")

    # Step 3: Customize some configurations
    print("\n3️⃣  Customizing dataset configurations...")
    for config in dataset_configs:
        if "ThermalStandard" in config.name and config.apply_base_power:
            config.custom_multiplier = 125.0
            print(f"   ⚙ Set custom multiplier (125.0) for: {config.name}")
            break

    # Update the scenario with modified configs
    scenario.set_dataset_configs_from_objects(dataset_configs)

    # Step 4: Save to YAML
    print("\n4️⃣  Saving to YAML...")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml_path = f.name
        yaml_content = scenario.model_dump(exclude_none=True)
        yaml.dump(yaml_content, f, sort_keys=False, default_flow_style=False)

    print(f"   ✓ Saved to: {yaml_path}")

    # Step 5: Display YAML content
    print("\n5️⃣  YAML file content:")
    print("   " + "-" * 66)
    with open(yaml_path, "r") as f:
        content = f.read()
        # Show first 50 lines
        lines = content.split("\n")
        for i, line in enumerate(lines[:50], 1):
            print(f"   {i:3d} | {line}")
        if len(lines) > 50:
            print(f"   ... ({len(lines) - 50} more lines)")
    print("   " + "-" * 66)

    # Step 6: Verify dataset_configs section
    print("\n6️⃣  Verifying dataset_configs section in YAML...")
    with open(yaml_path, "r") as f:
        loaded_yaml = yaml.safe_load(f)

    if "dataset_configs" not in loaded_yaml:
        print("   ❌ ERROR: dataset_configs not found in YAML!")
        return False

    yaml_datasets = loaded_yaml["dataset_configs"]
    print(f"   ✓ Found {len(yaml_datasets)} datasets in YAML")

    # Check structure of first few datasets
    print("\n   Sample dataset configurations from YAML:")
    for i, ds in enumerate(yaml_datasets[:3], 1):
        print(f"\n   Dataset {i}:")
        print(f"     name: {ds.get('name', 'MISSING')}")
        print(f"     h5_path: {ds.get('h5_path', 'MISSING')}")
        print(f"     apply_base_power: {ds.get('apply_base_power', 'MISSING')}")
        if "custom_multiplier" in ds:
            print(f"     custom_multiplier: {ds['custom_multiplier']}")

    # Step 7: Reload from YAML
    print("\n7️⃣  Reloading scenario from YAML...")
    with open(yaml_path, "r") as f:
        reloaded_data = yaml.safe_load(f)

    reloaded_scenario = SiennaScenarioConfig(**reloaded_data)
    print(f"   ✓ Reloaded scenario: {reloaded_scenario.name}")

    # Step 8: Verify configurations were preserved
    print("\n8️⃣  Verifying configurations were preserved...")
    reloaded_configs = reloaded_scenario.get_dataset_configs()

    if reloaded_configs is None:
        print("   ❌ ERROR: No dataset configs after reload!")
        return False

    print(f"   ✓ Found {len(reloaded_configs)} datasets after reload")

    # Check counts match
    if len(reloaded_configs) != len(dataset_configs):
        print(f"   ❌ ERROR: Dataset count mismatch!")
        print(f"      Original: {len(dataset_configs)}")
        print(f"      Reloaded: {len(reloaded_configs)}")
        return False

    print(f"   ✓ Dataset count matches: {len(reloaded_configs)}")

    # Check power dataset count
    reloaded_power = [c for c in reloaded_configs if c.apply_base_power]
    if len(reloaded_power) != len(power_datasets):
        print(f"   ❌ ERROR: Power dataset count mismatch!")
        print(f"      Original: {len(power_datasets)}")
        print(f"      Reloaded: {len(reloaded_power)}")
        return False

    print(f"   ✓ Power dataset count matches: {len(reloaded_power)}")

    # Check custom multiplier was preserved
    custom_found = False
    for config in reloaded_configs:
        if config.custom_multiplier is not None:
            custom_found = True
            print(
                f"   ✓ Custom multiplier preserved: {config.custom_multiplier} for {config.name}"
            )
            break

    if not custom_found:
        print("   ⚠️  Warning: No custom multipliers found after reload")

    # Step 9: Test manual YAML editing
    print("\n9️⃣  Demonstrating manual YAML editing...")
    print("\n   To manually edit dataset configurations, find the dataset_configs")
    print("   section in the YAML file and modify values like this:")
    print("\n   dataset_configs:")
    print("   - name: ActivePowerVariable__ThermalStandard")
    print(
        "     h5_path: /simulation/decision_models/UC/optimizer/ActivePowerVariable__ThermalStandard"
    )
    print("     apply_base_power: true")
    print("     custom_multiplier: 150.0  # Change this value as needed")
    print("\n   - name: SomeOtherDataset")
    print("     h5_path: /simulation/emulation_model/results/SomeOtherDataset")
    print("     apply_base_power: false  # Change to true to enable multiplication")

    # Cleanup
    Path(yaml_path).unlink()
    print(f"\n   🗑️  Cleaned up test file: {yaml_path}")

    # Success!
    print("\n" + "=" * 70)
    print("✅ All Tests Passed!")
    print("=" * 70)

    return True


def show_yaml_example():
    """Show an example of what the YAML file looks like."""
    print("\n" + "=" * 70)
    print("Example YAML Output")
    print("=" * 70)

    example = """
name: My UC Scenario
description: Unit commitment simulation
type: sienna
system_path: /path/to/system.json
simulation_paths: /path/to/simulation.h5
simulation_type: UC
dataset_configs:
- name: ActivePowerVariable__ThermalStandard
  h5_path: /simulation/decision_models/UC/optimizer/ActivePowerVariable__ThermalStandard
  apply_base_power: true
  custom_multiplier: null
- name: ActivePowerVariable__RenewableDispatch
  h5_path: /simulation/decision_models/UC/optimizer/ActivePowerVariable__RenewableDispatch
  apply_base_power: true
  custom_multiplier: 125.0
- name: OnVariable__ThermalStandard
  h5_path: /simulation/decision_models/UC/optimizer/OnVariable__ThermalStandard
  apply_base_power: false
  custom_multiplier: null
- name: ReserveVariable__VariableReserve__ReserveUp
  h5_path: /simulation/decision_models/UC/optimizer/ReserveVariable__VariableReserve__ReserveUp
  apply_base_power: true
  custom_multiplier: null
created_at: 2026-01-23T10:30:00
updated_at: 2026-01-23T10:30:00
"""

    print(example)

    print("\n📝 Key Points:")
    print("  • dataset_configs is a list of dataset configurations")
    print("  • Each dataset has: name, h5_path, apply_base_power, custom_multiplier")
    print("  • apply_base_power: true means multiply by base_power (default 100 MW)")
    print("  • custom_multiplier: overrides base_power with a custom value")
    print("  • You can edit these values directly in the YAML file")
    print("  • Changes take effect when the scenario is loaded")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test dataset configuration YAML serialization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "file_path",
        nargs="?",
        help="Path to simulation file (optional, use --example to see YAML format)",
    )

    parser.add_argument(
        "--example",
        action="store_true",
        help="Show example YAML output without testing",
    )

    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Reduce logging output"
    )

    args = parser.parse_args()

    # Configure logging
    if args.quiet:
        logger.remove()
        logger.add(sys.stderr, level="WARNING")

    # Show example if requested
    if args.example:
        show_yaml_example()
        sys.exit(0)

    # Check file was provided
    if not args.file_path:
        print("❌ Error: file_path is required (or use --example)")
        parser.print_help()
        sys.exit(1)

    # Check file exists
    if not Path(args.file_path).exists():
        print(f"❌ Error: File not found: {args.file_path}")
        sys.exit(1)

    try:
        success = test_yaml_serialization(args.file_path)
        sys.exit(0 if success else 1)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        logger.exception("Test failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
