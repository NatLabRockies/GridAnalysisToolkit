# Scenario Quick Start Guide

## TL;DR

```bash
# Auto-discover all simulation types in your H5 file
gat project scenario add sienna my_case \
    --system path/to/system.json \
    --simulation path/to/results.h5

# This creates separate scenarios for each simulation type:
# - my_case_UC
# - my_case_ED  
# - my_case_PF
```

---

## Understanding Scenarios

**A scenario is**: System + Simulation Files + Simulation Type

One H5 file often contains multiple simulation types:
- **UC** (Unit Commitment)
- **ED** (Economic Dispatch)
- **PF** (Power Flow)
- **emulation_model** (High-resolution)

Each type is a different analysis scenario.

---

## Two Ways to Add Scenarios

### Option 1: Auto-Discover (Recommended)

Let GAT find all simulation types and create separate scenarios:

```bash
gat project scenario add sienna base_2035 \
    --system data/system_2035.json \
    --simulation data/results_2035.h5
```

**Result**: Creates `base_2035_UC`, `base_2035_ED`, `base_2035_PF`

### Option 2: Specify Simulation Type

Create one scenario for a specific simulation type:

```bash
gat project scenario add sienna base_2035_uc \
    --system data/system_2035.json \
    --simulation data/results_2035.h5 \
    --simulation-type UC
```

**Result**: Creates `base_2035_uc` (uses UC simulation only)

---

## Working with Scenarios

### List Your Scenarios

```bash
gat project scenario list
```

Output shows simulation type:
```
my_project scenarios:
  base_2035_UC    base 2035 (UC)    [sienna] [UC]
  base_2035_ED    base 2035 (ED)    [sienna] [ED]
  base_2035_PF    base 2035 (PF)    [sienna] [PF]
```

### Load a Scenario

```python
from gat import load_scenario

# Load the UC scenario
scenario = load_scenario("base_2035_UC")

# Parser is automatically set to UC
dispatch = scenario.parser.get_dataset("generator_dispatch")
```

No need to manually set `selected_model` anymore!

---

## Common Workflows

### Workflow 1: Analyze Multi-Stage Simulation

You ran UC → ED → PF workflow:

```bash
# Auto-discover creates all three scenarios
gat project scenario add sienna workflow \
    --system system.json \
    --simulation workflow_results.h5
```

Then analyze each independently:
```python
uc = load_scenario("workflow_UC")
ed = load_scenario("workflow_ED")
pf = load_scenario("workflow_PF")
```

### Workflow 2: Compare UC vs ED

```bash
# Auto-discover
gat project scenario add sienna comparison \
    --system system.json \
    --simulation results.h5
```

```python
uc_scenario = load_scenario("comparison_UC")
ed_scenario = load_scenario("comparison_ED")

uc_dispatch = uc_scenario.get_generator_dispatch()
ed_dispatch = ed_scenario.get_generator_dispatch()

# Compare commitment vs dispatch-only
```

### Workflow 3: Focus on One Simulation Type

You only care about UC:

```bash
gat project scenario add sienna uc_analysis \
    --system system.json \
    --simulation results.h5 \
    --simulation-type UC
```

Clean and simple - one scenario.

---

## Multiple Simulation Files

Works with multiple files too:

```bash
# All files must contain the specified simulation type
gat project scenario add sienna multi_week \
    --system system.json \
    --simulation week1.h5 \
    --simulation week2.h5 \
    --simulation week3.h5 \
    --simulation-type UC
```

Or auto-discover across all files:

```bash
gat project scenario add sienna multi_week \
    --system system.json \
    --simulation week1.h5 \
    --simulation week2.h5 \
    --simulation week3.h5
# Creates multi_week_UC, multi_week_ED, etc.
```

---

## What's in a Scenario Config?

Each scenario creates a YAML file like this:

```yaml
name: "base 2035 (UC)"
type: "sienna"
system_path: "/absolute/path/to/system_2035.json"
simulation_paths: "/absolute/path/to/results_2035.h5"
simulation_type: "UC"  # <-- New field!
default_palette: null
```

