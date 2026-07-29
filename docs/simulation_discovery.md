# Simulation Model Discovery in GAT

This document explains how GAT automatically discovers and manages multiple simulation models within Sienna H5 files.

## Overview

Sienna simulation files can contain multiple simulation models in a single H5 file:
- **Emulation Models**: Power flow simulations (e.g., AC-OPF, DC-OPF, PF)
- **Decision Models**: Unit commitment and economic dispatch (e.g., UC, ED, RAUC)

GAT automatically discovers all available simulations when you open a file, eliminating the need for hardcoded model names.

## H5 File Structure

### Emulation Models

Emulation models are stored under `/simulation/emulation_model/` and can be organized in two ways:

#### Pattern A: Single Emulation Model
```
/simulation/emulation_model/
  ├─ attributes:
  │   ├─ name = "PF"                 # Model name from attribute
  │   ├─ base_power = 100
  │   └─ ...
  └─ [datasets and groups]
```

#### Pattern B: Multiple Emulation Models
```
/simulation/emulation_model/
  ├─ AC_OPF/                          # Subgroup name
  │   ├─ attributes:
  │   │   ├─ name = "AC-OPF"         # Model name from attribute
  │   │   └─ ...
  │   └─ [datasets]
  └─ DC_OPF/                          # Subgroup name
      ├─ attributes:
      │   ├─ name = "DC-OPF"         # Model name from attribute
      │   └─ ...
      └─ [datasets]
```

**Key Point**: For emulation models, the model name always comes from the `name` attribute, NOT the group name.

### Decision Models

Decision models are stored under `/simulation/decision_models/`:

```
/simulation/decision_models/
  ├─ UC/                              # Model name = group name
  │   ├─ attributes:
  │   │   └─ ...
  │   └─ [datasets]
  ├─ ED/                              # Model name = group name
  │   └─ [datasets]
  └─ RAUC/                            # Model name = group name
      └─ [datasets]
```

**Key Point**: For decision models, the model name comes from the group name itself.

## Discovery Algorithm

When you create a `SiennaSimulationParser`, GAT automatically:

1. **Scans for emulation models**:
   - Checks if `/simulation/emulation_model` has attributes
   - If yes: single model, reads `name` attribute
   - If no: multiple models, iterates subgroups and reads `name` attribute from each

2. **Scans for decision models**:
   - Iterates through subgroups under `/simulation/decision_models`
   - Uses each subgroup name as the model name

3. **Combines all models** into a single list accessible via `parser.simulation_models`

4. **Sets default simulation**: First emulation model if available, otherwise first decision model

## Usage Examples

### Basic Usage

```python
from gat.simulations import SiennaSimulationParser

# Load file - automatically discovers all simulations
parser = SiennaSimulationParser("simulation.h5")

# See what simulations are available
print(parser.simulation_models)  # ['PF', 'UC', 'ED']

# Default simulation is automatically selected
print(parser.simulation)  # 'PF'

# List datasets for default simulation
datasets = parser.list_datasets()
```

### Working with Specific Simulations

```python
# Method 1: Set the simulation property (recommended)
parser.simulation = "UC"
datasets = parser.list_datasets()
data = parser.get_dataset("generator_dispatch")

# Method 2: Use selected_model property (legacy API, still supported)
parser.selected_model = "ED"
datasets = parser.list_datasets()

# Method 3: Query without changing default (NEW!)
datasets_uc = parser.list_datasets(simulation="UC")
datasets_ed = parser.list_datasets(simulation="ED")

# The default simulation remains unchanged
print(parser.simulation)  # Still 'PF'
```

### Querying Multiple Simulations

```python
# Get data from different simulations without changing default
parser = SiennaSimulationParser("simulation.h5")

for sim_name in parser.simulation_models:
    print(f"\n=== {sim_name} ===")
    datasets = parser.list_datasets(simulation=sim_name)
    print(f"Datasets: {len(datasets)}")
    
    # Load a specific dataset
    data = parser.get_dataset("generator_dispatch", simulation=sim_name)
    print(f"Shape: {data.shape}")

# Default simulation is still the original
print(f"Default: {parser.simulation}")
```

### Error Handling

```python
# Invalid simulation name raises ValueError
try:
    parser.simulation = "INVALID"
except ValueError as e:
    print(e)  # "Model 'INVALID' not found. Available models: UC, ED, PF"

# Must select a simulation before querying
parser._selected_model = None  # Don't do this normally!
try:
    datasets = parser.list_datasets()
except ValueError as e:
    print(e)  # "No simulation model selected..."

# But can still query with simulation parameter
datasets = parser.list_datasets(simulation="UC")  # Works!
```

## Scenario Configuration

When creating scenarios, you can specify which simulation to use:

