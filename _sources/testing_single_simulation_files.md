# Testing Single Simulation Files - Quick Start

This guide shows how to load and test a single simulation file directly, without creating a full scenario.

## Basic Usage

### Load a Single Sienna Simulation File

```python
from gat.simulations import SiennaSimulationParser

# Load the file
parser = SiennaSimulationParser("/path/to/your/simulation.h5")

# See what models are available
print("Available models:", parser.simulation_models)

# Select a model (if you have multiple)
parser.selected_model = "UC"  # or "ED", "emulation_model", etc.

# List all available datasets
datasets = parser.list_datasets()
print(f"\nFound {len(datasets)} datasets:")
for name, path in list(datasets.items())[:10]:  # Show first 10
    print(f"  {name}: {path}")

# Get a specific dataset
data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
print(f"\nDataset shape: {data.shape}")
print(f"Date range: {data.index.min()} to {data.index.max()}")
print(f"Generators: {list(data.columns[:5])}")
```

## Interactive Testing in Python/IPython

```python
# Start Python or IPython
from gat.simulations import SiennaSimulationParser
import pandas as pd

# Load your file
parser = SiennaSimulationParser("results/simulation_1.h5")

# Explore what's available
parser.simulation_models
# Output: ['UC', 'ED', 'emulation_model']

parser.selected_model = "UC"

datasets = parser.list_datasets()
list(datasets.keys())[:20]  # See first 20 dataset names

# Get some data
dispatch = parser.get_dataset("ActivePowerVariable__ThermalStandard")
dispatch.head()
dispatch.describe()

# Try different datasets
commit = parser.get_dataset("OnVariable__ThermalStandard")
curtailment = parser.get_dataset("ActivePowerVariable__RenewableDispatch")
```

## Common Workflow: Find and Test Datasets

```python
from gat.simulations import SiennaSimulationParser

# 1. Load the file
parser = SiennaSimulationParser("your_simulation.h5")

# 2. Set the model you want
parser.selected_model = "UC"  # Change to your model

# 3. Get all dataset names
datasets = parser.list_datasets()

# 4. Filter for what you're interested in
thermal_datasets = [k for k in datasets.keys() if "Thermal" in k]
print("Thermal datasets:", thermal_datasets)

renewable_datasets = [k for k in datasets.keys() if "Renewable" in k]
print("Renewable datasets:", renewable_datasets)

power_datasets = [k for k in datasets.keys() if "ActivePower" in k or "Power" in k]
print("Power datasets:", power_datasets)

# 5. Test loading one
if power_datasets:
    df = parser.get_dataset(power_datasets[0])
    print(f"\n{power_datasets[0]}:")
    print(f"  Shape: {df.shape}")
    print(f"  Time range: {df.index.min()} to {df.index.max()}")
    print(f"  Components: {len(df.columns)}")
```

## Testing Multiple Datasets

```python
from gat.simulations import SiennaSimulationParser

parser = SiennaSimulationParser("simulation.h5")
parser.selected_model = "UC"

# Get multiple datasets at once
data = parser.get_datasets(
    "ActivePowerVariable__ThermalStandard",
    "OnVariable__ThermalStandard",
    "ActivePowerVariable__RenewableDispatch"
)

# Access each dataset
thermal_dispatch = data["ActivePowerVariable__ThermalStandard"]
thermal_commit = data["OnVariable__ThermalStandard"]
renewable_dispatch = data["ActivePowerVariable__RenewableDispatch"]

print(f"Thermal dispatch: {thermal_dispatch.shape}")
print(f"Thermal commit: {thermal_commit.shape}")
print(f"Renewable dispatch: {renewable_dispatch.shape}")
```

## Using Context Managers (Auto-Cleanup)

```python
from gat.simulations import SiennaSimulationParser

# File automatically closed when done
with SiennaSimulationParser("simulation.h5") as parser:
    parser.selected_model = "UC"
    
    datasets = parser.list_datasets()
    dispatch = parser.get_dataset("ActivePowerVariable__ThermalStandard")
    
    print(f"Got {len(dispatch)} timesteps")
# Parser automatically closed here
```

## Complete Test Script

Save this as `test_simulation.py`:

```python
#!/usr/bin/env python
"""Test script for loading and exploring a single simulation file."""

import sys
from pathlib import Path
from gat.simulations import SiennaSimulationParser

def test_simulation(file_path: str):
    """Load and explore a simulation file."""
    
    print(f"Loading: {file_path}")
    print("=" * 70)
    
    # Load file
    parser = SiennaSimulationParser(file_path)
    
    # Show available models
    models = parser.simulation_models
    print(f"\nAvailable models ({len(models)}):")
    for model in models:
        print(f"  - {model}")
    
    # Test each model
    for model in models:
        print(f"\n{'=' * 70}")
        print(f"Testing model: {model}")
        print("=" * 70)
        
        parser.selected_model = model
        
        # List datasets
        datasets = parser.list_datasets()
        print(f"\nDatasets in {model}: {len(datasets)}")
        
        # Show first 10
        for i, (name, path) in enumerate(list(datasets.items())[:10]):
            print(f"  {i+1}. {name}")
        
        # Try loading first dataset
        if datasets:
            first_key = list(datasets.keys())[0]
            try:
                df = parser.get_dataset(first_key)
                print(f"\nTest load '{first_key}':")
                print(f"  Shape: {df.shape}")
                print(f"  Time range: {df.index.min()} to {df.index.max()}")
                print(f"  Columns: {len(df.columns)}")
                if len(df.columns) > 0:
                    print(f"  Sample columns: {list(df.columns[:3])}")
            except Exception as e:
                print(f"  Error loading: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_simulation.py <path_to_simulation.h5>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)
    
    test_simulation(file_path)
```

