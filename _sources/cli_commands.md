# CLI Command Reference

Complete reference for GAT v1.0 command-line interface.

## Command Structure

```
gat
├── project                   # Project management
│   ├── init                 # Initialize new project
│   ├── add                  # Add existing project
│   ├── list                 # List all projects
│   ├── show                 # Show project details
│   ├── remove               # Remove project reference
│   ├── set-default          # Set default project
│   ├── scenario             # Scenario management
│   │   ├── add              # Add scenario
│   │   ├── remove           # Remove scenario
│   │   ├── list             # List scenarios
│   │   └── show             # Show scenario details
│   └── palette              # Palette management
│       ├── add              # Generate palette
│       ├── remove           # Remove palette
│       ├── list             # List palettes
│       └── show             # Show palette details
├── projects                 # Data source project discovery (v2.0)
│   ├── list                 # List discovered projects
│   ├── refresh              # Refresh project cache
│   └── show                 # Show project details
├── sources                  # Data source management (v2.0)
│   ├── add                  # Add data source
│   │   ├── sienna          # Add Sienna source
│   │   ├── reeds           # Add ReEDS source
│   │   └── plexos          # Add Plexos source
│   ├── list                 # List sources
│   ├── show                 # Show source details
│   ├── remove               # Remove source
│   └── types                # List available source types
├── config                   # Configuration management
├── init                     # Initialize configurations
│   └── report               # Initialize report config
└── run                      # Run reports
    └── report               # Run report from config
```

## Project Management Commands

### `gat project init`

Initialize a new GAT project with standard directory structure.

**Syntax:**
```bash
gat project init [PATH] [OPTIONS]
```

**Arguments:**
- `PATH` - Directory path for project (default: current directory)

**Options:**
- `--name TEXT` - Project name (defaults to directory name)
- `--description TEXT` - Project description
- `--gat-version TEXT` - Required GAT version (default: 1.0.0)
- `--no-palettes` - Don't copy user palettes into project
- `--no-add` - Don't add project to user metadata
- `--set-default` - Set as default project

**Examples:**
```bash
# Initialize in current directory
gat project init .

# Initialize in new directory
gat project init ./my-analysis --name "My Analysis"

# Initialize and set as default
gat project init ./my-analysis --set-default
```

---

### `gat project add`

Add an existing project to user metadata.

**Syntax:**
```bash
gat project add PATH [OPTIONS]
```

**Arguments:**
- `PATH` - Path to existing project directory

**Options:**
- `--id TEXT` - Custom project ID (defaults to directory name)
- `--set-default` - Set as default project

**Examples:**
```bash
# Add local project
gat project add ./my-project

# Add with custom ID and set as default
gat project add ./my-project --id analysis --set-default
```

---

### `gat project list`

List all projects in user metadata.

**Syntax:**
```bash
gat project list [OPTIONS]
```

**Options:**
- `--verbose, -v` - Show detailed information

**Examples:**
```bash
# Compact listing
gat project list

# Detailed listing
gat project list --verbose
```

**Output:**
```
my-analysis     My Analysis Project    ✓ /home/user/projects/my-analysis
planning        Planning Study         ✓ /home/user/projects/planning
old-project     Old Project            ✗ (path not found)
```

---

### `gat project show`

Show detailed information about a project.

**Syntax:**
```bash
gat project show PROJECT_ID [SCENARIO_ID] [OPTIONS]
```

**Arguments:**
- `PROJECT_ID` - Project identifier
- `SCENARIO_ID` - (Optional) Show specific scenario

**Options:**
- `--verbose, -v` - Show detailed scenario information

**Examples:**
```bash
# Show project overview
gat project show my-analysis

# Show project with verbose scenario details
gat project show my-analysis --verbose

# Show specific scenario
gat project show my-analysis base_2035
```

---

### `gat project remove`

Remove project from user metadata (does not delete project directory).

