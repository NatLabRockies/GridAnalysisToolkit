# GAT Plugin Development Guide

This guide explains how to extend GAT to support new simulation tools and system formats.

## Table of Contents

- [Overview](#overview)
- [Simulation Parsers](#simulation-parsers)
- [System Parsers](#system-parsers)
- [Automatic Multi-File Aggregation](#automatic-multi-file-aggregation)
- [Best Practices](#best-practices)
- [Examples](#examples)

---

## Overview

GAT uses a plugin architecture that allows developers to add support for new simulation tools and system formats without modifying the core codebase. The architecture consists of:

1. **Base Interfaces**: Abstract classes that define the required API
2. **Concrete Implementations**: Plugin implementations for specific tools (Sienna, ReEDS, PLEXOS, etc.)
3. **Automatic Aggregation**: GAT handles combining multiple files transparently

### Key Design Principles

- **Single File Focus**: Plugin developers implement parsers for ONE simulation file
- **Consistent Interface**: All parsers expose the same methods (`list_datasets()`, `get_dataset()`)
- **Automatic Scaling**: GAT handles multi-file scenarios with parallel loading
- **GIL Avoidance**: Multi-file aggregation uses multiprocessing for true parallelism

---

## Simulation Parsers

Simulation parsers read results from power system simulations and provide time-series data.

### Required Interface

All simulation parsers must inherit from `BaseSimulationParser` and implement:

```python
from gat.simulations import BaseSimulationParser
import pandas as pd
from typing import Dict, List

class MySimulationParser(BaseSimulationParser):
    
    def __init__(self, file_path: str):
        """Initialize parser for a single simulation file."""
        super().__init__()
        self.file_path = file_path
        # Open file, validate, extract metadata
    
    @property
    def simulation_models(self) -> List[str]:
        """Return list of available model names."""
        return ["default"]  # or ["ED", "UC", "emulation"] for multi-model tools
    
    def list_datasets(self) -> Dict[str, str]:
        """Return {friendly_name: internal_path} for all datasets."""
        return {
            "generator_dispatch": "/results/generators/power",
            "generator_commit": "/results/generators/status",
            "load_served": "/results/loads/power"
        }
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        """Return dataset as DataFrame with DatetimeIndex."""
        # Read from file (HDF5, CSV, database, etc.)
        df = self._read_from_file(key)
        # Ensure datetime index
        df.index = pd.to_datetime(df.index)
        return df
```

### Key Requirements

#### 1. DatetimeIndex

All datasets **must** return a pandas DataFrame with a `DatetimeIndex`:

```python
#                      Gen1  Gen2  Gen3
# 2024-01-01 00:00:00  100.0  50.0  75.0
# 2024-01-01 01:00:00  110.0  55.0  80.0
# 2024-01-01 02:00:00  105.0  52.0  78.0
```

This is critical for automatic time-series aggregation across multiple files.

#### 2. Consistent Dataset Keys

Use descriptive, stable keys that work across all files:

✅ **Good**: `"generator_dispatch"`, `"curtailment"`, `"load_served"`  
❌ **Bad**: `"gen_1_power"`, `"output_file_3"`, `"data"`

#### 3. Unit Scaling

Apply any necessary unit conversions in `get_dataset()`:

```python
def get_dataset(self, key: str) -> pd.DataFrame:
    df = self._read_raw_data(key)
    
    # Convert per-unit to MW
    if self.unit_system == "per_unit":
        df = df * self.base_power_mva
    
    return df
```

### Optional Methods

#### Model Selection

If your simulation tool produces multiple model types (e.g., day-ahead, real-time), implement model selection:

```python
@property
def selected_model(self) -> Optional[str]:
    """Get currently selected model name."""
    return self._selected_model

@selected_model.setter
def selected_model(self, model_name: Optional[str]):
    """Set selected model with validation."""
    if model_name not in self.simulation_models:
        raise ValueError(f"Model '{model_name}' not found")
    self._selected_model = model_name
    # Update internal state to read from correct model
```

#### Metadata

Provide useful metadata about the simulation:

```python
def get_metadata(self) -> Dict[str, Any]:
    """Return simulation metadata."""
    return {
        "start_time": "2024-01-01T00:00:00",
        "end_time": "2024-12-31T23:00:00",
        "resolution": "1H",
        "software": "MySimTool v2.1",
        "solver": "HiGHS"
    }
```

#### Validation

Implement validation to catch common issues:

```python
def validate(self) -> List[str]:
    """Validate file and return warnings."""
    warnings = []
    
    if not self._has_required_datasets():
        warnings.append("Missing required datasets")
    
    if self._has_time_gaps():
        warnings.append("Time series has gaps")
    
    return warnings
```

#### Resource Cleanup

If your parser maintains open file handles, implement cleanup:

```python
def close(self):
    """Close file handles."""
    if hasattr(self, '_file_handle'):
        self._file_handle.close()

# Bonus: context manager support (inherited from base)
with MySimulationParser("sim.h5") as parser:
    data = parser.get_dataset("generator_dispatch")
# File automatically closed
```

---

## System Parsers

System parsers read power system topology and component data (generators, loads, buses, etc.).

### Required Interface

All system parsers must inherit from `BaseSystem` and implement:

```python
from gat.datahelpers import BaseSystem, SystemInfo, GeneratorCategory, LoadCategory
import pandas as pd
from typing import List, Optional

class MySystemParser(BaseSystem):
    
    def __init__(self, system_path: str):
        """Initialize system parser."""
        super().__init__(system_path)
        # Read and parse system file
    
    def get_system_info(self) -> SystemInfo:
        """Return basic system information."""
        return SystemInfo(
            name="My Test System",
            base_power=100.0,  # MVA
            num_generators=150,
            num_buses=73,
            num_loads=42
        )
    
    def list_generator_categories(self) -> List[GeneratorCategory]:
        """Return list of generator categories."""
        return [
            GeneratorCategory(
                name="Solar_PV",
                display_name="Solar PV",
                fuel_type="Solar",
                count=45,
                total_capacity=2500.0,  # MW
                is_vre=True,
                is_curtailable=True
            ),
            GeneratorCategory(
                name="Gas_CT",
                display_name="Gas Combustion Turbine",
                fuel_type="Natural Gas",
                prime_mover="CT",
                count=12,
                total_capacity=1200.0
            )
        ]
    
    def list_load_categories(self) -> List[LoadCategory]:
        """Return list of load categories."""
        return [
            LoadCategory(
                name="fixed_load",
                display_name="Fixed Load",
                count=42
            )
        ]
    
    def get_generator_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """Return detailed generator data."""
        df = self._read_generators()
        
        if category:
            df = df[df['category'] == category]
        
        return df
    
    def get_load_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """Return detailed load data."""
        df = self._read_loads()
        
        if category:
            df = df[df['category'] == category]
        
        return df
```

### Dataset Interface

System parsers automatically support the dataset interface:

```python
# List available datasets
datasets = system.list_datasets()
# Returns: {"generators": "generator_data", "loads": "load_data", ...}

# Get a dataset
df = system.get_dataset("generators")

# Get multiple datasets
data = system.get_datasets("generators", "loads")
# Returns: {"generators": DataFrame, "loads": DataFrame}

# Get with filters
df = system.get_dataset("generators", category="Solar_PV")
```

### Generator Categories

Categories are used for palette generation and visualization. Classify generators based on your platform's conventions:

```python
GeneratorCategory(
    name="Wind_Offshore",           # Unique identifier
    display_name="Offshore Wind",   # Human-readable
    fuel_type="Wind",               # Fuel classification
    prime_mover="WT",               # Prime mover type
    technology="Type 4",            # Technology details
    count=8,                        # Number of units
    total_capacity=800.0,           # Total MW
    is_vre=True,                    # Variable renewable
    is_storage=False,               # Storage flag
    is_curtailable=True             # Can be curtailed
)
```

---

## Automatic Multi-File Aggregation

GAT automatically handles combining multiple simulation files through the `SimulationAggregator` class.

### How It Works

1. **Plugin Developer**: Implements parser for **one** file
2. **GAT**: Creates aggregator for **multiple** files
3. **User**: Gets transparent access to combined data

```python
# Single file (plugin developer's implementation)
parser = MySimulationParser("simulation_1.h5")

# Multiple files (GAT's automatic aggregation)
from gat.simulations import SimulationAggregator

aggregator = SimulationAggregator(
    file_paths=["sim_1.h5", "sim_2.h5", "sim_3.h5"],
    parser_class=MySimulationParser,
    parallel=True  # Use multiprocessing
)

# Same interface!
datasets = aggregator.list_datasets()
data = aggregator.get_dataset("generator_dispatch")
```

### Parallel Loading

The aggregator uses `multiprocessing` to avoid Python's Global Interpreter Lock (GIL):

```python
aggregator = SimulationAggregator(
    file_paths=file_list,
    parser_class=MySimulationParser,
    parallel=True,           # Enable parallel loading
    max_workers=4            # Number of processes
)
```

Benefits:
- True parallelism (not limited by GIL)
- Faster loading for large file sets
- Automatic fallback to sequential if parallel fails

### Time-Series Deduplication

When combining multiple files, GAT automatically handles overlapping time periods:

```python
# Get data with merge strategy
data = aggregator.get_dataset(
    "generator_dispatch",
    merge_strategy="left"  # or "right"
)
```

**Merge Strategies:**

- `"left"`: Keep earlier timestamps, remove future overlap (typical for multi-stage simulations)
- `"right"`: Keep later timestamps, remove previous overlap (typical for rolling forecasts)

Example:
```
File 1: |-----|xxxxx|              (x = removed)
File 2:       |-----|xxxxx|
File 3:             |-----|-----|  (kept)

Result: |-----|-----|-----|-----| 
```

### Model Selection

Model selection applies to all files in the aggregator:

```python
aggregator.selected_model = "UC"  # Sets model for ALL parsers

# All subsequent operations use the UC model
data = aggregator.get_dataset("generator_commit")
```

---

## Best Practices

### 1. Error Handling

Provide helpful error messages:

```python
def get_dataset(self, key: str) -> pd.DataFrame:
    try:
        return self._read_dataset(key)
    except KeyError:
        available = ', '.join(self.list_datasets().keys())
        raise KeyError(
            f"Dataset '{key}' not found. Available: {available}"
        )
    except Exception as e:
        raise ValueError(f"Failed to read '{key}': {e}")
```

### 2. Logging

Use `loguru` for informative logging:

```python
from loguru import logger

def __init__(self, file_path: str):
    logger.info(f"Loading simulation: {file_path}")
    
    if not self._is_valid_format():
        logger.error(f"Invalid file format: {file_path}")
        raise ValueError("Invalid format")
    
    logger.debug(f"Found {len(self.simulation_models)} models")
```

### 3. Lazy Loading

Don't read entire files in `__init__()`. Load data on-demand:

```python
def __init__(self, file_path: str):
    self.file_path = file_path
    self._cache = {}
    # Don't read data yet!

def get_dataset(self, key: str) -> pd.DataFrame:
    # Load on first access
    if key not in self._cache:
        self._cache[key] = self._read_from_file(key)
    return self._cache[key]
```

### 4. Input Validation

Validate inputs early:

```python
def __init__(self, file_path: str):
    if not Path(file_path).exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    if not self._is_valid_format(file_path):
        raise ValueError(f"Invalid format: {file_path}")
```

### 5. Testing

Test your parser thoroughly:

```python
def test_parser():
    parser = MySimulationParser("test_simulation.h5")
    
    # Test interface methods
    assert len(parser.simulation_models) > 0
    assert len(parser.list_datasets()) > 0
    
    # Test data retrieval
    df = parser.get_dataset("generator_dispatch")
    assert isinstance(df.index, pd.DatetimeIndex)
    assert not df.empty
    
    # Test with aggregator
    aggregator = SimulationAggregator(
        ["test_1.h5", "test_2.h5"],
        MySimulationParser
    )
    combined = aggregator.get_dataset("generator_dispatch")
    assert combined.shape[0] > df.shape[0]
```

---

## Examples

### Example 1: CSV-Based Simulation Parser

```python
from gat.simulations import BaseSimulationParser
import pandas as pd
from pathlib import Path

class CSVSimulationParser(BaseSimulationParser):
    """Parser for CSV-based simulation results."""
    
    def __init__(self, directory_path: str):
        super().__init__()
        self.directory = Path(directory_path)
        
        if not self.directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory_path}")
        
        # Find all CSV files
        self.csv_files = {
            f.stem: f for f in self.directory.glob("*.csv")
        }
    
    @property
    def simulation_models(self) -> list[str]:
        return ["default"]
    
    def list_datasets(self) -> dict[str, str]:
        """List CSV files as datasets."""
        return {name: str(path) for name, path in self.csv_files.items()}
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        """Read CSV file."""
        if key not in self.csv_files:
            raise KeyError(f"Dataset '{key}' not found")
        
        df = pd.read_csv(self.csv_files[key], index_col=0, parse_dates=True)
        return df
```

### Example 2: Database Simulation Parser

```python
from gat.simulations import BaseSimulationParser
import pandas as pd
import sqlalchemy as sa

class DatabaseSimulationParser(BaseSimulationParser):
    """Parser for simulation results stored in a database."""
    
    def __init__(self, connection_string: str):
        super().__init__()
        self.engine = sa.create_engine(connection_string)
        
        # Read available tables
        inspector = sa.inspect(self.engine)
        self.tables = inspector.get_table_names()
    
    @property
    def simulation_models(self) -> list[str]:
        return ["default"]
    
    def list_datasets(self) -> dict[str, str]:
        """List database tables as datasets."""
        return {table: table for table in self.tables}
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        """Query database table."""
        query = f"SELECT * FROM {key} ORDER BY timestamp"
        df = pd.read_sql(query, self.engine, index_col='timestamp', parse_dates=['timestamp'])
        return df
    
    def close(self):
        """Close database connection."""
        self.engine.dispose()
```

### Example 3: Multi-Model HDF5 Parser

```python
from gat.simulations import BaseSimulationParser
import pandas as pd
import h5py

class MultiModelParser(BaseSimulationParser):
    """Parser supporting multiple model types in one file."""
    
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
        
        with h5py.File(file_path, 'r') as f:
            # Discover available models
            self._models = list(f.keys())
        
        # Set default model
        if self._models:
            self.selected_model = self._models[0]
    
    @property
    def simulation_models(self) -> list[str]:
        return self._models
    
    @property
    def selected_model(self) -> str:
        return self._selected_model
    
    @selected_model.setter
    def selected_model(self, model_name: str):
        if model_name not in self._models:
            raise ValueError(f"Model '{model_name}' not found")
        self._selected_model = model_name
    
    def list_datasets(self) -> dict[str, str]:
        """List datasets in selected model."""
        with h5py.File(self.file_path, 'r') as f:
            model_group = f[self._selected_model]
            return {
                name: f"{self._selected_model}/{name}"
                for name in model_group.keys()
                if isinstance(model_group[name], h5py.Dataset)
            }
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        """Read dataset from selected model."""
        datasets = self.list_datasets()
        
        if key in datasets:
            h5_path = datasets[key]
        else:
            h5_path = key
        
        with h5py.File(self.file_path, 'r') as f:
            data = f[h5_path][:]
            
            # Get timestamp data
            timestamps = f[f"{self._selected_model}/timestamps"][:]
            
            df = pd.DataFrame(data, index=pd.to_datetime(timestamps))
        
        return df
```

---

## Summary

**For Simulation Parsers:**
1. Inherit from `BaseSimulationParser`
2. Implement `simulation_models`, `list_datasets()`, `get_dataset()`
3. Return DataFrames with `DatetimeIndex`
4. GAT handles multi-file aggregation automatically

**For System Parsers:**
1. Inherit from `BaseSystem`
2. Implement system info and category methods
3. Provide generator/load data methods
4. Dataset interface is automatic

**Key Benefits:**
- Plugin developers only handle single files
- GAT provides parallel multi-file loading
- Consistent interface across all tools
- True parallelism via multiprocessing