"""FastAPI application with DuckDB lifecycle management."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from loguru import logger

try:
    import duckdb
    from fastapi import FastAPI
except ImportError as e:
    raise ImportError(
        "Server dependencies not installed. Run: pip install nlr-gat[server]"
    ) from e

from gat.backends.duckdb_backend import GATDatabase
from gat.server.config import ServerConfig
from gat.server.registry import ensure_registry


class ServerState:
    """Holds server-wide state: DuckDB connection, config, write lock."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self.conn: Any = None
        self.db: GATDatabase | None = None
        self.write_lock = asyncio.Lock()

    def open(self) -> None:
        """Open the persistent DuckDB connection."""
        db_path = Path(self.config.db_path).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Opening DuckDB at {}", db_path)
        self.db = GATDatabase(path=str(db_path))
        self.conn = self.db.get_connection()
        ensure_registry(self.conn)

    def close(self) -> None:
        """Close the DuckDB connection."""
        if self.db is not None:
            self.db.close()
            logger.info("DuckDB connection closed")


def create_app(config: ServerConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if config is None:
        config = ServerConfig.from_env()

    state = ServerState(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state.open()
        yield
        state.close()

    app = FastAPI(
        title="GAT Server",
        description="Grid Analysis Toolkit — scenario data server",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Attach state to app for access in route handlers
    app.state.server = state

    # Register routes
    from gat.server.routes import router
    app.include_router(router)

    # Add auth middleware if token is configured
    if config.auth_token:
        _add_auth_middleware(app, config.auth_token)

    return app


def _add_auth_middleware(app: FastAPI, token: str) -> None:
    """Add bearer token authentication middleware."""
    from fastapi import Request
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Allow health endpoint without auth
            if request.url.path == "/health":
                return await call_next(request)

            auth = request.headers.get("Authorization", "")
            if not auth.startswith("Bearer ") or auth[7:] != token:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing auth token"},
                )
            return await call_next(request)

    app.add_middleware(AuthMiddleware)
