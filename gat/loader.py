"""
GAT Loader - Simplified API for loading projects, scenarios, and palettes.

Provides a high-level `load()` function that handles defaults and provides
informative logging to guide users.
"""

from pathlib import Path
from typing import Optional, Union

from loguru import logger

from gat.models.palette import Palette
from gat.models.user import (
    get_default_project_ref,
    list_project_refs,
    load_project_ref,
)
from gat.project_management.manager import ProjectManager
from gat.scenariohandlers import (
    PlexosScenario,
    ReEDsScenario,
    SiennaScenario,
)


def load(
    project: Optional[str] = None,
    scenario: Optional[str] = None,
    palette: Optional[str] = None,
    verbose: bool = True,
    server_url: Optional[str] = None,
) -> tuple:
    """
    Load a GAT project, scenario, and palette with smart defaults.

    This is the primary entry point for loading GAT data in Python scripts.
    It handles default resolution and provides informative logging.

    Args:
        project: Project ID. If None, uses default project.
        scenario: Scenario ID. If None, uses default scenario from project.
        palette: Palette name. If None, uses default palette from scenario or project.
        verbose: If True, logs informative messages about what's being loaded.
                 Set to False to suppress info messages.
        server_url: If provided, connects to a GAT server and returns a
            RemoteScenario instead of loading locally. Requires project and
            scenario to be specified.

    Returns:
        tuple: (scenario_object, palette_object, project_manager)
            - scenario_object: The loaded scenario handler or RemoteScenario
            - palette_object: The loaded Palette object (or None for remote)
            - project_manager: ProjectManager instance (or None for remote)

    Raises:
        ValueError: If project, scenario, or required resources cannot be found
        FileNotFoundError: If configuration files are missing

    Examples:
        # Load default project, scenario, and palette
        scenario, palette, project = gat.load()

        # Load from a remote GAT server
        scenario, palette, project = gat.load(
            project="rts-gmlc", scenario="base",
            server_url="http://localhost:8815"
        )
    """
    # Check for server URL from env if not provided
    import os
    if server_url is None:
        server_url = os.environ.get("GAT_SERVER")

    # Remote mode: return a RemoteScenario
    if server_url:
        return _load_remote(project, scenario, server_url, verbose)
    # Setup logging context
    if verbose:
        log_func = logger.info
    else:
        log_func = logger.debug

    # Step 1: Resolve project
    if project is None:
        project_ref = get_default_project_ref()
        if project_ref is None:
            available_projects = list_project_refs()
            if not available_projects:
                raise ValueError(
                    "No projects found. Create a project with 'gat project init' "
                    "or add an existing project with 'gat project add'"
                )
            raise ValueError(
                "No default project set. Either:\n"
                "  1. Set a default: gat project set-default <project-id>\n"
                "  2. Pass project explicitly: gat.load(project='<project-id>')\n"
                f"\nAvailable projects: {', '.join(p.project_id for p in available_projects)}"
            )
        project_id = project_ref.project_id
        log_func(f"Loading default project: '{project_ref.name}' ({project_id})")
        if verbose:
            logger.info(
                "💡 To load a specific project, use: gat.load(project='<project-id>')"
            )
    else:
        project_id = project
        project_ref = load_project_ref(project_id)
        if project_ref is None:
            available_projects = list_project_refs()
            raise ValueError(
                f"Project '{project_id}' not found. "
                f"Available projects: {', '.join(p.project_id for p in available_projects)}"
            )
        log_func(f"Loading project: '{project_ref.name}' ({project_id})")

    # Validate project exists
    if not project_ref.exists():
        raise FileNotFoundError(
            f"Project path not found: {project_ref.path}\n"
            f"The project directory may have been moved or deleted."
        )

    # Create project manager
    manager = ProjectManager(project_ref.get_path())
    project_config = manager.load_config()

    # Step 2: Resolve scenario
    available_scenarios = manager.list_scenarios()
    if not available_scenarios:
        raise ValueError(
            f"Project '{project_ref.name}' has no scenarios.\n"
            f"Add a scenario with: gat project scenario add"
        )

    if scenario is None:
        # Try to use default scenario from project config
        if project_config.default_scenario:
            scenario_id = project_config.default_scenario
            if scenario_id not in available_scenarios:
                logger.warning(
                    f"Default scenario '{scenario_id}' not found in project. "
                    f"Using first available scenario."
                )
                scenario_id = available_scenarios[0]
            else:
                log_func(f"Loading default scenario: '{scenario_id}'")
                if verbose:
                    logger.info(
                        "💡 To load a specific scenario, use: gat.load(scenario='<scenario-id>')"
                    )
        else:
            # No default set, use first available
            scenario_id = available_scenarios[0]
            log_func(f"No default scenario set, using first available: '{scenario_id}'")
            if verbose:
                logger.info(
                    "💡 To set a default scenario, edit gat-project.yaml or use: "
                    f"gat.load(scenario='<scenario-id>')"
                )
                logger.info(f"💡 Available scenarios: {', '.join(available_scenarios)}")
    else:
        scenario_id = scenario
        if scenario_id not in available_scenarios:
            raise ValueError(
                f"Scenario '{scenario_id}' not found in project '{project_ref.name}'.\n"
                f"Available scenarios: {', '.join(available_scenarios)}"
            )
        log_func(f"Loading scenario: '{scenario_id}'")

    # Load scenario configuration
    scenario_config = manager.load_scenario(scenario_id)

    # Step 3: Resolve palette
    available_palettes = manager.list_palettes()
    palette_obj = None
    palette_name = None

    if palette is None:
        # Try default palette from scenario config first
        if scenario_config.default_palette:
            palette_name = scenario_config.default_palette
            if palette_name not in available_palettes:
                logger.warning(
                    f"Scenario's default palette '{palette_name}' not found. "
                    f"Trying project default..."
                )
                palette_name = None
            else:
                log_func(f"Loading scenario's default palette: '{palette_name}'")
                if verbose:
                    logger.info(
                        "💡 To load a different palette, use: gat.load(palette='<palette-name>')"
                    )

        # Try default palette from project config
        if palette_name is None and project_config.default_palette:
            palette_name = project_config.default_palette
            if palette_name not in available_palettes:
                logger.warning(f"Project's default palette '{palette_name}' not found.")
                palette_name = None
            else:
                log_func(f"Loading project's default palette: '{palette_name}'")
                if verbose:
                    logger.info(
                        "💡 To load a different palette, use: gat.load(palette='<palette-name>')"
                    )

        # Use first available palette if no defaults
        if palette_name is None and available_palettes:
            palette_name = available_palettes[0]
            log_func(f"No default palette set, using first available: '{palette_name}'")
            if verbose:
                logger.info(
                    "💡 To set a default palette, add 'default_palette' to scenario "
                    "or project config"
                )
                logger.info(f"💡 Available palettes: {', '.join(available_palettes)}")
        elif palette_name is None:
            logger.warning("No palettes found in project. Palette will be None.")
            if verbose:
                logger.info(
                    "💡 Generate a palette with: gat project palette add <name> <scenario-id>"
                )
    else:
        palette_name = palette
        if palette_name not in available_palettes:
            logger.warning(
                f"Palette '{palette_name}' not found in project. "
                f"Available palettes: {', '.join(available_palettes) if available_palettes else 'none'}"
            )
            palette_name = None
        else:
            log_func(f"Loading palette: '{palette_name}'")

    # Load palette if we have one
    if palette_name:
        try:
            palette_obj = manager.load_palette(palette_name)
        except Exception as e:
            logger.error(f"Failed to load palette '{palette_name}': {e}")
            palette_obj = None

    # Step 4: Load scenario object
    log_func(f"Creating scenario handler for type: {scenario_config.type}")

    if scenario_config.type == "sienna":
        # Accept both the structured system: SystemConfig API and the legacy
        # flat system_path attribute (for backwards-compat with mocks/older configs).
        system_file = getattr(scenario_config, "system_path", None) or (
            getattr(scenario_config.system, "path", None)
            if hasattr(scenario_config, "system") and scenario_config.system is not None
            else None
        )
        scenario_obj = SiennaScenario(
            simulation_files=scenario_config.get_simulation_paths_list(),
            system_file=system_file,
            metadata_file=getattr(scenario_config, "metadata_path", None),
        )
    elif scenario_config.type == "reeds":
        scenario_obj = ReEDsScenario(
            path=scenario_config.path,
            solve_year=scenario_config.solve_year,
        )
    elif scenario_config.type == "plexos":
        scenario_obj = PlexosScenario(
            solution_path=scenario_config.solution_path,
        )
    else:
        raise ValueError(f"Unsupported scenario type: {scenario_config.type}")

    # Show summary and tips
    if verbose:
        logger.info("✅ Successfully loaded:")
        logger.info(f"   Project:  {project_ref.name} ({project_id})")
        logger.info(f"   Scenario: {scenario_id} [{scenario_config.type}]")
        logger.info(f"   Palette:  {palette_name if palette_name else 'None'}")
        logger.info("")
        logger.info("💡 To suppress these messages, use: gat.load(verbose=False)")
        logger.info(
            "💡 To reduce all GAT logging: "
            "logger.remove(); logger.add(sys.stderr, level='WARNING')"
        )
        logger.info("")

    return scenario_obj, palette_obj, manager


