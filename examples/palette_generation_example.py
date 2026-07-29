# examples/palette_generation_example.py
"""
Example: Automatic Palette Generation from System Files

This example demonstrates how to use GAT's palette generation capabilities
to automatically create palette configurations from system files.

The palette generator:
1. Reads a system file (Sienna JSON, ReEDS, etc.)
2. Analyzes generator categories and classifications
3. Creates display categories with appropriate colors
4. Maps simulation categories to display categories
5. Identifies VRE, storage, and curtailable technologies
6. Creates a sensible stack order for visualizations

Usage:
    python examples/palette_generation_example.py path/to/system.json
"""

import sys
from pathlib import Path

import yaml

from gat.datahelpers.sienna_system import SiennaSystem
from gat.palette_generator import PaletteGenerator


def inspect_system(system_path: str):
    """
    Inspect a system file and print detailed information.

    Args:
        system_path: Path to system file
    """
    print(f"\n{'=' * 70}")
    print(f"SYSTEM FILE INSPECTION")
    print(f"{'=' * 70}\n")

    # Load system
    print(f"Loading system: {system_path}")
    system = SiennaSystem(system_path)

    # Get basic info
    info = system.get_system_info()
    print(f"\nSystem Information:")
    print(f"  Name: {info.name}")
    print(f"  Description: {info.description}")
    print(f"  Base Power: {info.base_power} MVA")
    print(f"  Generators: {info.num_generators}")
    print(f"  Buses: {info.num_buses}")
    print(f"  Loads: {info.num_loads}")
    print(f"  Data Format Version: {info.data_format_version}")

    # List component types
    print(f"\nComponent Types:")
    for comp_type in sorted(system.list_component_types()):
        print(f"  - {comp_type}")

    # List generator categories
    print(f"\nGenerator Categories:")
    categories = system.list_generator_categories()
    print(f"{'Category':<40} {'Count':>8} {'Capacity':>12} {'VRE':>6} {'Storage':>8}")
    print("-" * 80)
    for cat in categories:
        capacity_str = f"{cat.total_capacity:.1f} MW" if cat.total_capacity else "N/A"
        vre_str = "Yes" if cat.is_vre else "No"
        storage_str = "Yes" if cat.is_storage else "No"
        print(
            f"{cat.name:<40} {cat.count:>8} {capacity_str:>12} {vre_str:>6} {storage_str:>8}"
        )

    # VRE technologies
    vre_cats = system.get_vre_categories()
    if vre_cats:
        print(f"\nVRE Technologies ({len(vre_cats)}):")
        for cat in vre_cats:
            print(f"  - {cat}")

    # Storage technologies
    storage_cats = system.get_storage_categories()
    if storage_cats:
        print(f"\nStorage Technologies ({len(storage_cats)}):")
        for cat in storage_cats:
            print(f"  - {cat}")

    # Curtailable technologies
    curtailable_cats = system.get_curtailable_categories()
    if curtailable_cats:
        print(f"\nCurtailable Technologies ({len(curtailable_cats)}):")
        for cat in curtailable_cats:
            print(f"  - {cat}")

    # Validation
    warnings = system.validate()
    if warnings:
        print(f"\nValidation Warnings:")
        for warning in warnings:
            print(f"  ! {warning}")
    else:
        print(f"\n✓ No validation warnings")

    return system


def generate_palette(system: SiennaSystem, palette_name: str = "example_palette"):
    """
    Generate a palette from a system.

    Args:
        system: SiennaSystem instance
        palette_name: Name for the generated palette
    """
    print(f"\n{'=' * 70}")
    print(f"PALETTE GENERATION")
    print(f"{'=' * 70}\n")

    # Create palette generator
    generator = PaletteGenerator(system)

    # Generate palette
    print(f"Generating palette '{palette_name}'...")
    palette = generator.generate(
        name=palette_name,
        simulation_type="sienna",
        description="Auto-generated example palette demonstrating GAT's palette generation capabilities",
    )

    print(f"✓ Palette generated successfully\n")

    # Print detailed summary
    generator.print_summary(palette)

    return palette


