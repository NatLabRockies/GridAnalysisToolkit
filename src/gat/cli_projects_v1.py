# gat/cli_projects_v1.py
"""
CLI commands for GAT v1.0 project management.

Commands for creating, managing, and working with GAT projects.
"""

import sys
from pathlib import Path
from typing import List

import click
from loguru import logger


@click.group("project")
def project():
    """Manage GAT projects (v1.0)."""
    pass


@project.command("init")
@click.argument("path", type=click.Path(), default=".")
@click.option("--name", help="Project name (defaults to directory name)")
@click.option("--description", help="Project description")
@click.option("--gat-version", default="1.0.0", help="Required GAT version")
@click.option(
    "--no-palettes",
    is_flag=True,
    help="Don't copy user palettes into project",
)
@click.option(
    "--no-add",
    is_flag=True,
    help="Don't add project to user metadata",
)
@click.option(
    "--set-default",
    is_flag=True,
    help="Set as default project",
)
def init_project(
    path: str,
    name: str,
    description: str,
    gat_version: str,
    no_palettes: bool,
    no_add: bool,
    set_default: bool,
):
    """
    Initialize a new GAT project.

    Creates the project directory structure with:
    - gat-project.yaml (project config)
    - scenarios/ (scenario configs)
    - palettes/ (visualization palettes)
    - pipelines/ (reporting pipelines)
    - notebooks/ (analysis notebooks)
    - .gitignore
    - README.md

    Examples:

        # Initialize in current directory
        gat project init .

        # Initialize in new directory
        gat project init ./my-project --name "My Analysis"

        # Initialize and set as default
        gat project init ./my-project --set-default
    """
    from gat.models.user import save_project_ref
    from gat.project_management.manager import (
        ProjectManager,
        create_project_ref_from_path,
    )

    project_path = Path(path).resolve()

    # Default name to directory name
    if not name:
        name = project_path.name

    try:
        manager = ProjectManager(project_path)
        manager.init_project(
            name=name,
            gat_version=gat_version,
            description=description,
            copy_user_palettes=not no_palettes,
        )

        click.echo(f"✓ Created project directory structure at {project_path}")
        click.echo("✓ Created gat-project.yaml")

        if not no_palettes:
            palettes = manager.list_palettes()
            if palettes:
                click.echo(f"✓ Copied {len(palettes)} user palette(s)")

        # Add to user metadata
        if not no_add:
            project_ref = create_project_ref_from_path(
                project_path, is_default=set_default
            )
            save_project_ref(project_ref)
            click.echo(f"✓ Added to projects as '{project_ref.project_id}'")

            if set_default:
                click.echo("✓ Set as default project")

        click.echo(f"\nProject '{name}' initialized successfully!")
        click.echo("\nNext steps:")
        click.echo(f"  cd {project_path}")
        click.echo("  gat project add-scenario sienna my_scenario \\")
        click.echo("      --system ../data/system.json \\")
        click.echo("      --simulation ../data/results.h5")

    except FileExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error initializing project: {e}", err=True)
        logger.exception("Project init failed")
        sys.exit(1)


@project.command("add")
@click.argument("path", type=click.Path(exists=True))
@click.option("--id", "project_id", help="Project ID (defaults to directory name)")
@click.option("--set-default", is_flag=True, help="Set as default project")
def add_project(path: str, project_id: str, set_default: bool):
    """
    Add an existing project to your projects.

    This creates a lightweight reference in your user metadata that
    points to the project directory.

    Examples:

        # Add a local project
        gat project add ./my-project

        # Add and set as default
        gat project add ./my-project --set-default

        # Add with custom ID
        gat project add ./my-project --id my_proj
    """
    from gat.models.user import save_project_ref
    from gat.project_management.manager import create_project_ref_from_path

    project_path = Path(path).resolve()

    try:
        project_ref = create_project_ref_from_path(
            project_path,
            project_id=project_id,
            is_default=set_default,
        )

        save_project_ref(project_ref)

        click.echo(f"✓ Added project: {project_ref.name}")
        click.echo(f"  ID: {project_ref.project_id}")
        click.echo(f"  Path: {project_ref.path}")

        if set_default:
            click.echo("  Default: Yes")

    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error adding project: {e}", err=True)
        logger.exception("Project add failed")
        sys.exit(1)


@project.command("list")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed information")
def list_projects(verbose: bool):
    """
    List all your projects.

    Shows projects from your user metadata directory (~/.config/gat/projects/).

    Examples:

        gat project list
        gat project list --verbose
    """
    from gat.models.user import list_project_refs

    project_refs = list_project_refs()

    if not project_refs:
        click.echo("No projects found.")
        click.echo("\nAdd a project with:")
        click.echo("  gat project add <path>")
        click.echo("Or create a new one:")
        click.echo("  gat project init <path>")
        return

    # Sort by last accessed (most recent first)
    project_refs.sort(
        key=lambda p: p.last_accessed or "",
        reverse=True,
    )

    click.echo(f"\nFound {len(project_refs)} project(s):\n")

    if verbose:
        # Detailed listing
        for ref in project_refs:
            default_marker = " (default)" if ref.is_default else ""
            click.echo(f"{click.style(ref.name, bold=True)}{default_marker}")
            click.echo(f"  ID:          {ref.project_id}")
            click.echo(f"  Path:        {ref.path}")
            if ref.description:
                click.echo(f"  Description: {ref.description}")
            if ref.remote_url:
                click.echo(f"  Remote:      {ref.remote_url}")
            if ref.last_accessed:
                click.echo(
                    f"  Accessed:    {ref.last_accessed.strftime('%Y-%m-%d %H:%M')}"
                )
            if ref.tags:
                click.echo(f"  Tags:        {', '.join(ref.tags)}")

            # Check if path exists
            if not ref.exists():
                click.echo(f"  {click.style('⚠ Path not found', fg='yellow')}")

            click.echo()
    else:
        # Compact table listing
        # Header
        click.echo(f"{'ID':<20} {'Name':<30} {'Status':<10}")
        click.echo("-" * 61)

        for ref in project_refs:
            status = "✓" if ref.exists() else "✗ missing"
            default_marker = " *" if ref.is_default else ""
            name_display = ref.name[:28] + ".." if len(ref.name) > 30 else ref.name

            click.echo(
                f"{ref.project_id:<20} {name_display:<30} {status:<10}{default_marker}"
            )

        click.echo("\n* = default project")
        click.echo("\nUse --verbose for more details")