def load_scenario_only(
    project: Optional[str] = None,
    scenario: Optional[str] = None,
    verbose: bool = True,
):
    """
    Load only a scenario (without palette).

    This is a convenience function for when you don't need the palette.

    Args:
        project: Project ID. If None, uses default project.
        scenario: Scenario ID. If None, uses default scenario from project.
        verbose: If True, logs informative messages.

    Returns:
        Scenario handler object (SiennaScenario, ReEDsScenario, or PlexosScenario)

    Examples:
        # Load default scenario
        scenario = gat.load_scenario_only()

        # Load specific scenario
        scenario = gat.load_scenario_only(
            project="my-analysis",
            scenario="base_2035"
        )
    """
    scenario_obj, _, _ = load(
        project=project, scenario=scenario, palette=None, verbose=verbose
    )
    return scenario_obj


def load_palette_only(
    project: Optional[str] = None,
    palette: Optional[str] = None,
    verbose: bool = True,
) -> Palette:
    """
    Load only a palette (without scenario).

    This is a convenience function for when you only need palette information.

    Args:
        project: Project ID. If None, uses default project.
        palette: Palette name. If None, uses default palette from project.
        verbose: If True, logs informative messages.

    Returns:
        Palette object

    Examples:
        # Load default palette
        palette = gat.load_palette_only()

        # Load specific palette
        palette = gat.load_palette_only(
            project="my-analysis",
            palette="renewable_focus"
        )
    """
    if verbose:
        log_func = logger.info
    else:
        log_func = logger.debug

    # Resolve project
    if project is None:
        project_ref = get_default_project_ref()
        if project_ref is None:
            raise ValueError("No default project set")
        project_id = project_ref.project_id
        log_func(f"Loading default project: '{project_ref.name}' ({project_id})")
    else:
        project_id = project
        project_ref = load_project_ref(project_id)
        if project_ref is None:
            raise ValueError(f"Project '{project_id}' not found")
        log_func(f"Loading project: '{project_ref.name}' ({project_id})")

    # Create project manager
    manager = ProjectManager(project_ref.get_path())
    project_config = manager.load_config()

    # Resolve palette
    available_palettes = manager.list_palettes()
    if not available_palettes:
        raise ValueError(
            f"Project '{project_ref.name}' has no palettes.\n"
            f"Generate a palette with: gat project palette add"
        )

    if palette is None:
        # Use default from project config
        if project_config.default_palette:
            palette_name = project_config.default_palette
            if palette_name not in available_palettes:
                logger.warning(
                    f"Default palette '{palette_name}' not found. "
                    f"Using first available."
                )
                palette_name = available_palettes[0]
            else:
                log_func(f"Loading default palette: '{palette_name}'")
        else:
            # No default, use first available
            palette_name = available_palettes[0]
            log_func(f"No default palette set, using first available: '{palette_name}'")
            if verbose:
                logger.info(f"💡 Available palettes: {', '.join(available_palettes)}")
    else:
        palette_name = palette
        if palette_name not in available_palettes:
            raise ValueError(
                f"Palette '{palette_name}' not found. "
                f"Available: {', '.join(available_palettes)}"
            )
        log_func(f"Loading palette: '{palette_name}'")

    # Load and return palette
    palette_obj = manager.load_palette(palette_name)

    if verbose:
        logger.info(f"✅ Loaded palette: {palette_name}")
        logger.info(
            "💡 To suppress messages, use: gat.load_palette_only(verbose=False)"
        )

    return palette_obj


