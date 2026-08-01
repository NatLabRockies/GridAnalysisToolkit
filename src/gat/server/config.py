"""Server configuration model."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def _default_db_path() -> str:
    return str(Path.home() / ".gat" / "server" / "gat_server.duckdb")


def _default_data_dir() -> str:
    return str(Path.home() / ".gat" / "server" / "uploads")


class ServerConfig(BaseModel):
    """Configuration for the GAT server."""

    host: str = Field(default="127.0.0.1", description="Bind address")
    port: int = Field(default=8815, description="Listen port")
    db_path: str = Field(
        default_factory=_default_db_path,
        description="Path to persistent DuckDB file",
    )
    data_dir: str = Field(
        default_factory=_default_data_dir,
        description="Directory for uploaded data files",
    )
    auth_token: Optional[str] = Field(
        default=None,
        description="Bearer token for authentication (None = no auth)",
    )

    @classmethod
    def from_env(cls, **overrides) -> ServerConfig:
        """Build config from environment variables and overrides.

        Resolution: CLI overrides > env vars > defaults.
        """
        env_map = {
            "host": "GAT_SERVER_HOST",
            "port": "GAT_SERVER_PORT",
            "db_path": "GAT_SERVER_DB_PATH",
            "data_dir": "GAT_SERVER_DATA_DIR",
            "auth_token": "GAT_SERVER_AUTH_TOKEN",
        }

        kwargs = {}
        for field, env_var in env_map.items():
            val = os.environ.get(env_var)
            if val is not None:
                if field == "port":
                    val = int(val)
                kwargs[field] = val

        # CLI overrides take precedence
        kwargs.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**kwargs)
