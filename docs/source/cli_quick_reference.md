# CLI Quick Reference

A quick reference guide for GAT v1.0 command-line interface.

## Project Management

### Initialize a New Project

```bash
gat project init [PATH] [OPTIONS]
```

**Common Options:**
- `--name TEXT` - Project name
- `--description TEXT` - Project description
- `--set-default` - Set as default project
- `--no-palettes` - Don't copy user palettes

**Examples:**
```bash
gat project init my-project --name "My Analysis"
gat project init . --set-default
```

### Add Existing Project

```bash
gat project add PATH [OPTIONS]
```

**Options:**
- `--id TEXT` - Custom project ID
- `--set-default` - Set as default

**Example:**
```bash
gat project add ./my-project --set-default
```

### List Projects

```bash
gat project list [--verbose]
```

### Show Project Details

```bash
gat project show PROJECT_ID
```

### Set Default Project

```bash
gat project set-default PROJECT_ID
```

### Remove Project Reference

```bash
gat project remove PROJECT_ID [--yes]
```

## Scenario Management

### Add Sienna Scenario

```bash
gat project add-scenario sienna SCENARIO_ID \
    --system PATH \
    --simulation PATH \
    [--metadata PATH] \
    [--name TEXT] \
    [--description TEXT] \
    [--project PROJECT_ID]
```

**Multiple Simulations:**
```bash
gat project add-scenario sienna multi_week \
    --system ../data/system.json \
    --simulation ../data/week1.h5 \
    --simulation ../data/week2.h5 \
    --simulation ../data/week3.h5
```

### Add ReEDS Scenario

```bash
gat project add-scenario reeds SCENARIO_ID \
    --path PATH \
    [--solve-year YEAR] \
    [--name TEXT] \
    [--description TEXT] \
    [--project PROJECT_ID]
```

**Example:**
```bash
gat project add-scenario reeds reeds_2035 \
    --path ../reeds_output \
    --solve-year 2035
```

### Add Plexos Scenario

```bash
gat project add-scenario plexos SCENARIO_ID \
    --solution PATH \
    [--name TEXT] \
    [--description TEXT] \
    [--project PROJECT_ID]
```

**Example:**
```bash
gat project add-scenario plexos summer_peak \
    --solution ../plexos/solution.xml
```

### List Scenarios

```bash
gat project scenario list [PROJECT_ID]
```

**Examples:**
```bash
# List scenarios across all projects
gat project scenario list

# List scenarios in specific project
gat project scenario list my-project
```

### Show Scenario Details

```bash
gat project scenario show SCENARIO_ID [--project PROJECT_ID]
```

**Example:**
```bash
# Show scenario in default project
gat project scenario show base_2035

# Show scenario in specific project
gat project scenario show base_2035 --project my-analysis
```

### Remove Scenario

```bash
gat project scenario remove SCENARIO_ID [--project PROJECT_ID] [--yes]
```

**Example:**
```bash
# Remove with confirmation
gat project scenario remove old_scenario

# Remove without confirmation
gat project scenario remove old_scenario --yes
```

## Common Workflows

### Create New Project and Add Scenarios

```bash
# 1. Initialize project
gat project init my-analysis --name "My Analysis" --set-default

# 2. Add scenarios
gat project scenario add sienna base \
    --system ../data/system.json \
    --simulation ../data/base.h5

gat project scenario add sienna high_load \
    --system ../data/system.json \
    --simulation ../data/high_load.h5

# 3. View project
gat project show my-analysis

# 4. List all scenarios
gat project scenario list
```

### Share Project with Team

```bash
# On your machine
cd my-analysis
git init
git add .
git commit -m "Initial project setup"
git remote add origin git@github.com:team/my-analysis.git
git push -u origin main

# Teammate's machine
git clone git@github.com:team/my-analysis.git
cd my-analysis
gat project add . --set-default
```

### Add Scenario to Default Project