@project.command("show")
@click.argument("project_id")
@click.argument("scenario_id", required=False)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed scenario information including paths",
)
def show_project(project_id: str, scenario_id: str, verbose: bool):
    """
    Show details for a specific project or scenario.

    Displays project metadata, scenarios, palettes, and status.
    Use --verbose to see detailed scenario information.
    Specify a scenario_id to show details for a specific scenario.

    Examples:

        # Show project overview
        gat project show my_project

        # Show project with detailed scenario info
        gat project show my_project --verbose

        # Show specific scenario details
        gat project show my_project base_2035
    """
    from pathlib import Path

    from gat.models.project import (
        PlexosScenarioConfig,
        ReedsScenarioConfig,
        SiennaScenarioConfig,
    )
    from gat.models.user import load_project_ref
    from gat.project_management.manager import ProjectManager

    project_ref = load_project_ref(project_id)

    if not project_ref:
        click.echo(f"Error: Project '{project_id}' not found", err=True)
        click.echo("\nAvailable projects:")
        click.echo("  Run 'gat project list' to see all projects")
        sys.exit(1)

    # Check if project exists
    if not project_ref.exists():
        click.echo(f"\n{click.style('⚠ Project path not found!', fg='red')}")
        click.echo(f"Path: {project_ref.path}")
        return

    manager = ProjectManager(project_ref.get_path())

    # If scenario_id is provided, show only that scenario
    if scenario_id:
        try:
            scenario = manager.load_scenario(scenario_id)
        except FileNotFoundError:
            click.echo(f"Error: Scenario '{scenario_id}' not found", err=True)
            available = manager.list_scenarios()
            if available:
                click.echo(f"\nAvailable scenarios: {', '.join(available)}")
            sys.exit(1)
        except Exception as e:
            click.echo(f"Error loading scenario: {e}", err=True)
            sys.exit(1)

        # Show detailed scenario information
        click.echo(f"\n{click.style(f'Scenario: {scenario_id}', bold=True)}")
        click.echo(f"Name:        {scenario.name}")
        click.echo(f"Type:        {scenario.type}")

        if scenario.description:
            click.echo(f"Description: {scenario.description}")

        if scenario.created_at:
            click.echo(f"Created:     {scenario.created_at.strftime('%Y-%m-%d %H:%M')}")
        if scenario.updated_at:
            click.echo(f"Updated:     {scenario.updated_at.strftime('%Y-%m-%d %H:%M')}")

        # Show type-specific paths
        click.echo(f"\n{click.style('Paths:', bold=True)}")

        if isinstance(scenario, SiennaScenarioConfig):
            system_path = manager.resolve_path(scenario.system.path)
            system_exists = system_path.exists()
            status = "✓" if system_exists else "✗"
            click.echo(f"  System:      {status} {scenario.system.path}")
            if not system_exists:
                click.echo(f"               (resolved: {system_path})")

            sim_paths = scenario.get_simulation_paths_list()
            click.echo(f"  Simulations: ({len(sim_paths)} file(s))")
            for sim_path in sim_paths:
                sim_resolved = manager.resolve_path(sim_path)
                sim_exists = sim_resolved.exists()
                status = "✓" if sim_exists else "✗"
                click.echo(f"    - {status} {sim_path}")
                if not sim_exists:
                    click.echo(f"           (resolved: {sim_resolved})")

            if scenario.metadata_path:
                metadata_path = manager.resolve_path(scenario.metadata_path)
                metadata_exists = metadata_path.exists()
                status = "✓" if metadata_exists else "✗"
                click.echo(f"  Metadata:    {status} {scenario.metadata_path}")
                if not metadata_exists:
                    click.echo(f"               (resolved: {metadata_path})")

        elif isinstance(scenario, ReedsScenarioConfig):
            reeds_path = manager.resolve_path(scenario.path)
            reeds_exists = reeds_path.exists()
            status = "✓" if reeds_exists else "✗"
            click.echo(f"  Path:        {status} {scenario.path}")
            if not reeds_exists:
                click.echo(f"               (resolved: {reeds_path})")
            if scenario.solve_year:
                click.echo(f"  Solve Year:  {scenario.solve_year}")

        elif isinstance(scenario, PlexosScenarioConfig):
            solution_path = manager.resolve_path(scenario.solution_path)
            solution_exists = solution_path.exists()
            status = "✓" if solution_exists else "✗"
            click.echo(f"  Solution:    {status} {scenario.solution_path}")
            if not solution_exists:
                click.echo(f"               (resolved: {solution_path})")

        # Validate paths
        warnings = manager.validate_scenario_paths(scenario_id)
        if warnings:
            click.echo(f"\n{click.style('Warnings:', fg='yellow', bold=True)}")
            for warning in warnings:
                click.echo(f"  ⚠ {warning}")
        else:
            click.echo(f"\n{click.style('✓ All paths validated', fg='green')}")

        return

    # Otherwise show project overview
    click.echo(f"\n{click.style(project_ref.name, bold=True)}")
    click.echo(f"ID:          {project_ref.project_id}")
    click.echo(f"Path:        {project_ref.path}")

    if project_ref.description:
        click.echo(f"Description: {project_ref.description}")
    if project_ref.remote_url:
        click.echo(f"Remote:      {project_ref.remote_url}")
    if project_ref.last_accessed:
        click.echo(
            f"Last Access: {project_ref.last_accessed.strftime('%Y-%m-%d %H:%M')}"
        )

    click.echo(f"Default:     {'Yes' if project_ref.is_default else 'No'}")

    # Load project config
    try:
        config = manager.load_config()

        click.echo(f"\n{click.style('Project Configuration:', bold=True)}")
        click.echo(f"Version:     {config.version}")
        click.echo(f"GAT Version: {config.gat_version}")

        if config.contributors:
            click.echo(f"Contributors: {', '.join(config.contributors)}")

        # List scenarios
        scenarios = manager.list_scenarios()
        click.echo(f"\n{click.style('Scenarios:', bold=True)} ({len(scenarios)})")

        if scenarios:
            for scenario_id_item in scenarios:
                try:
                    scenario = manager.load_scenario(scenario_id_item)

                    if verbose:
                        # Show detailed info for each scenario
                        click.echo(f"\n  {click.style(scenario_id_item, bold=True)}")
                        click.echo(f"    Type:        {scenario.type}")
                        click.echo(f"    Name:        {scenario.name}")

                        if scenario.description:
                            click.echo(f"    Description: {scenario.description}")

                        # Show paths based on type
                        if isinstance(scenario, SiennaScenarioConfig):
                            system_path = manager.resolve_path(scenario.system.path)
                            system_exists = system_path.exists()
                            status = "✓" if system_exists else "✗"
                            click.echo(
                                f"    System:      {status} {scenario.system.path}"
                            )

                            sim_paths = scenario.get_simulation_paths_list()
                            click.echo(f"    Simulations: {len(sim_paths)} file(s)")
                            for sim_path in sim_paths:
                                sim_resolved = manager.resolve_path(sim_path)
                                sim_exists = sim_resolved.exists()
                                status = "✓" if sim_exists else "✗"
                                click.echo(f"      - {status} {sim_path}")

                        elif isinstance(scenario, ReedsScenarioConfig):
                            reeds_path = manager.resolve_path(scenario.path)
                            reeds_exists = reeds_path.exists()
                            status = "✓" if reeds_exists else "✗"
                            click.echo(f"    Path:        {status} {scenario.path}")
                            if scenario.solve_year:
                                click.echo(f"    Solve Year:  {scenario.solve_year}")

                        elif isinstance(scenario, PlexosScenarioConfig):
                            solution_path = manager.resolve_path(scenario.solution_path)
                            solution_exists = solution_path.exists()
                            status = "✓" if solution_exists else "✗"
                            click.echo(
                                f"    Solution:    {status} {scenario.solution_path}"
                            )
                    else:
                        # Show compact info
                        click.echo(
                            f"  - {scenario_id_item:<20} [{scenario.type}] {scenario.name}"
                        )

                except Exception as e:
                    click.echo(f"  - {scenario_id_item:<20} (error loading: {e})")
        else:
            click.echo("  No scenarios defined")

        if verbose and scenarios:
            click.echo(
                f"\n{click.style('Tip:', fg='cyan')} Use 'gat project show {project_id} <scenario_id>' for detailed scenario info"
            )

        # List palettes
        palettes = manager.list_palettes()
        click.echo(f"\n{click.style('Palettes:', bold=True)} ({len(palettes)})")
        if palettes:
            for palette_name in palettes:
                click.echo(f"  - {palette_name}")
        else:
            click.echo("  No palettes defined")

    except Exception as e:
        click.echo(f"\nError loading project: {e}", err=True)
        logger.exception("Failed to show project")


