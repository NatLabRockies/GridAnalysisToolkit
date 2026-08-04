# Project Management (v1.0)

GAT v1.0 introduces a comprehensive project management system that uses the filesystem and git for collaboration. Projects are self-contained directories with YAML configuration files that can be shared across teams. The CLI provides hierarchical subcommands for intuitive scenario and palette management.

## Overview

The project management system uses a two-tier architecture:

1. **User Metadata** (`~/.config/gat/`) - Lightweight references to projects on your system
2. **Project Directories** - Self-contained project folders (can be anywhere, typically git repositories)

This design allows teams to share projects via git while keeping user-specific settings separate.

## Quick Start

```bash
# Create a new project
gat project init my-analysis --name "My Analysis Project"

# Add a scenario
gat project scenario add sienna base_case \
    --system ../data/system.json \
    --simulation ../data/results.h5

# List all scenarios across all projects
gat project scenario list

# List scenarios in a specific project
gat project scenario list my-analysis

# Show project details
gat project show my-analysis
```

## Project Structure

When you initialize a project, GAT creates this directory structure:

```
my-project/
├── gat-project.yaml          # Project configuration
├── scenarios/                # Scenario configurations
│   └── base_case.yaml
├── palettes/                 # Visualization palettes
│   └── default.yaml
├── pipelines/                # Analysis pipelines
├── notebooks/                # Jupyter notebooks
├── outputs/                  # Generated plots (not tracked in git)
├── .gat-cache/              # Cached data (not tracked in git)
├── .gitignore
└── README.md
```

## Commands

### Initialize a Project

```bash
gat project init [PATH] [OPTIONS]
```

Creates a new GAT project with the standard directory structure.

**Arguments:**
- `PATH` - Directory path for the project (default: current directory)

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

# Initialize in new directory with name
gat project init ./my-analysis --name "My Analysis"

# Initialize and set as default
gat project init ./my-analysis --set-default
```

### Add an Existing Project

```bash
gat project add PATH [OPTIONS]
```

Adds an existing project to your user metadata. This creates a lightweight reference that points to the project directory.

**Arguments:**
- `PATH` - Path to existing project directory

**Options:**
- `--id TEXT` - Project ID (defaults to directory name)
- `--set-default` - Set as default project

**Examples:**

```bash
# Add a local project
gat project add ./my-project

# Add and set as default
gat project add ./my-project --set-default

# Add with custom ID
gat project add ./my-project --id my_proj
```

### List Projects

```bash
gat project list [OPTIONS]
```

Lists all projects from your user metadata.

**Options:**
- `--verbose, -v` - Show detailed information

**Examples:**

```bash
# Compact listing
gat project list

# Detailed listing
gat project list --verbose
```

### Show Project Details

```bash
gat project show PROJECT_ID
```

Displays detailed information about a project including scenarios, palettes, and configuration.

**Arguments:**
- `PROJECT_ID` - Project identifier

**Example:**

```bash
gat project show my-analysis
```

### Set Default Project

```bash
gat project set-default PROJECT_ID
```

Sets a project as the default. Commands that accept `--project` will use the default if not specified.

**Arguments:**
- `PROJECT_ID` - Project identifier

**Example:**

```bash
gat project set-default my-analysis

# Now you can omit --project in other commands
gat project add-scenario sienna test --system sys.json --simulation results.h5
```

### Scenario Management

GAT provides hierarchical subcommands for scenario management under `gat project scenario`.

#### Add a Scenario

```bash
gat project scenario add TYPE SCENARIO_ID [OPTIONS]
```

Adds a scenario configuration to a project.

**Arguments:**
- `TYPE` - Scenario type: `sienna`, `reeds`, or `plexos`
- `SCENARIO_ID` - Unique identifier for the scenario

**Common Options:**
- `--name TEXT` - Scenario name (defaults to ID)
- `--description TEXT` - Scenario description
- `--project TEXT` - Project ID (uses default if not specified)

**Sienna Options:**
- `--system TEXT` - Path to system JSON file (required)
- `--simulation TEXT` - Path to simulation HDF5 file (required, can specify multiple)
- `--metadata TEXT` - Path to GAT metadata JSON file

**ReEDS™ Options:**
- `--path TEXT` - Path to ReEDS output directory (required)
- `--solve-year INTEGER` - Solve year to analyze

**Plexos Options:**
- `--solution TEXT` - Path to Plexos solution file (required)

**Examples:**

```bash
# Add a Sienna scenario
gat project scenario add sienna base_2035 \
    --system ../data/system.json \
    --simulation ../data/results.h5

