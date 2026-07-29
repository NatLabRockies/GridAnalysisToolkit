# Migrating to GAT v1.0

This guide helps you transition from GAT v0.x to the new v1.0 project management system.

## What's New in v1.0

GAT v1.0 introduces a comprehensive project management system that replaces the old data sources approach:

### Key Changes

| v0.x | v1.0 |
|------|------|
| Data sources in single config | Projects as directories |
| TOML config files | YAML config files |
| `gat sources add` | `gat project init` / `gat project add` |
| Embedded project cache | Lightweight project references |
| No standard structure | Standard project directory layout |

### Benefits

- ✅ **Better Organization** - Each project is a self-contained directory
- ✅ **Team Collaboration** - Projects can be shared via git
- ✅ **Easier Management** - File-based project references
- ✅ **More Flexible** - Projects include scenarios, palettes, pipelines, notebooks
- ✅ **User-Friendly** - YAML is easier to read and edit than TOML

## Migration Overview

The migration process involves:

1. Understanding the new architecture
2. Converting your existing data sources to projects
3. Updating your workflow commands
4. (Optional) Organizing projects in git repositories

## Step-by-Step Migration

### Step 1: Check Your Current Setup

First, see what data sources you have configured:

```bash
# Old v0.x command
gat sources list
```

This shows your existing Sienna, ReEDS, or Plexos data sources.

### Step 2: Create Projects from Data Sources

For each data source, create a new project:

#### Example: Sienna Source → Project

**Old way (v0.x):**
```bash
gat sources add sienna "NTP Base" \
    --system-path ./data/system.json \
    --simulation-path ./data/results.h5
```

**New way (v1.0):**
```bash
# Create a project directory
mkdir ntp-base
cd ntp-base

# Initialize the project
gat project init . --name "NTP Base" --set-default

# Add the scenario
gat project add-scenario sienna base \
    --system ../data/system.json \
    --simulation ../data/results.h5
```

#### Example: ReEDS Source → Project

**Old way (v0.x):**
```bash
gat sources add reeds "ReEDS 2035" \
    --path ./reeds_output \
    --solve-year 2035
```

**New way (v1.0):**
```bash
mkdir reeds-2035
cd reeds-2035
gat project init . --name "ReEDS 2035"
gat project add-scenario reeds base \
    --path ../reeds_output \
    --solve-year 2035
```

#### Example: Plexos Source → Project

**Old way (v0.x):**
```bash
gat sources add plexos "Summer Peak" \
    --solution-path ./solution.xml
```

**New way (v1.0):**
```bash
mkdir summer-peak
cd summer-peak
gat project init . --name "Summer Peak"
gat project add-scenario plexos peak \
    --solution ../solution.xml
```

### Step 3: Verify Your Projects

After creating projects, verify they're set up correctly:

```bash
# List all projects
gat project list

# Show details for a project
gat project show ntp-base
```

### Step 4: Update Your Workflow

Update your scripts and workflows to use the new commands:

#### Before (v0.x)
```bash
gat sources list
gat projects list  # (from auto-discovery)
gat sources add sienna ...
```

#### After (v1.0)
```bash
gat project list
gat project show my-project
gat project add-scenario sienna ...
```

### Step 5: (Optional) Remove Old Data Sources

Once you've migrated, you can remove old data source references:

```bash
# This command still works but is deprecated
gat sources remove old-source
```

**Note:** In v1.0, old data sources are preserved in `legacy_sources` field in your config for backward compatibility, but new features will only work with projects.

## Configuration File Changes

### User Config Location

**Same location:** `~/.config/gat/config.yaml`

### What Changed

**v0.x config.yaml:**
```yaml
user_name: alice
default_theme: nrel
data_sources:
  - type: sienna
    name: NTP Base
    system_path: /path/to/system.json
    simulation_paths: /path/to/results.h5
project_cache:
  projects:
    - project_id: ntp_base
      name: NTP Base
      scenarios: [...]
```

**v1.0 config.yaml:**
```yaml
user_name: alice
default_theme: nrel
default_palette: renewable_focus
# No more data_sources or project_cache!
```

**v1.0 project references** (`~/.config/gat/projects/ntp_base.yaml`):
```yaml
project_id: ntp-base
name: NTP Base
path: /home/alice/projects/ntp-base
last_accessed: '2024-01-22T15:00:00Z'
is_default: true
```

**v1.0 project config** (`/home/alice/projects/ntp-base/gat-project.yaml`):
```yaml
name: NTP Base
version: 0.1.0
gat_version: 1.0.0
```

**v1.0 scenario config** (`scenarios/base.yaml`):
```yaml
name: Base Case
type: sienna
system_path: ../data/system.json
simulation_paths: ../data/results.h5
```

## Python API Changes

If you're using GAT in Python scripts, here are the changes:

### Loading Scenarios

**v0.x approach:**
```python
from gat.models.user import load_user_config
from gat.project_management.discovery import ProjectDiscovery

config = load_user_config()
discovery = ProjectDiscovery(config)
projects = discovery.refresh()
```

**v1.0 approach:**
```python
from gat.models.user import load_project_ref
from gat.project_management.manager import ProjectManager

# Load project
project_ref = load_project_ref('my-project')
manager = ProjectManager(project_ref.get_path())

# Load scenario
scenario_config = manager.load_scenario('base')

# Use scenario with existing GAT code
from gat.scenariohandlers.sienna import SiennaScenario

scenario = SiennaScenario(
    system_path=manager.resolve_path(scenario_config.system_path),
    simulation_paths=[manager.resolve_path(p) for p in scenario_config.get_simulation_paths_list()]
)
```

