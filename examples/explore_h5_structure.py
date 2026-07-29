#!/usr/bin/env python
"""
Explore H5 file structure to understand simulation model organization.

This script helps identify:
1. Whether emulation model names come from attributes or group names
2. How decision models are organized
3. The actual H5 structure for different simulation types

Usage:
    python examples/explore_h5_structure.py <path_to_simulation.h5>
"""

import argparse
import sys
from pathlib import Path

import h5py


def explore_group(h5_group, indent=0):
    """Recursively explore and print H5 group structure."""
    prefix = "  " * indent

    # Print attributes
    if len(h5_group.attrs) > 0:
        print(f"{prefix}📋 Attributes:")
        for key, value in h5_group.attrs.items():
            if isinstance(value, bytes):
                value = value.decode()
            print(f"{prefix}   {key} = {value}")

    # Print datasets and subgroups
    for key in h5_group.keys():
        item = h5_group[key]
        if isinstance(item, h5py.Group):
            print(f"{prefix}📁 {key}/ (Group)")
            explore_group(item, indent + 1)
        elif isinstance(item, h5py.Dataset):
            print(f"{prefix}📄 {key} (Dataset: {item.shape}, {item.dtype})")


def analyze_emulation_models(h5data):
    """Analyze emulation model structure."""
    print("\n" + "=" * 70)
    print("🔬 EMULATION MODEL ANALYSIS")
    print("=" * 70)

    if "/simulation/emulation_model" not in h5data:
        print("   ❌ No emulation_model group found")
        return

    em_group = h5data["/simulation/emulation_model"]

    # Check if emulation_model itself has attributes (single model case)
    print("\n1️⃣  Checking emulation_model group attributes:")
    if len(em_group.attrs) > 0:
        print("   ✅ Found attributes at /simulation/emulation_model:")
        for key, value in em_group.attrs.items():
            if isinstance(value, bytes):
                value = value.decode()
            print(f"      {key} = {value}")

        # Check for 'name' attribute
        if "name" in em_group.attrs:
            name = em_group.attrs["name"]
            if isinstance(name, bytes):
                name = name.decode()
            print(f"\n   🎯 Emulation model name from attribute: '{name}'")
    else:
        print("   ℹ️  No attributes found at /simulation/emulation_model")

    # Check for subgroups (multiple models case)
    print("\n2️⃣  Checking for subgroups under emulation_model:")
    subgroups = list(em_group.keys())

    if subgroups:
        print(f"   ✅ Found {len(subgroups)} subgroup(s):")
        for subgroup_name in subgroups:
            subgroup = em_group[subgroup_name]
            if isinstance(subgroup, h5py.Group):
                print(f"\n      📁 Subgroup: {subgroup_name}")
                if len(subgroup.attrs) > 0:
                    print(f"         Attributes:")
                    for key, value in subgroup.attrs.items():
                        if isinstance(value, bytes):
                            value = value.decode()
                        print(f"            {key} = {value}")

                    # Check for 'name' attribute
                    if "name" in subgroup.attrs:
                        name = subgroup.attrs["name"]
                        if isinstance(name, bytes):
                            name = name.decode()
                        print(f"         🎯 Model name from attribute: '{name}'")
                        if name != subgroup_name:
                            print(
                                f"         ⚠️  WARNING: name attribute ('{name}') != group name ('{subgroup_name}')"
                            )
            else:
                print(f"      📄 Dataset (not a group): {subgroup_name}")
    else:
        print("   ℹ️  No subgroups found")

    # Conclusion
    print("\n3️⃣  Structure Pattern Identified:")
    if len(em_group.attrs) > 0 and not subgroups:
        print("   📌 PATTERN A: Single emulation model")
        print("      - Attributes stored directly on /simulation/emulation_model")
        print("      - Model name from 'name' attribute")
    elif subgroups:
        print("   📌 PATTERN B: Multiple emulation models")
        print("      - Each subgroup represents a model")
        print("      - Model name could be:")
        print("        a) Group name itself (subgroup_name)")
        print("        b) 'name' attribute within the subgroup")
    else:
        print("   ⚠️  PATTERN UNCLEAR: No attributes and no subgroups")