**Syntax:**
```bash
gat project remove PROJECT_ID [OPTIONS]
```

**Arguments:**
- `PROJECT_ID` - Project identifier

**Options:**
- `--yes, -y` - Skip confirmation prompt

**Examples:**
```bash
# Remove with confirmation
gat project remove old-project

# Remove without confirmation
gat project remove old-project --yes
```

---

### `gat project set-default`

Set a project as the default.

**Syntax:**
```bash
gat project set-default PROJECT_ID
```

**Arguments:**
- `PROJECT_ID` - Project identifier

**Example:**
```bash
gat project set-default my-analysis
```

---

## Scenario Management Commands

### `gat project scenario add`

Add a scenario to a project.

**Syntax:**
```bash
gat project scenario add TYPE SCENARIO_ID [OPTIONS]
```

**Arguments:**
- `TYPE` - Scenario type: `sienna`, `reeds`, or `plexos`
- `SCENARIO_ID` - Unique identifier for scenario

**Common Options:**
- `--name TEXT` - Scenario name (defaults to ID)
- `--description TEXT` - Scenario description
- `--project TEXT` - Project ID (uses default if not specified)

**Sienna Options:**
- `--system TEXT` - Path to system JSON file (required)
- `--simulation TEXT` - Path to simulation HDF5 (required, repeatable)
- `--metadata TEXT` - Path to GAT metadata JSON

**ReEDS Options:**
- `--path TEXT` - Path to ReEDS output directory (required)
- `--solve-year INTEGER` - Solve year to analyze

**Plexos Options:**
- `--solution TEXT` - Path to Plexos solution file (required)

**Examples:**
```bash
# Add Sienna scenario
gat project scenario add sienna base_2035 \
    --system ./data/system.json \
    --simulation ./data/results.h5

# Add with multiple simulation files
gat project scenario add sienna multi_week \
    --system ./system.json \
    --simulation ./week1.h5 \
    --simulation ./week2.h5 \
    --simulation ./week3.h5

# Add with description
gat project scenario add sienna high_load \
    --name "High Load Scenario" \
    --description "Sensitivity with 10% load increase" \
    --system ./system.json \
    --simulation ./results.h5

# Add ReEDS scenario
gat project scenario add reeds reeds_2035 \
    --path ./reeds_output \
    --solve-year 2035

# Add Plexos scenario
gat project scenario add plexos summer_peak \
    --solution ./solution.xml

# Add to specific project
gat project scenario add sienna test \
    --project my-other-project \
    --system ./system.json \
    --simulation ./results.h5
```

**Note:** All paths are automatically resolved to absolute paths.

---

### `gat project scenario list`

List scenarios across all projects or in a specific project.

**Syntax:**
```bash
gat project scenario list [PROJECT_ID]
```

**Arguments:**
- `PROJECT_ID` - (Optional) Project identifier. If omitted, lists scenarios from all projects.

**Examples:**
```bash
# List scenarios across all projects
gat project scenario list

# List scenarios in specific project
gat project scenario list my-analysis
```

**Output (all projects):**
```
My Analysis (my-analysis):
  base_2035            [sienna] Base 2035 Scenario
  high_renewable       [sienna] High Renewable Scenario

Planning Study (planning):
  reeds_2050           [reeds] ReEDS 2050 Scenario
  plexos_base          [plexos] Plexos Base Case

Total scenarios: 4
```

**Output (specific project):**
```
Scenarios in 'My Analysis': (2)
  base_2035            [sienna] Base 2035 Scenario
  high_renewable       [sienna] High Renewable Scenario
```

---

### `gat project scenario show`

Show detailed information about a scenario.

**Syntax:**
```bash
gat project scenario show SCENARIO_ID [OPTIONS]
```

**Arguments:**
- `SCENARIO_ID` - Scenario identifier

**Options:**
- `--project TEXT` - Project ID (uses default if not specified)

