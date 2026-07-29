# gat/models/user.py
"""
User configuration models for GAT.

This module defines the user's GAT configuration, including:
- Personal settings and preferences
- Lightweight references to projects (the actual projects live elsewhere)
- User-level palettes (personal, can be copied into projects)

The user config lives at ~/.config/gat/config.yaml
Project references live at ~/.config/gat/projects/*.toml
User palettes live at ~/.config/gat/palettes/*.toml
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml
from loguru import logger
from pydantic import BaseModel, Field

# ============================================================
# User Project Reference (Lightweight)
# ============================================================


class UserProjectRef(BaseModel):
    """
    Lightweight reference to a GAT project.

    This lives in ~/.config/gat/projects/{project_id}.toml
    The actual project (with scenarios, palettes, etc.) lives at the path.
    """

    # Identification
    project_id: str = Field(
        description="Unique identifier for this project (used in CLI commands)"
    )
    name: str = Field(description="Human-readable project name")

    # Location
    path: str = Field(
        description="Absolute path to the project directory (contains gat-project.toml)"
    )

    # Optional metadata
    description: Optional[str] = None
    remote_url: Optional[str] = Field(
        None, description="Git remote URL for sharing (optional)"
    )

    # User-specific tracking
    last_accessed: Optional[datetime] = Field(
        None, description="Last time this user accessed the project"
    )
    is_default: bool = Field(
        default=False,
        description="Whether this is the default project for CLI commands",
    )

    # Tags for organization
    tags: List[str] = Field(default_factory=list, description="User-defined tags")

    def get_path(self) -> Path:
        """Get the project path as a Path object."""
        return Path(self.path).expanduser().resolve()

    def exists(self) -> bool:
        """Check if the project directory exists."""
        return self.get_path().exists()

    def get_project_config_path(self) -> Path:
        """Get the path to the project's gat-project.toml file."""
        return self.get_path() / "gat-project.toml"

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "project_id": "ntp_base",
                "name": "NTP Base Case",
                "path": "/home/user/projects/ntp-base",
                "description": "National Transmission Planning base scenario",
                "remote_url": "git@github.com:team/ntp-base.git",
                "last_accessed": "2024-01-20T15:45:00Z",
                "is_default": True,
                "tags": ["transmission", "nrel"],
            }
        }


# ============================================================
# User Configuration
# ============================================================


class UserConfig(BaseModel):
    """
    User's GAT configuration.

    Stored at ~/.config/gat/config.yaml

    Note: Project references are stored separately in ~/.config/gat/projects/*.toml
    This keeps the main config file lightweight and allows projects to be
    easily added/removed.
    """

    # User identity (optional, for future multi-user features)
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    email: Optional[str] = None

    # Display preferences
    default_theme: str = Field(
        default="nrel", description="Default color theme for plots"
    )
    default_output_format: str = Field(
        default="png", description="Default output format (png, svg, html)"
    )

    # Default paths
    default_output_dir: Optional[str] = Field(
        default=None, description="Default directory for saving outputs"
    )

    # Default palette
    default_palette: Optional[str] = Field(
        default=None, description="Default user palette name"
    )

    # CLI preferences
    verbose: bool = Field(default=False, description="Verbose CLI output")
    color_output: bool = Field(default=True, description="Use colored CLI output")

    # Editor preference
    editor: Optional[str] = Field(
        default=None,
        description="Preferred text editor for 'gat config edit' (defaults to $EDITOR)",
    )

    # Legacy data sources (for backward compatibility)
    # Will be migrated to project references
    legacy_sources: List = Field(
        default_factory=list,
        description="Legacy data sources (deprecated, will be migrated)",
    )

    class Config:
        """Pydantic config."""

        # Allow extra fields for forward compatibility
        extra = "allow"


# ============================================================
# Config File Management
# ============================================================