---

## Tips & Best Practices

### 1. Use Descriptive Base Names

Names should work well with suffixes:

✅ **Good**:
- `base_2035` → `base_2035_UC`, `base_2035_ED`
- `high_wind` → `high_wind_UC`, `high_wind_ED`

❌ **Avoid**:
- `case_uc` → `case_uc_UC` (redundant)

### 2. Auto-Discover for Multi-Stage Workflows

If your simulation has UC → ED → PF stages, auto-discover to get all of them.

### 3. Specify Type for Focused Analysis

If you're only analyzing UC results, specify `--simulation-type UC` to avoid creating unnecessary scenarios.

### 4. Check What's Available First

Not sure what simulation types are in your file?

```python
from gat.models.project import SiennaScenarioConfig

types = SiennaScenarioConfig.discover_simulations("results.h5")
print(types)  # ['UC', 'ED', 'PF']
```

---

## Troubleshooting

### "No simulations discovered"

**Problem**: Auto-discovery didn't find any simulation types.

**Solutions**:
1. Check that H5 file exists and is valid
2. Try loading directly:
   ```python
   from gat.simulations import SiennaSimulationParser
   parser = SiennaSimulationParser("results.h5")
   print(parser.simulation_models)
   ```
3. Specify simulation type manually if discovery fails

### "Simulation type not found"

**Problem**: You specified a type that doesn't exist in the file.

**Solution**: Check available types first or use auto-discovery.

### Multiple Scenarios Created Unexpectedly

**Problem**: Auto-discovery created more scenarios than you wanted.

**Solution**: Use `--simulation-type` to specify which one you need:
```bash
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5 \
    --simulation-type UC  # Only creates UC scenario
```

---

## Migrating Old Scenarios

### Old Approach
```bash
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5

# Then in code:
scenario = load_scenario("my_case")
scenario.parser.selected_model = "UC"  # Manual selection
```

### New Approach
```bash
# Option A: Auto-discover
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5
# Creates: my_case_UC, my_case_ED, my_case_PF

# Option B: Specify type
gat project scenario add sienna my_case \
    --system system.json \
    --simulation results.h5 \
    --simulation-type UC

# Then in code:
scenario = load_scenario("my_case_UC")
# Already configured!
```

**Note**: Old scenarios still work! No breaking changes.

---

## Examples Cheat Sheet

```bash
# Auto-discover all types
gat project scenario add sienna case --system sys.json --simulation sim.h5

# Specify UC only
gat project scenario add sienna case --system sys.json --simulation sim.h5 --simulation-type UC

# Multiple files, auto-discover
gat project scenario add sienna case --system sys.json --simulation s1.h5 --simulation s2.h5

# Multiple files, UC only
gat project scenario add sienna case --system sys.json --simulation s1.h5 --simulation s2.h5 --simulation-type UC

# List scenarios
gat project scenario list

# Show specific scenario
gat project scenario show case_UC
```

---

## Related Documentation

- **[Detailed Guide](scenarios_and_simulations.md)**: Complete explanation of scenarios vs simulations
- **[Loading Files](loading_single_simulation_file.md)**: How to work with simulation files directly
- **[Project Management](cli_project_management.md)**: Full CLI reference
- **[Migration Guide](simulation_refactor_migration.md)**: Updating existing code

---

## Summary

**Key Points**:
- One H5 file can contain multiple simulation types (UC, ED, PF)
- Each type is typically a separate analytical scenario
- Auto-discover to create all scenarios automatically
- Specify `--simulation-type` for focused analysis
- Scenarios are automatically configured when loaded

**Quick Commands**:
```bash
# Auto-discover (recommended)
gat project scenario add sienna case --system sys.json --simulation sim.h5

# Specific type
gat project scenario add sienna case --system sys.json --simulation sim.h5 --simulation-type UC

# List all
gat project scenario list
```

**Questions?** See [scenarios_and_simulations.md](scenarios_and_simulations.md) for more details.