**Examples:**
```bash
# Show scenario in default project
gat project scenario show base_2035

# Show scenario in specific project
gat project scenario show base_2035 --project my-analysis
```

**Output:**
```
Scenario: base_2035
Name:        Base 2035 Scenario
Type:        sienna
Description: Baseline scenario for 2035 analysis
Created:     2024-01-15 10:30
Updated:     2024-01-20 14:45

Paths:
  System:      ✓ /data/shared/systems/base_2035.json
  Simulations: (2 file(s))
    - ✓ /data/shared/results/week1.h5
    - ✓ /data/shared/results/week2.h5

✓ All paths validated
```

---

### `gat project scenario remove`

Remove a scenario from a project.

**Syntax:**
```bash
gat project scenario remove SCENARIO_ID [OPTIONS]
```

**Arguments:**
- `SCENARIO_ID` - Scenario identifier

**Options:**
- `--project TEXT` - Project ID (uses default if not specified)
- `--yes, -y` - Skip confirmation prompt

**Examples:**
```bash
# Remove with confirmation
gat project scenario remove old_scenario

# Remove without confirmation
gat project scenario remove old_scenario --yes

# Remove from specific project
gat project scenario remove old_scenario --project my-analysis
```

---

## Palette Management Commands

### `gat project palette add`

Generate a palette from a scenario's system file.

**Syntax:**
```bash
gat project palette add PALETTE_NAME SCENARIO_ID [OPTIONS]
```

**Arguments:**
- `PALETTE_NAME` - Name for the palette
- `SCENARIO_ID` - Scenario to generate palette from

**Options:**
- `--project TEXT` - Project ID (uses default if not specified)
- `--description TEXT` - Palette description
- `--print-summary` - Print detailed summary after generation

**Examples:**
```bash
# Generate palette
gat project palette add my_palette base_2035

# With description
gat project palette add renewable_focus base_2035 \
    --description "Focus on renewable energy sources"

# Show detailed summary
gat project palette add my_palette base_2035 --print-summary

# For specific project
gat project palette add my_palette base_2035 --project my-analysis
```

---

### `gat project palette list`

List all palettes in a project.

**Syntax:**
```bash
gat project palette list [OPTIONS]
```

**Options:**
- `--project TEXT` - Project ID (uses default if not specified)

**Examples:**
```bash
# List palettes in default project
gat project palette list

# List palettes in specific project
gat project palette list --project my-analysis
```

**Output:**
```
Palettes in 'My Analysis': (2)
  default
  renewable_focus
```

---

### `gat project palette show`

Show detailed information about a palette.

**Syntax:**
```bash
gat project palette show PALETTE_NAME [OPTIONS]
```

**Arguments:**
- `PALETTE_NAME` - Palette name

**Options:**
- `--project TEXT` - Project ID (uses default if not specified)

**Examples:**
```bash
# Show palette in default project
gat project palette show my_palette

# Show palette in specific project
gat project palette show my_palette --project my-analysis
```

**Output:**
```
Palette: my_palette
Description: Custom palette for analysis
Simulation Type: sienna
Version: 1.0.0

Display Categories (7):
------------------------------------------------------------
  Solar                          #FFD700 (2 sim categories)
  Wind                           #87CEEB (1 sim categories)
  Natural Gas                    #FF6B6B (2 sim categories)
  Coal                           #2F4F4F (1 sim categories)
  Hydro                          #4682B4 (1 sim categories)
  Battery Storage                #9932CC (1 sim categories)

VRE Technologies (2):
  - Solar_PV
  - Wind_Onshore

Stack Order (bottom to top):
  1. Coal
  2. Hydro
  3. Natural Gas
  4. Wind
  5. Solar
  6. Battery Storage

✓ Palette validated
```

---

### `gat project palette remove`

Remove a palette from a project.

**Syntax:**
```bash
gat project palette remove PALETTE_NAME [OPTIONS]
```

**Arguments:**
- `PALETTE_NAME` - Palette name