@project.command("set-default")
@click.argument("project_id")
def set_default_project_cmd(project_id: str):
    """
    Set a project as the default.

    The default project is used when no --project option is specified.

    Examples:

        gat project set-default my_project
    """
    from gat.models.user import load_project_ref, set_default_project

    # Check if project exists
    project_ref = load_project_ref(project_id)
    if not project_ref:
        click.echo(f"Error: Project '{project_id}' not found", err=True)
        sys.exit(1)

    # Set as default
    if set_default_project(project_id):
        click.echo(f"✓ Set '{project_ref.name}' as default project")
    else:
        click.echo(f"Error setting default project", err=True)
        sys.exit(1)


# Scenario subcommand group
@project.group("scenario")
def scenario():
    """Manage project scenarios."""
    pass


@scenario.command("add")
@click.argument("scenario_type", type=click.Choice(["sienna", "reeds", "plexos"]))
@click.argument("scenario_id")
@click.option("--name", help="Scenario name (defaults to scenario_id)")
@click.option("--description", help="Scenario description")
@click.option(
    "--project", "project_id", help="Project ID (uses default if not specified)"
)
@click.option("--default-palette", help="Default palette to use for this scenario")
@click.option(
    "--yes", "-y", is_flag=True, help="Overwrite existing scenarios without prompting"
)
# Sienna options
@click.option("--system", help="[Sienna] Path to system JSON file")
@click.option(
    "--simulation",
    "simulation_paths",
    multiple=True,
    help="[Sienna] Path to simulation HDF5 file. Supports: single file, multiple files, or glob patterns (e.g., 'week*.h5')",
)
@click.option(
    "--simulation-type",
    help="[Sienna] Specific simulation type (UC, ED, PF, etc.). If not specified, auto-discovers all simulations.",
)
@click.option("--metadata", help="[Sienna] Path to GAT metadata JSON file")
# ReEDS options
@click.option("--path", "reeds_path", help="[ReEDS] Path to ReEDS output directory")
@click.option("--solve-year", type=int, help="[ReEDS] Solve year to analyze")
# Plexos options
@click.option("--solution", help="[Plexos] Path to Plexos solution file")
def add_scenario(
    scenario_type: str,
    scenario_id: str,
    name: str,
    description: str,
    project_id: str,
    default_palette: str,
    yes: bool,
    system: str,
    simulation_paths: tuple,
    simulation_type: str,
    metadata: str,
    reeds_path: str,
    solve_year: int,
    solution: str,
):
    """
    Add a scenario to a project with automatic path resolution.

    Creates a YAML scenario configuration file in the project's scenarios/ directory.

    Paths can be relative (to current directory) or absolute. All paths are resolved
    to absolute filesystem paths for storage.

    For Sienna scenarios:

    - If --simulation-type is specified (e.g., UC, ED, PF), creates a single scenario
      for that specific simulation type
    - If --simulation-type is NOT specified, auto-discovers all simulation types in the
      file and creates separate scenarios for each (e.g., base_2035_UC, base_2035_ED)

    Examples:

        # Add a Sienna scenario for a specific simulation type
        gat project scenario add sienna base_2035 \
            --system ../data/system.json \
            --simulation ../data/results.h5 \
            --simulation-type UC

        # Auto-discover all simulation types (creates multiple scenarios)
        gat project scenario add sienna base_2035 \
            --system ../data/system.json \
            --simulation ../data/results.h5
        # This might create: base_2035_UC, base_2035_ED, base_2035_PF

        # Add a Sienna scenario with absolute paths
        gat project scenario add sienna base_2035 \
            --system /full/path/to/system.json \
            --simulation /full/path/to/results.h5 \
            --simulation-type UC

        # Add a Sienna scenario with multiple simulation files
        gat project scenario add sienna multi_week \
            --system ../data/system.json \
            --simulation ../data/week1.h5 \
            --simulation ../data/week2.h5 \
            --simulation-type UC

        # Add a Sienna scenario using a glob pattern
        gat project scenario add sienna weekly \
            --system ../data/system.json \
            --simulation "../data/week*.h5" \
            --simulation-type UC

        # Add a ReEDS scenario
        gat project scenario add reeds reeds_2035 \
            --path ../reeds_output \
            --solve-year 2035

        # Add to specific project
        gat project scenario add sienna test \
            --project my_project \
            --system ../data/system.json \
            --simulation ../data/results.h5 \
            --simulation-type ED
    """
    from pathlib import Path

    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            click.echo("Either specify --project or set a default with:")
            click.echo("  gat project set-default <project_id>")
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Helper function to resolve paths to absolute paths
    def resolve_to_absolute(path_str: str) -> str:
        """
        Convert a path to an absolute path.

        Paths can be:
        - Relative to current working directory (./data/file.json)
        - Absolute (/full/path/to/file.json)

        All paths are resolved to absolute filesystem paths.
        """
        if not path_str:
            return path_str

        # Convert to absolute path (relative to current working directory)
        return str(Path(path_str).resolve())

    def resolve_simulation_paths(path_or_pattern: str) -> List[str]:
        """
        Resolve simulation path(s) from a file path or glob pattern.

        Args:
            path_or_pattern: Single file path or glob pattern (e.g., "*.h5", "data/week*.h5")

        Returns:
            List of absolute paths to files found

        Raises:
            ValueError: If pattern matches no files or if path doesn't exist
        """
        import glob as glob_module

        path = Path(path_or_pattern)

        # Check if it contains glob patterns
        has_glob_chars = any(
            char in str(path_or_pattern) for char in ["*", "?", "[", "]"]
        )

        if has_glob_chars:
            # Expand glob pattern
            matches = sorted(glob_module.glob(str(path_or_pattern)))
            if not matches:
                raise ValueError(f"Glob pattern matched no files: {path_or_pattern}")

            # Convert to absolute paths
            return [str(Path(m).resolve()) for m in matches]
        else:
            # Single file path
            resolved = path.resolve()
            if not resolved.exists():
                raise ValueError(f"Simulation file not found: {path_or_pattern}")
            return [str(resolved)]

    # Default name to scenario_id
    if not name:
        name = scenario_id.replace("_", " ").title()

    # Build kwargs based on scenario type
    kwargs = {}
    if description:
        kwargs["description"] = description
    if default_palette:
        # Validate palette exists in project
        available_palettes = manager.list_palettes()
        if default_palette not in available_palettes:
            click.echo(
                f"Warning: Palette '{default_palette}' not found in project.",
                err=True,
            )
            click.echo(
                f"Available palettes: {', '.join(available_palettes) if available_palettes else 'none'}",
                err=True,
            )
            click.echo("Scenario will be created without a default palette.")
        else:
            kwargs["default_palette"] = default_palette

    try:
        # Initialize auto_discover for all branches
        auto_discover = False

        if scenario_type == "sienna":
            if not system:
                click.echo("Error: --system is required for Sienna scenarios", err=True)
                sys.exit(1)
            if not simulation_paths:
                click.echo(
                    "Error: --simulation is required for Sienna scenarios",
                    err=True,
                )
                sys.exit(1)

            # Resolve simulation paths - handle globs and multiple paths
            resolved_sim_paths = []
            glob_pattern = None

            # Track if we used a glob pattern (only if single pattern provided)
            if len(simulation_paths) == 1:
                sim_path = simulation_paths[0]
                has_glob_chars = any(
                    char in str(sim_path) for char in ["*", "?", "[", "]"]
                )
                if has_glob_chars:
                    glob_pattern = sim_path

            for sim_path in simulation_paths:
                try:
                    paths = resolve_simulation_paths(sim_path)
                    resolved_sim_paths.extend(paths)
                except ValueError as e:
                    click.echo(f"Error: {e}", err=True)
                    sys.exit(1)

            # Remove duplicates while preserving order
            seen = set()
            unique_sim_paths = []
            for path in resolved_sim_paths:
                if path not in seen:
                    seen.add(path)
                    unique_sim_paths.append(path)

            if not unique_sim_paths:
                click.echo("Error: No simulation files found", err=True)
                sys.exit(1)

            # Store as single path or list
            sim_paths = (
                unique_sim_paths if len(unique_sim_paths) > 1 else unique_sim_paths[0]
            )

            # Build simulation and system configs
            from gat.models.project import SimulationConfig, SystemConfig

            kwargs["simulation"] = SimulationConfig(
                paths=sim_paths, type=simulation_type, pattern=glob_pattern
            )
            kwargs["system"] = SystemConfig(path=resolve_to_absolute(system))

            if metadata:
                kwargs["metadata_path"] = resolve_to_absolute(metadata)

            # Determine if we should auto-discover
            auto_discover = simulation_type is None

        elif scenario_type == "reeds":
            auto_discover = False
            if not reeds_path:
                click.echo("Error: --path is required for ReEDS scenarios", err=True)
                sys.exit(1)

            kwargs["path"] = resolve_to_absolute(reeds_path)
            if solve_year:
                kwargs["solve_year"] = int(solve_year)

        elif scenario_type == "plexos":
            auto_discover = False
            if not solution:
                click.echo(
                    "Error: --solution is required for Plexos scenarios", err=True
                )
                sys.exit(1)

            kwargs["solution_path"] = resolve_to_absolute(solution)

        # Add the scenario (may return single config or list of configs)
        result = manager.add_scenario(
            scenario_id=scenario_id,
            name=name,
            scenario_type=scenario_type,
            auto_discover=auto_discover,
            overwrite=yes,
            **kwargs,
        )

        # Handle single or multiple scenarios
        if result is None:
            click.echo("No scenarios were created or updated.", err=True)
            sys.exit(1)

        configs = result if isinstance(result, list) else [result]

        if len(configs) == 0:
            click.echo("All scenarios already exist. Use --yes to overwrite.", err=True)
            sys.exit(1)

        if len(configs) > 1:
            click.echo(
                f"✓ Auto-discovered {len(configs)} simulation types. Created scenarios:"
            )
        else:
            click.echo(f"✓ Added scenario to project '{project_ref.name}':")

        from gat.models.project import SiennaScenarioConfig as SiennaConfig

        for config in configs:
            # Determine the actual scenario_id used
            if (
                len(configs) > 1
                and hasattr(config, "simulation")
                and config.simulation.type
            ):
                actual_id = f"{scenario_id}_{config.simulation.type}"
            else:
                actual_id = scenario_id

            click.echo(f"\n  Scenario ID: {actual_id}")
            click.echo(f"  Type: {config.type}")
            click.echo(f"  Name: {config.name}")

            if hasattr(config, "simulation") and config.simulation.type:
                click.echo(f"  Simulation Type: {config.simulation.type}")

            if config.default_palette:
                click.echo(f"  Default Palette: {config.default_palette}")

            # Show paths
            if isinstance(config, SiennaConfig):
                click.echo(f"  System: {config.system.path}")
                if isinstance(config.simulation.paths, list):
                    if config.simulation.pattern:
                        click.echo(
                            f"  Simulations: {len(config.simulation.paths)} file(s) from pattern: {config.simulation.pattern}"
                        )
                    else:
                        click.echo(
                            f"  Simulations: {len(config.simulation.paths)} file(s)"
                        )
                    for sim_path in config.simulation.paths[:3]:  # Show first 3
                        click.echo(f"    - {sim_path}")
                    if len(config.simulation.paths) > 3:
                        click.echo(
                            f"    ... and {len(config.simulation.paths) - 3} more"
                        )
                else:
                    click.echo(f"  Simulation: {config.simulation.paths}")

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error adding scenario: {e}", err=True)
        logger.exception("Scenario add failed")
        sys.exit(1)


