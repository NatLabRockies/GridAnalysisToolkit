"""Server-side scenario ingestion logic."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from loguru import logger

from gat.backends.duckdb_backend import GATDatabase
from gat.scenario import Scenario
from gat.server.registry import register_scenario, set_status


def schema_name_for(project: str, scenario: str, model: str) -> str:
    """The DuckDB schema that holds one (project, scenario, model)'s
    ingested tables. Stable across the registry and API clients —
    both call this so the encoding only lives in one place.

    Lowercased because DuckDB stores unquoted CREATE SCHEMA names as
    lowercase in information_schema, and client query paths do
    case-sensitive ``WHERE table_schema = ?`` lookups.
    Keeping the user-typed casing here would mean every place doing
    SQL against information_schema has to ``LOWER(...)`` both sides.
    Display fields (project / scenario / model) keep their original
    casing in API responses — only the identifier is normalized.
    """
    return (
        f"{project}__{scenario}__{model}"
        .replace("-", "_")
        .replace(" ", "_")
        .lower()
    )


def ingest_scenario(
    conn: Any,
    db: GATDatabase,
    project: str,
    scenario: str,
    handler: str,
    system_path: str | None = None,
    simulation_paths: list[str] | None = None,
    scenario_root_uri: str | None = None,
    model: str | None = None,
    is_default: bool | None = None,
    dataset_filter: "Callable[[Any], bool] | None" = None,
    include_system: bool = True,
) -> dict:
    """Ingest one (project, scenario, model) into the server's
    persistent DuckDB.

    Sienna H5 files contain multiple optimization stages — UC, RAUC,
    Emulation Model, etc. Each is its own model; each lives in its
    own DuckDB schema (``{project}__{scenario}__{model}``) and its
    own parquet subtree. Re-ingesting a different model for the same
    scenario doesn't disturb its siblings.

    Args:
        conn: DuckDB connection (for registry updates).
        db: GATDatabase wrapping the same connection.
        project: Project identifier.
        scenario: Scenario identifier.
        handler: Handler type ("sienna", "reeds", "plexos").
        system_path: Path to system definition file.
        simulation_paths: Paths to simulation result files.
        scenario_root_uri: Canonical URI under which this scenario's
            data lives. Parquet files for ``model`` land at
            ``{scenario_root_uri}/parquet/{model}/{dataset}.parquet``.
        model: Which stage to ingest. For sienna H5 files that means
            a decision-model or emulation-model name. ``None`` means
            "pick the default from the H5" (emulation > first
            decision-model). Other handlers ignore this — they're
            single-stage and ingest under ``model='default'``.
        is_default: Whether this row should be marked as the
            scenario's default model in the registry. When ``None``,
            inferred: True if ``model`` matches the H5's natural
            default, False otherwise. Pass explicitly to override.

    Returns:
        Dict with ingestion result info, including the resolved
        ``model`` and ``schema_name``.
    """
    # Resolve model — pick the H5's natural default if the caller
    # didn't specify one.
    if model is None and handler == "sienna":
        model = _pick_default_sienna_model(simulation_paths)
    if model is None:
        model = "default"

    model = _sanitize_identifier(model)
    schema_name = schema_name_for(project, scenario, model)

    if is_default is None:
        # Default-flagged when this *was* the auto-picked default.
        natural_default = (
            _pick_default_sienna_model(simulation_paths) if handler == "sienna" else "default"
        )
        is_default = (model == _sanitize_identifier(natural_default))

    source_info = json.dumps({
        "system_path": system_path,
        "simulation_paths": simulation_paths,
    })

    # Registry writes route through ``db.with_write_conn`` so server
    # callers that injected a lock-aware write provider get brief
    # locked windows. CLI / test callers see ``with_write_conn`` fall
    # back to executing against ``conn`` directly — identical behavior
    # to the prior ``register_scenario(conn, ...)`` call.
    db.with_write_conn(
        lambda c: register_scenario(
            c, project, scenario, handler, schema_name,
            model=model, source_paths=source_info, status="ingesting",
            is_default=is_default,
        )
    )

    try:
        system, simulation = _create_parser(
            handler, system_path, simulation_paths, model=model,
        )

        if scenario_root_uri is not None:
            db.set_parquet_root(f"{scenario_root_uri}/parquet/{model}")

        scenario_obj = Scenario(
            system=system,
            simulation=simulation,
            db=db,
            project=project,
            name=scenario,
            schema_name=schema_name,
        )
        scenario_obj.ingest(dataset_filter=dataset_filter, include_system=include_system)

        db.with_write_conn(
            lambda c: set_status(c, project, scenario, "ready", model=model)
        )
        logger.info(
            "Ingested {}/{} model={} (schema: {})",
            project, scenario, model, schema_name,
        )

        return {
            "project": project,
            "scenario": scenario,
            "model": model,
            "schema": schema_name,
            "status": "ready",
        }

    except Exception as e:
        try:
            db.with_write_conn(
                lambda c: set_status(c, project, scenario, "error", model=model)
            )
        except Exception as e2:
            logger.warning("Could not mark scenario as error in registry: {}", e2)
        # `logger.exception` (loguru) attaches the traceback. Without it this
        # line was the ONLY record of the failure — a wrapped message naming
        # neither the call that raised nor the file, which made a production
        # RecursionError undiagnosable from logs alone.
        logger.exception(
            "Ingestion failed for {}/{} model={}: {}", project, scenario, model, e
        )
        raise
    finally:
        db.set_parquet_root(None)


def list_available_models(handler: str, simulation_paths: list[str] | None) -> list[str]:
    """Enumerate the optimization stages present in the source files
    without ingesting. Upload handlers use this to populate the
    registry with everything that *could* be ingested and to drive
    a model-selection dropdown."""
    if handler != "sienna" or not simulation_paths:
        return ["default"]
    return _list_sienna_models(simulation_paths[0])


def _list_sienna_models(simulation_path: str) -> list[str]:
    """Return all decision + emulation model names in a Sienna H5."""
    try:
        from gat.simulations.sienna import SiennaSimulationConfig
        cfg = SiennaSimulationConfig.from_h5_file(str(simulation_path))
        return list(cfg.simulation_models) or ["default"]
    except Exception as e:
        logger.warning("Could not enumerate Sienna models from {}: {}", simulation_path, e)
        return ["default"]


def _pick_default_sienna_model(simulation_paths: list[str] | None) -> str:
    """Choose the default model for a Sienna scenario: an emulation
    model if one exists, else the first decision model. Mirrors how
    most analysts open a Sienna result interactively."""
    if not simulation_paths:
        return "default"
    try:
        from gat.simulations.sienna import SiennaSimulationConfig
        cfg = SiennaSimulationConfig.from_h5_file(str(simulation_paths[0]))
        if cfg.emulation_models:
            return next(iter(cfg.emulation_models.keys()))
        if cfg.decision_models:
            return next(iter(cfg.decision_models.keys()))
    except Exception as e:
        logger.warning("Default-model pick fell back to 'default': {}", e)
    return "default"


def _sanitize_identifier(name: str) -> str:
    """Same rules as schema_name_for — keep model names safe for use
    as both a DuckDB identifier and a path component."""
    return name.replace("-", "_").replace(" ", "_").replace("/", "_")


def _create_parser(
    handler: str,
    system_path: str | None,
    simulation_paths: list[str] | None,
    model: str | None = None,
) -> tuple:
    """Instantiate the appropriate system + simulation parsers."""
    if handler == "sienna":
        from gat.systems.sienna import SiennaSystem
        from gat.simulations.sienna_v1 import SiennaSimulation

        if not system_path:
            raise ValueError("sienna handler requires system_path")
        if not simulation_paths:
            raise ValueError("sienna handler requires simulation_paths")

        system = SiennaSystem(system_path)
        # SiennaSimulation takes a single path; use first file
        sim_path = simulation_paths[0] if isinstance(simulation_paths, list) else simulation_paths
        # ``model`` becomes ``selected_model`` inside the parser, which
        # decides which group of HDF5 datasets get exposed.
        sienna_model = None if model in (None, "default") else model
        simulation = SiennaSimulation(sim_path, simulation=sienna_model)
        return system, simulation

    elif handler == "reeds":
        from gat.systems.reeds import ReEDsSystem
        from gat.simulations.reeds import ReEDsSimulation

        if not simulation_paths:
            raise ValueError("reeds handler requires simulation_paths")

        # ReEDs uses a single directory path
        path = simulation_paths[0] if isinstance(simulation_paths, list) else simulation_paths
        system = ReEDsSystem(path)
        simulation = ReEDsSimulation(path)
        return system, simulation

    elif handler == "plexos":
        from gat.systems.plexos import PlexosSystem
        from gat.simulations.plexos import PlexosSimulation

        if not simulation_paths:
            raise ValueError("plexos handler requires simulation_paths")

        system = PlexosSystem()  # Plexos may not have a separate system file
        simulation = PlexosSimulation(simulation_paths)
        return system, simulation

    else:
        raise ValueError(f"Unknown handler type: {handler}")