**Options:**
- `--project TEXT` - Project ID (uses default if not specified)
- `--yes, -y` - Skip confirmation prompt

**Examples:**
```bash
# Remove with confirmation
gat project palette remove my_palette

# Remove without confirmation
gat project palette remove my_palette --yes

# Remove from specific project
gat project palette remove my_palette --project my-analysis
```

---

## Data Source Management (v2.0)

### `gat sources add sienna`

Add a Sienna simulation source.

**Syntax:**
```bash
gat sources add sienna NAME [OPTIONS]
```

**Arguments:**
- `NAME` - Source name

**Options:**
- `--system-path PATH` - Path to system JSON file (required)
- `--simulation-path PATH` - Path to simulation HDF5 (required, repeatable)
- `--description TEXT` - Source description

**Examples:**
```bash
# Single simulation file
gat sources add sienna "NTP Base" \
    --system-path ./system.json \
    --simulation-path ./results.h5

# Multiple simulation files
gat sources add sienna "Multi-file" \
    --system-path ./system.json \
    --simulation-path ./week1.h5 \
    --simulation-path ./week2.h5
```

---

### `gat sources add reeds`

Add a ReEDS simulation source.

**Syntax:**
```bash
gat sources add reeds NAME [OPTIONS]
```

**Arguments:**
- `NAME` - Source name

**Options:**
- `--path PATH` - Path to ReEDS output directory (required)
- `--solve-year INTEGER` - Solve year to filter results
- `--description TEXT` - Source description

**Example:**
```bash
gat sources add reeds "ReEDS 2035" \
    --path ./reeds_outputs \
    --solve-year 2035
```

---

### `gat sources add plexos`

Add a Plexos simulation source.

**Syntax:**
```bash
gat sources add plexos NAME [OPTIONS]
```

**Arguments:**
- `NAME` - Source name

**Options:**
- `--solution-path PATH` - Path to Plexos solution file (required)
- `--description TEXT` - Source description

**Example:**
```bash
gat sources add plexos "Summer Peak" \
    --solution-path ./Model.xml
```

---

### `gat sources list`

List configured data sources.

**Syntax:**
```bash
gat sources list
```

**Output:**
```
Configured data sources:

  NTP Base [sienna]
    System:      /data/systems/base.json
    Simulation:  /data/results/base.h5

  ReEDS 2035 [reeds]
    Path: /data/reeds/outputs
    Solve Year: 2035
```

---

### `gat sources show`

Show details for a specific source with path validation.

**Syntax:**
```bash
gat sources show NAME
```

**Arguments:**
- `NAME` - Source name

**Example:**
```bash
gat sources show "NTP Base"
```

**Output:**
```
NTP Base
  Type: sienna
  System Path: /data/systems/base.json
  Simulation Paths (2):
    - /data/results/week1.h5
    - /data/results/week2.h5

  Path Validation:
    ✓ /data/systems/base.json
    ✓ /data/results/week1.h5
    ✗ /data/results/week2.h5
```

---

### `gat sources remove`

Remove a data source.

**Syntax:**
```bash
gat sources remove NAME [OPTIONS]
```

**Arguments:**
- `NAME` - Source name

**Options:**
- `--yes, -y` - Skip confirmation prompt

**Examples:**
```bash
# Remove with confirmation
gat sources remove "Old Source"

# Remove without confirmation
gat sources remove "Old Source" --yes
```

---

### `gat sources types`

List available source types and their required arguments.

**Syntax:**
```bash
gat sources types
```

**Output:**
```
Available source types:

  sienna
    Production Cost Model simulation results from Sienna
    Required: system_path, simulation_path
    Optional: metadata_path, description

  reeds
    Capacity Expansion Model results from ReEDS
    Required: path
    Optional: solve_year, description

  plexos
    Production Cost Model results from Plexos
    Required: solution_path
    Optional: description
```

---

## Project Discovery (v2.0)

### `gat projects list`