```bash
# Set default once
gat project set-default my-analysis

# Then add scenarios without --project flag
gat project scenario add sienna test \
    --system ../data/system.json \
    --simulation ../data/test.h5
```

### View All Scenarios Across Projects

```bash
# List scenarios in all projects
gat project scenario list

# Output shows scenarios grouped by project
```

## Configuration Commands

### View Configuration

```bash
gat config [--show] [--show-path]
```

**Options:**
- `--show` - Display configuration
- `--show-path` - Show config file path
- `--edit` - Open in editor

### Edit Configuration

```bash
gat config --edit
```

## File Locations

### User Configuration
```
~/.config/gat/
├── config.yaml              # User settings
├── projects/                # Project references
│   └── *.yaml
└── palettes/                # User palettes
    └── *.yaml
```

### Project Structure
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

## Scenario Configuration Paths

All paths in scenario configurations are **relative to the project root**:

```yaml
# scenarios/base.yaml
type: sienna
system_path: ../data/systems/2035_base.json
simulation_paths:
  - ../data/results/week1.h5
  - ../data/results/week2.h5
```

## Tips & Tricks

### Use Tab Completion

If your shell supports it, tab completion can help with project IDs and file paths.

### Set Default Project

Save typing by setting a default project:
```bash
gat project set-default my-analysis
```

Then omit `--project` from commands:
```bash
gat project add-scenario sienna test --system sys.json --simulation sim.h5
```

### Organize with Tags

Edit project references to add tags:
```yaml
# ~/.config/gat/projects/my-project.yaml
project_id: my-project
name: My Project
tags:
  - transmission
  - 2035
  - high-priority
```

### Use Absolute Paths (Recommended)

All paths in scenario configurations are stored as absolute paths. When adding scenarios, paths are automatically resolved:

```bash
# Relative paths are resolved to absolute paths
cd /home/user/data
gat project scenario add sienna test \
    --system ./systems/system.json \
    --simulation ./results/results.h5

# Stored as absolute paths in scenario config:
# /home/user/data/systems/system.json
# /home/user/data/results/results.h5
```

### Multiple Simulation Files

When simulations are split across multiple files:
```bash
gat project scenario add sienna annual \
    --system ../data/system.json \
    --simulation ../data/jan_mar.h5 \
    --simulation ../data/apr_jun.h5 \
    --simulation ../data/jul_sep.h5 \
    --simulation ../data/oct_dec.h5
```

### View Project Before Adding

Before adding a project, check if it's valid:
```bash
# Navigate to project directory
cd /path/to/project

# Check for gat-project.yaml
ls -la gat-project.yaml

# If it exists, add it
gat project add . --id my_proj
```

## Error Messages

### "Project not found"
```bash
Error: Project 'my-project' not found
```
**Solution:** Add the project first:
```bash
gat project add /path/to/my-project
```

### "Scenario already exists"
```bash
Error: Scenario already exists: base
```
**Solution:** Use a different scenario ID or remove the existing one.

### "Path not found"
```bash
⚠ Path not found
```
**Solution:** The project directory moved. Update the reference:
```bash
gat project remove old-id
gat project add /new/path
```

### "--system is required"
```bash
Error: --system is required for Sienna scenarios
```
**Solution:** Provide required options:
```bash
gat project scenario add sienna test \
    --system ../data/system.json \
    --simulation ../data/sim.h5
```

### "No scenarios found"
```bash
No scenarios found across any projects.
```
**Solution:** Add scenarios to your projects:
```bash
gat project scenario add sienna test \
    --system ../data/system.json \
    --simulation ../data/sim.h5
```

## Version Information

```bash
gat --version
```

## Getting Help

```bash
# General help
gat --help

# Project command help
gat project --help

# Specific command help
gat project scenario add --help
gat project scenario list --help
gat project init --help
```

## See Also

- [Project Management Guide](cli_project_management.md) - Comprehensive documentation
- [Configuration](api/Configuration/general.md) - GAT configuration
- [Scenario Objects](api/ScenarioObjects/BaseScenario.md) - Using scenarios in Python