def analyze_decision_models(h5data):
    """Analyze decision model structure."""
    print("\n" + "=" * 70)
    print("🔬 DECISION MODEL ANALYSIS")
    print("=" * 70)

    if "/simulation/decision_models" not in h5data:
        print("   ❌ No decision_models group found")
        return

    dm_group = h5data["/simulation/decision_models"]

    # Check attributes on decision_models group itself
    print("\n1️⃣  Checking decision_models group attributes:")
    if len(dm_group.attrs) > 0:
        print("   ℹ️  Found attributes:")
        for key, value in dm_group.attrs.items():
            if isinstance(value, bytes):
                value = value.decode()
            print(f"      {key} = {value}")
    else:
        print("   ℹ️  No attributes on /simulation/decision_models")

    # Check for subgroups
    print("\n2️⃣  Checking for model subgroups:")
    subgroups = list(dm_group.keys())

    if subgroups:
        print(f"   ✅ Found {len(subgroups)} model(s):")
        for model_name in subgroups:
            model_group = dm_group[model_name]
            if isinstance(model_group, h5py.Group):
                print(f"\n      📁 Model: {model_name}")
                if len(model_group.attrs) > 0:
                    print(f"         Attributes:")
                    for key, value in model_group.attrs.items():
                        if isinstance(value, bytes):
                            value = value.decode()
                        print(f"            {key} = {value}")

                    # Check if 'name' attribute exists and differs from group name
                    if "name" in model_group.attrs:
                        name = model_group.attrs["name"]
                        if isinstance(name, bytes):
                            name = name.decode()
                        print(f"         🎯 'name' attribute: '{name}'")
                        if name != model_name:
                            print(
                                f"         ⚠️  WARNING: name attribute ('{name}') != group name ('{model_name}')"
                            )
            else:
                print(f"      📄 Dataset (not a group): {model_name}")
    else:
        print("   ℹ️  No model subgroups found")

    # Conclusion
    print("\n3️⃣  Structure Pattern Identified:")
    if subgroups:
        print("   📌 PATTERN: Decision models as subgroups")
        print(
            "      - Each subgroup name represents a model (e.g., 'UC', 'ED', 'RAUC')"
        )
        print("      - Model name = group name")


def compare_with_parser_logic(h5data):
    """Compare H5 structure with current parser logic."""
    print("\n" + "=" * 70)
    print("🔍 PARSER LOGIC VALIDATION")
    print("=" * 70)

    print("\n📖 Current parser logic:")
    print("   Emulation Models:")
    print("   1. If /simulation/emulation_model has attributes:")
    print("      → Single model, use 'name' attribute")
    print("   2. Else, iterate subgroups:")
    print("      → Each subgroup is a model, use 'name' attribute from subgroup")
    print("\n   Decision Models:")
    print("   1. Iterate subgroups under /simulation/decision_models")
    print("      → Each subgroup name is the model name")

    # Check if current logic will work
    print("\n✅ Validation:")

    # Emulation models
    if "/simulation/emulation_model" in h5data:
        em_group = h5data["/simulation/emulation_model"]
        has_attrs = len(em_group.attrs) > 0
        has_subgroups = len(list(em_group.keys())) > 0

        print(f"\n   Emulation Models:")
        print(f"      Has attributes: {has_attrs}")
        print(f"      Has subgroups: {has_subgroups}")

        if has_attrs and not has_subgroups:
            if "name" in em_group.attrs:
                name = em_group.attrs["name"]
                if isinstance(name, bytes):
                    name = name.decode()
                print(f"      ✅ Single model detected, name='{name}'")
            else:
                print(f"      ⚠️  WARNING: Has attributes but no 'name' attribute")

        if has_subgroups:
            print(f"      ✅ Multiple models detected via subgroups")
            for sg_name in list(em_group.keys())[:3]:  # Show first 3
                sg = em_group[sg_name]
                if isinstance(sg, h5py.Group) and "name" in sg.attrs:
                    name = sg.attrs["name"]
                    if isinstance(name, bytes):
                        name = name.decode()
                    print(f"         - Subgroup '{sg_name}' → name='{name}'")

    # Decision models
    if "/simulation/decision_models" in h5data:
        dm_group = h5data["/simulation/decision_models"]
        model_names = list(dm_group.keys())

        print(f"\n   Decision Models:")
        print(f"      Found {len(model_names)} model(s)")
        for model_name in model_names:
            print(f"         ✅ Model: {model_name}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Explore H5 simulation file structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("file_path", help="Path to H5 simulation file")

    parser.add_argument(
        "--full-tree", action="store_true", help="Show full H5 tree structure"
    )

    args = parser.parse_args()

    # Check file exists
    file_path = Path(args.file_path)
    if not file_path.exists():
        print(f"❌ Error: File not found: {file_path}")
        sys.exit(1)

    print("\n" + "=" * 70)
    print(f"📂 Exploring: {file_path.name}")
    print("=" * 70)

    try:
        with h5py.File(file_path, "r") as h5data:
            # Show basic file info
            print("\n📊 File Overview:")
            print(f"   Keys at root: {list(h5data.keys())}")

            if "/simulation" in h5data:
                sim_group = h5data["/simulation"]
                print(f"   Keys under /simulation: {list(sim_group.keys())}")

                print(f"\n   Simulation attributes:")
                for key, value in sim_group.attrs.items():
                    if isinstance(value, bytes):
                        value = value.decode()
                    print(f"      {key} = {value}")

            # Analyze emulation models
            analyze_emulation_models(h5data)

            # Analyze decision models
            analyze_decision_models(h5data)

            # Compare with parser logic
            compare_with_parser_logic(h5data)

            # Optional: show full tree
            if args.full_tree:
                print("\n" + "=" * 70)
                print("🌳 FULL H5 TREE STRUCTURE")
                print("=" * 70)
                if "/simulation" in h5data:
                    explore_group(h5data["/simulation"])

        print("\n" + "=" * 70)
        print("✅ Exploration Complete")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
