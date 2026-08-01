# BaseSystem Architecture

## Overview

The `BaseSystem` abstraction provides a unified interface for reading system files from different simulation platforms (Sienna, ReEDS, Plexos, etc.). This abstraction enables:

- **Palette auto-generation**: Automatically create palette configurations from system metadata
- **Platform independence**: Write code that works across different simulation platforms
- **Consistent data access**: Standardized API for accessing generator categories, classifications, and metadata
- **Extensibility**: Easy to add support for new simulation platforms

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                       │
│  (PaletteGenerator, CLI commands, plotting functions)       │
└────────────────────────────┬────────────────────────────────┘
                             │
                             │ uses
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   BaseSystem (Abstract)                      │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ - get_system_info() -> SystemInfo                     │  │
│  │ - list_generator_categories() -> List[GeneratorCategory]│
│  │ - list_load_categories() -> List[LoadCategory]        │  │
│  │ - get_generator_data() -> DataFrame                   │  │
│  │ - get_load_data() -> DataFrame                        │  │
│  │ - get_vre_categories() -> List[str]                   │  │
│  │ - get_storage_categories() -> List[str]               │  │
│  │ - validate() -> List[str]                             │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             │ implements
                             ▼
┌──────────────────┬──────────────────┬──────────────────────┐
│                  │                  │                      │
│  SiennaSystem    │  ReedsSystem     │  PlexosSystem        │
│  (Implemented)   │  (Future)        │  (Future)            │
│                  │                  │                      │
└──────────────────┴──────────────────┴──────────────────────┘
```

## Core Components

### 1. BaseSystem Abstract Class

Location: `gat/datahelpers/base_system.py`

The abstract base class defines the interface that all system parsers must implement:

```python
class BaseSystem(ABC):
    """Abstract base class for system file parsers."""
    
    @abstractmethod
    def get_system_info(self) -> SystemInfo:
        """Get basic system information."""
        pass
    
    @abstractmethod
    def list_generator_categories(self) -> List[GeneratorCategory]:
        """List all generator categories in the system."""
        pass
    
    @abstractmethod
    def list_load_categories(self) -> List[LoadCategory]:
        """List all load categories in the system."""
        pass
    
    @abstractmethod
    def get_generator_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """Get detailed generator data."""
        pass
    
    @abstractmethod
    def get_load_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """Get detailed load data."""
        pass
