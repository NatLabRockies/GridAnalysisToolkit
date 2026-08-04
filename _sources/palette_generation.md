# Palette Generation

GAT can automatically generate palette configurations from system files, creating sensible defaults for display categories, colors, and classifications based on the generators found in your system.

## Overview

Palettes control how simulation data is aggregated and visualized. Instead of manually creating palette configurations, you can generate them automatically from a scenario's system file using the `add-palette` command.

The palette generator:
- Analyzes generator categories in the system file
- Creates appropriate display categories with colors
- Maps simulation categories to display categories
- Identifies VRE (Variable Renewable Energy) technologies
- Classifies storage and curtailable resources
- Creates a sensible stack order for visualizations

## Quick Start

```bash
# Generate a palette from a scenario
gat project add-palette my_palette base_2035

# With custom description
gat project add-palette renewable_focus base_2035 \
    --description "Emphasizes renewable energy sources"

# For a specific project
gat project add-palette my_palette base_2035 --project my_project

# Show detailed summary of generated palette
gat project add-palette my_palette base_2035 --print-summary
```

## How It Works

### 1. System Analysis

The generator reads the scenario's system file and extracts:
- All generator components and their metadata
- Fuel types (coal, gas, solar, wind, etc.)
- Prime movers (CT, CC, PV, WT, etc.)
- Technology classifications
- Capacity information

### 2. Category Simplification

Raw simulation categories are grouped into display categories:

| Simulation Categories | Display Category |
|----------------------|------------------|
| `Solar_PV`, `Solar_Photovoltaic` | `Solar` |
| `Wind_Onshore`, `Wind_Offshore` | `Wind` |
| `NaturalGas_CT`, `NaturalGas_CC` | `Natural Gas` |
| `Coal_Steam`, `Coal_Sub` | `Coal` |
| `Battery_LithiumIon`, `Battery_Storage` | `Battery Storage` |

This reduces clutter in legends and visualizations while maintaining important distinctions.

### 3. Color Assignment

Colors are automatically assigned based on technology type:

- **Solar**: Gold (`#FFD700`)
- **Wind**: Sky blue (`#87CEEB`)
- **Hydro**: Steel blue (`#4682B4`)
- **Natural Gas**: Light red (`#FF6B6B`)
- **Coal**: Dark slate gray (`#2F4F4F`)
- **Nuclear**: Medium purple (`#9370DB`)
- **Battery Storage**: Dark orchid (`#9932CC`)
- **Other**: Gray tones

Colors are selected from a colorblind-friendly palette.

### 4. Stack Order

Categories are ordered for stacked visualizations following typical dispatch order:

1. **Bottom (Baseload)**
   - Nuclear
   - Coal
   - Hydro

2. **Middle (Dispatchable)**
   - Natural Gas
   - Biomass

3. **Top (Variable/Storage)**
   - Wind
   - Solar
   - Battery Storage

### 5. Classifications

The generator automatically identifies:

**VRE (Variable Renewable Energy)**:
- Solar (PV, CSP without storage)
- Wind (onshore, offshore)

**Storage**:
- Battery systems (lithium-ion, etc.)
- Pumped hydro storage

**Curtailable**:
- All VRE technologies
- Other resources marked as curtailable

## Supported System Types

### Sienna/PowerSystems.jl (Supported)

Extracts information from Sienna JSON system files:
- Generator types (RenewableDispatch, ThermalStandard, etc.)
- Fuel and prime mover fields
- Technology classifications
- Capacity limits

```bash
gat project add-palette my_palette sienna_scenario
```

### ReEDS™ (Future)

Support for ReEDS system files is planned for a future release.

### Plexos (Future)

Support for Plexos system files is planned for a future release.

## Customizing Generated Palettes

After generation, you can manually edit the palette YAML file to customize:

### Colors

Edit the `color` field for any display category:

```yaml
display_categories:
  - name: Solar
    color: "#FFD700"  # Change to your preferred color
    label: Solar PV
```

### Display Names

Change how categories appear in legends:

```yaml
display_categories:
  - name: Solar
    color: "#FFD700"
    label: Solar PV and CSP  # Custom label
```

### Category Mappings

Add or modify simulation-to-display category mappings:

```yaml
category_mappings:
  - simulation_category: Solar_PV
    display_category: Solar
  - simulation_category: Solar_CSP
    display_category: Solar  # Group with solar
```

### Stack Order

Adjust the order of categories in stacked plots:

```yaml
stack_order:
  - Nuclear
  - Coal
  - Hydro
  - Natural Gas
  - Wind
  - Solar
  - Battery Storage
```