List projects discovered from data sources.

**Syntax:**
```bash
gat projects list [OPTIONS]
```

**Options:**
- `--refresh` - Refresh project cache before listing

**Example:**
```bash
# List cached projects
gat projects list

# Refresh and list
gat projects list --refresh
```

**Output:**
```
NTP Base
----------
  ntp-base-2035        [sienna] NTP Base 2035    (2 scenarios)
  ntp-high-load        [sienna] NTP High Load    (1 scenarios)

ReEDS Study
----------
  reeds-2035           [reeds]  ReEDS 2035       (1 scenarios)
```

---

### `gat projects refresh`

Refresh the project cache by scanning all sources.

**Syntax:**
```bash
gat projects refresh
```

---

### `gat projects show`

Show details for a discovered project.

**Syntax:**
```bash
gat projects show PROJECT_ID
```

**Arguments:**
- `PROJECT_ID` - Project identifier

**Example:**
```bash
gat projects show ntp-base-2035
```

**Output:**
```
NTP Base 2035
  ID:     ntp-base-2035
  Type:   sienna
  Source: NTP Base
  Path:   /data/projects/ntp-base-2035

  Scenarios (2):
    - week1
    - week2
```

---

## Configuration Commands

### `gat config`

View or edit GAT configuration.

**Syntax:**
```bash
gat config [OPTIONS]
```

**Options:**
- `--show` - Display configuration
- `--path` - Show config file path
- `--edit` - Open config file in editor

**Examples:**
```bash
# Show configuration
gat config --show

# Show config file location
gat config --path

# Edit config file
gat config --edit
```

---

## Report Commands

### `gat init report`

Initialize a report configuration.

**Syntax:**
```bash
gat init report [OPTIONS]
```

**Options:**
- `--type TEXT` - Type of report to initialize

**Example:**
```bash
gat init report --type scenario_single
```

---

### `gat run report`

Run a report from a configuration file.

**Syntax:**
```bash
gat run report CONFIG_PATH [OPTIONS]
```

**Arguments:**
- `CONFIG_PATH` - Path to report configuration file

**Options:**
- `--output, -o PATH` - Output directory

**Example:**
```bash
gat run report ./report_config.yaml --output ./outputs
```

---

## Global Options

All commands support:

- `--help` - Show help message
- `--version` - Show GAT version

**Examples:**
```bash
# Show general help
gat --help

# Show version
gat --version

# Show command-specific help
gat project scenario add --help
```

---

## File Locations

### User Configuration
```
~/.config/gat/
├── config.yaml              # User settings and data sources
├── projects/                # Project references (v1.0)
│   └── *.yaml
└── palettes/                # User palettes
    └── *.yaml
```

### Project Structure (v1.0)
```
my-project/
├── gat-project.yaml         # Project config
├── scenarios/               # Scenario configs
│   └── *.yaml
├── palettes/                # Project palettes
│   └── *.yaml
├── pipelines/               # Pipeline configs
├── notebooks/               # Jupyter notebooks
├── outputs/                 # Generated plots
└── .gat-cache/             # Cached data
```

---

## Path Handling

**Important:** All scenario paths are stored as absolute filesystem paths.

When adding scenarios, paths are automatically resolved:
- Relative paths (e.g., `./data/file.json`) → Resolved from current working directory
- Absolute paths (e.g., `/full/path/file.json`) → Stored as-is

**Example:**
```bash
cd /home/user/data
gat project scenario add sienna test \
    --system ./system.json \
    --simulation ./results.h5

# Stored as:
# /home/user/data/system.json
# /home/user/data/results.h5
```

This ensures clarity about which files are being used, regardless of where commands are run from.

---

## See Also

- [CLI Quick Reference](cli_quick_reference.md) - Common commands and workflows
- [Project Management Guide](cli_project_management.md) - Comprehensive project management documentation
- [Palette Generation](palette_generation.md) - Palette management and customization