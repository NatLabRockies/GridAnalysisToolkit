"""GAT backends — DuckDB analytical engine and SQLite metadata store."""

from .duckdb_backend import GATDatabase

__all__ = ["GATDatabase"]