Run it:
```bash
python test_simulation.py /path/to/simulation.h5
```

## Jupyter Notebook Example

```python
# Cell 1: Import and load
from gat.simulations import SiennaSimulationParser
import matplotlib.pyplot as plt

parser = SiennaSimulationParser("simulation.h5")

# Cell 2: Explore
parser.simulation_models

# Cell 3: Select model
parser.selected_model = "UC"
datasets = parser.list_datasets()
list(datasets.keys())

# Cell 4: Load and visualize
dispatch = parser.get_dataset("ActivePowerVariable__ThermalStandard")
dispatch.head()

# Cell 5: Plot
dispatch.sum(axis=1).plot(figsize=(12, 4), title="Total Thermal Dispatch")
plt.ylabel("Power (MW)")
plt.show()

# Cell 6: Check specific generator
gen_name = dispatch.columns[0]
dispatch[gen_name].plot(figsize=(12, 4), title=f"{gen_name} Dispatch")
plt.ylabel("Power (MW)")
plt.show()
```

## Comparison: Scenario vs Direct Loading

### Using a Scenario (Full setup)
```python
from gat.scenariohandlers import SiennaScenario

scenario = SiennaScenario(
    solution_data=["sim1.h5", "sim2.h5", "sim3.h5"],
    system_file="system.json"
)

# Access through scenario
data = scenario.parser.get_dataset("generator_dispatch")
```

### Direct Loading (Quick testing)
```python
from gat.simulations import SiennaSimulationParser

# Just load one file directly
parser = SiennaSimulationParser("sim1.h5")
parser.selected_model = "UC"

# Test methods immediately
datasets = parser.list_datasets()
data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
```

**When to use each:**
- **Scenario**: Full analysis with system data, multiple files, reports
- **Direct**: Quick testing, exploring datasets, debugging, single file analysis

## Testing Multiple Files

If you want to test multiple files together without a full scenario:

```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

# Load multiple files with automatic combining
agg = SimulationAggregator(
    file_paths=["sim1.h5", "sim2.h5", "sim3.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True  # Fast parallel loading
)

# Same interface as single file!
agg.selected_model = "UC"
datasets = agg.list_datasets()
data = agg.get_dataset("ActivePowerVariable__ThermalStandard")

print(f"Combined data shape: {data.shape}")
print(f"Time range: {data.index.min()} to {data.index.max()}")
```

## Common Issues and Solutions

### Issue: "No simulation model selected"
```python
# Error
parser = SiennaSimulationParser("sim.h5")
data = parser.get_dataset("some_dataset")  # Error!

# Solution: Select a model first
parser.selected_model = "UC"
data = parser.get_dataset("some_dataset")  # Works!
```

### Issue: Dataset key not found
```python
# Error
data = parser.get_dataset("wrong_name")  # KeyError!

# Solution: List datasets first
datasets = parser.list_datasets()
print(list(datasets.keys()))  # See what's available

# Then use correct name
data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
```

### Issue: Don't know which model to use
```python
# Check available models
parser = SiennaSimulationParser("sim.h5")
print(parser.simulation_models)

# Usually you want:
# - "UC" for unit commitment
# - "ED" for economic dispatch  
# - "emulation_model" for high-resolution results
```

## Quick Reference

```python
# 1. Load file
from gat.simulations import SiennaSimulationParser
parser = SiennaSimulationParser("file.h5")

# 2. Explore
parser.simulation_models              # List available models
parser.selected_model = "UC"          # Select a model
parser.list_datasets()                # List all datasets

# 3. Get data
data = parser.get_dataset("key")      # Single dataset
data = parser.get_datasets("a", "b")  # Multiple datasets

# 4. Metadata
parser.get_metadata()                 # File metadata
parser.validate()                     # Check for issues
```

## Next Steps

Once you've tested with a single file and understand the available datasets:

1. **Move to scenarios** for full analysis with system data
2. **Use aggregator** for multiple files
3. **Build analysis scripts** using the dataset keys you discovered
4. **Create visualizations** with the data you loaded

See also:
- `docs/plugin_development_guide.md` - For creating custom parsers
- `docs/simulation_interface_quick_reference.md` - API reference
- `examples/simulation_interface_example.py` - More examples