# Python API: Loading Projects and Scenarios

GAT provides a simple `load()` function for loading projects, scenarios, and palettes in Python scripts with smart defaults and helpful guidance.

## Overview

The `gat.load()` function is the primary entry point for loading GAT data in Python. It handles:
- Resolving default projects, scenarios, and palettes
- Loading scenario handlers (SiennaScenario, ReEDsScenario, PlexosScenario)
- Loading palette configurations
- Providing informative logging with usage tips
- Validating that all resources exist

## Quick Start

```python
import gat

# Load with all defaults
scenario, palette, project = gat.load()

# Load specific project and scenario
scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035"
)

# Suppress informative messages
scenario, palette, project = gat.load(verbose=False)
```

### Tuning a loaded scenario

Once you have a scenario object, the most common configuration knobs
are exposed as public properties — no need to reach into private
attributes:

```python
# Map raw model technology names to display groups
scenario.tech_simple.update({
    "NG/CC": "Gas-CC",
    "NG/CT": "Gas-CT",
    "Coal/Steam": "Coal",
})

# Tell the dispatch math that the load timeseries already includes
# storage charging (so it's "Total Demand" rather than "Native Demand")
scenario.load_includes_charging = True

# Override the auto-discovered generator → area mapping
scenario.gen_area_map = {"gen_101": "north", "gen_102": "south"}
```

These also have construction-time equivalents on `ScenarioConfig`
(`technology_mappings`, `load_includes_charging`).

## Function Signature

```python
def load(
    project: Optional[str] = None,
    scenario: Optional[str] = None,
    palette: Optional[str] = None,
    verbose: bool = True,
) -> tuple[ScenarioHandler, Palette | None, ProjectManager]:
    """
    Load a GAT project, scenario, and palette with smart defaults.
    
    Returns:
        tuple: (scenario_object, palette_object, project_manager)
    """
```

## Parameters

### `project` (Optional[str])
- **Default**: `None` (uses default project)
- **Description**: Project ID to load
- **Behavior**:
  - If `None`: Uses default project (set via `gat project set-default`)
  - If provided: Loads specified project
  - Raises `ValueError` if project not found or no default set

**Example:**
```python
# Use default project
scenario, palette, project = gat.load()

# Load specific project
scenario, palette, project = gat.load(project="my-analysis")
```

### `scenario` (Optional[str])
- **Default**: `None` (uses default scenario)
- **Description**: Scenario ID to load
- **Behavior**:
  - If `None`: Uses scenario from project config's `default_scenario` field
  - If no default set: Uses first available scenario
  - If provided: Loads specified scenario
  - Raises `ValueError` if scenario not found

**Example:**
```python
# Use default scenario
scenario, palette, project = gat.load(project="my-analysis")

# Load specific scenario
scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035"
)
```

### `palette` (Optional[str])
- **Default**: `None` (uses default palette)
- **Description**: Palette name to load
- **Behavior**:
  - If `None`: Tries scenario's `default_palette`, then project's `default_palette`, then first available
  - If provided: Loads specified palette
  - Returns `None` if palette not found (logs warning)

**Example:**
```python
# Use default palette
scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035"
)

# Load specific palette
scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035",
    palette="renewable_focus"
)
```

### `verbose` (bool)
- **Default**: `True`
- **Description**: Whether to log informative messages
- **Behavior**:
  - If `True`: Logs info messages about what's being loaded and tips
  - If `False`: Only logs debug messages (suppressed by default)

**Example:**
```python
# With informative messages (default)
scenario, palette, project = gat.load()

# Suppress messages
scenario, palette, project = gat.load(verbose=False)
```

## Return Values

The `load()` function returns a tuple of three objects:

### 1. Scenario Object
A scenario handler instance for interacting with simulation data:
- `SiennaScenario` for Sienna simulations
- `ReEDsScenario` for ReEDS™ simulations
- `PlexosScenario` for Plexos simulations

