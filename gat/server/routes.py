"""API route handlers for the GAT server."""

from __future__ import annotations

from typing import Optional

from loguru import logger

try:
    import pyarrow as pa
    from fastapi import APIRouter, HTTPException, Request
    from fastapi.responses import Response
    from pydantic import BaseModel
except ImportError as e:
    raise ImportError(
        "Server dependencies not installed. Run: pip install nlr-gat[server]"
    ) from e

from gat.server import registry

router = APIRouter()


# ------------------------------------------------------------------ #
# Request / Response Models
# ------------------------------------------------------------------ #


class IngestRequest(BaseModel):
    project: str
    scenario: str
    handler: str
    system_path: Optional[str] = None
    simulation_paths: Optional[list[str]] = None


class QueryRequest(BaseModel):
    project: str
    scenario: str
    sql: str


class GroupedQueryRequest(BaseModel):
    project: str
    scenario: str
    dataset: str
    group_by: list[str]


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _get_state(request: Request):
    """Extract ServerState from the request."""
    return request.app.state.server


def _arrow_response(df) -> Response:
    """Serialize a pandas DataFrame to Arrow IPC and return as Response."""
    table = pa.Table.from_pandas(df)
    sink = pa.BufferOutputStream()
    writer = pa.ipc.new_stream(sink, table.schema)
    writer.write_table(table)
    writer.close()
    buf = sink.getvalue()
    return Response(
        content=bytes(buf),
        media_type="application/vnd.apache.arrow.stream",
    )


# ------------------------------------------------------------------ #
# Management Endpoints (JSON)
# ------------------------------------------------------------------ #


@router.get("/health")
async def health():
    return {"status": "ok", "service": "gat-server", "version": "0.1.0"}


@router.get("/scenarios")
async def list_scenarios(request: Request):
    state = _get_state(request)
    scenarios = registry.list_scenarios(state.conn)
    return {"scenarios": scenarios}


@router.get("/scenarios/{project}/{scenario}")
async def get_scenario(request: Request, project: str, scenario: str):
    state = _get_state(request)
    entry = registry.get_scenario(state.conn, project, scenario)
    if entry is None:
        raise HTTPException(404, f"Scenario {project}/{scenario} not found")

    # Gather dataset and category map info
    schema = entry["schema_name"]
    try:
        tables = state.db.list_tables(schema)
        catmaps = state.db.list_category_maps(schema)
    except Exception:
        tables = []
        catmaps = []

    return {
        **entry,
        "datasets": tables,
        "category_maps": catmaps,
    }


@router.delete("/scenarios/{project}/{scenario}")
async def delete_scenario(request: Request, project: str, scenario: str):
    state = _get_state(request)
    async with state.write_lock:
        deleted = registry.delete_scenario(state.conn, project, scenario)
    if not deleted:
        raise HTTPException(404, f"Scenario {project}/{scenario} not found")
    return {"status": "deleted", "project": project, "scenario": scenario}


@router.post("/scenarios/ingest")
async def ingest_scenario(request: Request, body: IngestRequest):
    """Ingest a scenario from server-accessible file paths."""
    from gat.server.ingest import ingest_scenario as do_ingest

    state = _get_state(request)
    async with state.write_lock:
        try:
            result = do_ingest(
                conn=state.conn,
                db=state.db,
                project=body.project,
                scenario=body.scenario,
                handler=body.handler,
                system_path=body.system_path,
                simulation_paths=body.simulation_paths,
            )
        except Exception as e:
            logger.exception("Ingestion failed: {}", e)
            raise HTTPException(500, f"Ingestion failed: {e}")

    return result


# ------------------------------------------------------------------ #
# Data Endpoints (Arrow IPC)
# ------------------------------------------------------------------ #


@router.post("/query")
async def query(request: Request, body: QueryRequest):
    """Execute SQL scoped to a scenario's schema, return Arrow IPC."""
    state = _get_state(request)
    entry = registry.get_scenario(state.conn, body.project, body.scenario)
    if entry is None:
        raise HTTPException(404, f"Scenario {body.project}/{body.scenario} not found")

    schema = entry["schema_name"]

    # Auto-prefix: set the search path so users don't need to qualify table names
    try:
        state.conn.execute(f"SET search_path = '{schema}'")
        df = state.db.query(body.sql)
    except Exception as e:
        raise HTTPException(400, f"Query error: {e}")
    finally:
        state.conn.execute("SET search_path = 'main'")

    return _arrow_response(df)


@router.post("/query/grouped")
async def query_grouped(request: Request, body: GroupedQueryRequest):
    """High-level grouped query: dataset + group_by -> Arrow IPC."""
    state = _get_state(request)
    entry = registry.get_scenario(state.conn, body.project, body.scenario)
    if entry is None:
        raise HTTPException(404, f"Scenario {body.project}/{body.scenario} not found")

    schema = entry["schema_name"]

    try:
        df = state.db.query_grouped(schema, body.dataset, body.group_by)
    except Exception as e:
        raise HTTPException(400, f"Query error: {e}")

    return _arrow_response(df)
