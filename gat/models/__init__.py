# gat/models/__init__.py
"""
GAT data models.

This module exports the main data models used throughout GAT:
- User configuration and project references
- Project and scenario configurations
- Palette definitions for visualization
"""

# User models
# Palette models
from gat.models.palette import (
    CategoryMapping,
    DisplayCategory,
    GeneratorOverride,
    LoadClassification,
    Palette,
    VREClassification,
)

# Project models
from gat.models.project import (
    BaseScenarioConfig,
    PipelineConfig,
    PlexosScenarioConfig,
    ProjectConfig,
    ProjectSettings,
    ProjectStructure,
    ReedsScenarioConfig,
    ScenarioConfig,
    SiennaScenarioConfig,
    VenvConfig,
)
from gat.models.user import (
    UserConfig,
    UserProjectRef,
    create_default_config,
    delete_project_ref,
    get_config_dir,
    get_config_path,
    get_default_project_ref,
    get_palettes_dir,
    get_projects_dir,
    list_project_refs,
    load_project_ref,
    load_user_config,
    save_project_ref,
    save_user_config,
    set_default_project,
)

__all__ = [
    # User
    "UserConfig",
    "UserProjectRef",
    "create_default_config",
    "delete_project_ref",
    "get_config_dir",
    "get_config_path",
    "get_default_project_ref",
    "get_palettes_dir",
    "get_projects_dir",
    "list_project_refs",
    "load_project_ref",
    "load_user_config",
    "save_project_ref",
    "save_user_config",
    "set_default_project",
    # Project
    "BaseScenarioConfig",
    "PipelineConfig",
    "PlexosScenarioConfig",
    "ProjectConfig",
    "ProjectSettings",
    "ProjectStructure",
    "ReedsScenarioConfig",
    "ScenarioConfig",
    "SiennaScenarioConfig",
    "VenvConfig",
    # Palette
    "CategoryMapping",
    "DisplayCategory",
    "GeneratorOverride",
    "LoadClassification",
    "Palette",
    "VREClassification",
]