@project.command("remove")
@click.argument("project_id")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation")
def remove_project(project_id: str, yes: bool):
    """
    Remove a project from your projects.

    This only removes the reference from your user metadata.
    The project directory itself is NOT deleted.

    Examples:

        gat project remove my_project
        gat project remove my_project --yes
    """
    from gat.models.user import delete_project_ref, load_project_ref

    project_ref = load_project_ref(project_id)
    if not project_ref:
        click.echo(f"Error: Project '{project_id}' not found", err=True)
        sys.exit(1)

    if not yes:
        click.echo(f"Remove project '{project_ref.name}' from your projects?")
        click.echo(f"Path: {project_ref.path}")
        click.echo(
            "\nNote: This only removes the reference. The project directory will NOT be deleted."
        )
        if not click.confirm("Continue?"):
            click.echo("Cancelled")
            return

    if delete_project_ref(project_id):
        click.echo(f"✓ Removed project '{project_ref.name}'")
    else:
        click.echo("Error removing project", err=True)
        sys.exit(1)


@scenario.command("remove")
@click.argument("scenario_id")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def scenario_remove(scenario_id: str, project_id: str, yes: bool):
    """
    Remove a scenario from a project.

    Examples:

        # Remove a scenario
        gat project scenario remove base_2035

        # Remove without confirmation
        gat project scenario remove base_2035 --yes

        # Remove from specific project
        gat project scenario remove base_2035 --project my_project
    """
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            click.echo("Either specify --project or set a default with:")
            click.echo("  gat project set-default <project_id>")
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Check if scenario exists
    try:
        scenario_config = manager.load_scenario(scenario_id)
    except FileNotFoundError:
        click.echo(f"Error: Scenario '{scenario_id}' not found", err=True)
        available = manager.list_scenarios()
        if available:
            click.echo(f"\nAvailable scenarios: {', '.join(available)}")
        sys.exit(1)

    # Confirm deletion
    if not yes:
        click.echo(
            f"Remove scenario '{scenario_id}' from project '{project_ref.name}'?"
        )
        click.echo(f"  Type: {scenario_config.type}")
        click.echo(f"  Name: {scenario_config.name}")
        if not click.confirm("\nContinue?"):
            click.echo("Cancelled")
            return

    # Delete scenario
    if manager.delete_scenario(scenario_id):
        click.echo(f"✓ Removed scenario '{scenario_id}'")
    else:
        click.echo("Error removing scenario", err=True)
        sys.exit(1)