### Generator Overrides

Override specific generators to custom categories:

```yaml
generator_overrides:
  - generator_name: "SpecialHydro_1"
    custom_category: "Priority Hydro"
    display_category: "Priority Hydro"
```

Then add the custom display category:

```yaml
display_categories:
  - name: Priority Hydro
    color: "#2E8B57"
    label: Priority Hydro Resources
```

**If you have no generator overrides, leave it as an empty list:**

```yaml
generator_overrides: []
```

### VRE Classification

Add or remove technologies from VRE classification:

```yaml
vre_classification:
  vre_technologies:
    - Solar_PV
    - Wind_Onshore
    - Wind_Offshore
    # Add custom VRE types
  curtailable_technologies:
    - Solar_PV
    - Wind_Onshore
    - Wind_Offshore
```

### Load Classification

Define storage charging and flexible load categories:

```yaml
load_classification:
  storage_charging_categories:
    - Battery_LithiumIon
    - Pumped_Hydro
  flexible_load_categories:
    - Industrial_Load
    - EV_Charging
```

**If you have no storage charging or flexible load categories, use empty lists:**

```yaml
load_classification:
  storage_charging_categories: []
  flexible_load_categories: []
```

**Or omit categories you don't need:**

```yaml
load_classification:
  storage_charging_categories:
    - Battery_LithiumIon
  flexible_load_categories: []  # No flexible loads in this system
```

## Complete Example: Minimal Palette with Blank Options

Here's a complete example showing a minimal palette configuration with empty/blank optional fields:

```yaml
name: Minimal Example Palette
description: Example showing blank optional fields
simulation_type: sienna
version: 1.0.0

display_categories:
  - name: Solar
    color: "#FFD700"
    label: Solar
  - name: Wind
    color: "#87CEEB"
    label: Wind
  - name: Natural Gas
    color: "#FF6B6B"
    label: Natural Gas

category_mappings:
  - simulation_category: Solar_PV
    display_category: Solar
  - simulation_category: Wind_Onshore
    display_category: Wind
  - simulation_category: NaturalGas_CC
    display_category: Natural Gas

# No custom generator overrides in this palette
generator_overrides: []

stack_order:
  - Natural Gas
  - Wind
  - Solar

vre_classification:
  vre_technologies:
    - Solar_PV
    - Wind_Onshore
  curtailable_technologies:
    - Solar_PV
    - Wind_Onshore

# No storage or flexible loads in this system
load_classification:
  storage_charging_categories: []
  flexible_load_categories: []
```

This example shows that when you don't have generator overrides, storage charging categories, or flexible load categories, you can explicitly set them to empty lists (`[]`) to make it clear that these options were considered but are not applicable to your system.

## Command Reference

### `gat project add-palette`

Generate a palette from a scenario's system file.

**Arguments**:
- `PALETTE_NAME`: Name for the new palette
- `SCENARIO_ID`: Scenario to read system file from

**Options**:
- `--project PROJECT_ID`: Project to add palette to (uses default if not specified)
- `--description TEXT`: Custom description for the palette
- `--print-summary`: Print detailed summary after generation

**Examples**:

```bash
# Basic generation
gat project add-palette default base_2035

# With description
gat project add-palette renewable_focus base_2035 \
    --description "Focus on renewable energy sources"

# Show detailed summary
gat project add-palette my_palette base_2035 --print-summary

# For specific project
gat project add-palette my_palette base_2035 --project western_grid
```

## Programmatic Usage

You can also generate palettes programmatically in Python:

```python
from gat.datahelpers.sienna_system import SiennaSystem
from gat.palette_generator import PaletteGenerator

# Load system file
system = SiennaSystem("path/to/system.json")

# Create generator
generator = PaletteGenerator(system)

# Generate palette
palette = generator.generate(
    name="My Palette",
    simulation_type="sienna",
    description="Custom palette for my analysis"
)

# Print summary
generator.print_summary(palette)

# Save to file
import yaml
from pathlib import Path

palette_path = Path("palettes/my_palette.yaml")
with open(palette_path, "w") as f:
    yaml.dump(
        palette.model_dump(exclude_none=True),
        f,
        sort_keys=False
    )
```

### Inspecting System Data

