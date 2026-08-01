# gat/project_management/manager.py
"""
Project management for GAT v1.0.

This module handles project-level operations:
- Creating new projects
- Loading project configurations
- Adding scenarios
- Managing palettes
- Directory structure operations
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import yaml
from loguru import logger

from gat.models.palette import Palette
from gat.models.project import (
    PlexosScenarioConfig,
    ProjectConfig,
    ProjectStructure,
    ReedsScenarioConfig,
    ScenarioConfig,
    SiennaScenarioConfig,
)
from gat.models.user import (
    UserProjectRef,
    get_palettes_dir,
)


class ProjectManager:
    """
    Manages GAT project operations.

    Handles creating, loading, and modifying GAT projects.
    """

    def __init__(self, project_path: Path):
        """
        Initialize ProjectManager for a project directory.

        Args:
            project_path: Path to the project directory
        """
        self.project_path = Path(os.path.abspath(project_path))
        self.config_path = self.project_path / "gat-project.yaml"

    def exists(self) -> bool:
        """Check if the project exists."""
        return self.config_path.exists()

    def load_config(self) -> ProjectConfig:
        """
        Load the project configuration.

        Returns:
            ProjectConfig instance

        Raises:
            FileNotFoundError: If project config doesn't exist
        """
        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Project config not found: {self.config_path}\n"
                f"Run 'gat project init {self.project_path}' to create a project."
            )

        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f) or {}

        return ProjectConfig(**data)

    def save_config(self, config: ProjectConfig) -> None:
        """
        Save the project configuration.

        Args:
            config: ProjectConfig to save
        """
        # Update timestamp
        config.updated_at = datetime.now()

        with open(self.config_path, "w") as f:
            yaml.dump(
                config.model_dump(exclude_none=True),
                f,
                sort_keys=False,
                default_flow_style=False,
            )

        logger.debug(f"Saved project config to {self.config_path}")

    def init_project(
        self,
        name: str,
        gat_version: str = "1.0.0",
        description: Optional[str] = None,
        copy_user_palettes: bool = True,
    ) -> ProjectConfig:
        """
        Initialize a new project directory structure.

        Args:
            name: Project name
            gat_version: Required GAT version
            description: Optional project description
            copy_user_palettes: Whether to copy user palettes into project

        Returns:
            Created ProjectConfig

        Raises:
            FileExistsError: If project already exists
        """
        if self.exists():
            raise FileExistsError(
                f"Project already exists at {self.project_path}\n"
                f"Use 'gat project add {self.project_path}' to add it to your projects."
            )

        # Create directory structure
        self.project_path.mkdir(parents=True, exist_ok=True)

        for dir_name in ProjectStructure.STANDARD_STRUCTURE.keys():
            (self.project_path / dir_name).mkdir(exist_ok=True)

        # Create .gitignore
        gitignore_path = self.project_path / ".gitignore"
        with open(gitignore_path, "w") as f:
            f.write("\n".join(ProjectStructure.GITIGNORE_ENTRIES))

        # Create README
        readme_path = self.project_path / "README.md"
        with open(readme_path, "w") as f:
            f.write(ProjectStructure.get_readme_template(name))

        # Copy user palettes if requested
        if copy_user_palettes:
            user_palettes_dir = get_palettes_dir()
            project_palettes_dir = self.project_path / "palettes"

            for palette_file in user_palettes_dir.glob("*.toml"):
                dest = project_palettes_dir / palette_file.name
                if not dest.exists():
                    shutil.copy2(palette_file, dest)
                    logger.debug(f"Copied palette: {palette_file.name}")

        # Create project config
        config = ProjectConfig(
            name=name,
            description=description,
            gat_version=gat_version,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            default_scenario=None,
            default_palette=None,
            repository_url=None,
            documentation_url=None,
        )

        self.save_config(config)
        logger.info(f"Initialized project at {self.project_path}")

        return config

    def list_scenarios(self) -> List[str]:
        """
        List all scenario IDs in the project.

        Returns:
            List of scenario IDs
        """
        scenarios_dir = self.project_path / "scenarios"
        if not scenarios_dir.exists():
            return []

        return [f.stem for f in scenarios_dir.glob("*.yaml")]

    def load_scenario(self, scenario_id: str) -> ScenarioConfig:
        """
        Load a scenario configuration.

        Args:
            scenario_id: Scenario identifier

        Returns:
            ScenarioConfig instance

        Raises:
            FileNotFoundError: If scenario doesn't exist
        """
        scenario_path = self.project_path / "scenarios" / f"{scenario_id}.yaml"

        if not scenario_path.exists():
            raise FileNotFoundError(f"Scenario not found: {scenario_id}")

        with open(scenario_path, "r") as f:
            data = yaml.safe_load(f) or {}

        # Determine scenario type and create appropriate config
        scenario_type = data.get("type")
        if scenario_type == "sienna":
            return SiennaScenarioConfig(**data)
        elif scenario_type == "reeds":
            return ReedsScenarioConfig(**data)
        elif scenario_type == "plexos":
            return PlexosScenarioConfig(**data)
        else:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

    def save_scenario(self, scenario_id: str, config: ScenarioConfig) -> None:
        """
        Save a scenario configuration.

        Args:
            scenario_id: Scenario identifier
            config: ScenarioConfig to save
        """
        scenarios_dir = self.project_path / "scenarios"
        scenarios_dir.mkdir(exist_ok=True)

        scenario_path = scenarios_dir / f"{scenario_id}.yaml"

        # Update timestamp
        config.updated_at = datetime.now()
        if config.created_at is None:
            config.created_at = datetime.now()

        with open(scenario_path, "w") as f:
            yaml.dump(
                config.model_dump(exclude_none=True),
                f,
                sort_keys=False,
                default_flow_style=False,
            )

        logger.debug(f"Saved scenario to {scenario_path}")

    def add_scenario(
        self,
        scenario_id: str,
        name: str,
        scenario_type: str,
        auto_discover: bool = False,
        overwrite: bool = False,
        **kwargs,
    ) -> Union[ScenarioConfig, List[ScenarioConfig]]:
        """
        Add a new scenario to the project.

        For Sienna scenarios, if simulation_type is not specified and auto_discover=True,
        this will discover all available simulation types in the file and create
        separate scenarios for each (e.g., scenario_UC, scenario_ED, scenario_PF).

        Args:
            scenario_id: Unique identifier for the scenario (base name for auto-discovery)
            name: Human-readable scenario name (base name for auto-discovery)
            scenario_type: Type of scenario (sienna, reeds, plexos)
            auto_discover: If True and simulation_type not specified, create multiple
                          scenarios for each discovered simulation type
            overwrite: If True, overwrite existing scenarios without error
            **kwargs: Type-specific arguments (including simulation_type for Sienna)

        Returns:
            Created ScenarioConfig, or list of configs if auto_discover created multiple

        Raises:
            ValueError: If scenario type is unknown or scenario already exists (and not overwrite)
        """
        # Check if scenario already exists (for non-auto-discover cases)
        if not auto_discover:
            scenario_path = self.project_path / "scenarios" / f"{scenario_id}.yaml"
            if scenario_path.exists() and not overwrite:
                raise ValueError(f"Scenario already exists: {scenario_id}")

        # Handle Sienna auto-discovery
        if (
            scenario_type == "sienna"
            and auto_discover
            and "simulation_type" not in kwargs
        ):
            # Extract system_path and simulation_paths from the new structure
            system_config = kwargs.pop("system")
            simulation_config = kwargs.pop("simulation")

            system_path = system_config.path
            simulation_paths = simulation_config.paths

            # Use class method to create multiple scenarios
            scenarios = SiennaScenarioConfig.create_scenarios_for_all_simulations(
                base_scenario_id=scenario_id,
                name=name,
                system_path=system_path,
                simulation_paths=simulation_paths,
                **kwargs,
            )

            created_configs = []
            for sid, config in scenarios:
                # Check if this specific scenario already exists
                scenario_path = self.project_path / "scenarios" / f"{sid}.yaml"
                if scenario_path.exists() and not overwrite:
                    logger.warning(f"Scenario already exists, skipping: {sid}")
                    continue

                # Discover and set dataset configurations
                try:
                    config.discover_and_set_dataset_configs()
                    logger.info(f"Auto-discovered dataset configurations for {sid}")
                except Exception as e:
                    logger.warning(f"Could not discover dataset configs for {sid}: {e}")

                self.save_scenario(sid, config)
                action = "Updated" if scenario_path.exists() else "Added"
                logger.info(
                    f"{action} scenario: {sid} (simulation_type: {config.simulation.type})"
                )
                created_configs.append(config)

            # Return empty list if nothing was created/updated
            if not created_configs:
                return []

            return created_configs if len(created_configs) > 1 else created_configs[0]

        # Relativize absolute paths that fall under the project root so
        # scenarios stay portable when the project directory moves.
        def _relativize(p):
            try:
                pp = Path(p)
                if pp.is_absolute():
                    rel = pp.resolve().relative_to(self.project_path.resolve())
                    return os.path.normpath(str(rel))
            except (ValueError, OSError):
                pass
            return os.path.normpath(p) if isinstance(p, str) else p

        if "system_path" in kwargs:
            kwargs["system_path"] = _relativize(kwargs["system_path"])
        if "simulation_paths" in kwargs:
            sp = kwargs["simulation_paths"]
            if isinstance(sp, list):
                kwargs["simulation_paths"] = [_relativize(x) for x in sp]
            else:
                kwargs["simulation_paths"] = _relativize(sp)

        # Create appropriate scenario config (single scenario)
        if scenario_type == "sienna":
            config = SiennaScenarioConfig(name=name, **kwargs)
        elif scenario_type == "reeds":
            config = ReedsScenarioConfig(name=name, **kwargs)
        elif scenario_type == "plexos":
            config = PlexosScenarioConfig(name=name, **kwargs)
        else:
            raise ValueError(
                f"Unknown scenario type: {scenario_type}. "
                f"Valid types: sienna, reeds, plexos"
            )

        # Discover and set dataset configurations for Sienna scenarios
        if scenario_type == "sienna":
            try:
                config.discover_and_set_dataset_configs()
                logger.info(f"Auto-discovered dataset configurations for {scenario_id}")
            except Exception as e:
                logger.warning(
                    f"Could not discover dataset configs for {scenario_id}: {e}"
                )

        self.save_scenario(scenario_id, config)
        logger.info(f"Added scenario: {scenario_id}")

        return config

    def delete_scenario(self, scenario_id: str) -> bool:
        """
        Delete a scenario from the project.

        Args:
            scenario_id: Scenario identifier

        Returns:
            True if deleted, False if not found
        """
        scenario_path = self.project_path / "scenarios" / f"{scenario_id}.yaml"

        if scenario_path.exists():
            scenario_path.unlink()
            logger.debug(f"Deleted scenario: {scenario_id}")
            return True
        return False

    def list_palettes(self) -> List[str]:
        """
        List all palette names in the project.

        Returns:
            List of palette names
        """
        palettes_dir = self.project_path / "palettes"
        if not palettes_dir.exists():
            return []

        return [f.stem for f in palettes_dir.glob("*.yaml")]

    def load_palette(self, palette_name: str) -> Palette:
        """
        Load a project palette.

        Args:
            palette_name: Palette name

        Returns:
            Palette instance

        Raises:
            FileNotFoundError: If palette doesn't exist
        """
        palette_path = self.project_path / "palettes" / f"{palette_name}.yaml"

        if not palette_path.exists():
            raise FileNotFoundError(f"Palette not found: {palette_name}")

        with open(palette_path, "r") as f:
            data = yaml.safe_load(f) or {}

        return Palette(**data)

    def save_palette(self, palette_name: str, palette: Palette) -> None:
        """
        Save a palette to the project.

        Args:
            palette_name: Palette name
            palette: Palette instance to save
        """
        palettes_dir = self.project_path / "palettes"
        palettes_dir.mkdir(exist_ok=True)

        palette_path = palettes_dir / f"{palette_name}.yaml"

        with open(palette_path, "w") as f:
            yaml.dump(
                palette.model_dump(exclude_none=True),
                f,
                sort_keys=False,
                default_flow_style=False,
            )

        logger.debug(f"Saved palette to {palette_path}")

    def resolve_path(self, relative_path: str) -> Path:
        """
        Resolve a relative path to an absolute path from project root.

        Args:
            relative_path: Path relative to project root

        Returns:
            Absolute Path
        """
        # Use os.path.abspath rather than Path.resolve() so symlinks (e.g. macOS
        # /var → /private/var) are not chased — callers expect a path under the
        # project_path they passed in.
        return Path(os.path.abspath(self.project_path / relative_path))

    def validate_scenario_paths(self, scenario_id: str) -> List[str]:
        """
        Validate that all paths in a scenario exist.

        Args:
            scenario_id: Scenario identifier

        Returns:
            List of warnings for missing paths
        """
        warnings = []
        config = self.load_scenario(scenario_id)

        if isinstance(config, SiennaScenarioConfig):
            system_path = self.resolve_path(config.system.path)
            if not system_path.exists():
                warnings.append(f"System path not found: {config.system.path}")

            for sim_path in config.get_simulation_paths_list():
                full_path = self.resolve_path(sim_path)
                if not full_path.exists():
                    warnings.append(f"Simulation path not found: {sim_path}")

        elif isinstance(config, ReedsScenarioConfig):
            reeds_path = self.resolve_path(config.path)
            if not reeds_path.exists():
                warnings.append(f"ReEDS path not found: {config.path}")

        elif isinstance(config, PlexosScenarioConfig):
            solution_path = self.resolve_path(config.solution_path)
            if not solution_path.exists():
                warnings.append(
                    f"Plexos solution path not found: {config.solution_path}"
                )

        return warnings


def create_project_ref_from_path(
    project_path: Path,
    project_id: Optional[str] = None,
    is_default: bool = False,
) -> UserProjectRef:
    """
    Create a UserProjectRef from a project directory.

    Args:
        project_path: Path to project directory
        project_id: Optional project ID (defaults to directory name)
        is_default: Whether to set as default project

    Returns:
        UserProjectRef instance

    Raises:
        FileNotFoundError: If project config doesn't exist
    """
    project_path = Path(project_path).resolve()
    manager = ProjectManager(project_path)

    if not manager.exists():
        raise FileNotFoundError(
            f"No GAT project found at {project_path}\n"
            f"Run 'gat project init {project_path}' to create one."
        )

    config = manager.load_config()

    # Generate project_id if not provided
    if project_id is None:
        import re

        project_id = re.sub(r"[^a-zA-Z0-9_-]", "_", project_path.name.lower())
        project_id = re.sub(r"_+", "_", project_id).strip("_")

    return UserProjectRef(
        project_id=project_id,
        name=config.name,
        path=str(project_path),
        description=config.description,
        remote_url=config.repository_url,
        last_accessed=datetime.now(),
        is_default=is_default,
    )
