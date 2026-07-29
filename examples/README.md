# GAT Examples

This directory contains example scripts demonstrating various GAT capabilities.

## Available Examples

### Palette Generation

**File**: `palette_generation_example.py`

Demonstrates automatic palette generation from system files. This example shows how to:
- Load and inspect system files
- Extract generator categories and classifications
- Generate palettes with auto-assigned colors
- Customize generated palettes
- Save palettes for use in visualizations

**Usage**:
```bash
python examples/palette_generation_example.py path/to/system.json
```

**What it does**:
1. **System Inspection**: Reads the system file and displays:
   - System metadata (name, base power, number of components)
   - All component types
   - Generator categories with capacity and classifications
   - VRE, storage, and curtailable technologies
   - Validation warnings

2. **Palette Generation**: Creates a palette with:
   - Display categories (simplified from simulation categories)
   - Color assignments (colorblind-friendly palette)
   - Stack order (baseload to VRE/storage)
   - VRE and storage classifications
   - Category mappings

3. **Output**: Saves palette to `example_palette.yaml` and shows customization examples

**Example Output**:
```
======================================================================
SYSTEM FILE INSPECTION
======================================================================

Loading system: data/system.json

System Information:
  Name: Test System
  Generators: 45
  Buses: 12
  
Generator Categories:
Category                                    Count    Capacity    VRE  Storage
--------------------------------------------------------------------------------
NaturalGas_CC                                  12    3600.0 MW    No       No
Wind_Onshore                                    8    1600.0 MW   Yes       No
Solar_PV                                       15    1500.0 MW   Yes       No
Coal_Steam                                      5    2000.0 MW    No       No
Battery_LithiumIon                              3     150.0 MW    No      Yes
Hydro_Reservoir                                 2     400.0 MW    No       No

======================================================================
PALETTE GENERATION
======================================================================

Generating palette 'example_palette'...
✓ Palette generated successfully

Palette: example_palette
Description: Auto-generated example palette...

Display Categories (7):
------------------------------------------------------------
  Natural Gas CC                 #FF6B6B (2 sim categories)
  Wind                           #87CEEB (1 sim categories)
  Solar                          #FFD700 (1 sim categories)
  Coal                           #2F4F4F (1 sim categories)
  Battery Storage                #9932CC (1 sim categories)
  Hydro                          #4682B4 (1 sim categories)

VRE Technologies (2):
  - Wind_Onshore
  - Solar_PV

Storage Charging Categories (1):
  - Battery_LithiumIon

Stack Order (bottom to top):
  1. Coal
  2. Hydro
  3. Natural Gas CC
  4. Wind
  5. Solar
  6. Battery Storage
```

### CLI Alternative

For project-based workflows, use the CLI command:
```bash
# Add scenario to project
gat project add-scenario sienna base_2035 \
    --system data/system.json \
    --simulation data/results.h5

# Generate palette from scenario
gat project add-palette my_palette base_2035 --print-summary
```

## Running Examples

### Prerequisites

Ensure GAT is installed:
```bash
pip install -e .
```

### System File Requirements

Examples that use system files (like palette generation) require:
- **Sienna**: JSON system file from PowerSystems.jl
- **ReEDS**: (Future) ReEDS output directory
- **Plexos**: (Future) Plexos solution files

### Getting Help

For any example, use:
```bash
python examples/example_name.py --help
```

Or refer to the documentation:
- [Palette Generation Guide](../docs/source/palette_generation.md)
- [Project Management](../docs/source/project_management.md)
- [GAT Documentation](../docs/source/index.rst)

## Contributing Examples

To add a new example:

1. Create a well-documented Python script
2. Include usage instructions in docstring
3. Add comprehensive comments
4. Handle errors gracefully
5. Show example output
6. Update this README

Example template:
```python
"""
Example: My Feature

Description of what this example demonstrates.

Usage:
    python examples/my_example.py <args>
    
Requirements:
    - List any special requirements
"""

def main():
    """Main example function."""
    # Your code here
    pass

if __name__ == "__main__":
    main()
```

## Additional Resources

- [GAT Documentation](https://gat.readthedocs.io)
- [API Reference](../docs/source/api/)
- [User Guides](../docs/source/guides/)
- [GitHub Repository](https://github.com/NREL/GAT)

## Support

For questions or issues:
- Open an issue on GitHub
- Check the documentation
- Contact the development team