**Usage:**
```python
scenario, palette, project = gat.load()

# Access scenario data
gen_data = scenario.get_generation_data()
load_data = scenario.get_load_data()
```

### 2. Palette Object
A `Palette` instance containing visualization configuration, or `None` if no palette found.

**Usage:**
```python
scenario, palette, project = gat.load()

if palette:
    print(f"Display categories: {[cat.name for cat in palette.display_categories]}")
    print(f"Stack order: {palette.stack_order}")
```

### 3. Project Manager
A `ProjectManager` instance for accessing project configuration and resources.

**Usage:**
```python
scenario, palette, project = gat.load()

# Access project info
config = project.load_config()
print(f"Project: {config.name}")

# List available scenarios
scenarios = project.list_scenarios()
print(f"Available scenarios: {scenarios}")
```

## Default Resolution Order

### Project Resolution
1. If `project` argument provided → Use specified project
2. Otherwise → Use default project (from user metadata)
3. If no default → Raise error with instructions

### Scenario Resolution
1. If `scenario` argument provided → Use specified scenario
2. Otherwise → Use project's `default_scenario` field
3. If no default → Use first available scenario
4. If no scenarios → Raise error

### Palette Resolution
1. If `palette` argument provided → Use specified palette
2. Otherwise → Try scenario's `default_palette` field
3. If not found → Try project's `default_palette` field
4. If not found → Use first available palette
5. If no palettes → Return `None` (with warning)

## Logging Behavior

### With `verbose=True` (Default)

The function provides informative logging:

```
INFO: Loading default project: 'My Analysis' (my-analysis)
INFO: 💡 To load a specific project, use: gat.load(project='<project-id>')
INFO: Loading default scenario: 'base_2035'
INFO: 💡 To load a specific scenario, use: gat.load(scenario='<scenario-id>')
INFO: Loading scenario's default palette: 'renewable_focus'
INFO: 💡 To load a different palette, use: gat.load(palette='<palette-name>')
INFO: Creating scenario handler for type: sienna
INFO: ✅ Successfully loaded:
INFO:    Project:  My Analysis (my-analysis)
INFO:    Scenario: base_2035 [sienna]
INFO:    Palette:  renewable_focus
INFO: 
INFO: 💡 To suppress these messages, use: gat.load(verbose=False)
INFO: 💡 To reduce all GAT logging: logger.remove(); logger.add(sys.stderr, level='WARNING')
```

### With `verbose=False`

Only debug-level messages are logged (suppressed by default logger configuration).

### Adjusting Logging Globally

To control GAT's logging more broadly:

```python
from loguru import logger
import sys

# Remove default handler
logger.remove()

# Add custom handler with different level
logger.add(sys.stderr, level="WARNING")  # Only warnings and errors
logger.add(sys.stderr, level="ERROR")    # Only errors

# Or completely disable
logger.disable("gat")
```

## Usage Examples

### Example 1: Load Default Everything

```python
import gat

# Load default project, scenario, and palette
scenario, palette, project = gat.load()

# Use scenario to get data
generation = scenario.get_generation_data()
print(generation.head())
```

### Example 2: Load Specific Resources

```python
import gat

# Load specific project and scenario
scenario, palette, project = gat.load(
    project="western-grid-2035",
    scenario="high_renewable",
    palette="presentation"
)

# Create plots with palette
import matplotlib.pyplot as plt
fig, ax = plt.subplots()

# Use palette for colors
colors = {cat.name: cat.color for cat in palette.display_categories}
```

### Example 3: Handle Missing Palettes

```python
import gat

scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035"
)

if palette is None:
    print("No palette available, generating one...")
    # Generate palette from scenario
    import subprocess
    subprocess.run([
        "gat", "project", "palette", "add",
        "default", "base_2035"
    ])
    # Reload with palette
    scenario, palette, project = gat.load(
        project="my-analysis",
        scenario="base_2035",
        palette="default"
    )
```

