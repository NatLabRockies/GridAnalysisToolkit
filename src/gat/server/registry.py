"""Scenario registry — tracks materialized scenarios in DuckDB."""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

REGISTRY_SCHEMA = "_gat_registry"
REGISTRY_TABLE = f"{REGISTRY_SCHEMA}.scenarios"
PROJECT_GEO_TABLE = f"{REGISTRY_SCHEMA}.project_geo"

CREATE_REGISTRY = f"""
CREATE SCHEMA IF NOT EXISTS {REGISTRY_SCHEMA};
-- One row per (project, scenario, model) — Sienna H5 files contain
-- multiple optimization stages (UC, RAUC, DC-OPF emulation, ...), each
-- ingested into its own ``schema_name`` (``{{project}}__{{scenario}}__{{model}}``).
-- ``is_default`` marks the model the UI should land on when no model
-- is explicitly requested (typically the emulation model).
CREATE TABLE IF NOT EXISTS {REGISTRY_TABLE} (
    project      VARCHAR NOT NULL,
    scenario     VARCHAR NOT NULL,
    model        VARCHAR NOT NULL,
    handler      VARCHAR NOT NULL,
    schema_name  VARCHAR NOT NULL,
    ingested_at  TIMESTAMP DEFAULT now(),
    source_paths VARCHAR,
    status       VARCHAR DEFAULT 'ready',
    is_default   BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (project, scenario, model)
);
-- Project-scoped bus geometry. The same physical system is reused across
-- scenarios with different parameter sets, so coords belong on the project,
-- not the per-scenario system file. `bus_id_field` records whether coords
-- are keyed by ACBus.name or ACBus.number.
CREATE TABLE IF NOT EXISTS {PROJECT_GEO_TABLE} (
    project          VARCHAR NOT NULL,
    bus_id_field     VARCHAR,                  -- 'name' | 'number' (column on sys__ACBus)
    bus_id_column    VARCHAR,                  -- source: which CSV column / GeoJSON property
    lat_column       VARCHAR,                  -- CSV-only
    lon_column       VARCHAR,                  -- CSV-only
    source_filename  VARCHAR,
    bus_count        INTEGER,
    unmatched_count  INTEGER,
    uploaded_at      TIMESTAMP DEFAULT now(),
    PRIMARY KEY (project)
);
"""


def ensure_registry(conn: Any) -> None:
    """Create the registry schema and tables if they don't exist.

    Also handles the M2a schema migration: pre-M2a registries don't have
    the ``model`` / ``is_default`` columns, and ``CREATE TABLE IF NOT
    EXISTS`` is a no-op against an existing table. Detect the old shape
    by probing for the new columns; if missing, drop the table so the
    fresh ``CREATE`` below can install the new schema. There's no data
    migration — pre-M2a registry rows lose their schema-name pointer
    and the corresponding scenarios need to be re-uploaded. Acceptable
    because we have no real prod data yet (user confirmed).
    """
    needs_reset = False
    try:
        conn.execute(f"SELECT model, is_default FROM {REGISTRY_TABLE} LIMIT 0")
    except Exception:
        # Either the table doesn't exist yet (fresh install) or it
        # exists with the pre-M2a shape. Probe the table itself to
        # distinguish.
        try:
            conn.execute(f"SELECT 1 FROM {REGISTRY_TABLE} LIMIT 0")
            needs_reset = True
        except Exception:
            needs_reset = False  # table just doesn't exist — fall through to CREATE

    if needs_reset:
        logger.warning(
            "Detected pre-M2a registry schema; dropping for fresh "
            "(project,scenario,model) layout. Existing scenarios need re-upload."
        )
        conn.execute(f"DROP TABLE IF EXISTS {REGISTRY_TABLE}")

    conn.execute(CREATE_REGISTRY)
    logger.debug("Registry table ensured")