```

### 2. Data Models

#### SystemInfo

Basic metadata about a power system:

```python
class SystemInfo(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    base_power: Optional[float] = None  # MVA base
    data_format_version: Optional[str] = None
    num_generators: Optional[int] = None
    num_buses: Optional[int] = None
    num_loads: Optional[int] = None
```

#### GeneratorCategory

Information about a generator category/type:

```python
class GeneratorCategory(BaseModel):
    name: str                              # Category name
    display_name: Optional[str] = None     # Human-readable name
    fuel_type: Optional[str] = None        # Fuel type
    prime_mover: Optional[str] = None      # Prime mover type
    technology: Optional[str] = None       # Technology classification
    count: int = 0                         # Number of generators
    total_capacity: Optional[float] = None # Total capacity in MW
    is_vre: bool = False                   # Variable Renewable Energy
    is_storage: bool = False               # Storage flag
    is_curtailable: bool = False           # Can be curtailed
```

#### LoadCategory

Information about load categories:

```python
class LoadCategory(BaseModel):
    name: str
    display_name: Optional[str] = None
    is_flexible: bool = False              # Flexible/dispatchable
    is_storage_charging: bool = False      # Storage charging load
    count: int = 0
    total_demand: Optional[float] = None   # Total demand in MW
```

### 3. SiennaSystem Implementation

Location: `gat/datahelpers/sienna_system.py`

Concrete implementation for Sienna/PowerSystems.jl JSON files:

**Key Features**:
- Parses Sienna JSON system files
- Extracts generator metadata (fuel type, prime mover, technology)
- Builds categories from component types and attributes
- Identifies VRE technologies (Solar, Wind, etc.)
- Identifies storage technologies (Battery, Pumped Hydro)
- Returns standardized DataFrames for generator and load data

**Category Extraction Logic**:
1. Group generators by component type + fuel + prime mover
2. Calculate total capacity per category
3. Classify as VRE based on technology patterns
4. Classify as storage based on component type
5. Mark curtailable resources (typically VRE)

**Example**:
```python
system = SiennaSystem("path/to/system.json")

# Get system info
info = system.get_system_info()
print(f"Generators: {info.num_generators}")

# List categories
categories = system.list_generator_categories()
for cat in categories:
    print(f"{cat.name}: {cat.count} units, {cat.total_capacity:.1f} MW")

# Get detailed data
df = system.get_generator_data()
print(df[['name', 'category', 'capacity', 'is_vre']])
```

## Design Principles

### 1. Separation of Concerns

- **BaseSystem**: Defines the interface and common functionality
- **Concrete implementations**: Handle platform-specific file formats
- **PaletteGenerator**: Uses BaseSystem to generate palettes, platform-agnostic
- **CLI/Application**: Interacts only with the abstraction

### 2. Platform Independence

Code that uses `BaseSystem` works with any implementation:

```python
def analyze_system(system: BaseSystem):
    """Works with any BaseSystem implementation."""
    info = system.get_system_info()
    categories = system.list_generator_categories()
    vre = system.get_vre_categories()
    return info, categories, vre

# Works with Sienna
sienna_sys = SiennaSystem("system.json")
analyze_system(sienna_sys)

# Will work with ReEDS (future)
reeds_sys = ReedsSystem("reeds_output/")
analyze_system(reeds_sys)
```

### 3. Standardized Output

All implementations return the same data structures:
- `SystemInfo` for metadata
- `GeneratorCategory` for category information
- `pd.DataFrame` for detailed data with standard columns

### 4. Extensibility

Adding support for a new platform:

1. Create new class inheriting from `BaseSystem`
2. Implement required abstract methods
3. Handle platform-specific file formats internally
4. Return standardized data structures
5. No changes needed to consuming code

## Comparison with SiennaSystemParser

The new `BaseSystem` abstraction improves upon `SiennaSystemParser`:

| Aspect | SiennaSystemParser | BaseSystem + SiennaSystem |
|--------|-------------------|---------------------------|
| **Scope** | Sienna-only | Multi-platform |
| **Interface** | Sienna-specific methods | Standardized abstract interface |
| **Categories** | Limited category extraction | Rich category metadata with classifications |
| **Type hints** | Partial | Complete with Pydantic models |
| **Documentation** | Basic | Comprehensive with examples |
| **Validation** | Minimal | Built-in validation with warnings |
| **Testing** | Limited | Comprehensive test coverage |
| **Use case** | Direct data access | Palette generation, analysis, visualization |

**Migration Path**:

`SiennaSystemParser` is retained for backward compatibility. New code should use `SiennaSystem`.

## Usage Patterns

### Pattern 1: System Inspection

```python
from gat.datahelpers.sienna_system import SiennaSystem

system = SiennaSystem("system.json")

# Basic info
info = system.get_system_info()
print(f"System: {info.name}")
print(f"Generators: {info.num_generators}")

# Categories
for cat in system.list_generator_categories():
    print(f"{cat.name}: {cat.total_capacity:.1f} MW")
    if cat.is_vre:
        print("  → VRE technology")
```

### Pattern 2: Palette Generation

```python
from gat.datahelpers.sienna_system import SiennaSystem
from gat.palette_generator import PaletteGenerator

system = SiennaSystem("system.json")
generator = PaletteGenerator(system)

palette = generator.generate(
    name="My Palette",
    simulation_type="sienna"
)
```

### Pattern 3: Data Analysis

```python
from gat.datahelpers.sienna_system import SiennaSystem

system = SiennaSystem("system.json")

# Get all generators as DataFrame
df = system.get_generator_data()

# Analyze VRE capacity
vre_df = df[df['is_vre']]
vre_capacity = vre_df['capacity'].sum()
print(f"Total VRE capacity: {vre_capacity:.1f} MW")

# Analyze by fuel type
capacity_by_fuel = df.groupby('fuel_type')['capacity'].sum()
print(capacity_by_fuel)
```

### Pattern 4: Validation

```python
from gat.datahelpers.sienna_system import SiennaSystem

system = SiennaSystem("system.json")
warnings = system.validate()

if warnings:
    print("System validation warnings:")
    for warning in warnings:
        print(f"  ⚠ {warning}")
else:
    print("✓ System validation passed")
```

## Future Extensions

### Support for Additional Platforms

#### ReedsSystem (Planned)

```python
class ReedsSystem(BaseSystem):
    """Parser for ReEDS output files."""
    
    def __init__(self, reeds_path: str, solve_year: Optional[int] = None):
        self.reeds_path = Path(reeds_path)
        self.solve_year = solve_year
        # Load ReEDS data from CSV files
```

#### PlexosSystem (Planned)

```python
class PlexosSystem(BaseSystem):
    """Parser for Plexos solution files."""
    
    def __init__(self, solution_path: str):
        self.solution_path = Path(solution_path)
        # Load Plexos XML/database
```

### Additional Methods

Potential additions to `BaseSystem`:

- `get_bus_data()`: Bus/node information
- `get_branch_data()`: Transmission line data
- `get_zone_data()`: Zone/region aggregations
- `get_time_series_metadata()`: Available time series
- `export_to_format()`: Convert between formats

## Testing Strategy

### Unit Tests

Test each implementation independently:

```python
def test_sienna_system_info():
    system = SiennaSystem("test_system.json")
    info = system.get_system_info()
    assert info.num_generators > 0
    assert info.base_power is not None

def test_generator_categories():
    system = SiennaSystem("test_system.json")
    categories = system.list_generator_categories()
    assert len(categories) > 0
    assert all(cat.count > 0 for cat in categories)
```

### Integration Tests

Test with PaletteGenerator:

```python
def test_palette_generation():
    system = SiennaSystem("test_system.json")
    generator = PaletteGenerator(system)
    palette = generator.generate(name="Test")
    assert len(palette.display_categories) > 0
```

### Fixture-Based Testing

Use synthetic system files for testing:

```python
@pytest.fixture
def sample_system():
    """Create minimal valid system for testing."""
    system_data = {
        "data_format_version": "3.0.0",
        "data": {
            "base_power": 100.0,
            "components": [
                # Test generators
            ]
        }
    }
    # Save to temp file and return path
```

## Best Practices

### For Implementation Authors

1. **Follow the interface**: Implement all abstract methods
2. **Return standard structures**: Use `SystemInfo`, `GeneratorCategory`, etc.
3. **Handle errors gracefully**: Raise meaningful exceptions
4. **Document platform specifics**: Note any limitations or special cases
5. **Validate input**: Check file format and raise clear errors
6. **Test thoroughly**: Cover edge cases and malformed data

### For Consumers

1. **Use the abstraction**: Write code against `BaseSystem`, not concrete implementations
2. **Handle validation warnings**: Check `validate()` output
3. **Check for missing data**: Not all fields are available in all platforms
4. **Use type hints**: Leverage Pydantic models for validation
5. **Test with multiple platforms**: Ensure code works across implementations

## See Also

- [Palette Generation Guide](../palette_generation.md)
- [Palette Model Reference](../palette.md)
- [API Documentation](../api/)
- [Testing Guide](../testing.md)