def _load_remote(
    project: Optional[str],
    scenario: Optional[str],
    server_url: str,
    verbose: bool,
) -> tuple:
    """Load a RemoteScenario from a GAT server.

    If project/scenario are not specified, lists available scenarios
    from the server and uses the first one.
    """
    if verbose:
        log_func = logger.info
    else:
        log_func = logger.debug

    try:
        from gat.client import GATClient
    except ImportError:
        raise ImportError(
            "Client dependencies not installed. Run: pip install nlr-gat[client]"
        )

    client = GATClient(server_url)

    if project is None or scenario is None:
        # List scenarios from server and pick the first
        scenarios = client.list_scenarios()
        if not scenarios:
            raise ValueError(
                f"No scenarios available on server at {server_url}. "
                "Push a scenario first with: gat push"
            )

        if project is None:
            project = scenarios[0]["project"]
        # Find matching scenario for this project
        if scenario is None:
            matching = [s for s in scenarios if s["project"] == project]
            if not matching:
                raise ValueError(
                    f"No scenarios for project '{project}' on {server_url}"
                )
            scenario = matching[0]["scenario"]

    log_func(f"Connecting to GAT server at {server_url}")
    log_func(f"Loading remote scenario: {project}/{scenario}")

    remote = client.scenario(project, scenario)

    if verbose:
        logger.info(f"Connected to {server_url} — {project}/{scenario}")

    return remote, None, None