### Configuration Models

**New models available:**
```python
from gat.models.user import UserConfig, UserProjectRef
from gat.models.project import ProjectConfig, SiennaScenarioConfig
from gat.models.palette import Palette
```

## Common Migration Scenarios

### Scenario 1: Single Analysis Project

**Before:** One Sienna data source with one system and one simulation file.

**After:**
```bash
mkdir my-analysis
cd my-analysis
gat project init . --name "My Analysis" --set-default
gat project add-scenario sienna base \
    --system ../data/system.json \
    --simulation ../data/results.h5
```

### Scenario 2: Multiple Scenarios for Comparison

**Before:** Multiple data sources, each representing a scenario.

**After:** One project with multiple scenarios:
```bash
mkdir comparison-study
cd comparison-study
gat project init . --name "Comparison Study"

gat project add-scenario sienna base \
    --system ../data/system.json \
    --simulation ../data/base.h5

gat project add-scenario sienna high_load \
    --system ../data/system.json \
    --simulation ../data/high_load.h5

gat project add-scenario sienna sensitivity \
    --system ../data/system.json \
    --simulation ../data/sensitivity.h5
```

### Scenario 3: Team Collaboration

**Before:** Shared network drive with config files.

**After:** Git repository with project structure:
```bash
# On shared repository
mkdir team-analysis
cd team-analysis
gat project init . --name "Team Analysis"
gat project add-scenario sienna base --system ../data/sys.json --simulation ../data/sim.h5

git init
git add .
git commit -m "Initial project"
git remote add origin git@github.com:team/analysis.git
git push -u origin main

# Team members
git clone git@github.com:team/analysis.git
cd analysis
gat project add . --set-default
```

## Troubleshooting

### Issue: Old commands don't work

**Problem:**
```bash
$ gat sources add sienna ...
Command 'sources' is deprecated. Use 'gat project' instead.
```

**Solution:** Use the new project commands. See the [Quick Reference](cli_quick_reference.md).

### Issue: Can't find my old data

**Problem:** "Where did my data sources go?"

**Solution:** Old data sources are preserved in your config file under `legacy_sources`. You can still access them, but it's recommended to migrate to projects.

### Issue: Project paths are absolute

**Problem:** Scenario configs have absolute paths instead of relative paths.

**Solution:** Edit the scenario YAML files and change paths to be relative to the project root:

```yaml
# Before
system_path: /home/alice/data/system.json

# After
system_path: ../data/system.json
```

### Issue: Multiple simulation files

**Problem:** How do I add a scenario with multiple simulation files?

**Solution:** Use `--simulation` multiple times:
```bash
gat project add-scenario sienna annual \
    --system ../data/system.json \
    --simulation ../data/q1.h5 \
    --simulation ../data/q2.h5 \
    --simulation ../data/q3.h5 \
    --simulation ../data/q4.h5
```

### Issue: Want to keep old and new

**Problem:** Can I use both v0.x and v1.0 features?

**Solution:** Yes! The old `gat sources` commands still work (though deprecated). You can gradually migrate to projects while keeping old sources.

## Best Practices After Migration

### 1. Organize Your Files

```
workspace/
├── projects/              # GAT projects (git repos)
│   ├── ntp-base/
│   ├── wecc-study/
│   └── sensitivity-analysis/
└── data/                  # Shared data files
    ├── systems/
    └── results/
```

### 2. Use Git for Projects

Initialize git in each project directory:
```bash
cd my-project
git init
git add .
git commit -m "Initial project setup"
```

### 3. Add README Files

Document each project:
```markdown
# My Analysis Project

## Purpose
This project analyzes...

## Scenarios
- base: Base case scenario
- high_load: 10% load increase

## Data Sources
Data files are located in `../data/`
```

### 4. Share Palettes

Copy your custom palettes into projects:
```bash
cp ~/.config/gat/palettes/my_custom.yaml my-project/palettes/
```

### 5. Set Default Project

For your main working project:
```bash
gat project set-default my-analysis
```

## Getting Help

If you encounter issues during migration:

1. Check the [CLI documentation](cli_project_management.md)
2. Review the [Quick Reference](cli_quick_reference.md)
3. Look at example YAML files in your project directories
4. Ask for help on the GAT issue tracker

## Summary Checklist

- [ ] Listed existing data sources (`gat sources list`)
- [ ] Created project directory for each source
- [ ] Initialized projects (`gat project init`)
- [ ] Added scenarios to projects (`gat project add-scenario`)
- [ ] Verified projects (`gat project list`, `gat project show`)
- [ ] Updated scripts to use new commands
- [ ] (Optional) Initialized git in project directories
- [ ] (Optional) Removed old data sources
- [ ] Set default project (`gat project set-default`)

## Next Steps

After migration:

1. **Explore new features** - Projects support palettes, pipelines, and notebooks
2. **Customize projects** - Edit `gat-project.yaml` to add metadata
3. **Collaborate** - Share projects with your team via git
4. **Organize** - Use tags and descriptions to organize your projects

Welcome to GAT v1.0! 🎉