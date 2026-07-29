# Loading a Single Simulation File

**Quick Answer:** You can load and test a single simulation file directly without creating a full scenario.

## Simplest Method

```python
from gat.simulations import SiennaSimulationParser

# Load the file
parser = SiennaSimulationParser("/path/to/your/simulation.h5")

# Select a model
parser.selected_model = "UC"

# List what's available
datasets = parser.list_datasets()
print(datasets.keys())

# Get a dataset
data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
```

## Step-by-Step Example

```python
from gat.simulations import SiennaSimulationParser

# 1. Load your simulation file
parser = SiennaSimulationParser("results/simulation_1.h5")

# 2. See what models are available
print(parser.simulation_models)
# Output: ['UC', 'ED', 'emulation_model']

# 3. Select the model you want to work with
parser.selected_model = "UC"

# 4. List all available datasets
datasets = parser.list_datasets()

# 5. See what datasets exist
for name in list(datasets.keys())[:10]:  # First 10
    print(name)

# 6. Load a specific dataset
dispatch = parser.get_dataset("ActivePowerVariable__ThermalStandard")

# 7. Work with the data
print(f"Shape: {dispatch.shape}")
print(f"Date range: {dispatch.index.min()} to {dispatch.index.max()}")
print(f"Generators: {list(dispatch.columns)}")
```

## Interactive Exploration (IPython/Jupyter)

```python
# Start IPython or Jupyter
from gat.simulations import SiennaSimulationParser

parser = SiennaSimulationParser("simulation.h5")
parser.simulation_models  # See available models

parser.selected_model = "UC"
datasets = parser.list_datasets()

# Explore
list(datasets.keys())  # See all dataset names

# Load some data
data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
data.head()  # Preview
data.plot()  # Visualize
```

## Using the Test Script

We provide a ready-to-use script:

```bash
# Basic test
python examples/test_simulation_file.py your_simulation.h5

# Test specific model
python examples/test_simulation_file.py your_simulation.h5 --model UC

# Load specific datasets
python examples/test_simulation_file.py your_simulation.h5 --datasets dispatch commit
```

## Comparison: Scenario vs. Direct Loading

### Loading Through Scenario (Full Setup)

```python
from gat.scenariohandlers import SiennaScenario

scenario = SiennaScenario(
    solution_data=["sim1.h5", "sim2.h5"],
    system_file="system.json"
)

# Access through scenario
data = scenario.parser.get_dataset("generator_dispatch")
```

**Use when:** You need full analysis with system data, reports, multiple files

### Direct File Loading (Quick Testing)

```python
from gat.simulations import SiennaSimulationParser

parser = SiennaSimulationParser("sim1.h5")
parser.selected_model = "UC"

data = parser.get_dataset("ActivePowerVariable__ThermalStandard")
```

**Use when:** You want to quickly test, explore datasets, or work with a single file

## Common Dataset Names (Sienna)

```python
# Thermal generation
"ActivePowerVariable__ThermalStandard"
"OnVariable__ThermalStandard"

# Renewable generation
"ActivePowerVariable__RenewableDispatch"
"ActivePowerVariable__RenewableFix"

# Hydro
"ActivePowerVariable__HydroDispatch"

# Storage
"ActivePowerVariable__BatteryDischarge"
"EnergyVariable__Battery"

# System
"ActivePowerVariable__Load"
"ServiceSlackVariable__ReserveUp"
```

## Finding Dataset Names

If you don't know the exact dataset names:

```python
parser = SiennaSimulationParser("simulation.h5")
parser.selected_model = "UC"

# Get all datasets
datasets = parser.list_datasets()

# Search for what you need
thermal = [k for k in datasets.keys() if "Thermal" in k]
print("Thermal datasets:", thermal)

renewable = [k for k in datasets.keys() if "Renewable" in k]
print("Renewable datasets:", renewable)

power = [k for k in datasets.keys() if "Power" in k]
print("Power datasets:", power)
```

## Working with Multiple Files

If you have multiple simulation files and want to test them together:

```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

# Automatically combines multiple files
agg = SimulationAggregator(
    file_paths=["sim1.h5", "sim2.h5", "sim3.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True  # Fast parallel loading
)

# Same interface as single file!
agg.selected_model = "UC"
data = agg.get_dataset("ActivePowerVariable__ThermalStandard")
```

## Tips

1. **Always select a model first** before calling `list_datasets()` or `get_dataset()`
2. **Use context managers** for automatic cleanup:
   ```python
   with SiennaSimulationParser("sim.h5") as parser:
       data = parser.get_dataset("...")
   ```
3. **List datasets first** to see what's available before loading
4. **Use the test script** (`examples/test_simulation_file.py`) for quick exploration

## More Information

- **Complete examples**: `examples/simulation_interface_example.py`
- **Quick reference**: `docs/simulation_interface_quick_reference.md`
- **Detailed guide**: `docs/testing_single_simulation_files.md`
- **API documentation**: See docstrings in `gat/simulations/base.py`