```bash
# CLI - specify simulation type
gat project scenario add sienna my_scenario \
    --system system.json \
    --simulation simulation.h5 \
    --simulation-type UC

# Or auto-discover and create scenarios for all simulations
gat project scenario add sienna my_scenario \
    --system system.json \
    --simulation simulation.h5
# Creates: my_scenario_UC, my_scenario_ED, my_scenario_PF
```

In Python:

```python
from gat.models import SiennaScenarioConfig

# Explicitly specify simulation type
config = SiennaScenarioConfig(
    name="Test UC",
    system_path="system.json",
    simulation_paths="simulation.h5",
    simulation_type="UC"
)

# Or discover all simulations
simulations = SiennaScenarioConfig.discover_simulations("simulation.h5")
print(simulations)  # ['UC', 'ED', 'PF']

# Create a scenario for each
for sim in simulations:
    config = SiennaScenarioConfig(
        name=f"Test {sim}",
        system_path="system.json",
        simulation_paths="simulation.h5",
        simulation_type=sim
    )
```

## Validation and Debugging

### Explore H5 Structure

Use the exploration script to understand your file's structure:

```bash
python examples/explore_h5_structure.py simulation.h5

# Show full tree
python examples/explore_h5_structure.py simulation.h5 --full-tree
```

### Test Discovery

Use the test script to verify discovery is working correctly:

```bash
python examples/test_simulation_discovery.py simulation.h5
```

### Check Available Simulations

```python
parser = SiennaSimulationParser("simulation.h5")

# Simple check
print(f"Found {len(parser.simulation_models)} simulations:")
for sim in parser.simulation_models:
    parser.simulation = sim
    datasets = parser.list_datasets()
    print(f"  - {sim}: {len(datasets)} datasets")
```

## Best Practices

1. **Always check available simulations first**:
   ```python
   simulations = parser.simulation_models
   if "UC" not in simulations:
       raise ValueError("UC simulation not found in file")
   ```

2. **Use the `simulation` parameter for queries across multiple simulations**:
   ```python
   # Good - doesn't change default
   for sim in parser.simulation_models:
       data = parser.get_dataset("dispatch", simulation=sim)
   
   # Less ideal - changes default each time
   for sim in parser.simulation_models:
       parser.simulation = sim
       data = parser.get_dataset("dispatch")
   ```

3. **Set a default simulation explicitly if needed**:
   ```python
   parser = SiennaSimulationParser("simulation.h5")
   if "UC" in parser.simulation_models:
       parser.simulation = "UC"  # Set preferred default
   ```

4. **Use descriptive names in scenarios**:
   ```python
   # Include simulation type in scenario name
   config = SiennaScenarioConfig(
       name="2035_HighRE_UC",  # Clear what simulation this represents
       system_path="system.json",
       simulation_paths="simulation.h5",
       simulation_type="UC"
   )
   ```

## Migration from Old Code

If you have code using hardcoded model names:

```python
# Old way (hardcoded)
parser = SiennaSimulationParser("simulation.h5")
parser.selected_model = "emulation_model"  # Hardcoded assumption

# New way (auto-discovered)
parser = SiennaSimulationParser("simulation.h5")
# Default is automatically set to first emulation model
# Or query available models:
if parser.config.emulation_models:
    emulation_sims = list(parser.config.emulation_models.keys())
    parser.simulation = emulation_sims[0]
```

## Troubleshooting

### "Model not found" errors

Check what models are actually in the file:
```python
parser = SiennaSimulationParser("simulation.h5")
print("Available:", parser.simulation_models)
```

### Unexpected model names

The model name comes from the H5 file's `name` attribute:
```python
python examples/explore_h5_structure.py simulation.h5
# Look for "name" attributes in the output
```

### No simulations found

The file might not have the expected structure:
```python
python examples/explore_h5_structure.py simulation.h5 --full-tree
# Check if /simulation/emulation_model or /simulation/decision_models exist
```

## Technical Details

### Model Configuration

Each discovered model is represented by a `SiennaModelConfig`:

```python
@dataclass
class SiennaModelConfig:
    root_path: str          # H5 path to model data
    base_power: int         # Base power in MW
    horizon_count: int      # Number of time steps per horizon
    interval_ms: int        # Interval between horizons in ms
    num_executions: int     # Number of execution horizons
    resolution_ms: int      # Time resolution in ms
    system_uuid: str        # Unique system identifier
    name: str              # Model name (from 'name' attribute)
```

### Internal Structure

```python
parser = SiennaSimulationParser("simulation.h5")

# Access internal config
config = parser.config
print(config.emulation_models)  # Dict[str, SiennaModelConfig]
print(config.decision_models)   # Dict[str, SiennaModelConfig]

# Currently selected model
selected = parser.selected_model  # SiennaModelConfig object
print(selected.name)              # Model name
print(selected.root_path)         # H5 path
```

## See Also

- [Simulation Interface Guide](simulation_interface.md)
- [Scenario Management](scenarios.md)
- [Plugin Development](plugin_development.md)