def register_scenario(
    conn: Any,
    project: str,
    scenario: str,
    handler: str,
    schema_name: str,
    model: str = "default",
    source_paths: Optional[str] = None,
    status: str = "ready",
    is_default: bool = False,
) -> None:
    """Insert or update a (project, scenario, model) registry row.

    When ``is_default`` is True, also flip any existing default row for
    this (project, scenario) to False so only one model is the default
    at a time.
    """
    if is_default:
        conn.execute(
            f"UPDATE {REGISTRY_TABLE} SET is_default = FALSE "
            f"WHERE project = ? AND scenario = ?",
            [project, scenario],
        )
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {REGISTRY_TABLE}
            (project, scenario, model, handler, schema_name, ingested_at,
             source_paths, status, is_default)
        VALUES (?, ?, ?, ?, ?, now(), ?, ?, ?)
        """,
        [
            project,
            scenario,
            model,
            handler,
            schema_name,
            source_paths,
            status,
            is_default,
        ],
    )


def set_status(
    conn: Any, project: str, scenario: str, status: str, model: Optional[str] = None
) -> None:
    """Update the status of a scenario+model. When ``model`` is None,
    update every row for the scenario — useful for bulk error states
    on a failed parse."""
    if model is None:
        conn.execute(
            f"UPDATE {REGISTRY_TABLE} SET status = ? WHERE project = ? AND scenario = ?",
            [status, project, scenario],
        )
    else:
        conn.execute(
            f"UPDATE {REGISTRY_TABLE} SET status = ? "
            f"WHERE project = ? AND scenario = ? AND model = ?",
            [status, project, scenario, model],
        )


def list_scenarios(conn: Any) -> list[dict]:
    """List all registered scenario+model rows."""
    df = conn.execute(
        f"SELECT * FROM {REGISTRY_TABLE} ORDER BY project, scenario, model"
    ).fetchdf()
    return df.to_dict(orient="records")


def get_scenario(
    conn: Any, project: str, scenario: str, model: Optional[str] = None
) -> Optional[dict]:
    """Get a single (project, scenario, model) registry row.

    When ``model`` is None, returns the default-flagged row, or the
    most recently ingested row if no default has been set.
    """
    if model is not None:
        df = conn.execute(
            f"SELECT * FROM {REGISTRY_TABLE} "
            f"WHERE project = ? AND scenario = ? AND model = ?",
            [project, scenario, model],
        ).fetchdf()
    else:
        df = conn.execute(
            f"SELECT * FROM {REGISTRY_TABLE} "
            f"WHERE project = ? AND scenario = ? "
            f"ORDER BY is_default DESC, ingested_at DESC LIMIT 1",
            [project, scenario],
        ).fetchdf()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def list_models_for_scenario(conn: Any, project: str, scenario: str) -> list[dict]:
    """Return one dict per ingested model for the scenario, ordered with
    the default model first. Each dict has ``model``, ``status``,
    ``is_default``, ``ingested_at``. The UI's model dropdown reads this.
    """
    df = conn.execute(
        f"SELECT model, status, is_default, ingested_at "
        f"FROM {REGISTRY_TABLE} "
        f"WHERE project = ? AND scenario = ? "
        f"ORDER BY is_default DESC, ingested_at ASC",
        [project, scenario],
    ).fetchdf()
    return df.to_dict(orient="records")


def get_default_model(conn: Any, project: str, scenario: str) -> Optional[str]:
    """Return the default model name for a (project, scenario), or None
    if no models have been ingested."""
    entry = get_scenario(conn, project, scenario)
    return entry["model"] if entry else None


def upsert_project_geo(
    conn: Any,
    project: str,
    bus_id_field: str,
    bus_id_column: str,
    lat_column: Optional[str],
    lon_column: Optional[str],
    source_filename: str,
    bus_count: int,
    unmatched_count: int,
) -> None:
    """Insert or update the project-geo registry row for a project."""
    conn.execute(
        f"""
        INSERT OR REPLACE INTO {PROJECT_GEO_TABLE}
            (project, bus_id_field, bus_id_column, lat_column, lon_column,
             source_filename, bus_count, unmatched_count, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, now())
        """,
        [
            project,
            bus_id_field,
            bus_id_column,
            lat_column,
            lon_column,
            source_filename,
            bus_count,
            unmatched_count,
        ],
    )


def get_project_geo(conn: Any, project: str) -> Optional[dict]:
    """Look up the project-geo registry row, if any."""
    df = conn.execute(
        f"SELECT * FROM {PROJECT_GEO_TABLE} WHERE project = ?",
        [project],
    ).fetchdf()
    if df.empty:
        return None
    return df.iloc[0].to_dict()


def delete_scenario(
    conn: Any, project: str, scenario: str, model: Optional[str] = None
) -> bool:
    """Delete a (project, scenario) — by default every model's schema +
    its registry rows. Pass ``model`` to delete only one model's
    schema/row, leaving siblings intact.
    """
    if model is not None:
        entry = get_scenario(conn, project, scenario, model=model)
        if entry is None:
            return False
        conn.execute(f"DROP SCHEMA IF EXISTS {entry['schema_name']} CASCADE")
        conn.execute(
            f"DELETE FROM {REGISTRY_TABLE} "
            f"WHERE project = ? AND scenario = ? AND model = ?",
            [project, scenario, model],
        )
        logger.info(
            "Deleted scenario {}/{} model={} (schema: {})",
            project,
            scenario,
            model,
            entry["schema_name"],
        )
        return True

    rows = conn.execute(
        f"SELECT model, schema_name FROM {REGISTRY_TABLE} "
        f"WHERE project = ? AND scenario = ?",
        [project, scenario],
    ).fetchall()
    if not rows:
        return False
    for _model, schema_name in rows:
        conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
    conn.execute(
        f"DELETE FROM {REGISTRY_TABLE} WHERE project = ? AND scenario = ?",
        [project, scenario],
    )
    logger.info("Deleted scenario {}/{} ({} model(s))", project, scenario, len(rows))
    return True