@scenario.command("list")
@click.argument("project_id", required=False)
def scenario_list(project_id: str):
    """
    List scenarios across all projects or in a specific project.

    Examples:

        # List scenarios in all projects
        gat project scenario list

        # List scenarios in specific project
        gat project scenario list my-project
    """
    from gat.models.user import list_project_refs, load_project_ref
    from gat.project_management.manager import ProjectManager

    if project_id:
        # List scenarios for specific project
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)

        # Check project exists
        if not project_ref.exists():
            click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
            sys.exit(1)

        manager = ProjectManager(project_ref.get_path())
        scenarios = manager.list_scenarios()

        click.echo(f"\nScenarios in '{project_ref.name}': ({len(scenarios)})")

        if scenarios:
            for scenario_id in scenarios:
                try:
                    scenario = manager.load_scenario(scenario_id)
                    # Show simulation type if it exists (for Sienna scenarios)
                    sim_type_str = ""
                    if hasattr(scenario, "simulation") and scenario.simulation.type:
                        sim_type_str = f" [{scenario.simulation.type}]"
                    click.echo(
                        f"  {scenario_id:<20} {scenario.name:<30} [{scenario.type}]{sim_type_str}"
                    )
                except Exception as e:
                    click.echo(f"  {scenario_id:<20} (error loading: {e})")
        else:
            click.echo("  No scenarios found")
    else:
        # List scenarios across all projects
        project_refs = list_project_refs()

        if not project_refs:
            click.echo(
                "No projects found. Add a project with 'gat project add' or 'gat project init'"
            )
            return

        total_scenarios = 0
        for project_ref in project_refs:
            # Skip projects with missing paths
            if not project_ref.exists():
                continue

            manager = ProjectManager(project_ref.get_path())
            scenarios = manager.list_scenarios()

            if scenarios:
                click.echo(
                    f"\n{click.style(project_ref.name, bold=True)} ({project_ref.project_id}):"
                )
                for scenario_id in scenarios:
                    try:
                        scenario = manager.load_scenario(scenario_id)
                        # Show simulation type if it exists (for Sienna scenarios)
                        sim_type_str = ""
                        if hasattr(scenario, "simulation") and scenario.simulation.type:
                            sim_type_str = f" [{scenario.simulation.type}]"
                        click.echo(
                            f"  {scenario_id:<20} {scenario.name:<30} [{scenario.type}]{sim_type_str}"
                        )
                        total_scenarios += 1
                    except Exception as e:
                        click.echo(f"  {scenario_id:<20} (error loading: {e})")
                        total_scenarios += 1

        if total_scenarios == 0:
            click.echo("\nNo scenarios found across any projects.")
        else:
            click.echo(f"\nTotal scenarios: {total_scenarios}")


