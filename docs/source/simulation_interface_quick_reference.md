# GAT Simulation & System Interface - Quick Reference

## Single File Simulation

```python
from gat.simulations import SiennaSimulationParser

# Open file
parser = SiennaSimulationParser("simulation.h5")

# Select model (if multiple exist)
parser.selected_model = "UC"

# List available datasets
datasets = parser.list_datasets()
# Returns: {"generator_dispatch": "/path/to/data", ...}

# Get a dataset
data = parser.get_dataset("generator_dispatch")
# Returns: DataFrame with DatetimeIndex
```

## Multi-File Simulation (Automatic Aggregation)

```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

# Create aggregator with parallel loading
agg = SimulationAggregator(
    file_paths=["sim1.h5", "sim2.h5", "sim3.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True,      # Use multiprocessing
    max_workers=4       # Number of processes
)

# Same interface as single parser!
agg.selected_model = "UC"
datasets = agg.list_datasets()
data = agg.get_dataset("generator_dispatch")
```

## Merge Strategies (Overlapping Time Periods)

```python
# Strategy 1: "left" - Keep earlier timestamps
# Use for: Sequential simulations where earlier data is "realized"
data = agg.get_dataset("dispatch", merge_strategy="left")

# Strategy 2: "right" - Keep later timestamps  
# Use for: Rolling forecasts where later data is more accurate
data = agg.get_dataset("dispatch", merge_strategy="right")
```

## System Data Access

```python
from gat.datahelpers import SiennaSystem

system = SiennaSystem("system.json")

# List available datasets
datasets = system.list_datasets()
# Returns: {"generators": "generator_data", "loads": "load_data", ...}

# Get dataset
generators = system.get_dataset("generators")

# Get filtered dataset
solar = system.get_dataset("generators", category="Solar_PV")

# Get multiple datasets
data = system.get_datasets("generators", "loads", "system_info")
# Returns: {"generators": DataFrame, "loads": DataFrame, ...}

# Traditional methods still work
categories = system.list_generator_categories()
gen_data = system.get_generator_data()
```

## Creating a Custom Parser

```python
from gat.simulations import BaseSimulationParser
import pandas as pd

class MySimParser(BaseSimulationParser):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        # Initialize/validate file
    
    @property
    def simulation_models(self) -> list[str]:
        return ["default"]  # or ["ED", "UC"] for multi-model
    
    def list_datasets(self) -> dict[str, str]:
        return {
            "generator_dispatch": "/results/generators/power",
            "load_served": "/results/loads/power"
        }
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        # Read data from file
        df = self._read_from_file(key)
        # MUST return DataFrame with DatetimeIndex
        df.index = pd.to_datetime(df.index)
        return df
```

## Using Custom Parser with Aggregator

```python
from gat.simulations import SimulationAggregator

# Works automatically with generic aggregator!
agg = SimulationAggregator(
    file_paths=["sim1/", "sim2/", "sim3/"],
    parser_class=MySimParser,  # Your custom parser
    parallel=True
)

# Same interface as built-in parsers
data = agg.get_dataset("generator_dispatch")
```

## Context Managers (Auto Cleanup)

```python
# Single parser
with SiennaSimulationParser("sim.h5") as parser:
    data = parser.get_dataset("dispatch")
# File automatically closed

# Aggregator
with SimulationAggregator(files, ParserClass) as agg:
    data = agg.get_dataset("dispatch")
# All parsers automatically closed
```

## Multiple Datasets

```python
# Get multiple at once
data = parser.get_datasets(
    "generator_dispatch",
    "generator_commit", 
    "curtailment"
)
# Returns: {"generator_dispatch": DataFrame, ...}
```

## Metadata & Validation

```python
# Get metadata
metadata = parser.get_metadata()
# Returns: {"start_time": "...", "resolution": "1H", ...}

# Validate file
warnings = parser.validate()
for warning in warnings:
    print(f"Warning: {warning}")
```

## Common Patterns

### Pattern 1: Load and Process Multiple Files