### Example 4: Iterate Through Scenarios

```python
import gat

# Load project
scenario, palette, project = gat.load(verbose=False)

# Get all scenarios
scenario_ids = project.list_scenarios()

# Process each scenario
for scenario_id in scenario_ids:
    scenario, palette, _ = gat.load(
        scenario=scenario_id,
        verbose=False
    )
    
    # Analyze scenario
    gen_data = scenario.get_generation_data()
    print(f"{scenario_id}: {gen_data['generation'].sum()} MWh")
```

### Example 5: Suppress Messages After Setup

```python
import gat

# First load - see what's happening
print("=== Initial Setup ===")
scenario, palette, project = gat.load()

# Subsequent loads - suppress messages
print("\n=== Processing Data ===")
for scenario_id in ["base", "sensitivity_1", "sensitivity_2"]:
    scenario, palette, _ = gat.load(
        scenario=scenario_id,
        verbose=False  # Suppress messages
    )
    # Process data...
```

### Example 6: Error Handling

```python
import gat

try:
    scenario, palette, project = gat.load(
        project="nonexistent-project"
    )
except ValueError as e:
    print(f"Error: {e}")
    # Shows available projects in error message
```

## Convenience Functions

### `load_scenario_only()`

Load only a scenario (without palette):

```python
import gat

# Load just the scenario
scenario = gat.load_scenario_only(
    project="my-analysis",
    scenario="base_2035"
)

# Use scenario
gen_data = scenario.get_generation_data()
```

**Signature:**
```python
def load_scenario_only(
    project: Optional[str] = None,
    scenario: Optional[str] = None,
    verbose: bool = True,
) -> ScenarioHandler:
```

### `load_palette_only()`

Load only a palette (without scenario):

```python
import gat

# Load just the palette
palette = gat.load_palette_only(
    project="my-analysis",
    palette="renewable_focus"
)

# Inspect palette
for category in palette.display_categories:
    print(f"{category.name}: {category.color}")
```

**Signature:**
```python
def load_palette_only(
    project: Optional[str] = None,
    palette: Optional[str] = None,
    verbose: bool = True,
) -> Palette:
```

## Setting Defaults

### Set Default Project

```bash
# Via CLI
gat project set-default my-analysis
```

### Set Default Scenario

Edit `gat-project.yaml`:

```yaml
name: My Analysis
default_scenario: base_2035  # Add this line
default_palette: default     # Optionally add default palette
```

Or programmatically:

```python
from gat.project_management.manager import ProjectManager
from pathlib import Path

manager = ProjectManager(Path("./my-project"))
config = manager.load_config()
config.default_scenario = "base_2035"
config.default_palette = "default"
manager.save_config(config)
```

### Set Default Palette for Scenario

Edit scenario YAML (e.g., `scenarios/base_2035.yaml`):

```yaml
name: Base 2035 Scenario
type: sienna
default_palette: renewable_focus  # Add this line
system_path: /data/system.json
simulation_paths: /data/results.h5
```

Or via CLI when adding scenario:

```bash
gat project scenario add sienna base_2035 \
    --system ./data/system.json \
    --simulation ./data/results.h5 \
    --default-palette renewable_focus
```

## Common Patterns

### Pattern 1: Analysis Script Template

```python
#!/usr/bin/env python3
"""
Standard analysis script template using gat.load().
"""
import gat
import matplotlib.pyplot as plt

# Load resources
scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035",
    verbose=True  # Show what's being loaded
)

# Perform analysis
generation = scenario.get_generation_data()
total_gen = generation.groupby('category')['generation'].sum()

# Create visualization
fig, ax = plt.subplots(figsize=(10, 6))
colors = {cat.name: cat.color for cat in palette.display_categories}
total_gen.plot(kind='bar', color=colors, ax=ax)

plt.title(f"Total Generation - {scenario.name}")
plt.ylabel("Energy (MWh)")
plt.tight_layout()
plt.savefig("output/generation_summary.png")
print("✓ Saved: output/generation_summary.png")
```

