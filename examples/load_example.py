#!/usr/bin/env python3
"""
Example: Using gat.load() to load projects, scenarios, and palettes.

This script demonstrates the various ways to use gat.load() to load
GAT resources in Python scripts.
"""

import gat

# =============================================================================
# Example 1: Load with all defaults
# =============================================================================
print("=" * 70)
print("Example 1: Load with all defaults")
print("=" * 70)

# This will use:
# - Default project (from user metadata)
# - Default scenario (from project config or first available)
# - Default palette (from scenario/project config or first available)
scenario, palette, project = gat.load()

print(f"\nLoaded scenario type: {type(scenario).__name__}")
print(f"Palette available: {palette is not None}")
print(f"Project path: {project.project_path}")


# =============================================================================
# Example 2: Load specific project and scenario
# =============================================================================
print("\n" + "=" * 70)
print("Example 2: Load specific resources")
print("=" * 70)

scenario, palette, project = gat.load(
    project="my-project",
    scenario="base",
    verbose=False,  # Suppress informative messages
)

print(f"\nLoaded scenario: base")
print(f"Scenario name: {scenario.name if hasattr(scenario, 'name') else 'N/A'}")


# =============================================================================
# Example 3: Load only scenario (no palette needed)
# =============================================================================
print("\n" + "=" * 70)
print("Example 3: Load scenario only")
print("=" * 70)

scenario = gat.load_scenario_only(project="my-project", scenario="base", verbose=False)

print(f"\nLoaded scenario: {type(scenario).__name__}")


# =============================================================================
# Example 4: Iterate through scenarios
# =============================================================================
print("\n" + "=" * 70)
print("Example 4: Process multiple scenarios")
print("=" * 70)

# Get list of scenarios
_, _, project = gat.load(verbose=False)
scenarios = project.list_scenarios()

print(f"\nFound {len(scenarios)} scenarios:")
for scenario_id in scenarios:
    print(f"  - {scenario_id}")

# Process each scenario
print("\nProcessing scenarios:")
for scenario_id in scenarios:
    scenario, palette, _ = gat.load(scenario=scenario_id, verbose=False)
    print(f"  ✓ Processed: {scenario_id}")


# =============================================================================
# Example 5: Handle missing resources
# =============================================================================
print("\n" + "=" * 70)
print("Example 5: Error handling")
print("=" * 70)

try:
    scenario, palette, project = gat.load(project="nonexistent-project")
except ValueError as e:
    print(f"\n✓ Caught expected error: {str(e)[:60]}...")


# =============================================================================
# Example 6: Check palette availability
# =============================================================================
print("\n" + "=" * 70)
print("Example 6: Check for palette")
print("=" * 70)

scenario, palette, project = gat.load(verbose=False)

if palette is None:
    print("\nNo palette available - would need to generate one")
    print("  Command: gat project palette add <name> <scenario-id>")
else:
    print(
        f"\n✓ Palette loaded: {palette.name if hasattr(palette, 'name') else 'unnamed'}"
    )
    print(f"  Display categories: {len(palette.display_categories)}")
    print(f"  Stack order: {len(palette.stack_order)} categories")


# =============================================================================
# Example 7: Access project configuration
# =============================================================================
print("\n" + "=" * 70)
print("Example 7: Access project info")
print("=" * 70)

scenario, palette, project = gat.load(verbose=False)

# Access project configuration
config = project.load_config()
print(f"\nProject: {config.name}")
print(f"GAT Version: {config.gat_version}")

# List available resources
scenarios = project.list_scenarios()
palettes = project.list_palettes()

print(f"\nAvailable resources:")
print(f"  Scenarios: {len(scenarios)}")
for s in scenarios:
    print(f"    - {s}")
print(f"  Palettes: {len(palettes)}")
for p in palettes:
    print(f"    - {p}")


# =============================================================================
# Summary
# =============================================================================
print("\n" + "=" * 70)
print("Summary")
print("=" * 70)
print("""
gat.load() provides a simple way to load GAT resources:

1. Use defaults for quick scripts:
   scenario, palette, project = gat.load()

2. Specify resources explicitly:
   scenario, palette, project = gat.load(
       project="my-project",
       scenario="base_2035",
       palette="renewable_focus"
   )

3. Suppress messages in production:
   scenario, palette, project = gat.load(verbose=False)

4. Use convenience functions:
   scenario = gat.load_scenario_only()
   palette = gat.load_palette_only()

See docs/source/python_api_load.md for complete documentation.
""")