```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

with SimulationAggregator(
    file_paths=["day1.h5", "day2.h5", "day3.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True
) as agg:
    agg.selected_model = "UC"
    
    # Get all needed data
    data = agg.get_datasets(
        "generator_dispatch",
        "generator_commit",
        "curtailment"
    )
    
    # Process data
    dispatch = data["generator_dispatch"]
    commit = data["generator_commit"]
    # ... analysis ...
```

### Pattern 2: Discover and Explore Datasets

```python
parser = SiennaSimulationParser("simulation.h5")

# What models are available?
print(f"Models: {parser.simulation_models}")

# Select first model
parser.selected_model = parser.simulation_models[0]

# What data is available?
datasets = parser.list_datasets()
print(f"Found {len(datasets)} datasets:")
for name in datasets:
    print(f"  - {name}")

# Load and inspect first dataset
first_key = list(datasets.keys())[0]
df = parser.get_dataset(first_key)
print(f"{first_key}: {df.shape}")
```

### Pattern 3: System + Simulation

```python
from gat.datahelpers import SiennaSystem
from gat.simulations import SiennaSimulationParser

# Load system
system = SiennaSystem("system.json")
generators = system.get_dataset("generators")

# Load simulation  
parser = SiennaSimulationParser("simulation.h5")
parser.selected_model = "UC"
dispatch = parser.get_dataset("generator_dispatch")

# Join on generator names
result = dispatch.join(generators.set_index('name'))
```

## Error Handling

```python
try:
    parser = SiennaSimulationParser("sim.h5")
    parser.selected_model = "UC"
    data = parser.get_dataset("generator_dispatch")
except FileNotFoundError:
    print("Simulation file not found")
except ValueError as e:
    print(f"Invalid model or dataset: {e}")
except KeyError as e:
    print(f"Dataset not found: {e}")
```

## Performance Tips

1. **Use parallel loading** for 3+ files:
   ```python
   agg = SimulationAggregator(files, ParserClass, parallel=True)
   ```

2. **Adjust worker count** based on CPU cores:
   ```python
   import multiprocessing as mp
   agg = SimulationAggregator(files, ParserClass, max_workers=mp.cpu_count())
   ```

3. **Get multiple datasets at once** instead of individually:
   ```python
   # Good
   data = parser.get_datasets("a", "b", "c")
   
   # Less efficient
   a = parser.get_dataset("a")
   b = parser.get_dataset("b") 
   c = parser.get_dataset("c")
   ```

4. **Use context managers** for automatic cleanup:
   ```python
   with parser:
       data = parser.get_dataset("dispatch")
   ```

## Import Cheatsheet

```python
# Simulation parsers
from gat.simulations import (
    BaseSimulationParser,          # Base class for plugins
    SiennaSimulationParser,         # Sienna/PowerSimulations.jl
    SimulationAggregator,           # Generic multi-file aggregator (parallel)
)

# System parsers
from gat.datahelpers import (
    BaseSystem,                     # Base class for system plugins
    SiennaSystem,                   # Sienna/PowerSystems.jl
    SystemInfo,                     # System metadata model
    GeneratorCategory,              # Generator category model
    LoadCategory,                   # Load category model
)

# Utilities
from gat.simulations.utils import (
    dedup_slices,                   # Time-series deduplication
    block_combination_strategy,     # Type hint for merge strategies
)
```

## Key Requirements for Custom Parsers

### Must Implement
- ✅ `simulation_models` property
- ✅ `list_datasets()` method
- ✅ `get_dataset(key)` method

### Critical Requirements
- ✅ `get_dataset()` MUST return DataFrame with `DatetimeIndex`
- ✅ Dataset keys should be consistent across files
- ✅ Parser class must be pickleable (for parallel loading)

### Optional but Recommended
- ✅ `get_metadata()` - Return simulation metadata
- ✅ `validate()` - Check for issues
- ✅ `close()` - Cleanup resources
- ✅ `selected_model` setter - Handle model selection

## Documentation

- **Plugin Development**: `docs/plugin_development_guide.md`
- **Migration Guide**: `docs/simulation_refactor_migration.md`
- **Full Examples**: `examples/simulation_interface_example.py`
- **API Reference**: See docstrings in source files

## Questions?

1. Check the plugin development guide
2. Review example scripts
3. Open a GitHub issue
4. Contact the GAT team