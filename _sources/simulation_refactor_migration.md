# Migration Guide: Simulation and System Interface Refactor

This guide helps you update code to use GAT's refactored simulation and system interfaces.

> **Note (Phase 10):** `SiennaSimulationAggregator` has been **removed** —
> the snippets below labeled "still works" in earlier revisions of this
> guide are now historical. Use
> `SimulationAggregator(parser_class=SiennaSimulationParser)` exclusively.

## Table of Contents

- [Overview](#overview)
- [What Changed](#what-changed)
- [Migration Steps](#migration-steps)
- [Before and After Examples](#before-and-after-examples)
- [Breaking Changes](#breaking-changes)
- [New Features](#new-features)

---

## Overview

GAT's simulation and system interfaces have been refactored to provide:

1. **Consistent API**: Both simulations and systems now expose `list_datasets()` and `get_dataset()` methods
2. **Generic Aggregation**: New `SimulationAggregator` works with any parser type
3. **Parallel Loading**: Multi-file scenarios load faster with multiprocessing
4. **Plugin-Friendly**: Easier to add support for new simulation tools

**Timeline**: This refactor is live as of version X.Y.Z

**Compatibility**: Most existing code will continue to work, but some deprecated patterns should be updated.

---

## What Changed

### Simulation Parsers

#### New Base Interface

```python
# New standardized interface
class BaseSimulationParser(ABC):
    @property
    @abstractmethod
    def simulation_models(self) -> List[str]:
        """List available models"""
        
    @abstractmethod
    def list_datasets(self) -> Dict[str, str]:
        """List available datasets"""
        
    @abstractmethod
    def get_dataset(self, key: str) -> pd.DataFrame:
        """Get a dataset"""
```

#### Generic Aggregator

```python
# New generic aggregator (works with any parser)
from gat.simulations import SimulationAggregator

aggregator = SimulationAggregator(
    file_paths=["sim1.h5", "sim2.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True
)
```

### System Parsers

#### Dataset Interface Added

```python
# New methods on BaseSystem
class BaseSystem(ABC):
    def list_datasets(self) -> Dict[str, str]:
        """List available datasets"""
        
    def get_dataset(self, key: str, **kwargs) -> pd.DataFrame:
        """Get a dataset"""
        
    def get_datasets(self, *keys: str) -> Dict[str, pd.DataFrame]:
        """Get multiple datasets"""
```

---

## Migration Steps

### Step 1: Update Imports

**Before:**
```python
from gat.datahelpers.sienna import SiennaSimulationAggregator
```

**After:**
```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser
```

### Step 2: Update Aggregator Creation (Optional)

**Before:**
```python
from gat.simulations import SiennaSimulationAggregator

aggregator = SiennaSimulationAggregator(
    file_paths=["sim1.h5", "sim2.h5", "sim3.h5"]
)
```

**After (recommended):**
```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

aggregator = SimulationAggregator(
    file_paths=["sim1.h5", "sim2.h5", "sim3.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True  # Enable parallel loading
)
```

### Step 3: Update System Data Access (Optional)

**Before:**
```python
system = SiennaSystem("system.json")
generators = system.get_generator_data()
loads = system.get_load_data()
```

**After (recommended):**
```python
system = SiennaSystem("system.json")

# New unified interface
generators = system.get_dataset("generators")
loads = system.get_dataset("loads")

# Or get multiple at once
data = system.get_datasets("generators", "loads")
```

**After (compatible):**
```python
# Old methods still work
system = SiennaSystem("system.json")
generators = system.get_generator_data()
loads = system.get_load_data()
```

### Step 4: Update Custom Parsers

If you have custom simulation parsers, update them to follow the new interface:

**Before:**
```python
class MyParser:
    def get_data(self, dataset_name):
        # Custom implementation
        pass
```

**After:**
```python
from gat.simulations import BaseSimulationParser

class MyParser(BaseSimulationParser):
    @property
    def simulation_models(self) -> List[str]:
        return ["default"]
    
    def list_datasets(self) -> Dict[str, str]:
        return {"power": "/results/power"}
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        # Implementation
        pass
```

---

## Before and After Examples

### Example 1: Loading Multiple Simulation Files

**Before:**
```python
from gat.simulations import SiennaSimulationAggregator

# Sienna-specific aggregator
agg = SiennaSimulationAggregator(
    file_paths=["day1.h5", "day2.h5", "day3.h5"]
)

# Set model
agg.selected_model = "UC"

# Get data
datasets = agg.list_datasets()
dispatch = agg.get_dataset("generator_dispatch")
```

**After:**
```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

# Generic aggregator with parallel loading
agg = SimulationAggregator(
    file_paths=["day1.h5", "day2.h5", "day3.h5"],
    parser_class=SiennaSimulationParser,
    parallel=True,  # NEW: Parallel loading
    max_workers=4   # NEW: Control parallelism
)

# Set model (same API)
agg.selected_model = "UC"

# Get data (same API)
datasets = agg.list_datasets()
dispatch = agg.get_dataset(
    "generator_dispatch",
    merge_strategy="left"  # NEW: Control overlap handling
)
```

### Example 2: Single File Parser

**Before:**
```python
from gat.simulations import SiennaSimulationParser

parser = SiennaSimulationParser("simulation.h5")
parser.selected_model = "ED"

data = parser.get_dataset("ActivePowerTimeSeriesParameter__RenewableDispatch")
```

**After:**
```python
from gat.simulations import SiennaSimulationParser

# API is unchanged!
parser = SiennaSimulationParser("simulation.h5")
parser.selected_model = "ED"

data = parser.get_dataset("ActivePowerTimeSeriesParameter__RenewableDispatch")
```

### Example 3: System Data Access

**Before:**
```python
from gat.datahelpers import SiennaSystem

system = SiennaSystem("system.json")

# Get data using specific methods
generators = system.get_generator_data()
solar_gens = system.get_generator_data(category="Solar_PV")

# Get categories
categories = system.list_generator_categories()
```

**After:**
```python
from gat.datahelpers import SiennaSystem

system = SiennaSystem("system.json")

# New unified dataset interface
generators = system.get_dataset("generators")
solar_gens = system.get_dataset("generators", category="Solar_PV")

# Or use specific methods (still work)
generators = system.get_generator_data()
solar_gens = system.get_generator_data(category="Solar_PV")

# Categories unchanged
categories = system.list_generator_categories()

# NEW: List all available datasets
datasets = system.list_datasets()
# Returns: {"generators": "generator_data", "loads": "load_data", ...}

# NEW: Get multiple datasets at once
data = system.get_datasets("generators", "loads", "system_info")
```

### Example 4: Creating a Scenario

**Before:**
```python
from gat.scenariohandlers import SiennaScenario

scenario = SiennaScenario(
    solution_data=["sim1.h5", "sim2.h5"],
    system_file="system.json"
)

# Access parser
dispatch = scenario.parser.get_dataset("generator_dispatch")
```

**After:**
```python
from gat.scenariohandlers import SiennaScenario

# API unchanged - aggregation happens automatically
scenario = SiennaScenario(
    solution_data=["sim1.h5", "sim2.h5"],
    system_file="system.json"
)

# Parser is now using new aggregator internally
# (transparent to user)
dispatch = scenario.parser.get_dataset("generator_dispatch")
```

### Example 5: Custom Parser Plugin

**Before:**
```python
# No standard interface - custom implementation
class MySimParser:
    def __init__(self, path):
        self.path = path
    
    def read_dispatch(self):
        return pd.read_csv(self.path)
```

**After:**
```python
from gat.simulations import BaseSimulationParser
import pandas as pd

class MySimParser(BaseSimulationParser):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
    
    @property
    def simulation_models(self) -> list[str]:
        return ["default"]
    
    def list_datasets(self) -> dict[str, str]:
        return {
            "generator_dispatch": "dispatch.csv",
            "generator_commit": "commit.csv"
        }
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        datasets = self.list_datasets()
        if key not in datasets:
            raise KeyError(f"Dataset '{key}' not found")
        
        file_path = datasets[key]
        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
        return df

# Now works with generic aggregator!
from gat.simulations import SimulationAggregator

agg = SimulationAggregator(
    file_paths=["sim1/", "sim2/", "sim3/"],
    parser_class=MySimParser,
    parallel=True
)
```

---

## Breaking Changes

### Minimal Breaking Changes

The refactor was designed to be **backward compatible**. Most existing code will continue to work.

#### Parser Class Must Be Pickleable (for parallel loading)

If using parallel loading, your parser class must be pickleable:

```python
# ✅ Good - pickleable
class GoodParser(BaseSimulationParser):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
        # Don't store unpickleable objects in __init__

# ❌ Bad - not pickleable
class BadParser(BaseSimulationParser):
    def __init__(self, path: str):
        super().__init__()
        self.file_handle = open(path, 'rb')  # File handles aren't pickleable
```

**Solution**: Open files in methods, not `__init__()`:

```python
class GoodParser(BaseSimulationParser):
    def __init__(self, path: str):
        super().__init__()
        self.path = path
    
    def get_dataset(self, key: str) -> pd.DataFrame:
        with open(self.path, 'rb') as f:
            # Use file handle here
            pass
```

#### Import Paths Changed

Some imports have moved:

```python
# ❌ Old (removed in Phase 10)
from gat.datahelpers.sienna import SiennaSimulationAggregator
from gat.simulations import SiennaSimulationAggregator

# ✅ New
from gat.simulations import SimulationAggregator, SiennaSimulationParser
```

---

## New Features

### 1. Parallel File Loading

Speed up multi-file scenarios with parallel loading:

```python
from gat.simulations import SimulationAggregator, SiennaSimulationParser

# Load 10 files in parallel
agg = SimulationAggregator(
    file_paths=[f"sim_{i}.h5" for i in range(10)],
    parser_class=SiennaSimulationParser,
    parallel=True,      # Enable parallel loading
    max_workers=4       # Use 4 processes
)
```

**Performance**: ~4x faster for 10 files on a 4-core system

### 2. Merge Strategy Control

Control how overlapping time periods are handled:

```python
# Keep earlier timestamps (typical for multi-stage sims)
data = agg.get_dataset("dispatch", merge_strategy="left")

# Keep later timestamps (typical for rolling forecasts)
data = agg.get_dataset("dispatch", merge_strategy="right")
```

### 3. Context Manager Support

Automatic resource cleanup:

```python
with SiennaSimulationParser("sim.h5") as parser:
    data = parser.get_dataset("dispatch")
# File automatically closed

with SimulationAggregator(files, SiennaSimulationParser) as agg:
    data = agg.get_dataset("dispatch")
# All parsers automatically closed
```

### 4. Unified Dataset Interface

Systems now support the same dataset interface as simulations:

```python
system = SiennaSystem("system.json")

# List available datasets
datasets = system.list_datasets()

# Get single dataset
generators = system.get_dataset("generators")

# Get multiple datasets
data = system.get_datasets("generators", "loads", "system_info")
```

### 5. Enhanced Metadata

Access simulation metadata:

```python
parser = SiennaSimulationParser("sim.h5")

metadata = parser.get_metadata()
# {
#     "start_time": "2024-01-01T00:00:00",
#     "end_time": "2024-12-31T23:00:00",
#     "resolution": "1H",
#     ...
# }
```

### 6. Validation

Check for issues before processing:

```python
parser = SiennaSimulationParser("sim.h5")

warnings = parser.validate()
for warning in warnings:
    print(f"Warning: {warning}")
```

---

## Checklist

Use this checklist to ensure your code is updated:

- [ ] Updated imports to use `gat.simulations` instead of `gat.datahelpers`
- [ ] Consider using `SimulationAggregator` instead of tool-specific aggregators
- [ ] Enable `parallel=True` for multi-file scenarios
- [ ] Use `list_datasets()` and `get_dataset()` for consistent API
- [ ] Update custom parsers to inherit from `BaseSimulationParser`
- [ ] Ensure custom parsers are pickleable (for parallel loading)
- [ ] Test with both single and multiple files
- [ ] Update documentation and examples

---

## Getting Help

If you encounter issues during migration:

1. **Check the plugin development guide**: `docs/plugin_development_guide.md`
2. **Review examples**: Look at `SiennaSimulationParser` for reference
3. **Open an issue**: Report migration problems on GitHub
4. **Ask the team**: Reach out on Slack/Discord

---

## Summary

**Most code requires no changes** - the refactor is backward compatible.

**Recommended updates**:
- Use `SimulationAggregator` for better performance
- Enable parallel loading for multi-file scenarios
- Use unified dataset interface for consistency

**Benefits**:
- Faster multi-file loading (parallel processing)
- Easier to add new simulation tools
- Consistent API across simulations and systems
- Better resource management