def save_palette(palette, output_path: str = "example_palette.yaml"):
    """
    Save palette to YAML file.

    Args:
        palette: Palette instance
        output_path: Output file path
    """
    print(f"\n{'=' * 70}")
    print(f"SAVING PALETTE")
    print(f"{'=' * 70}\n")

    output_path = Path(output_path)

    print(f"Saving palette to: {output_path}")

    with open(output_path, "w") as f:
        yaml.dump(
            palette.model_dump(exclude_none=True),
            f,
            sort_keys=False,
            default_flow_style=False,
        )

    print(f"✓ Palette saved\n")

    # Show file size
    size = output_path.stat().st_size
    print(f"File size: {size:,} bytes")

    return output_path


def show_color_preview(palette):
    """
    Show a preview of palette colors (text-based).

    Args:
        palette: Palette instance
    """
    print(f"\n{'=' * 70}")
    print(f"COLOR PREVIEW")
    print(f"{'=' * 70}\n")

    print(f"{'Display Category':<30} {'Color':>10} {'Mappings':>10}")
    print("-" * 55)

    for cat in palette.display_categories:
        # Count how many simulation categories map to this
        mappings = [
            m for m in palette.category_mappings if m.display_category == cat.name
        ]

        print(f"{cat.name:<30} {cat.color:>10} {len(mappings):>10}")


def customize_palette_example(palette):
    """
    Show examples of how to customize a generated palette.

    Args:
        palette: Palette instance
    """
    print(f"\n{'=' * 70}")
    print(f"CUSTOMIZATION EXAMPLES")
    print(f"{'=' * 70}\n")

    print(
        "After generating a palette, you can customize it by editing the YAML file.\n"
    )

    print("Example 1: Change a color")
    print("-" * 40)
    print("""
display_categories:
  - name: Solar
    color: "#FFAA00"  # Changed from default gold
    label: Solar PV
""")

    print("\nExample 2: Add a generator override")
    print("-" * 40)
    print("""
generator_overrides:
  - generator_name: "SpecialHydro_1"
    custom_category: "Priority Hydro"
    display_category: "Priority Hydro"

display_categories:
  - name: Priority Hydro
    color: "#2E8B57"
    label: Priority Hydro Resources
""")

    print("\nExample 3: Modify stack order")
    print("-" * 40)
    print("""
stack_order:
  - Nuclear
  - Coal
  - Natural Gas  # Moved up
  - Hydro
  - Wind
  - Solar
  - Battery Storage
""")

    print("\nExample 4: Update VRE classification")
    print("-" * 40)
    print("""
vre_classification:
  vre_technologies:
    - Solar_PV
    - Wind_Onshore
    - Wind_Offshore
    - Geothermal  # Added geothermal as VRE
  curtailable_technologies:
    - Solar_PV
    - Wind_Onshore
    - Wind_Offshore
""")


def main():
    """Main example function."""
    print(f"\n{'#' * 70}")
    print(f"# GAT Palette Generation Example")
    print(f"{'#' * 70}")

    # Get system file path
    if len(sys.argv) < 2:
        print("\nUsage: python palette_generation_example.py <system_file_path>")
        print("\nExample:")
        print("  python palette_generation_example.py data/system.json")
        sys.exit(1)

    system_path = sys.argv[1]

    # Check file exists
    if not Path(system_path).exists():
        print(f"\nError: System file not found: {system_path}")
        sys.exit(1)

    try:
        # 1. Inspect the system file
        system = inspect_system(system_path)

        # 2. Generate palette
        palette = generate_palette(system, palette_name="example_palette")

        # 3. Show color preview
        show_color_preview(palette)

        # 4. Save palette
        output_path = save_palette(palette, output_path="example_palette.yaml")

        # 5. Show customization examples
        customize_palette_example(palette)

        # Final summary
        print(f"\n{'=' * 70}")
        print(f"SUMMARY")
        print(f"{'=' * 70}\n")
        print(f"✓ System file analyzed: {system_path}")
        print(f"✓ Palette generated: {palette.name}")
        print(f"✓ Display categories: {len(palette.display_categories)}")
        print(f"✓ Category mappings: {len(palette.category_mappings)}")
        print(f"✓ Palette saved: {output_path}")
        print(f"\nNext steps:")
        print(f"  1. Review the generated palette: {output_path}")
        print(f"  2. Customize colors, labels, or classifications as needed")
        print(f"  3. Use with GAT plotting functions for consistent visualizations")
        print(f"\nFor CLI usage:")
        print(f"  gat project add-palette <palette_name> <scenario_id>")
        print()

    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
