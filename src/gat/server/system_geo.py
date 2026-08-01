"""
GAT core: project-scoped bus-geometry sidecar store.

Owns *all* the path/storage/load logic for "user supplied lat/lons for the
buses in this project". Lives in `gat.server` (not a client extension)
so it's usable from any GAT entry point — CLI, scripts, notebooks — not
just a client-facing upload dialog.

Why project-scoped (not system-scoped):
    A project usually has multiple scenarios that exercise the *same*
    physical system with different parameters (different generation mixes,
    contingencies, demand growth, etc.). Bus locations don't change across
    those, so coords belong on the project. Sienna UUIDs are per-system-
    file and so are unstable across scenarios — we therefore key the
    persisted coords on the user's chosen ACBus column (`name` or
    `number`). Each scenario resolves its own UUIDs at lookup time via
    its `sys__ACBus` table.

Layout under `<data_root>/project_geo/<safe_project>/`:
    buses.geojson    — Point per bus, properties = {bus_id, bus_name?,
                       bus_number?}. Source of truth.
    metadata.json    — {bus_id_field: 'name' | 'number',
                       source_filename, uploaded_at_iso, …}

Generator/line geometries are *not* persisted here — client extensions
regenerate them lazily per scenario from the bus coordinates, which
now consult this module first.

Public entry points:
    project_geo_dir(data_root, project)
    has_project_geo(data_root, project) -> bool
    write_project_buses(data_root, project, buses_fc, *, bus_id_field, ...) -> Path
    load_project_bus_coords(data_root, project) -> (dict[str, (lon, lat)], bus_id_field) | None
    register(conn, project, ...) -> upsert registry row
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _safe_project_dir(project: str) -> str:
    """Filesystem-safe project segment. Preserves printable ASCII; replaces
    everything else with '_'. Two distinct project names that collide after
    sanitisation would step on each other; we add a short hash suffix to
    keep them disjoint."""
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", project).strip("_") or "_"
    if cleaned == project:
        return cleaned
    # Disambiguate when sanitisation was lossy.
    import hashlib

    suffix = hashlib.sha256(project.encode("utf-8")).hexdigest()[:6]
    return f"{cleaned}-{suffix}"


def project_geo_dir(data_root: str | Path, project: str) -> Path:
    return Path(data_root) / "project_geo" / _safe_project_dir(project)


def has_project_geo(data_root: str | Path, project: str) -> bool:
    return (project_geo_dir(data_root, project) / "buses.geojson").exists()


def load_project_bus_coords(
    data_root: str | Path,
    project: str,
) -> Optional[tuple[dict[str, tuple[float, float]], str]]:
    """Load `(coords_by_id_str, bus_id_field)` for a project.

    `coords_by_id_str` maps the stringified bus identifier (whatever the
    user mapped on upload — `name` or `number`) to `(lon, lat)`.
    `bus_id_field` is `'name'` or `'number'`, telling callers which
    column on `sys__ACBus` to join against.

    Returns None when no project geo exists or the files are unreadable.
    """
    d = project_geo_dir(data_root, project)
    buses_p = d / "buses.geojson"
    meta_p = d / "metadata.json"
    if not buses_p.exists() or not meta_p.exists():
        return None
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8"))
        bus_id_field = meta.get("bus_id_field") or "name"
        gj = json.loads(buses_p.read_text(encoding="utf-8"))
    except Exception:
        return None
    out: dict[str, tuple[float, float]] = {}
    for f in gj.get("features") or []:
        props = f.get("properties") or {}
        bid = props.get("bus_id")
        coords = (f.get("geometry") or {}).get("coordinates") or []
        if bid is None or len(coords) < 2:
            continue
        try:
            out[str(bid).strip()] = (float(coords[0]), float(coords[1]))
        except (TypeError, ValueError):
            continue
    if not out:
        return None
    return out, bus_id_field


def write_project_buses(
    data_root: str | Path,
    project: str,
    buses_fc: dict[str, Any],
    *,
    bus_id_field: str,
    bus_id_column: str,
    lat_column: Optional[str],
    lon_column: Optional[str],
    source_filename: str,
) -> Path:
    """Persist the buses FeatureCollection + metadata.

    Overwrites any existing project geo. Returns the directory path.
    """
    d = project_geo_dir(data_root, project)
    d.mkdir(parents=True, exist_ok=True)
    (d / "buses.geojson").write_text(json.dumps(buses_fc), encoding="utf-8")
    (d / "metadata.json").write_text(
        json.dumps(
            {
                "project": project,
                "bus_id_field": bus_id_field,
                "bus_id_column": bus_id_column,
                "lat_column": lat_column,
                "lon_column": lon_column,
                "source_filename": source_filename,
                "uploaded_at": datetime.now(timezone.utc).isoformat(),
            }
        ),
        encoding="utf-8",
    )
    return d


def register(
    conn: Any,
    project: str,
    *,
    bus_id_field: str,
    bus_id_column: str,
    lat_column: Optional[str],
    lon_column: Optional[str],
    source_filename: str,
    bus_count: int,
    unmatched_count: int,
) -> None:
    """Upsert the `_gat_registry.project_geo` row.

    `conn` must be a writable DuckDB connection with the registry already
    ensured.
    """
    from gat.server.registry import upsert_project_geo

    upsert_project_geo(
        conn,
        project=project,
        bus_id_field=bus_id_field,
        bus_id_column=bus_id_column,
        lat_column=lat_column,
        lon_column=lon_column,
        source_filename=source_filename,
        bus_count=bus_count,
        unmatched_count=unmatched_count,
    )
