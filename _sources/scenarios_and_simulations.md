# Scenarios and Simulations in GAT

## Understanding the Concepts

### Simulation vs. Scenario

**Simulation**: A single H5 file from a simulation tool can contain multiple simulation runs with different characteristics:
- **UC** (Unit Commitment) - Commitment decisions for generators
- **ED** (Economic Dispatch) - Economic dispatch without commitment
- **PF** (Power Flow) - AC or DC power flow analysis
- **emulation_model** - High-resolution operational model

**Scenario**: A GAT scenario is defined as:
- System file (topology, generator data, etc.)
- Simulation file(s) (one or more H5 files)
- **Specific simulation type** within those files (UC, ED, PF, etc.)

### Why This Matters

A single Sienna H5 file often contains multiple simulation types. For example:
```
results.h5
├── UC (Unit Commitment)
├── ED (Economic Dispatch)
└── PF (Power Flow)
```

Each simulation type represents a **different analytical scenario**:
- UC results show commitment decisions
- ED results show economic dispatch without commitment
- PF results show detailed power flow analysis

GAT treats each as a separate scenario since you typically want to analyze them independently.

---

## Adding Scenarios

### Option 1: Specify the Simulation Type

Create a single scenario for a specific simulation type:

```bash
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5 \
    --simulation-type UC
```

This creates one scenario:
- **Scenario ID**: `my_case`
- **Name**: `my_case`
- **Simulation Type**: UC

### Option 2: Auto-Discover All Simulation Types

Let GAT discover all simulation types and create separate scenarios:

```bash
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5
```

If `results.h5` contains UC, ED, and PF, this creates three scenarios:
- **Scenario ID**: `my_case_UC`, **Name**: `my_case (UC)`, **Type**: UC
- **Scenario ID**: `my_case_ED`, **Name**: `my_case (ED)`, **Type**: ED
- **Scenario ID**: `my_case_PF`, **Name**: `my_case (PF)`, **Type**: PF

### Naming Convention

When auto-discovering:
- **Scenario IDs** are suffixed with the simulation type: `{base_id}_{UC|ED|PF}`
- **Scenario names** include the type in parentheses: `{base_name} (UC)`

When specifying simulation type:
- Uses your provided scenario ID and name directly

---

## Working with Scenarios

### Loading a Scenario

```python
from gat import load_scenario

# Load a specific scenario
scenario = load_scenario("my_case_UC")

# The parser is automatically set to the UC simulation
data = scenario.parser.get_dataset("generator_dispatch")
```

### Scenario Configuration

Each scenario config includes:

```yaml
name: "my_case (UC)"
type: "sienna"
system_path: "/path/to/system.json"
simulation_paths: "/path/to/results.h5"
simulation_type: "UC"  # Specifies which simulation to use
default_palette: "my_palette"
```

### Multiple Simulation Files

You can have multiple simulation files in one scenario:

```bash
gat project scenario add sienna multi_week \
    --system system.json \
    --simulation week1.h5 \
    --simulation week2.h5 \
    --simulation-type UC
```

All files must contain the specified simulation type.

---

## Use Cases

### Use Case 1: Comparing UC vs ED

Auto-discover to create separate scenarios:

```bash
gat project scenario add sienna base_case \
    --system system.json \
    --simulation results.h5
```

Creates: `base_case_UC` and `base_case_ED`

Then compare:
```python
from gat import load_scenario

uc_scenario = load_scenario("base_case_UC")
ed_scenario = load_scenario("base_case_ED")

uc_dispatch = uc_scenario.parser.get_dataset("generator_dispatch")
ed_dispatch = ed_scenario.parser.get_dataset("generator_dispatch")

# Compare commitment vs dispatch-only
```

### Use Case 2: Workflow Analysis

Analyze a UC → ED → PF workflow:

```bash
# Auto-discover creates all three
gat project scenario add sienna workflow_2035 \
    --system system_2035.json \
    --simulation workflow_results.h5
```

Each stage is its own scenario for independent analysis.

### Use Case 3: Single Simulation Type

You only care about UC results:

```bash
gat project scenario add sienna uc_only \
    --system system.json \
    --simulation results.h5 \
    --simulation-type UC
```

Clean and simple - one scenario, one simulation type.

---

## Listing Scenarios

See all scenarios in your project:

```bash
gat project scenario list
```

Output shows simulation type for each scenario:
```
my_project scenarios:
  my_case_UC       my_case (UC)       sienna    [UC]
  my_case_ED       my_case (ED)       sienna    [ED]
  my_case_PF       my_case (PF)       sienna    [PF]
```

