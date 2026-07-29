# gat/cli_projects.py
"""
CLI commands for project and source management.
"""

import click


@click.group("projects")
def projects():
    """Manage GAT projects."""
    pass


@projects.command("list")
@click.option("--refresh", is_flag=True, help="Refresh project cache before listing")
def list_projects(refresh: bool):
    """List all available projects."""
    from gat.models.user import load_user_config
    from gat.project_management.discovery import ProjectDiscovery

    config = load_user_config()

    if refresh or not config.project_cache.projects:
        discovery = ProjectDiscovery(config)
        discovery.refresh()
        config = load_user_config()  # Reload after refresh

    if not config.project_cache.projects:
        click.echo("No projects found. Add a source with 'gat sources add'")
        return

    # Group by source
    by_source = {}
    for project in config.project_cache.projects:
        if project.source_name not in by_source:
            by_source[project.source_name] = []
        by_source[project.source_name].append(project)

    for source_name, source_projects in by_source.items():
        click.echo(f"\n{click.style(source_name, bold=True)}")
        click.echo("-" * len(source_name))
        for p in source_projects:
            scenarios_str = f"({len(p.scenarios)} scenarios)" if p.scenarios else ""
            type_str = f"[{p.source_type}]"
            click.echo(
                f"  {p.project_id:<20} {type_str:<10} {p.name:<25} {scenarios_str}"
            )


@projects.command("refresh")
def refresh_projects():
    """Refresh the project cache by scanning all sources."""
    from gat.models.user import load_user_config
    from gat.project_management.discovery import ProjectDiscovery

    config = load_user_config()

    if not config.data_sources:
        click.echo("No sources configured. Add one with 'gat sources add'")
        return

    discovery = ProjectDiscovery(config)

    click.echo("Scanning data sources...")
    projects_found = discovery.refresh()

    click.echo(
        f"\nFound {len(projects_found)} projects across "
        f"{len(config.data_sources)} sources"
    )


@projects.command("show")
@click.argument("project_id")
def show_project(project_id: str):
    """Show details for a specific project."""
    from gat.models.user import load_user_config
    from gat.project_management.discovery import ProjectDiscovery

    config = load_user_config()
    discovery = ProjectDiscovery(config)

    project = discovery.get_project(project_id)

    if not project:
        click.echo(f"Project '{project_id}' not found. Try 'gat projects refresh'")
        return

    click.echo(f"\n{click.style(project.name, bold=True)}")
    click.echo(f"  ID:     {project.project_id}")
    click.echo(f"  Type:   {project.source_type}")
    click.echo(f"  Source: {project.source_name}")
    click.echo(f"  Path:   {project.path}")

    if project.last_modified:
        click.echo(f"  Modified: {project.last_modified.strftime('%Y-%m-%d %H:%M')}")

    if project.scenarios:
        click.echo(f"\n  Scenarios ({len(project.scenarios)}):")
        for scenario in project.scenarios:
            click.echo(f"    - {scenario}")


# ============================================================
# Sources Command Group
# ============================================================


@click.group("sources")
def sources():
    """Manage data sources (Sienna, ReEDS, Plexos simulations)."""
    pass


@sources.command("list")
def list_sources():
    """List configured data sources."""
    from gat.models.user import load_user_config

    config = load_user_config()

    if not config.data_sources:
        click.echo("No sources configured. Add one with 'gat sources add'")
        return

    click.echo("\nConfigured data sources:\n")
    for source in config.data_sources:
        click.echo(f"  {click.style(source.name, bold=True)} [{source.type}]")

        # Display type-specific info
        if source.type == "sienna":
            click.echo(f"    System:      {source.system_path}")
            paths = source.get_simulation_paths_list()
            if len(paths) == 1:
                click.echo(f"    Simulation:  {paths[0]}")
            else:
                click.echo(f"    Simulations: {len(paths)} files")
                for p in paths[:3]:  # Show first 3
                    click.echo(f"      - {p}")
                if len(paths) > 3:
                    click.echo(f"      ... and {len(paths) - 3} more")

        elif source.type == "reeds":
            click.echo(f"    Path: {source.path}")
            if source.solve_year:
                click.echo(f"    Solve Year: {source.solve_year}")

        elif source.type == "plexos":
            click.echo(f"    Solution: {source.solution_path}")

        if source.description:
            click.echo(f"    Description: {source.description}")
        click.echo()


@sources.command("types")
def list_source_types():
    """List available source types and their required arguments."""
    from gat.models.user import SOURCE_TYPES

    click.echo("\nAvailable source types:\n")
    for type_name, info in SOURCE_TYPES.items():
        click.echo(f"  {click.style(type_name, bold=True)}")
        click.echo(f"    {info['description']}")
        click.echo(f"    Required: {', '.join(info['required_args'])}")
        if info["optional_args"]:
            click.echo(f"    Optional: {', '.join(info['optional_args'])}")
        click.echo()


# ============================================================
# Source Add Subcommands (one per type)
# ============================================================


@sources.group("add")
def add_source():
    """Add a new data source."""
    pass


