# gat/models/project.py
"""
Project and scenario models for GAT.

Projects are directories containing:
- gat-project.toml: Project metadata and configuration
- scenarios/: Individual scenario configurations
- palettes/: Project-specific palettes
- pipelines/: Reporting pipeline configurations
- notebooks/: Optional analysis notebooks

Projects are typically git repositories shared across teams.
"""

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator

# Import for type hints only to avoid circular imports
if TYPE_CHECKING:
    from gat.simulations.sienna import SiennaSimulationDataset

# ============================================================
# Scenario Configurations (Base and Type-Specific)
# ============================================================


class BaseScenarioConfig(BaseModel):
    """
    Base class for all scenario configurations.

    Each scenario type (Sienna, ReEDS, Plexos) extends this with
    type-specific fields.
    """

    name: str
    description: Optional[str] = None

    # Tags for organization and filtering
    tags: List[str] = Field(default_factory=list)

    # Default palette to use for this scenario
    default_palette: Optional[str] = Field(
        None, description="Default palette name to use for visualizations"
    )

    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SimulationConfig(BaseModel):
    """Configuration for simulation files and datasets."""

    paths: Union[str, List[str]] = Field(
        description="Absolute path(s) to simulation HDF5 file(s)"
    )
    pattern: Optional[str] = Field(
        None,
        description="Original glob pattern used to find simulation files (if applicable)",
    )
    type: Optional[str] = Field(
        None,
        description="Specific simulation type (UC, ED, PF, etc.). If None, uses first available.",
    )
    datasets: Optional[Dict] = Field(
        None,
        description="DatasetConfig with aggregate dataset definitions",
    )


class SystemConfig(BaseModel):
    """Configuration for system file and system-specific settings."""

    path: str = Field(description="Absolute path to Sienna system JSON file")
    config: Optional[Dict] = Field(
        None,
        description="SiennaSystemConfig with component mappings and relationships",
    )