### Pattern 2: Batch Processing

```python
#!/usr/bin/env python3
"""
Process multiple scenarios in batch.
"""
import gat
import pandas as pd

# Get project and scenario list
_, _, project = gat.load(verbose=False)
scenario_ids = project.list_scenarios()

results = []

for scenario_id in scenario_ids:
    print(f"Processing: {scenario_id}")
    
    # Load scenario
    scenario, palette, _ = gat.load(
        scenario=scenario_id,
        verbose=False
    )
    
    # Analyze
    gen_data = scenario.get_generation_data()
    total = gen_data['generation'].sum()
    
    results.append({
        'scenario': scenario_id,
        'total_generation': total
    })

# Save results
df = pd.DataFrame(results)
df.to_csv("output/batch_results.csv", index=False)
print(f"✓ Processed {len(results)} scenarios")
```

### Pattern 3: Interactive Notebook

```python
# Cell 1: Setup
import gat
from IPython.display import display

# Load with verbose logging to see what's available
scenario, palette, project = gat.load()

# Cell 2: Explore
print("Available scenarios:")
for scenario_id in project.list_scenarios():
    print(f"  - {scenario_id}")

print("\nAvailable palettes:")
for palette_name in project.list_palettes():
    print(f"  - {palette_name}")

# Cell 3: Switch scenarios
scenario, palette, _ = gat.load(
    scenario="high_renewable",
    verbose=False  # Suppress messages in notebook
)

# Analyze new scenario
generation = scenario.get_generation_data()
display(generation.head())
```

## Error Messages

### No Default Project

```
ValueError: No default project set. Either:
  1. Set a default: gat project set-default <project-id>
  2. Pass project explicitly: gat.load(project='<project-id>')

Available projects: my-analysis, planning-study, sensitivity
```

### Project Not Found

```
ValueError: Project 'unknown-project' not found. 
Available projects: my-analysis, planning-study
```

### No Scenarios in Project

```
ValueError: Project 'My Analysis' has no scenarios.
Add a scenario with: gat project scenario add
```

### Scenario Not Found

```
ValueError: Scenario 'unknown-scenario' not found in project 'My Analysis'.
Available scenarios: base_2035, high_renewable, sensitivity_1
```

## Best Practices

### 1. Use Verbose Mode During Development

```python
# During development - see what's happening
scenario, palette, project = gat.load(verbose=True)
```

### 2. Suppress Messages in Production

```python
# In production scripts
scenario, palette, project = gat.load(verbose=False)
```

### 3. Set Defaults for Team Consistency

```yaml
# gat-project.yaml
default_scenario: base_2035
default_palette: presentation

# Makes team scripts simpler:
# scenario, palette, project = gat.load()
```

### 4. Validate Resources Before Analysis

```python
import gat

try:
    scenario, palette, project = gat.load()
except ValueError as e:
    print(f"Setup error: {e}")
    exit(1)

if palette is None:
    print("Warning: No palette available")
    # Could generate one or proceed without
```

### 5. Document Required Resources

```python
#!/usr/bin/env python3
"""
Generate annual dispatch plots.

Required:
- Project: western-grid-2035
- Scenario: base_2035 or high_renewable
- Palette: Any (uses default)

Usage:
    python generate_plots.py
"""
import gat

scenario, palette, project = gat.load(
    project="western-grid-2035",
    # scenario uses default
)
```

## See Also

- [Project Management](cli_project_management.md) - Managing projects and scenarios
- [CLI Quick Reference](cli_quick_reference.md) - CLI commands
- [Palette Generation](palette_generation.md) - Creating and customizing palettes
- [Scenario Objects](api/ScenarioObjects/BaseScenario.md) - Using scenario handlers