@add_source.command("sienna")
@click.argument("name")
@click.option(
    "--system-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to Sienna system JSON file",
)
@click.option(
    "--simulation-path",
    "simulation_paths",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Path to simulation HDF5 file(s). Can be specified multiple times.",
)
@click.option("--description", help="Description of this source")
def add_sienna(name, system_path, simulation_paths, description):
    """Add a Sienna simulation source.

    Examples:

        gat sources add sienna "NTP Base" --system-path ./system.json --simulation-path ./results.h5

        gat sources add sienna "Multi-file" --system-path ./system.json \\
            --simulation-path ./week1.h5 --simulation-path ./week2.h5
    """
    from gat.models.user import SiennaSource, load_user_config, save_user_config

    config = load_user_config()

    # Check for duplicate names
    if config.get_source(name):
        click.echo(f"Error: Source '{name}' already exists", err=True)
        raise SystemExit(1)

    # Convert paths to absolute paths
    import os

    system_path = os.path.abspath(system_path)
    simulation_paths = [os.path.abspath(p) for p in simulation_paths]

    # Create source (single path if only one, list otherwise)
    sim_paths = (
        simulation_paths[0] if len(simulation_paths) == 1 else list(simulation_paths)
    )

    source = SiennaSource(
        name=name,
        system_path=system_path,
        simulation_paths=sim_paths,
        description=description,
    )

    config.data_sources.append(source)
    save_user_config(config)

    click.echo(f"Added Sienna source '{name}'")
    click.echo(f"  System: {system_path}")
    click.echo(f"  Simulations: {len(simulation_paths)} file(s)")


@add_source.command("reeds")
@click.argument("name")
@click.option(
    "--path",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Path to ReEDS output directory",
)
@click.option("--solve-year", type=int, help="Solve year to filter results")
@click.option("--description", help="Description of this source")
def add_reeds(name, path, solve_year, description):
    """Add a ReEDS simulation source.

    Example:

        gat sources add reeds "ReEDS 2035" --path ./reeds_outputs --solve-year 2035
    """
    from gat.models.user import ReedsSource, load_user_config, save_user_config

    config = load_user_config()

    # Check for duplicate names
    if config.get_source(name):
        click.echo(f"Error: Source '{name}' already exists", err=True)
        raise SystemExit(1)

    # Convert to absolute path
    import os

    path = os.path.abspath(path)

    source = ReedsSource(
        name=name,
        path=path,
        solve_year=solve_year,
        description=description,
    )

    config.data_sources.append(source)
    save_user_config(config)

    click.echo(f"Added ReEDS source '{name}'")
    click.echo(f"  Path: {path}")
    if solve_year:
        click.echo(f"  Solve Year: {solve_year}")


@add_source.command("plexos")
@click.argument("name")
@click.option(
    "--solution-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to Plexos solution file or directory",
)
@click.option("--description", help="Description of this source")
def add_plexos(name, solution_path, description):
    """Add a Plexos simulation source.

    Example:

        gat sources add plexos "Summer Peak" --solution-path ./Model.xml
    """
    from gat.models.user import PlexosSource, load_user_config, save_user_config

    config = load_user_config()

    # Check for duplicate names
    if config.get_source(name):
        click.echo(f"Error: Source '{name}' already exists", err=True)
        raise SystemExit(1)

    # Convert to absolute path
    import os

    solution_path = os.path.abspath(solution_path)

    source = PlexosSource(
        name=name,
        solution_path=solution_path,
        description=description,
    )

    config.data_sources.append(source)
    save_user_config(config)

    click.echo(f"Added Plexos source '{name}'")
    click.echo(f"  Solution: {solution_path}")


@sources.command("remove")
@click.argument("name")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def remove_source(name, yes):
    """Remove a data source."""
    from gat.models.user import load_user_config, save_user_config

    config = load_user_config()

    # Check if source exists
    if not config.get_source(name):
        click.echo(f"Error: Source '{name}' not found", err=True)
        raise SystemExit(1)

    if not yes:
        click.confirm(f"Remove source '{name}'?", abort=True)

    config.data_sources = [s for s in config.data_sources if s.name != name]

    # Also remove cached projects from this source
    config.project_cache.projects = [
        p for p in config.project_cache.projects if p.source_name != name
    ]

    save_user_config(config)
    click.echo(f"Removed source '{name}'")


@sources.command("show")
@click.argument("name")
def show_source(name):
    """Show details for a specific source."""
    from gat.models.user import load_user_config

    config = load_user_config()
    source = config.get_source(name)

    if not source:
        click.echo(f"Error: Source '{name}' not found", err=True)
        raise SystemExit(1)

    click.echo(f"\n{click.style(source.name, bold=True)}")
    click.echo(f"  Type: {source.type}")

    if source.type == "sienna":
        click.echo(f"  System Path: {source.system_path}")
        paths = source.get_simulation_paths_list()
        click.echo(f"  Simulation Paths ({len(paths)}):")
        for p in paths:
            click.echo(f"    - {p}")

    elif source.type == "reeds":
        click.echo(f"  Path: {source.path}")
        if source.solve_year:
            click.echo(f"  Solve Year: {source.solve_year}")

    elif source.type == "plexos":
        click.echo(f"  Solution Path: {source.solution_path}")

    if source.description:
        click.echo(f"  Description: {source.description}")

    # Validate paths exist
    click.echo("\n  Path Validation:")
    for path in source.get_paths():
        import os

        exists = os.path.exists(path)
        status = click.style("✓", fg="green") if exists else click.style("✗", fg="red")
        click.echo(f"    {status} {path}")


# ============================================================
# Config Command
# ============================================================


@click.command("config")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--path", "show_path", is_flag=True, help="Show config file path")
@click.option("--edit", is_flag=True, help="Open config file in editor")
def config_cmd(show, show_path, edit):
    """View or edit GAT configuration."""
    import json
    import os
    import subprocess

    from gat.models.user import get_config_path, load_user_config

    config_path = get_config_path()

    if show_path:
        click.echo(config_path)
        return

    if edit:
        editor = os.environ.get("EDITOR", "vim")
        subprocess.run([editor, str(config_path)])
        return

    if show or not (show_path or edit):
        config = load_user_config()
        click.echo(f"Config file: {config_path}\n")
        # Pretty print the config
        config_dict = config.model_dump(exclude_none=True)
        click.echo(json.dumps(config_dict, indent=2, default=str))