```python
from gat.datahelpers.sienna_system import SiennaSystem

# Load system
system = SiennaSystem("path/to/system.json")

# Get system info
info = system.get_system_info()
print(f"Generators: {info.num_generators}")
print(f"Buses: {info.num_buses}")

# List generator categories
categories = system.list_generator_categories()
for cat in categories:
    print(f"{cat.name}: {cat.count} generators, {cat.total_capacity:.1f} MW")
    print(f"  VRE: {cat.is_vre}, Storage: {cat.is_storage}")

# Get detailed generator data
df = system.get_generator_data()
print(df.head())

# Get VRE categories
vre_cats = system.get_vre_categories()
print(f"VRE categories: {vre_cats}")
```

## BaseSystem Abstraction

The palette generator uses the `BaseSystem` abstraction, which provides a consistent interface for reading system files across different simulation platforms.

### Implementing Custom System Parsers

To support a new simulation platform, implement the `BaseSystem` abstract class:

```python
from gat.datahelpers.base_system import (
    BaseSystem,
    GeneratorCategory,
    LoadCategory,
    SystemInfo
)
import pandas as pd

class MyCustomSystem(BaseSystem):
    """Parser for MyCustom simulation platform."""
    
    def get_system_info(self) -> SystemInfo:
        """Extract basic system metadata."""
        # Read system file and extract info
        return SystemInfo(
            name="My System",
            num_generators=100,
            num_buses=50
        )
    
    def list_generator_categories(self) -> List[GeneratorCategory]:
        """List all generator categories."""
        # Analyze generators and group by category
        categories = []
        # ... extraction logic ...
        return categories
    
    def list_load_categories(self) -> List[LoadCategory]:
        """List load categories."""
        return []  # If not applicable
    
    def get_generator_data(self, category=None) -> pd.DataFrame:
        """Get detailed generator data."""
        # Return DataFrame with generator metadata
        pass
    
    def get_load_data(self, category=None) -> pd.DataFrame:
        """Get detailed load data."""
        pass
```

Then use it with the palette generator:

```python
system = MyCustomSystem("path/to/system/file")
generator = PaletteGenerator(system)
palette = generator.generate(name="My Palette", simulation_type="mycustom")
```

## Best Practices

### 1. Start with Auto-Generation

Always start by generating a palette automatically, then customize:

```bash
# Generate base palette
gat project add-palette base base_scenario --print-summary

# Review and customize the YAML file
# project/palettes/base.yaml
```

### 2. Create Scenario-Specific Palettes

Different scenarios may need different palettes:

```bash
# Renewable-heavy scenario
gat project add-palette high_renewable renewable_2050

# Conventional scenario
gat project add-palette conventional baseline_2025
```

### 3. Share Palettes in Git

Commit palette files to version control:

```bash
git add palettes/my_palette.yaml
git commit -m "Add palette for renewable scenario"
```

Team members can use the same palette for consistent visualizations.

### 4. Validate Your Palette

After customization, check for issues:

```python
from gat.models.palette import Palette
import yaml

# Load palette
with open("palettes/my_palette.yaml") as f:
    data = yaml.safe_load(f)
palette = Palette(**data)

# Validate
warnings = palette.validate_stack_order()
if warnings:
    for warning in warnings:
        print(f"Warning: {warning}")
```

### 5. Document Custom Categories

If you add custom categories or overrides, document them in the palette description:

```yaml
name: Custom Western Grid Palette
description: |
  Custom palette for Western Grid analysis.
  
  Customizations:
  - Hydro cascade grouped as "Priority Hydro"
  - Behind-the-meter solar separated from utility solar
  - Custom colors for regional generation
```

## Troubleshooting

### Palette Already Exists

```
Error: Palette 'my_palette' already exists
```

**Solution**: Use a different name or delete the existing palette:

```bash
rm project/palettes/my_palette.yaml
gat project add-palette my_palette scenario_id
```

### System File Not Found

```
Error: System file not found: data/system.json
```

**Solution**: Check that the scenario's system file path is correct and the file exists. You may need to update the scenario configuration.

### No Generators Found

```
Error: System has no generators - cannot generate palette
```

**Solution**: Verify the system file is valid and contains generator components. For Sienna systems, check that components have `__metadata__.type` matching generator types.

### Color Conflicts

If too many categories use similar colors:

**Solution**: Manually edit the palette YAML to assign distinct colors:

```yaml
display_categories:
  - name: Solar
    color: "#FFD700"  # Distinct gold
  - name: Wind
    color: "#4169E1"  # Distinct blue
```

## See Also

- [Palette Model Reference](palette.md) - Detailed palette model documentation
- [Project Management](project_management.md) - Managing projects and scenarios
- [Visualization Guide](visualization.md) - Using palettes in visualizations