@scenario.command("show")
@click.argument("scenario_id")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
def scenario_show(scenario_id: str, project_id: str):
    """
    Show details for a specific scenario.

    Examples:

        # Show scenario in default project
        gat project scenario show base_2035

        # Show scenario in specific project
        gat project scenario show base_2035 --project my_project
    """
    from pathlib import Path

    from gat.models.project import (
        PlexosScenarioConfig,
        ReedsScenarioConfig,
        SiennaScenarioConfig,
    )
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Load scenario
    try:
        scenario = manager.load_scenario(scenario_id)
    except FileNotFoundError:
        click.echo(f"Error: Scenario '{scenario_id}' not found", err=True)
        available = manager.list_scenarios()
        if available:
            click.echo(f"\nAvailable scenarios: {', '.join(available)}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error loading scenario: {e}", err=True)
        sys.exit(1)

    # Show detailed scenario information
    click.echo(f"\n{click.style(f'Scenario: {scenario_id}', bold=True)}")
    click.echo(f"Name:        {scenario.name}")
    click.echo(f"Type:        {scenario.type}")

    if scenario.description:
        click.echo(f"Description: {scenario.description}")

    if scenario.created_at:
        click.echo(f"Created:     {scenario.created_at.strftime('%Y-%m-%d %H:%M')}")
    if scenario.updated_at:
        click.echo(f"Updated:     {scenario.updated_at.strftime('%Y-%m-%d %H:%M')}")

    # Show type-specific paths
    click.echo(f"\n{click.style('Paths:', bold=True)}")

    if isinstance(scenario, SiennaScenarioConfig):
        system_path = manager.resolve_path(scenario.system.path)
        system_exists = system_path.exists()
        status = "✓" if system_exists else "✗"
        click.echo(f"  System:      {status} {scenario.system.path}")
        if not system_exists:
            click.echo(f"               (resolved: {system_path})")

        sim_paths = scenario.get_simulation_paths_list()
        if scenario.simulation.pattern:
            click.echo(
                f"  Simulations: ({len(sim_paths)} file(s) from pattern: {scenario.simulation.pattern})"
            )
        else:
            click.echo(f"  Simulations: ({len(sim_paths)} file(s))")
        for sim_path in sim_paths:
            sim_resolved = manager.resolve_path(sim_path)
            sim_exists = sim_resolved.exists()
            status = "✓" if sim_exists else "✗"
            click.echo(f"    - {status} {sim_path}")
            if not sim_exists:
                click.echo(f"           (resolved: {sim_resolved})")

        if scenario.metadata_path:
            metadata_path = manager.resolve_path(scenario.metadata_path)
            metadata_exists = metadata_path.exists()
            status = "✓" if metadata_exists else "✗"
            click.echo(f"  Metadata:    {status} {scenario.metadata_path}")
            if not metadata_exists:
                click.echo(f"               (resolved: {metadata_path})")

    elif isinstance(scenario, ReedsScenarioConfig):
        reeds_path = manager.resolve_path(scenario.path)
        reeds_exists = reeds_path.exists()
        status = "✓" if reeds_exists else "✗"
        click.echo(f"  Path:        {status} {scenario.path}")
        if not reeds_exists:
            click.echo(f"               (resolved: {reeds_path})")
        if scenario.solve_year:
            click.echo(f"  Solve Year:  {scenario.solve_year}")

    elif isinstance(scenario, PlexosScenarioConfig):
        solution_path = manager.resolve_path(scenario.solution_path)
        solution_exists = solution_path.exists()
        status = "✓" if solution_exists else "✗"
        click.echo(f"  Solution:    {status} {scenario.solution_path}")
        if not solution_exists:
            click.echo(f"               (resolved: {solution_path})")

    # Validate paths
    warnings = manager.validate_scenario_paths(scenario_id)
    if warnings:
        click.echo(f"\n{click.style('Warnings:', fg='yellow', bold=True)}")
        for warning in warnings:
            click.echo(f"  ⚠ {warning}")
    else:
        click.echo(f"\n{click.style('✓ All paths validated', fg='green')}")