def get_config_dir() -> Path:
    """
    Get the GAT config directory, creating if needed.

    Uses ~/.config/gat/ following XDG Base Directory Specification.

    Returns:
        Path to ~/.config/gat/
    """
    # Check for XDG_CONFIG_HOME, otherwise use ~/.config
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        config_dir = Path(xdg_config) / "gat"
    else:
        config_dir = Path.home() / ".config" / "gat"

    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the path to the user config file."""
    return get_config_dir() / "config.yaml"


def get_projects_dir() -> Path:
    """
    Get the directory for project references, creating if needed.

    Returns:
        Path to ~/.config/gat/projects/
    """
    projects_dir = get_config_dir() / "projects"
    projects_dir.mkdir(parents=True, exist_ok=True)
    return projects_dir


def get_palettes_dir() -> Path:
    """
    Get the directory for user palettes, creating if needed.

    Returns:
        Path to ~/.config/gat/palettes/
    """
    palettes_dir = get_config_dir() / "palettes"
    palettes_dir.mkdir(parents=True, exist_ok=True)
    return palettes_dir


def load_user_config() -> UserConfig:
    """
    Load user configuration from ~/.config/gat/config.yaml

    Creates a default config if none exists.

    Returns:
        UserConfig instance
    """
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f) or {}

            # Ensure all optional fields have defaults
            if "default_output_dir" not in data:
                data["default_output_dir"] = str(Path.home() / "gat-output")
            if "default_palette" not in data:
                data["default_palette"] = None
            if "editor" not in data:
                data["editor"] = None

            return UserConfig(**data)
        except Exception as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
            logger.warning("Using default configuration")
            return UserConfig()
    else:
        # Create default config
        logger.info(f"Creating default configuration at {config_path}")
        config = create_default_config()
        save_user_config(config)
        return config


def save_user_config(config: UserConfig) -> None:
    """
    Save user configuration to ~/.config/gat/config.yaml

    Args:
        config: UserConfig instance to save
    """
    config_path = get_config_path()

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(
            config.model_dump(exclude_none=True),
            f,
            sort_keys=False,
            default_flow_style=False,
        )

    logger.debug(f"Saved configuration to {config_path}")


def create_default_config() -> UserConfig:
    """
    Create a default user configuration.

    Returns:
        UserConfig with default values
    """
    # Try to detect user info from environment
    user_name = os.environ.get("USER") or os.environ.get("USERNAME")

    return UserConfig(
        user_name=user_name,
        default_output_dir=str(Path.home() / "gat-output"),
        default_palette=None,
        editor=None,
    )


# ============================================================
# Project Reference Management
# ============================================================


def list_project_refs() -> List[UserProjectRef]:
    """
    List all project references from ~/.config/gat/projects/

    Returns:
        List of UserProjectRef instances
    """
    projects_dir = get_projects_dir()
    project_refs = []

    for yaml_file in projects_dir.glob("*.yaml"):
        try:
            with open(yaml_file, "r") as f:
                data = yaml.safe_load(f) or {}
            project_ref = UserProjectRef(**data)
            project_refs.append(project_ref)
        except Exception as e:
            logger.warning(f"Failed to load project reference {yaml_file}: {e}")

    return project_refs


def load_project_ref(project_id: str) -> Optional[UserProjectRef]:
    """
    Load a project reference by ID.

    Args:
        project_id: Project identifier

    Returns:
        UserProjectRef instance or None if not found
    """
    projects_dir = get_projects_dir()
    yaml_file = projects_dir / f"{project_id}.yaml"

    if not yaml_file.exists():
        return None

    try:
        with open(yaml_file, "r") as f:
            data = yaml.safe_load(f) or {}
        return UserProjectRef(**data)
    except Exception as e:
        logger.error(f"Failed to load project reference {project_id}: {e}")
        return None


def save_project_ref(project_ref: UserProjectRef) -> None:
    """
    Save a project reference to ~/.config/gat/projects/{project_id}.yaml

    Args:
        project_ref: UserProjectRef instance to save
    """
    projects_dir = get_projects_dir()
    yaml_file = projects_dir / f"{project_ref.project_id}.yaml"

    try:
        with open(yaml_file, "w") as f:
            yaml.dump(
                project_ref.model_dump(exclude_none=True),
                f,
                sort_keys=False,
                default_flow_style=False,
            )

        logger.debug(f"Saved project reference to {yaml_file}")
    except Exception as e:
        logger.error(f"Failed to save project reference: {e}")
        raise


def delete_project_ref(project_id: str) -> bool:
    """
    Delete a project reference.

    Args:
        project_id: Project identifier

    Returns:
        True if deleted, False if not found
    """
    projects_dir = get_projects_dir()
    yaml_file = projects_dir / f"{project_id}.yaml"

    if yaml_file.exists():
        yaml_file.unlink()
        logger.debug(f"Deleted project reference {project_id}")
        return True
    return False


def get_default_project_ref() -> Optional[UserProjectRef]:
    """
    Get the default project reference.

    Returns:
        UserProjectRef marked as default, or None if no default set
    """
    for project_ref in list_project_refs():
        if project_ref.is_default:
            return project_ref
    return None


def set_default_project(project_id: str) -> bool:
    """
    Set a project as the default.

    Clears the default flag from all other projects.

    Args:
        project_id: Project identifier to set as default

    Returns:
        True if successful, False if project not found
    """
    # Clear all defaults
    for project_ref in list_project_refs():
        if project_ref.is_default:
            project_ref.is_default = False
            save_project_ref(project_ref)

    # Set the new default
    project_ref = load_project_ref(project_id)
    if project_ref:
        project_ref.is_default = True
        save_project_ref(project_ref)
        return True
    return False
