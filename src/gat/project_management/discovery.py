# gat/project_management/discovery.py
"""
Project discovery - scan data sources and find GAT projects.
"""

from datetime import datetime
from pathlib import Path
from typing import Iterator, List, Optional

from loguru import logger

from gat.models.user import (
    CachedProject,
    DataSource,
    PlexosSource,
    ReedsSource,
    SiennaSource,
    UserConfig,
    save_user_config,
)


class ProjectDiscovery:
    """
    Discovers GAT projects from configured data sources.
    """

    def __init__(self, config: UserConfig):
        self.config = config

    def scan_source(self, source: DataSource) -> Iterator[CachedProject]:
        """Scan a single source for projects based on its type."""
        if isinstance(source, SiennaSource):
            yield from self._scan_sienna(source)
        elif isinstance(source, ReedsSource):
            yield from self._scan_reeds(source)
        elif isinstance(source, PlexosSource):
            yield from self._scan_plexos(source)
        else:
            logger.warning(f"Unknown source type: {type(source)}")

    def _scan_sienna(self, source: SiennaSource) -> Iterator[CachedProject]:
        """Scan a Sienna source for projects."""
        system_path = Path(source.system_path)
        simulation_paths = source.get_simulation_paths_list()

        if not system_path.exists():
            logger.warning(f"Sienna system path does not exist: {system_path}")
            return

        # Check simulation paths exist
        valid_sim_paths = []
        for sim_path in simulation_paths:
            if Path(sim_path).exists():
                valid_sim_paths.append(sim_path)
            else:
                logger.warning(f"Sienna simulation path does not exist: {sim_path}")

        if not valid_sim_paths:
            logger.warning(f"No valid simulation paths for source: {source.name}")
            return

        # Sienna source = one project
        # Try to extract scenarios from simulation files or directory structure
        scenarios = self._discover_sienna_scenarios(valid_sim_paths)

        # Get last modified time from the most recent simulation file
        last_modified = None
        for sim_path in valid_sim_paths:
            p = Path(sim_path)
            if p.exists():
                mtime = datetime.fromtimestamp(p.stat().st_mtime)
                if last_modified is None or mtime > last_modified:
                    last_modified = mtime

        yield CachedProject(
            project_id=self._sanitize_id(source.name),
            name=source.name,
            source_name=source.name,
            source_type="sienna",
            path=str(system_path.parent),
            scenarios=scenarios,
            last_modified=last_modified,
        )

    def _discover_sienna_scenarios(self, simulation_paths: List[str]) -> List[str]:
        """Discover scenarios from Sienna simulation files."""
        scenarios = []

        for sim_path in simulation_paths:
            p = Path(sim_path)
            # Use the filename without extension as a scenario name
            scenario_name = p.stem
            if scenario_name not in scenarios:
                scenarios.append(scenario_name)

        return scenarios

    def _scan_reeds(self, source: ReedsSource) -> Iterator[CachedProject]:
        """Scan a ReEDS source for projects."""
        reeds_path = Path(source.path)

        if not reeds_path.exists():
            logger.warning(f"ReEDS path does not exist: {reeds_path}")
            return

        if not reeds_path.is_dir():
            logger.warning(f"ReEDS path is not a directory: {reeds_path}")
            return

        # Try to find scenarios in the ReEDS output structure
        scenarios = self._discover_reeds_scenarios(reeds_path, source.solve_year)

        # Get last modified from directory
        last_modified = datetime.fromtimestamp(reeds_path.stat().st_mtime)

        yield CachedProject(
            project_id=self._sanitize_id(source.name),
            name=source.name,
            source_name=source.name,
            source_type="reeds",
            path=str(reeds_path),
            scenarios=scenarios,
            last_modified=last_modified,
        )

    def _discover_reeds_scenarios(
        self, reeds_path: Path, solve_year: Optional[int] = None
    ) -> List[str]:
        """Discover scenarios from ReEDS output structure."""
        scenarios = []

        # ReEDS typically has an 'outputs' directory
        outputs_dir = reeds_path / "outputs"
        if outputs_dir.exists():
            # Look for scenario directories or files
            for item in outputs_dir.iterdir():
                if item.is_dir():
                    scenarios.append(item.name)
        else:
            # Maybe the path IS the outputs directory
            # Look for typical ReEDS output files
            for item in reeds_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    scenarios.append(item.name)

        # If solve_year is specified, we might filter or label differently
        if solve_year and not scenarios:
            scenarios.append(f"year_{solve_year}")

        return scenarios

    def _scan_plexos(self, source: PlexosSource) -> Iterator[CachedProject]:
        """Scan a Plexos source for projects."""
        solution_path = Path(source.solution_path)

        if not solution_path.exists():
            logger.warning(f"Plexos solution path does not exist: {solution_path}")
            return

        # Discover scenarios from Plexos structure
        scenarios = self._discover_plexos_scenarios(solution_path)

        # Get last modified
        last_modified = datetime.fromtimestamp(solution_path.stat().st_mtime)

        yield CachedProject(
            project_id=self._sanitize_id(source.name),
            name=source.name,
            source_name=source.name,
            source_type="plexos",
            path=str(solution_path),
            scenarios=scenarios,
            last_modified=last_modified,
        )

    def _discover_plexos_scenarios(self, solution_path: Path) -> List[str]:
        """Discover scenarios from Plexos solution."""
        scenarios = []

        if solution_path.is_file():
            # Single solution file - use filename as scenario
            scenarios.append(solution_path.stem)
        elif solution_path.is_dir():
            # Look for solution files in directory
            for item in solution_path.iterdir():
                if item.suffix.lower() in [".xml", ".zip"]:
                    scenarios.append(item.stem)

        return scenarios

    def _sanitize_id(self, name: str) -> str:
        """Convert a name to a valid project ID."""
        import re

        # Convert to lowercase, replace spaces and special chars with underscores
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name.lower())
        # Remove consecutive underscores
        sanitized = re.sub(r"_+", "_", sanitized)
        # Remove leading/trailing underscores
        return sanitized.strip("_")

    def refresh(self) -> List[CachedProject]:
        """Scan all sources and update the cache."""
        projects = []

        for source in self.config.data_sources:
            logger.info(f"Scanning source: {source.name} ({source.type})")
            try:
                for project in self.scan_source(source):
                    projects.append(project)
            except Exception as e:
                logger.error(f"Error scanning source {source.name}: {e}")

        # Update cache
        self.config.project_cache.projects = projects
        self.config.project_cache.last_updated = datetime.now()

        # Save updated config
        save_user_config(self.config)

        logger.info(f"Found {len(projects)} projects")
        return projects

    def get_project(self, project_id: str) -> Optional[CachedProject]:
        """Get a project from the cache by ID."""
        for project in self.config.project_cache.projects:
            if project.project_id == project_id:
                return project
        return None

    def get_projects_by_source(self, source_name: str) -> List[CachedProject]:
        """Get all projects from a specific source."""
        return [
            p
            for p in self.config.project_cache.projects
            if p.source_name == source_name
        ]

    def get_projects_by_type(self, source_type: str) -> List[CachedProject]:
        """Get all projects of a specific source type."""
        return [
            p
            for p in self.config.project_cache.projects
            if p.source_type == source_type
        ]