@scenario.command("discover-datasets")
@click.argument("scenario_id")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
@click.option(
    "--save",
    is_flag=True,
    help="Save discovered dataset configurations to scenario YAML",
)
def scenario_discover_datasets(scenario_id: str, project_id: str, save: bool):
    """
    Discover datasets in a scenario and show which will have base_power applied.

    By default, datasets with "Power" in their name are flagged for base_power
    multiplication. Use --save to store these configurations in the scenario YAML.

    Examples:

        # Discover datasets (preview only)
        gat project scenario discover-datasets my_scenario_UC

        # Discover and save to scenario configuration
        gat project scenario discover-datasets my_scenario_UC --save

        # For specific project
        gat project scenario discover-datasets my_scenario_UC --project my_project --save
    """
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.project_management.manager import ProjectManager
    from gat.simulations import SiennaSimulationParser

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Load scenario
    try:
        scenario = manager.load_scenario(scenario_id)
    except FileNotFoundError:
        click.echo(f"Error: Scenario '{scenario_id}' not found", err=True)
        sys.exit(1)

    # Only works with Sienna scenarios
    if scenario.type != "sienna":
        click.echo(f"Error: This command only works with Sienna scenarios", err=True)
        click.echo(f"Scenario '{scenario_id}' is type: {scenario.type}")
        sys.exit(1)

    click.echo(f"\n{click.style('Discovering datasets...', bold=True)}")
    click.echo(f"Scenario: {scenario.name}")
    click.echo(f"Simulation type: {scenario.simulation.type or 'default'}")

    try:
        # Discover datasets
        scenario.discover_and_set_dataset_configs()

        # Get the config
        dataset_config = scenario.get_dataset_config()

        if not dataset_config:
            click.echo("No dataset configuration found", err=True)
            sys.exit(1)

        # Get configured datasets
        dataset_names = dataset_config.list_dataset_names()

        click.echo(
            f"\n{click.style(f'Configured {len(dataset_names)} datasets:', fg='green', bold=True)}"
        )

        # Display datasets by type
        from gat.models.base import AggregateDataset, RawDataset

        aggregate_datasets = []
        raw_datasets = []

        for name in dataset_names:
            definition = dataset_config.get_dataset_config(name)
            if isinstance(definition, AggregateDataset):
                aggregate_datasets.append((name, definition))
            elif isinstance(definition, RawDataset):
                raw_datasets.append((name, definition))

        if aggregate_datasets:
            click.echo(
                f"\n{click.style(f'  Aggregate Datasets ({len(aggregate_datasets)}):', fg='cyan')}"
            )
            for name, defn in aggregate_datasets[:15]:  # Show first 15
                patterns_str = ", ".join(defn.patterns[:2])
                if len(defn.patterns) > 2:
                    patterns_str += f", ... (+{len(defn.patterns) - 2})"
                scale_str = (
                    f"scale={defn.scale_factor}" if defn.scale_factor != 1.0 else ""
                )
                click.echo(f"    • {name}: [{patterns_str}] {scale_str}")
            if len(aggregate_datasets) > 15:
                click.echo(f"    ... and {len(aggregate_datasets) - 15} more")

        if raw_datasets:
            click.echo(
                f"\n{click.style(f'  Raw Datasets ({len(raw_datasets)}):', fg='white')}"
            )
            for name, defn in raw_datasets[:10]:  # Show first 10
                scale_str = (
                    f"scale={defn.scale_factor}" if defn.scale_factor != 1.0 else ""
                )
                click.echo(f"    • {name} {scale_str}")
            if len(raw_datasets) > 10:
                click.echo(f"    ... and {len(raw_datasets) - 10} more")

        # Save if requested
        if save:
            manager.save_scenario(scenario_id, scenario)
            click.echo(
                f"\n{click.style('✓ Saved dataset configurations to scenario', fg='green')}"
            )
            click.echo(f"  File: scenarios/{scenario_id}.yaml")
        else:
            click.echo(
                f"\n{click.style('Preview only - use --save to store configurations', fg='yellow')}"
            )

    except Exception as e:
        click.echo(f"Error discovering datasets: {e}", err=True)
        logger.exception("Dataset discovery failed")
        sys.exit(1)


# Palette subcommand group
@project.group("palette")
def palette():
    """Manage project palettes."""
    pass


@palette.command("add")
@click.argument("palette_name")
@click.argument("scenario_id")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
@click.option(
    "--description",
    help="Palette description",
)
@click.option(
    "--print-summary",
    is_flag=True,
    help="Print a summary of the generated palette",
)
def palette_add(
    palette_name: str,
    scenario_id: str,
    project_id: str,
    description: str,
    print_summary: bool,
):
    """
    Generate a palette from a scenario's system file.

    Creates a new palette by reading the system file from a scenario and
    auto-generating display categories, colors, and classifications based
    on the generators found in the system.

    Examples:

        # Generate palette from a scenario
        gat project palette add renewable_focus base_2035

        # With custom description
        gat project palette add my_palette base_2035 \
            --description "Focus on renewable technologies"

        # For specific project
        gat project palette add my_palette base_2035 \
            --project my_project

        # Show detailed summary
        gat project palette add my_palette base_2035 --print-summary
    """
    from gat.datahelpers.sienna_system import SiennaSystem
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.palette_generator import PaletteGenerator
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            click.echo("Either specify --project or set a default with:")
            click.echo("  gat project set-default <project_id>")
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Load scenario
    try:
        scenario_config = manager.load_scenario(scenario_id)
    except FileNotFoundError:
        click.echo(f"Error: Scenario '{scenario_id}' not found", err=True)
        available = manager.list_scenarios()
        if available:
            click.echo(f"\nAvailable scenarios: {', '.join(available)}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error loading scenario: {e}", err=True)
        sys.exit(1)

    # Check if it's a Sienna scenario (only supported for now)
    from gat.models.project import SiennaScenarioConfig

    if not isinstance(scenario_config, SiennaScenarioConfig):
        click.echo(
            f"Error: Palette generation only supported for Sienna scenarios",
            err=True,
        )
        click.echo(f"Scenario '{scenario_id}' is type: {scenario_config.type}")
        sys.exit(1)

    # Get system file path
    system_path = manager.resolve_path(scenario_config.system.path)
    if not system_path.exists():
        click.echo(
            f"Error: System file not found: {scenario_config.system.path}", err=True
        )
        sys.exit(1)

    # Check if palette already exists
    existing_palettes = manager.list_palettes()
    if palette_name in existing_palettes:
        click.echo(f"Error: Palette '{palette_name}' already exists", err=True)
        click.echo("Use a different name or delete the existing palette first")
        sys.exit(1)

    # Load system and generate palette
    try:
        click.echo(f"Reading system file: {scenario_config.system.path}")
        system = SiennaSystem(str(system_path))

        click.echo(f"Generating palette from system...")
        generator = PaletteGenerator(system)

        palette = generator.generate(
            name=palette_name,
            simulation_type=scenario_config.type,
            description=description,
        )

        # Save palette
        manager.save_palette(palette_name, palette)

        click.echo(
            f"✓ Created palette '{palette_name}' in project '{project_ref.name}'"
        )
        click.echo(f"  Display categories: {len(palette.display_categories)}")
        click.echo(f"  Simulation mappings: {len(palette.category_mappings)}")

        if palette.vre_classification:
            vre_count = len(palette.vre_classification.vre_technologies)
            click.echo(f"  VRE technologies: {vre_count}")

        # Print detailed summary if requested
        if print_summary:
            click.echo("")
            generator.print_summary(palette)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error generating palette: {e}", err=True)
        logger.exception("Palette generation failed")
        sys.exit(1)