---

## Advanced: Programmatic Access

### Discovering Available Simulations

```python
from gat.models.project import SiennaScenarioConfig

# Discover what's in a file
sim_types = SiennaScenarioConfig.discover_simulations("results.h5")
print(sim_types)  # ['UC', 'ED', 'PF']
```

### Creating Multiple Scenarios Programmatically

```python
from gat.project_management.manager import ProjectManager

manager = ProjectManager("/path/to/project")

# Auto-discover and create all scenarios
configs = manager.add_scenario(
    scenario_id="base_case",
    name="Base Case",
    scenario_type="sienna",
    system_path="/path/to/system.json",
    simulation_paths="/path/to/results.h5",
    auto_discover=True  # Creates multiple scenarios
)

# configs is a list of created scenario configs
for config in configs:
    print(f"Created: {config.name} - {config.simulation_type}")
```

### Specifying Simulation Type

```python
# Create single scenario with specific type
config = manager.add_scenario(
    scenario_id="uc_case",
    name="UC Analysis",
    scenario_type="sienna",
    system_path="/path/to/system.json",
    simulation_paths="/path/to/results.h5",
    simulation_type="UC",  # Specific type
    auto_discover=False
)
```

---

## Best Practices

### 1. Use Auto-Discovery for Multi-Stage Workflows

If your H5 file contains UC → ED → PF workflow results:
```bash
gat project scenario add sienna workflow \
    --system system.json \
    --simulation workflow.h5
# Auto-creates workflow_UC, workflow_ED, workflow_PF
```

### 2. Use Specific Types for Focused Analysis

If you only need UC results:
```bash
gat project scenario add sienna uc_study \
    --system system.json \
    --simulation results.h5 \
    --simulation-type UC
```

### 3. Consistent Naming

Use descriptive base names that work well with suffixes:
- ✅ Good: `base_2035` → `base_2035_UC`, `base_2035_ED`
- ✅ Good: `high_wind` → `high_wind_UC`, `high_wind_ED`
- ❌ Avoid: `case_uc` → `case_uc_UC` (redundant)

### 4. One System, Multiple Simulations

If you have multiple simulation runs with the same system:
```bash
# Auto-discover each
gat project scenario add sienna case_a --system sys.json --simulation a.h5
gat project scenario add sienna case_b --system sys.json --simulation b.h5
gat project scenario add sienna case_c --system sys.json --simulation c.h5
```

---

## Migration from Old Approach

### Old Way (No Simulation Type)

```bash
# Before: Created one scenario, manually select model in code
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5
```

```python
scenario = load_scenario("my_case")
scenario.parser.selected_model = "UC"  # Manual selection
```

### New Way (With Simulation Type)

```bash
# Now: Auto-discover or specify type
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5
# Creates: my_case_UC, my_case_ED, my_case_PF
```

```python
# Scenario is already configured
scenario = load_scenario("my_case_UC")
# Parser.selected_model is already set to "UC"
```

---

## Troubleshooting

### "No simulations discovered"

If auto-discovery fails:
1. Check that the H5 file exists and is valid
2. Try loading directly to see available models:
   ```python
   from gat.simulations import SiennaSimulationParser
   parser = SiennaSimulationParser("results.h5")
   print(parser.simulation_models)
   ```
3. Specify simulation type manually if discovery fails

### "Simulation type not found"

If you specify a simulation type that doesn't exist:
```bash
gat project scenario add sienna test \
    --system sys.json \
    --simulation results.h5 \
    --simulation-type INVALID  # Error!
```

Solution: Check available types first or use auto-discovery.

### Multiple Files, Different Simulation Types

If simulation files have different available simulations:
- Auto-discovery uses the first file to determine types
- All files should contain the specified simulation type
- GAT will warn if files have inconsistent simulation types

---

## Summary

**Key Points:**
- A scenario = system + simulation file(s) + **specific simulation type**
- One H5 file can contain multiple simulation types (UC, ED, PF)
- Each simulation type is typically a separate analytical scenario
- Use `--simulation-type` for specific analysis
- Omit `--simulation-type` to auto-discover and create multiple scenarios

**Quick Reference:**

```bash
# Create one scenario for UC
gat project scenario add sienna case --system sys.json --simulation sim.h5 --simulation-type UC

# Auto-discover all simulations (creates multiple scenarios)
gat project scenario add sienna case --system sys.json --simulation sim.h5
```

**Related Documentation:**
- [Loading Single Simulation Files](loading_single_simulation_file.md)
- [Project Management](cli_project_management.md)
- [Simulation Interface](simulation_interface_quick_reference.md)