# Add a Sienna scenario with multiple simulation files
gat project scenario add sienna multi_week \
    --system ../data/system.json \
    --simulation ../data/week1.h5 \
    --simulation ../data/week2.h5 \
    --simulation ../data/week3.h5

# Add with description
gat project scenario add sienna high_load \
    --name "High Load Scenario" \
    --description "Sensitivity with 10% load increase" \
    --system ../data/system.json \
    --simulation ../data/high_load.h5

# Add a ReEDS scenario
gat project scenario add reeds reeds_2035 \
    --path ../reeds_output \
    --solve-year 2035

# Add to specific project
gat project scenario add sienna test \
    --project my_other_project \
    --system ../data/system.json \
    --simulation ../data/results.h5
```

**Note:** All paths are automatically resolved to absolute paths when adding scenarios, ensuring clarity about which files are being used regardless of your current working directory.

#### List Scenarios

```bash
gat project scenario list [PROJECT_ID]
```

Lists scenarios across all projects or in a specific project.

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

#### Show Scenario Details

```bash
gat project scenario show SCENARIO_ID [OPTIONS]
```

Displays detailed information about a specific scenario including paths and validation.

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

#### Remove a Scenario

```bash
gat project scenario remove SCENARIO_ID [OPTIONS]
```

Removes a scenario from a project. This deletes the scenario configuration file but does not delete the underlying data files.

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

### Remove a Project

```bash
gat project remove PROJECT_ID [OPTIONS]
```

Removes a project from your user metadata. **This does not delete the project directory**, only the reference to it.

**Arguments:**
- `PROJECT_ID` - Project identifier

**Options:**
- `--yes, -y` - Skip confirmation prompt

**Example:**

```bash
gat project remove my-analysis
gat project remove old-project --yes
```

## Configuration Files

### Project Configuration (`gat-project.yaml`)

The main project configuration file:

```yaml
name: My Analysis Project
description: Comprehensive power system analysis
version: 0.1.0
gat_version: 1.0.0
created_at: '2024-01-15T10:30:00Z'
updated_at: '2024-01-22T15:00:00Z'

default_scenario: base_case
default_palette: default

contributors:
  - Alice Smith
  - Bob Jones

repository_url: git@github.com:team/my-project.git

settings:
  output_dir: ./outputs
  cache_dir: ./.gat-cache
  default_output_format: png
