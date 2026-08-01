"""
Bus-geometry upload helpers.

When a user provides external geographic coordinates for a Sienna system
(CSV with lat/lon + bus-ID column, or a GeoJSON of Point features keyed
by a property), this module:

1. Reads + validates the input file.
2. Joins coordinates onto the system's buses, generators, and lines by
   walking the Sienna system JSON's component graph.
3. Builds three GeoJSON FeatureCollections (buses, generators, lines).

Two entry points:

- `inspect_geo_file(...)`:        used by the preview step. Reads the file
  and reports columns / sample rows / detected fields. Optionally also
  joins against a system_path and reports match counts.
- `compute_bus_geometry(...)`:    used by the commit step. Returns the
  three GeoJSONs + summary stats. Caller persists them to disk.

Bus-ID matching is by Sienna `name` first, then `number` (stringified).
The user's chosen bus-ID column is matched against both — whichever
yields more matches wins. Match is exact after string normalization.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional

from .geo_helpers import (
    _normalize_col_name,
    detect_bus_id_column,
    detect_latlon_columns,
)


def _read_csv_columns_and_rows(
    path: Path, max_sample: int = 5
) -> tuple[list[str], list[dict], int]:
    """Stream a CSV and return (columns, sample_rows, total_row_count)."""
    columns: list[str] = []
    sample: list[dict] = []
    total = 0
    with open(path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = list(reader.fieldnames or [])
        for row in reader:
            total += 1
            if len(sample) < max_sample:
                sample.append(dict(row))
    return columns, sample, total


def _parse_geojson(path: Path) -> dict:
    """Load a GeoJSON file and validate it is a FeatureCollection of Points."""
    with open(path, "r", encoding="utf-8-sig") as f:
        gj = json.load(f)
    if not isinstance(gj, dict):
        raise ValueError("GeoJSON file must contain an object at the root.")
    if gj.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON file must be a FeatureCollection.")
    feats = gj.get("features") or []
    if not feats:
        raise ValueError("GeoJSON FeatureCollection has no features.")
    return gj


def _geojson_property_keys(gj: dict) -> list[str]:
    """Collect the union of property keys across features (preserving order)."""
    seen: dict[str, None] = {}  # ordered set
    for f in gj.get("features", []):
        for k in (f.get("properties") or {}).keys():
            if k not in seen:
                seen[k] = None
    return list(seen.keys())


def _geojson_sample_rows(gj: dict, max_sample: int = 5) -> list[dict]:
    """Flatten the first N features into property-only dicts (with lat/lon)."""
    out: list[dict] = []
    for f in gj.get("features", [])[:max_sample]:
        props = dict(f.get("properties") or {})
        geom = f.get("geometry") or {}
        coords = geom.get("coordinates")
        if isinstance(coords, list) and len(coords) >= 2:
            props["__lon__"] = coords[0]
            props["__lat__"] = coords[1]
        out.append(props)
    return out


def _file_kind(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in ("geojson",):
        return "geojson"
    if suffix == "json":
        # Peek: GeoJSON FeatureCollections start with `{"type":"FeatureCollection"`
        try:
            with open(path, "rb") as f:
                head = f.read(256).decode("utf-8", errors="ignore").lstrip()
            if '"FeatureCollection"' in head:
                return "geojson"
        except Exception:
            pass
        return "csv"  # fall through; let the caller choose
    return "csv"


# ── Sienna system parsing ──
# We avoid importing SiennaSystemParser here because it pulls geopandas/h5py
# eagerly. The fields we need are simple enough to read directly.


def _load_sienna_components(system_path: str) -> dict[str, list[dict]]:
    """Read a Sienna system JSON and bucket components by `__metadata__.type`.

    Returns a dict like `{"ACBus": [...], "Line": [...], ...}`. We only read
    the JSON; no DataFrame conversion (keeps this module stdlib-only).
    """
    with open(system_path, "r", encoding="utf-8") as f:
        sys_data = json.load(f)
    by_type: dict[str, list[dict]] = {}
    for c in sys_data.get("data", {}).get("components", []) or []:
        t = (c.get("__metadata__") or {}).get("type")
        if not t:
            continue
        by_type.setdefault(t, []).append(c)
    return by_type


_BUS_RESERVED_KEYS = {"internal", "supplemental_attributes_container", "ext"}


def _bus_table(by_type: dict[str, list[dict]]) -> list[dict]:
    """Project ACBus components down to flattened rows.

    Includes the canonical fields (`uuid`, `name`, `number`) plus every
    other top-level scalar property on each ACBus, so callers can match
    on arbitrary user-chosen columns. Nested fields (Internal, ext, …)
    are skipped — they don't make sense as join keys and would bloat
    the table.
    """
    rows: list[dict] = []
    for c in by_type.get("ACBus", []) or []:
        uuid = ((c.get("internal") or {}).get("uuid") or {}).get("value")
        row = {"uuid": uuid, "name": c.get("name"), "number": c.get("number")}
        for k, v in c.items():
            if k in row or k in _BUS_RESERVED_KEYS:
                continue
            # Only keep scalar/serializable values; nested dicts/lists are
            # noise for ID matching.
            if v is None or isinstance(v, (str, int, float, bool)):
                row[k] = v
        rows.append(row)
    return rows


def bus_table_columns(bus_table: list[dict]) -> list[str]:
    """Stable union of column names across the bus table, with the most
    common join candidates first."""
    seen: dict[str, None] = {}
    for k in ("name", "number", "uuid"):
        seen[k] = None
    for row in bus_table:
        for k in row.keys():
            if k not in seen:
                seen[k] = None
    return list(seen.keys())


# ── User-file parsing ──


def _parse_user_geo_file(
    path: Path,
    bus_id_column: str,
    lat_column: Optional[str],
    lon_column: Optional[str],
    geojson_id_property: Optional[str] = None,
) -> tuple[str, list[dict]]:
    """Parse the user's geo file into a list of `{bus_id, lat, lon}` rows.

    Returns `(kind, rows)` where kind is "csv" or "geojson". For GeoJSON,
    `bus_id_column` is interpreted as the property name (or the explicit
    `geojson_id_property`).
    """
    kind = _file_kind(path)
    rows: list[dict] = []
    if kind == "csv":
        if not lat_column or not lon_column:
            raise ValueError("CSV upload requires explicit lat/lon columns.")
        with open(path, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bid = row.get(bus_id_column)
                lat = row.get(lat_column)
                lon = row.get(lon_column)
                if bid is None or lat in (None, "") or lon in (None, ""):
                    continue
                try:
                    rows.append(
                        {
                            "bus_id": str(bid).strip(),
                            "lat": float(lat),
                            "lon": float(lon),
                        }
                    )
                except (TypeError, ValueError):
                    continue
    else:
        gj = _parse_geojson(path)
        prop_key = geojson_id_property or bus_id_column
        for f in gj.get("features", []):
            geom = f.get("geometry") or {}
            if geom.get("type") != "Point":
                continue
            coords = geom.get("coordinates") or []
            if len(coords) < 2:
                continue
            props = f.get("properties") or {}
            bid = props.get(prop_key)
            if bid is None:
                continue
            try:
                rows.append(
                    {
                        "bus_id": str(bid).strip(),
                        "lat": float(coords[1]),
                        "lon": float(coords[0]),
                    }
                )
            except (TypeError, ValueError):
                continue
    return kind, rows


def _build_bus_lookup(rows: list[dict]) -> dict[str, tuple[float, float]]:
    """`bus_id (str) → (lat, lon)`. Later rows win on duplicates."""
    out: dict[str, tuple[float, float]] = {}
    for r in rows:
        out[r["bus_id"]] = (r["lat"], r["lon"])
    return out


def _build_index_for_column(bus_table: list[dict], column: str) -> dict[str, dict]:
    """`stringified value of column` → bus row. Empty/None values dropped."""
    out: dict[str, dict] = {}
    for b in bus_table:
        v = b.get(column)
        if v is None or v == "":
            continue
        out[str(v).strip()] = b
    return out


def _match_buses(
    user_rows: list[dict],
    bus_table: list[dict],
    system_bus_id_column: Optional[str] = None,
) -> tuple[dict[str, tuple[float, float]], dict[str, dict], list[str], str]:
    """Match user bus IDs against the system's ACBus table.

    If `system_bus_id_column` is provided, match against that column only.
    Otherwise, evaluate `name` and `number` and pick whichever yields
    more hits (legacy auto-pick).

    Returns `(uuid_to_latlon, uuid_to_meta, unmatched_user_ids, used_column)`.
    """
    user_lookup = _build_bus_lookup(user_rows)

    if system_bus_id_column:
        by_key = _build_index_for_column(bus_table, system_bus_id_column)
        used_column = system_bus_id_column
    else:
        by_name = _build_index_for_column(bus_table, "name")
        by_number = _build_index_for_column(bus_table, "number")
        name_matches = {bid for bid in user_lookup if bid in by_name}
        number_matches = {bid for bid in user_lookup if bid in by_number}
        if len(number_matches) > len(name_matches):
            by_key, used_column = by_number, "number"
        else:
            by_key, used_column = by_name, "name"

    chosen = {bid for bid in user_lookup if bid in by_key}

    uuid_to_latlon: dict[str, tuple[float, float]] = {}
    uuid_to_meta: dict[str, dict] = {}
    for bid in chosen:
        bus = by_key[bid]
        uuid = bus.get("uuid")
        if not uuid:
            continue
        uuid_to_latlon[uuid] = user_lookup[bid]
        uuid_to_meta[uuid] = {
            "bus_id": bid,
            "bus_name": bus.get("name"),
            "bus_number": bus.get("number"),
        }

    unmatched = [bid for bid in user_lookup if bid not in chosen]
    return uuid_to_latlon, uuid_to_meta, unmatched, used_column


# ── Public API ──


def inspect_geo_file(
    path: Path,
    system_path: Optional[str] = None,
    bus_id_column: Optional[str] = None,
    lat_column: Optional[str] = None,
    lon_column: Optional[str] = None,
    system_bus_id_column: Optional[str] = None,
) -> dict:
    """Preview-step entrypoint. Returns a JSON-friendly dict.

    Optional explicit column overrides let the dialog re-run a preview
    after the user adjusts the dropdowns, so the match count reflects
    the actual choice (not just auto-detection).
    """
    kind = _file_kind(path)
    if kind == "csv":
        cols, sample, n = _read_csv_columns_and_rows(path)
        d_lat, d_lon = detect_latlon_columns(cols)
        d_id = detect_bus_id_column(cols)
        out: dict[str, Any] = {
            "kind": "csv",
            "columns": cols,
            "row_count": n,
            "sample_rows": sample,
            "detected_id_col": d_id,
            "detected_lat_col": d_lat,
            "detected_lon_col": d_lon,
        }
    else:
        gj = _parse_geojson(path)
        keys = _geojson_property_keys(gj)
        sample = _geojson_sample_rows(gj)
        d_id = detect_bus_id_column(keys)
        out = {
            "kind": "geojson",
            "columns": keys,
            "row_count": len(gj.get("features") or []),
            "sample_rows": sample,
            "detected_id_col": d_id,
            "detected_lat_col": None,
            "detected_lon_col": None,
        }

    # Effective column choices for the join preview: explicit overrides
    # win, otherwise fall back to auto-detection.
    eff_id = bus_id_column or out.get("detected_id_col")
    eff_lat = lat_column or out.get("detected_lat_col")
    eff_lon = lon_column or out.get("detected_lon_col")

    # Surface system-side columns regardless of file kind so the dialog
    # can populate the "system bus column" dropdown immediately.
    if system_path:
        try:
            by_type = _load_sienna_components(system_path)
            bus_table = _bus_table(by_type)
            out["system_bus_columns"] = bus_table_columns(bus_table)
            # Default suggestion: prefer 'name' if present, else 'number'.
            if "name" in out["system_bus_columns"]:
                out["detected_system_bus_col"] = "name"
            elif "number" in out["system_bus_columns"]:
                out["detected_system_bus_col"] = "number"
            else:
                out["detected_system_bus_col"] = (
                    out["system_bus_columns"][0] if out["system_bus_columns"] else None
                )
            out["system_bus_count"] = len(bus_table)
        except Exception as e:  # noqa: BLE001
            out["system_bus_columns"] = []
            out["match_preview_error"] = f"Could not load system: {e}"
            return out

        if eff_id and (kind == "geojson" or (eff_lat and eff_lon)):
            try:
                _, user_rows = _parse_user_geo_file(
                    path,
                    bus_id_column=eff_id,
                    lat_column=eff_lat,
                    lon_column=eff_lon,
                )
                uuid_map, _meta, unmatched, used_col = _match_buses(
                    user_rows,
                    bus_table,
                    system_bus_id_column=system_bus_id_column,
                )
                out["match_preview"] = {
                    "matched": len(uuid_map),
                    "unmatched_input": len(unmatched),
                    "unmatched_system": max(0, len(bus_table) - len(uuid_map)),
                    "unmatched_input_examples": unmatched[:10],
                    "unmatched_system_examples": [
                        str(b.get("name") or b.get("number"))
                        for b in bus_table
                        if (b.get("uuid") not in uuid_map)
                    ][:10],
                    "system_bus_count": len(bus_table),
                    "used_system_column": used_col,
                }
            except Exception as e:  # noqa: BLE001
                out["match_preview_error"] = str(e)
    return out


def compute_bus_geometry(
    system_path: str,
    user_geo_path: Path,
    bus_id_column: str,
    lat_column: Optional[str] = None,
    lon_column: Optional[str] = None,
    system_bus_id_column: Optional[str] = None,
) -> dict:
    """Commit-step join. Returns the buses FeatureCollection + stats.

    `system_path` is a *representative* system file from the project — it
    only drives validation of the join (so we can report a match count
    before persisting). The output is intentionally project-portable:
    bus features are keyed on `bus_id` (whichever ACBus column matched),
    NOT on UUID. Sienna UUIDs are per-system-file and so don't survive
    across scenarios; per-scenario UUID resolution happens at lookup
    time via `gat.server.system_geo.load_project_bus_coords`.

    Generator and transmission-line geometries are not produced here —
    client extensions regenerate them lazily per scenario from the
    persisted bus coordinates.

    Output shape:
    {
        "buses":           <FeatureCollection>,
        "bus_id_field":    "name" | "number",
        "stats":           {system_bus_count, bus_count,
                            unmatched_buses_input, unmatched_buses_system}
    }
    """
    _kind, user_rows = _parse_user_geo_file(
        user_geo_path,
        bus_id_column=bus_id_column,
        lat_column=lat_column,
        lon_column=lon_column,
    )

    by_type = _load_sienna_components(system_path)
    bus_table = _bus_table(by_type)
    uuid_to_latlon, uuid_to_meta, unmatched_user, used_col = _match_buses(
        user_rows,
        bus_table,
        system_bus_id_column=system_bus_id_column,
    )

    bus_features = []
    for uuid, (lat, lon) in uuid_to_latlon.items():
        m = uuid_to_meta.get(uuid, {})
        bus_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "bus_id": m.get("bus_id"),
                    "bus_name": m.get("bus_name"),
                    "bus_number": m.get("bus_number"),
                },
            }
        )
    buses_fc = {"type": "FeatureCollection", "features": bus_features}

    return {
        "buses": buses_fc,
        "bus_id_field": used_col,
        "stats": {
            "system_bus_count": len(bus_table),
            "bus_count": len(bus_features),
            "unmatched_buses_input": len(unmatched_user),
            "unmatched_buses_system": max(0, len(bus_table) - len(bus_features)),
        },
    }