class SiennaScenarioConfig(BaseScenarioConfig):
    """Configuration for a Sienna/PowerSimulations.jl scenario."""

    type: Literal["sienna"] = "sienna"

    # Simulation configuration
    simulation: SimulationConfig

    # System configuration
    system: SystemConfig

    # Optional metadata path
    metadata_path: Optional[str] = Field(
        None, description="Absolute path to GAT metadata JSON"
    )

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_flat_kwargs(cls, data):
        """Backwards-compat: accept the legacy flat-path API
        (``system_path=``, ``simulation_paths=``) and rewrite to the structured
        form. Existing callers that pass flat kwargs (project_management.manager
        and older configs) keep working without coordinated updates."""
        if not isinstance(data, dict):
            return data
        if "system_path" in data and "system" not in data:
            data["system"] = {"path": data.pop("system_path")}
        if "simulation_paths" in data and "simulation" not in data:
            data["simulation"] = {"paths": data.pop("simulation_paths")}
        return data

    @property
    def system_path(self) -> str:
        """Backwards-compat read accessor for the flat ``system_path`` API."""
        return self.system.path

    @property
    def simulation_paths(self) -> Union[str, List[str]]:
        """Backwards-compat read accessor for the flat ``simulation_paths`` API."""
        return self.simulation.paths

    def get_simulation_paths_list(self) -> List[str]:
        """Return simulation paths as a list."""
        if isinstance(self.simulation.paths, str):
            return [self.simulation.paths]
        return self.simulation.paths

    def get_dataset_config(self):
        """
        Get dataset configuration as DatasetConfig object.

        Returns:
            DatasetConfig object, or None if not set
        """
        if not self.simulation.datasets:
            return None

        from gat.models.base import DatasetConfig

        return DatasetConfig(**self.simulation.datasets)

    def get_system_config(self):
        """
        Get system configuration as SiennaSystemConfig object.

        Returns:
            SiennaSystemConfig object, or None if not set
        """
        if not self.system.config:
            return None

        from gat.models.sienna import SiennaSystemConfig

        return SiennaSystemConfig(**self.system.config)

    def set_dataset_config_from_object(self, config):
        """
        Set dataset configuration from DatasetConfig object.

        Args:
            config: DatasetConfig object
        """
        self.simulation.datasets = config.model_dump()

    def set_system_config_from_object(self, config):
        """
        Set system configuration from SiennaSystemConfig object.

        Args:
            config: SiennaSystemConfig object
        """
        self.system.config = config.model_dump()

    def discover_and_set_dataset_configs(self):
        """
        Auto-discover datasets from the simulation file and set unified dataset configuration.

        This will:
        1. Load the simulation file
        2. Discover all available raw datasets
        3. Create default aggregate dataset configurations (generation, flow, load, etc.)
        4. Store the unified DatasetConfig
        5. Create and store system configuration
        """
        from loguru import logger

        from gat.models.sienna import (
            initialize_sienna_dataset_config,
            initialize_sienna_system_config,
        )

        # Get first simulation file
        first_sim_path = self.get_simulation_paths_list()[0]

        # Detect data format version from simulation file
        try:
            from gat.simulations import SiennaSimulationParser

            parser = SiennaSimulationParser(first_sim_path)

            # Set simulation type if specified
            if self.simulation.type:
                parser.simulation = self.simulation.type

            # Try to detect version from file - fallback to 4.0.0
            data_format_version = "4.0.0"  # Default assumption

            # Initialize default Sienna dataset config
            dataset_config = initialize_sienna_dataset_config(data_format_version)

            # Validate against actual datasets in the file
            try:
                raw_datasets = list(parser.list_raw_datasets().keys())
                dataset_config.validate_datasets(raw_datasets)
                logger.info(
                    f"Validated dataset configuration against {len(raw_datasets)} raw datasets"
                )
            except ValueError as e:
                logger.warning(f"Dataset validation failed, using config anyway: {e}")

            # Store dataset configuration
            self.set_dataset_config_from_object(dataset_config)

            # Initialize and store system configuration
            system_config = initialize_sienna_system_config(data_format_version)
            self.set_system_config_from_object(system_config)

            logger.info(f"Auto-discovered configuration for scenario '{self.name}'")
            logger.info(
                f"  Configured {len(dataset_config.aggregates)} aggregate datasets"
            )

        except Exception as e:
            logger.error(f"Failed to discover configs: {e}")
            raise

    @classmethod
    def discover_simulations(cls, simulation_path: str) -> List[str]:
        """
        Discover available simulation types in a Sienna HDF5 file.

        Args:
            simulation_path: Path to HDF5 simulation file

        Returns:
            List of simulation type names (e.g., ["UC", "ED", "emulation_model"])
        """
        from gat.simulations import SiennaSimulationParser

        try:
            parser = SiennaSimulationParser(simulation_path)
            return parser.simulation_models
        except Exception as e:
            from loguru import logger

            logger.warning(f"Failed to discover simulations in {simulation_path}: {e}")
            return []

    @classmethod
    def create_scenarios_for_all_simulations(
        cls,
        base_scenario_id: str,
        name: str,
        system_path: str,
        simulation_paths: Union[str, List[str]],
        **kwargs,
    ) -> List[tuple[str, "SiennaScenarioConfig"]]:
        """
        Create multiple scenario configs, one for each simulation type in the file(s).

        Args:
            base_scenario_id: Base ID for scenarios (will append _{sim_type})
            name: Base name for scenarios
            system_path: Path to system file
            simulation_paths: Path(s) to simulation file(s)
            **kwargs: Additional fields for scenario config

        Returns:
            List of (scenario_id, config) tuples
        """
        # Get first simulation file to discover available simulations
        first_sim_path = (
            simulation_paths
            if isinstance(simulation_paths, str)
            else simulation_paths[0]
        )
        sim_types = cls.discover_simulations(first_sim_path)

        if not sim_types:
            # If discovery fails, create a single scenario without simulation_type
            config = cls(
                name=name,
                simulation=SimulationConfig(paths=simulation_paths, type=None),
                system=SystemConfig(path=system_path),
                **kwargs,
            )
            return [(base_scenario_id, config)]

        # Create a scenario for each simulation type
        scenarios = []
        for sim_type in sim_types:
            scenario_id = f"{base_scenario_id}_{sim_type}"
            scenario_name = f"{name} ({sim_type})"

            config = cls(
                name=scenario_name,
                simulation=SimulationConfig(paths=simulation_paths, type=sim_type),
                system=SystemConfig(path=system_path),
                **kwargs,
            )
            scenarios.append((scenario_id, config))

        return scenarios


class ReedsScenarioConfig(BaseScenarioConfig):
    """Configuration for a ReEDS scenario."""

    type: Literal["reeds"] = "reeds"

    # Path to ReEDS output directory (absolute filesystem path)
    path: str = Field(description="Absolute path to ReEDS output directory")

    # Optional solve year filter
    solve_year: Optional[int] = Field(
        None, description="Specific solve year to analyze"
    )


class PlexosScenarioConfig(BaseScenarioConfig):
    """Configuration for a Plexos scenario."""

    type: Literal["plexos"] = "plexos"

    # Path to Plexos solution (absolute filesystem path)
    solution_path: str = Field(
        description="Absolute path to Plexos solution file or directory"
    )


# Union type for all scenario types using discriminated union
ScenarioConfig = Annotated[
    Union[SiennaScenarioConfig, ReedsScenarioConfig, PlexosScenarioConfig],
    Field(discriminator="type"),
]


# ============================================================
# Virtual Environment Configuration
# ============================================================


class VenvConfig(BaseModel):
    """Virtual environment configuration for a project."""

    path: str = Field(
        default=".venv",
        description="Path to virtual environment (relative to project root)",
    )
    python_version: Optional[str] = Field(
        None, description="Required Python version (e.g., '3.11')"
    )
    requirements: List[str] = Field(
        default_factory=list,
        description="Additional packages to install (e.g., 'gat-ext-analysis==0.2.0')",
    )