```

### Scenario Configuration (`scenarios/*.yaml`)

Individual scenario configurations:

```yaml
name: Base Case 2035
description: Base scenario for 2035 analysis
type: sienna
tags:
  - base
  - '2035'

created_at: '2024-01-15T10:30:00Z'
updated_at: '2024-01-20T14:00:00Z'

system_path: ../data/systems/2035_base.json
simulation_paths:
  - ../data/results/week1.h5
  - ../data/results/week2.h5
  - ../data/results/week3.h5
metadata_path: ../data/gat_metadata.json
```

**Note:** All paths in scenario configs are stored as absolute filesystem paths. When adding scenarios via the CLI, relative paths are automatically resolved to absolute paths based on your current working directory.

### User Project Reference (`~/.config/gat/projects/*.yaml`)

Lightweight references in user metadata:

```yaml
project_id: my-analysis
name: My Analysis Project
path: /home/user/projects/my-analysis
description: Power system analysis
remote_url: git@github.com:team/my-analysis.git
last_accessed: '2024-01-22T15:00:00Z'
is_default: true
tags:
  - transmission
  - planning
```

## Team Collaboration

Projects are designed to be shared via git:

### Sharing a Project

```bash
# Initialize project
cd my-analysis
gat project init . --name "Team Analysis"

# Add scenarios and palettes
gat project scenario add sienna base --system ../data/sys.json --simulation ../data/sim.h5

# Initialize git and push
git init
git add .
git commit -m "Initial project setup"
git remote add origin git@github.com:team/my-analysis.git
git push -u origin main
```

### Using a Shared Project

```bash
# Clone the repository
git clone git@github.com:team/my-analysis.git
cd my-analysis

# Add to your GAT projects
gat project add . --set-default

# Now you can work with the project
gat project show my-analysis
```

### Collaborating

```bash
# Pull latest changes
cd my-analysis
git pull

# Make your changes
gat project scenario add sienna sensitivity --system ../data/sys.json --simulation ../data/sens.h5

# Commit and push
git add scenarios/sensitivity.yaml
git commit -m "Add sensitivity scenario"
git push
```

## Best Practices

### Project Organization

1. **Keep data separate** - Store large data files outside the project directory and use relative paths
2. **Use git** - Version control your project configuration and analysis code
3. **Document scenarios** - Use descriptive names and descriptions for scenarios
4. **Share palettes** - Copy user palettes into projects for team consistency

### Naming Conventions

- **Project IDs**: Use lowercase with hyphens or underscores (e.g., `ntp-base`, `wecc_2035`)
- **Scenario IDs**: Use descriptive names with underscores (e.g., `base_case`, `high_load`, `sensitivity_1`)
- **Palette names**: Use descriptive names (e.g., `renewable_focus`, `presentation`)

### File Structure

```
workspace/
├── my-analysis/              # GAT project (git repo)
│   ├── gat-project.yaml
│   ├── scenarios/
│   │   ├── base_case.yaml   # Contains absolute paths to data
│   │   └── high_load.yaml
│   └── ...
└── data/                     # Data directory (not in git)
    ├── systems/
    │   └── 2035_base.json
    └── results/
        ├── week1.h5
        └── week2.h5
```

Keep data files separate from projects. When adding scenarios, paths are automatically resolved to absolute paths, making it clear which files are being used.

## Migration from v0.x

If you're using the old data sources approach, you can migrate by:

1. **Create a project** for each data source:
   ```bash
   gat project init my-project --name "My Project"
   ```

2. **Add scenarios** from your old data sources:
   ```bash
   gat project scenario add sienna base \
       --system /path/to/old/system.json \
       --simulation /path/to/old/results.h5
   ```

3. **List all scenarios** to verify:
   ```bash
   gat project scenario list
   ```

## Advanced Usage

### Multiple Environments

Projects can specify their own virtual environment:

Edit `gat-project.yaml`:

```yaml
venv:
  path: .venv
  python_version: '3.11'
  requirements:
    - pandas>=2.0
    - matplotlib>=3.5
    - custom-extension==0.1.0
```

### Custom Metadata

Projects support arbitrary metadata through YAML:

```yaml
# gat-project.yaml
name: My Project
custom_field: custom_value
team_settings:
  slack_channel: "#grid-analysis"
  meeting_day: "Tuesday"
```

### Tags for Organization

Use tags in project references for organization:

```yaml
# ~/.config/gat/projects/my-project.yaml
project_id: my-project
name: My Project
tags:
  - transmission
  - nlr
  - 2035
  - high-priority
```

Then filter in your workflows or scripts.

## Troubleshooting

### Project not found

```bash
$ gat project show my-project
Error: Project 'my-project' not found
```

**Solution:** Add the project to your user metadata:
```bash
gat project add /path/to/my-project
```

### Path not found warning

```bash
$ gat project list
my-project    My Project    ✗ missing
```

**Solution:** The project directory has been moved or deleted. Either:
1. Move it back to the original location
2. Remove and re-add with new path:
   ```bash
   gat project remove my-project
   gat project add /new/path/to/my-project
   ```

### Scenario already exists

```bash
$ gat project scenario add sienna test ...
Error: Scenario already exists: test
```

**Solution:** Use a different scenario ID or remove the existing one first:
```bash
gat project scenario remove test
```

## See Also

- [Configuration](api/Configuration/general.md) - GAT configuration and mapping
- [Scenario Objects](api/ScenarioObjects/BaseScenario.md) - Using scenarios in Python
- [Palettes](api/Configuration/colors.md) - Visualization palettes