@palette.command("remove")
@click.argument("palette_name")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def palette_remove(palette_name: str, project_id: str, yes: bool):
    """
    Remove a palette from a project.

    Examples:

        # Remove a palette
        gat project palette remove my_palette

        # Remove without confirmation
        gat project palette remove my_palette --yes

        # Remove from specific project
        gat project palette remove my_palette --project my_project
    """
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            click.echo("Either specify --project or set a default with:")
            click.echo("  gat project set-default <project_id>")
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Check if palette exists
    palettes = manager.list_palettes()
    if palette_name not in palettes:
        click.echo(f"Error: Palette '{palette_name}' not found", err=True)
        if palettes:
            click.echo(f"\nAvailable palettes: {', '.join(palettes)}")
        sys.exit(1)

    # Confirm deletion
    if not yes:
        click.echo(
            f"Remove palette '{palette_name}' from project '{project_ref.name}'?"
        )
        if not click.confirm("\nContinue?"):
            click.echo("Cancelled")
            return

    # Delete palette
    palette_path = manager.project_path / "palettes" / f"{palette_name}.yaml"
    palette_path.unlink()
    click.echo(f"✓ Removed palette '{palette_name}'")


@palette.command("list")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
def palette_list(project_id: str):
    """
    List all palettes in a project.

    Examples:

        # List palettes in default project
        gat project palette list

        # List palettes in specific project
        gat project palette list --project my_project
    """
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())
    palettes = manager.list_palettes()

    click.echo(f"\nPalettes in '{project_ref.name}': ({len(palettes)})")

    if palettes:
        for palette_name in palettes:
            click.echo(f"  {palette_name}")
    else:
        click.echo("  No palettes found")


@palette.command("show")
@click.argument("palette_name")
@click.option(
    "--project",
    "project_id",
    help="Project ID (uses default if not specified)",
)
def palette_show(palette_name: str, project_id: str):
    """
    Show details for a specific palette.

    Examples:

        # Show palette in default project
        gat project palette show my_palette

        # Show palette in specific project
        gat project palette show my_palette --project my_project
    """
    from gat.models.user import get_default_project_ref, load_project_ref
    from gat.palette_generator import PaletteGenerator
    from gat.project_management.manager import ProjectManager

    # Get project
    if project_id:
        project_ref = load_project_ref(project_id)
        if not project_ref:
            click.echo(f"Error: Project '{project_id}' not found", err=True)
            sys.exit(1)
    else:
        project_ref = get_default_project_ref()
        if not project_ref:
            click.echo("Error: No default project set", err=True)
            sys.exit(1)

    # Check project exists
    if not project_ref.exists():
        click.echo(f"Error: Project path not found: {project_ref.path}", err=True)
        sys.exit(1)

    manager = ProjectManager(project_ref.get_path())

    # Load palette
    try:
        palette = manager.load_palette(palette_name)
    except FileNotFoundError:
        click.echo(f"Error: Palette '{palette_name}' not found", err=True)
        available = manager.list_palettes()
        if available:
            click.echo(f"\nAvailable palettes: {', '.join(available)}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error loading palette: {e}", err=True)
        sys.exit(1)

    # Show palette details using PaletteGenerator's print_summary
    # Create a mock generator just for the print function
    click.echo()  # Add newline

    click.echo(f"Palette: {palette.name}")
    if palette.description:
        click.echo(f"Description: {palette.description}")
    click.echo(f"Simulation Type: {palette.simulation_type}")
    click.echo(f"Version: {palette.version}")

    if palette.created_at:
        click.echo(f"Created: {palette.created_at}")
    if palette.updated_at:
        click.echo(f"Updated: {palette.updated_at}")

    click.echo(f"\nDisplay Categories ({len(palette.display_categories)}):")
    click.echo("-" * 60)

    for cat in palette.display_categories:
        # Count how many simulation categories map to this
        mappings = [
            m for m in palette.category_mappings if m.display_category == cat.name
        ]
        click.echo(f"  {cat.name:30s} {cat.color:10s} ({len(mappings)} sim categories)")

    if palette.vre_classification and palette.vre_classification.vre_technologies:
        click.echo(
            f"\nVRE Technologies ({len(palette.vre_classification.vre_technologies)}):"
        )
        for tech in palette.vre_classification.vre_technologies:
            click.echo(f"  - {tech}")

    if (
        palette.load_classification
        and palette.load_classification.storage_charging_categories
    ):
        click.echo(
            f"\nStorage Charging Categories ({len(palette.load_classification.storage_charging_categories)}):"
        )
        for cat in palette.load_classification.storage_charging_categories:
            click.echo(f"  - {cat}")

    click.echo(f"\nStack Order (bottom to top):")
    for i, cat_name in enumerate(palette.stack_order, 1):
        click.echo(f"  {i}. {cat_name}")

    # Validate
    warnings = palette.validate_stack_order()
    if warnings:
        click.echo(f"\n{click.style('Warnings:', fg='yellow', bold=True)}")
        for warning in warnings:
            click.echo(f"  ⚠ {warning}")
    else:
        click.echo(f"\n{click.style('✓ Palette validated', fg='green')}")