# ============================================================
# Pipeline Configuration
# ============================================================


class PipelineConfig(BaseModel):
    """Configuration for a reporting or analysis pipeline."""

    name: str
    description: Optional[str] = None

    # Scenarios to include in this pipeline
    scenarios: List[str] = Field(
        default_factory=list, description="Scenario IDs to include in this pipeline"
    )

    # Palette to use
    palette: Optional[str] = Field(
        None, description="Palette name to use (from project or user palettes)"
    )

    # Plot configurations
    plots: List[Dict] = Field(
        default_factory=list, description="List of plot configurations to generate"
    )

    # Output settings
    output_dir: str = Field(
        default="./outputs", description="Output directory (relative to project root)"
    )
    output_format: str = Field(
        default="png", description="Output format (png, svg, html)"
    )


# ============================================================
# Project Configuration
# ============================================================


class ProjectSettings(BaseModel):
    """Project-level settings."""

    output_dir: str = Field(
        default="./outputs",
        description="Default output directory (relative to project root)",
    )
    cache_dir: str = Field(
        default="./.gat-cache",
        description="Cache directory for processed data (relative to project root)",
    )
    default_output_format: str = Field(
        default="png", description="Default output format (png, svg, html)"
    )


class ProjectConfig(BaseModel):
    """
    Main project configuration (gat-project.yaml).

    This is the central configuration file for a GAT project,
    stored in the project root directory.
    """

    # Project metadata
    name: str
    description: Optional[str] = None
    version: str = Field(default="0.1.0", description="Project version")

    # GAT version pinning
    gat_version: str = Field(
        description="Required GAT version (e.g., '1.0.0', '>=1.0.0,<2.0.0')"
    )

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Default selections
    default_scenario: Optional[str] = Field(
        None, description="Default scenario ID for commands"
    )
    default_palette: Optional[str] = Field(None, description="Default palette name")

    # Virtual environment configuration
    venv: Optional[VenvConfig] = None

    # Project settings
    settings: ProjectSettings = Field(default_factory=ProjectSettings)

    # Contributors
    contributors: List[str] = Field(
        default_factory=list, description="List of project contributors"
    )

    # Links and documentation
    repository_url: Optional[str] = Field(None, description="Git repository URL")
    documentation_url: Optional[str] = Field(
        None, description="Project documentation URL"
    )

    def get_scenario_path(self, scenario_id: str) -> Path:
        """Get the path to a scenario config file."""
        return Path("scenarios") / f"{scenario_id}.yaml"

    def get_palette_path(self, palette_name: str) -> Path:
        """Get the path to a project palette file."""
        return Path("palettes") / f"{palette_name}.yaml"

    def get_pipeline_path(self, pipeline_name: str) -> Path:
        """Get the path to a pipeline config file."""
        return Path("pipelines") / f"{pipeline_name}.yaml"


# ============================================================
# Project Directory Structure
# ============================================================


class ProjectStructure:
    """
    Defines the standard GAT project directory structure.

    This is used by `gat project init` to create the directory tree.
    """

    STANDARD_STRUCTURE = {
        "scenarios": "Scenario configuration files",
        "palettes": "Project-specific visualization palettes",
        "pipelines": "Reporting and analysis pipeline configurations",
        "notebooks": "Jupyter notebooks for analysis",
        "outputs": "Generated plots and reports",
        ".gat-cache": "Cached processed data (add to .gitignore)",
    }

    GITIGNORE_ENTRIES = [
        "# GAT-specific ignores",
        ".gat-cache/",
        "outputs/",
        "*.pyc",
        "__pycache__/",
        ".venv/",
        ".DS_Store",
    ]

    @classmethod
    def get_readme_template(cls, project_name: str) -> str:
        """Get a README template for a new project."""
        return f"""# {project_name}

A GAT (Grid Analysis Tool) project for power system analysis.

## Project Structure

- `gat-project.yaml` - Project configuration and metadata
- `scenarios/` - Scenario configuration files
- `palettes/` - Visualization palettes
- `pipelines/` - Analysis and reporting pipelines
- `notebooks/` - Jupyter notebooks for custom analysis
- `outputs/` - Generated plots and reports (not tracked in git)

## Getting Started

1. Activate the project environment:
   ```bash
   source .venv/bin/activate  # or .venv\\Scripts\\activate on Windows
   ```

2. List available scenarios:
   ```bash
   gat scenarios list
   ```

3. Generate plots:
   ```bash
   gat plot generation base_scenario
   ```

## Adding Scenarios

Add new scenarios using the CLI:

```bash
gat project add-scenario sienna my_scenario \\
    --system ../data/system.json \\
    --simulation ../data/results.h5
```

## Collaboration

This project is designed to be shared via git. To contribute:

1. Clone the repository
2. Add the project to your GAT configuration: `gat project add .`
3. Create a branch for your changes
4. Commit and push your changes

## Documentation

See the main GAT documentation for more details on usage and features.
"""
