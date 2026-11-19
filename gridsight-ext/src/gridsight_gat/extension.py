"""
GAT GridSight extension — power system simulation results from GAT DuckDB.

Provides:
- Dynamic projects/scenarios from GAT's registry
- Bus point and transmission line geometries per scenario
- Timeseries datasets: generation, load, line_flow (daily partitioned)
- Category maps from GAT's catmap__ tables
- DuckDB views for AI queries
- Chart specs for dispatch, generation mix, load duration
- Input controls for scenario switching and time aggregation
"""

from __future__ import annotations

import io
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from gridsight.extensions import (
    Capability,
    CategoryMapDescriptor,
    DatasetDescriptor,
    DatasetTimeInfo,
    DuckDBTableInfo,
    ExtensionContext,
    ExtensionManifest,
    ExtensionProject,
    ExtensionScenario,
    FileGroupSpec,
    FileUploadSpec,
    GraphEdge,
    GraphNode,
    GraphStratum,
    GraphTopology,
    GraphTopologyDescriptor,
    LayerDefinition,
    GridSightExtensionBase,
    PreviewResult,
    UploadFormField,
    UploadResult,
)
from gridsight.extensions.ai import AISchema, AITableSchema
from gridsight.extensions.charts import ChartSpec

logger = logging.getLogger("gridsight_gat")

# GAT standard technology/fuel palette (inlined to avoid gat package dependency)
_STANDARD_COLORS: dict[str, str] = {
    "Nuclear": "#820000",
    "Coal": "#222222",
    "Coal CCS": "#707685",
    "Coal-CCS": "#707685",
    "Steam-Turbine": "#222223",
    "NG-CC": "#52216B",
    "Gas-CC": "#52216B",
    "NG-CCS": "#9467BD",
    "Gas-CCS": "#9467BD",
    "Combined-Cycle-Gas-Turbine": "#52216B",
    "NG-CC-CCS": "#5E1688",
    "Gas-CC-CCS": "#5E1688",
    "NG-CT": "#C2A1DB",
    "Gas-CT": "#C2A1DB",
    "NG": "#C2A1DB",
    "Gas": "#C2A1DB",
    "Combustion-Turbine": "#C2A1DB",
    "Dual-Fuel": "#000080",
    "Oil-Gas-Steam": "#3D3376",
    "o-g-s": "#3D3376",
    "Oil": "#3D3376",
    "Geothermal": "#A96235",
    "Landfill-Gas": "#5B9844",
    "Biopower": "#5B9844",
    "RE-CT": "#7FC340",
    "RE-CC": "#7FC340",
    "BECCS": "#A8C839",
    "PS": "#CC0079",
    "Other": "#FF7FBB",
    "Hydro": "#187F94",
    "Ocean": "#000080",
    "H2-CT": "#A8C839",
    "H2-CC": "#708238",
    "Pumped Hydro": "#CC0079",
    "Battery": "#FF4A88",
    "BESS": "#FF4A88",
    "Storage": "#FF4A88",
    "VRE": "#7FC340",
    "RE": "#7FC340",
    "Wind": "#00B6EF",
    "Land-based Wind": "#00B6EF",
    "Onshore Wind": "#00B6EF",
    "Offshore Wind": "#106BA7",
    "CSP": "#FC761A",
    "PV": "#FFC903",
    "UPV": "#FFC903",
    "dPV": "#FFAB02",
    "electrolyzer": "#896F2D",
    "PV-Battery": "#D1C202",
    "OSW-Battery": "#9B014F",
    "Net Imports": "#2762C4",
    "Net Exports": "#E43F3F",
    "Demand": "#000000",
    "Curtailment": "#E1E1E1",
    "Unserved Energy": "#FF0000",
}

# Case-insensitive lookup for GAT's standard technology/fuel colors
_color_lookup: dict[str, str] = {}
for _k, _v in _STANDARD_COLORS.items():
    _color_lookup[_k.lower().replace(" ", "-").replace("_", "-")] = _v


# Display groups treated as VRE (variable renewable energy). Curtailment —
# `max(0, availability - generation)` — is only physically meaningful for
# these technologies. Matches the inline list previously hard-coded in the
# system-demand chart SQL (mirror gat.config's `curtailable_tech` default).
# Used by:
#   - the renewable layer's per-feature `curtailable` property (gates the
#     curtailment band shader-side so a gas plant with availability data
#     doesn't render a fake "wasted" ring),
#   - the curtailment_total + system_generation_stacked chart SQLs (filter
#     the SUM(GREATEST(0, a-g)) aggregate to VRE entities only).
_VRE_DISPLAY_GROUPS: frozenset[str] = frozenset(
    {
        "Land-based Wind",
        "Offshore Wind",
        "Onshore Wind",
        "Wind",
        "PV",
        "UPV",
        "dPV",
        "VRE",
    }
)


def _vre_groups_sql_list() -> str:
    """Inline SQL string list for filtering display_group ∈ VRE."""
    return ", ".join(f"'{g}'" for g in sorted(_VRE_DISPLAY_GROUPS))


def _lookup_color(category: str) -> str | None:
    """Look up a hex color for a technology/fuel category name."""
    key = category.lower().replace(" ", "-").replace("_", "-")
    return _color_lookup.get(key)


def _hex_to_rgba(hex_color: str, alpha: int = 220) -> list[int]:
    """Convert hex color string to [r, g, b, a] array for deck.gl."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha]


def _rgba_to_hex(rgba: list[int]) -> str:
    """Convert [r, g, b, a?] to a #RRGGBB hex string (alpha dropped)."""
    r, g, b = rgba[0], rgba[1], rgba[2]
    return f"#{r:02X}{g:02X}{b:02X}"


# Sienna technology key → display group (inlined from gat/scenariohandlers/config_maps.py)
_SIENNA_TECH_MAP: dict[str, str] = {
    "BA": "BESS",
    "CA_NATURAL_GAS": "Gas-CT",
    "CC_NATURAL_GAS": "Gas-CC",
    "CC_MUNICIPAL_WASTE": "Gas-CC",
    "CC_OTHER": "Gas-CC",
    "CT_COAL": "Coal",
    "CT_DISTILLATE_FUEL_OIL": "o-g-s",
    "CT_MUNICIPAL_WASTE": "Biopower",
    "CT_NATURAL_GAS": "Gas-CT",
    "CT_OTHER": "Gas-CT",
    "CT_RESIDUAL_FUEL_OIL": "o-g-s",
    "CT_WASTE_OIL": "o-g-s",
    "GT_MUNICIPAL_WASTE": "Biopower",
    "GT_NATURAL_GAS": "Gas-CT",
    "GT_OTHER": "Other",
    "GT_WOOD_WASTE": "Biopower",
    "HY": "Hydro",
    "IC_DISTILLATE_FUEL_OIL": "o-g-s",
    "IC_MUNICIPAL_WASTE": "Biopower",
    "IC_NATURAL_GAS": "Gas-CT",
    "IC_OTHER": "Other",
    "OT": "Other",
    "OT_COAL": "Coal",
    "OT_MUNICIPAL_WASTE": "Biopower",
    "OT_NATURAL_GAS": "o-g-s",
    "OT_NUCLEAR": "Nuclear",
    "OT_OTHER": "Other",
    "OT_WASTE_COAL": "Coal",
    "PS_Other": "PS",
    "PVe": "PV",
    "ST_COAL": "Coal",
    "ST_DISTILLATE_FUEL_OIL": "o-g-s",
    "ST_GEOTHERMAL": "Geothermal",
    "ST_MUNICIPAL_WASTE": "Biopower",
    "ST_NATURAL_GAS": "o-g-s",
    "ST_NUCLEAR": "Nuclear",
    "ST_OTHER": "Other",
    "ST_PETROLEUM_COKE": "o-g-s",
    "ST_RESIDUAL_FUEL_OIL": "o-g-s",
    "ST_WASTE_COAL": "Coal",
    "ST_WASTE_OIL": "o-g-s",
    "WS": "Offshore Wind",
    "WT": "Land-based Wind",
    # Standalone prime_movers (when fuel is missing)
    "ST": "Other",
    "CT": "Gas-CT",
    "CC": "Gas-CC",
    "IC": "Other",
    "GT": "Gas-CT",
    "CA": "Gas-CT",
}


def _resolve_display_group(prime_mover: str, fuel: str | None) -> str:
    """Resolve a generator's display group using GAT's standard technology map.

    Builds the technology key as prime_mover + "_" + fuel (for thermal types),
    or just prime_mover (for VRE/hydro/storage), then looks up in the standard map.
    """
    pm = prime_mover.strip()
    fl = (fuel or "").strip()

    # Try combined key first (thermal convention: PM_FUEL)
    if fl:
        combined = f"{pm}_{fl}"
        if combined in _SIENNA_TECH_MAP:
            return _SIENNA_TECH_MAP[combined]

    # Try prime_mover alone (VRE, hydro, storage)
    if pm in _SIENNA_TECH_MAP:
        return _SIENNA_TECH_MAP[pm]

    # Fallback: use TechnologyMapping.new() logic — check standard colors
    color = _lookup_color(pm)
    if color:
        return pm
    if fl:
        color = _lookup_color(fl)
        if color:
            return fl

    return pm or "Other"


# ---------------------------------------------------------------------------
# Tier-1 essentials — the minimum set of simulation datasets the GridSight
# default view needs: generation/load/line_flow charts + map styling
# (which requires per-generator and per-line series via the composed
# tables). Everything else (UC binary vars, ancillary services, slack
# vars, voltage angles, production cost expressions, fuel consumption,
# storage regularization, ...) gets ingested in a Tier-2 background job
# so users see the map render in ~10s instead of ~30s.
#
# The Sienna name conventions:
#   ActivePowerVariable__{Type}              — primary dispatch result
#   ActivePowerOut/InVariable__Storage       — storage discharge/charge
#   ActivePowerTimeSeriesParameter__{Type}   — input forecasts (load, RE)
#   FlowActivePowerVariable__{LineKind}      — branch flows
# ---------------------------------------------------------------------------
TIER1_RAW_PREFIXES: frozenset[str] = frozenset(
    {
        "ActivePowerVariable__",
        "ActivePowerOutVariable__",
        "ActivePowerInVariable__",
        "ActivePowerTimeSeriesParameter__",
        "FlowActivePowerVariable__",
    }
)
TIER1_COMPOSED: frozenset[str] = frozenset(
    {
        "generation",
        "load",
        "line_flow",
        "availability",
        "charging",
    }
)


def _tier1_dataset_filter(ds) -> bool:
    """True for the minimum dataset set the default GridSight view needs.

    Used during the foreground (Tier-1) ingest. Tier-2 picks up the
    complement in a background job after the user-facing "ready" state.
    """
    from gat.datasets import DatasetKind

    if ds.kind == DatasetKind.RAW_SIMULATION:
        return any(ds.name.startswith(p) for p in TIER1_RAW_PREFIXES)
    if ds.kind == DatasetKind.COMPOSED:
        return ds.name in TIER1_COMPOSED
    return True  # system datasets always go in tier 1


def _tier2_dataset_filter(ds) -> bool:
    """Complement of tier-1: everything the foreground ingest skipped."""
    from gat.datasets import DatasetKind

    if ds.kind == DatasetKind.RAW_SIMULATION:
        return not any(ds.name.startswith(p) for p in TIER1_RAW_PREFIXES)
    if ds.kind == DatasetKind.COMPOSED:
        return ds.name not in TIER1_COMPOSED
    return False  # system datasets already wrote in tier 1


def _schema_name(project: str, scenario: str, model: str) -> str:
    """Build the DuckDB schema name for one (project, scenario, model).

    Each Sienna optimization stage (UC / RAUC / Emulation Model / ...)
    is ingested under its own schema, so re-ingesting a different model
    doesn't disturb its siblings. Lowercased to match DuckDB's storage
    of unquoted identifiers; encoding lives in
    ``gat.server.ingest.schema_name_for`` — keep them in sync.
    """
    return f"{project}__{scenario}__{model}".replace("-", "_").replace(" ", "_").lower()


_GAT_DB_RESOLVED: Path | None = None


def _gat_data_root() -> str:
    """Where uploaded GAT scenario artefacts (system JSON + HDF5s) live.

    Backend-neutral. Operators set this to whatever storage they have:

      - Local disk:        ``/data/gat/scenarios``
      - NFS / SMB mount:   ``/mnt/share/gat-scenarios`` (looks local)
      - PVC in k8s:        ``/data/gat/scenarios`` (mount path)
      - S3 / SeaweedFS:    ``s3://gridsight/GAT``

    Default is alongside the GAT DuckDB so a single mount point covers
    both. Per-scenario layout is always
    ``{root}/{project}/{scenario}/{filename}`` (with a trailing ``.gz``
    appended when root is S3, since gzip-on-the-wire is what gets the
    object past the WAF; a local mount just stores raw bytes).
    """
    explicit = os.environ.get("GAT_DATA_ROOT")
    if explicit:
        return explicit.rstrip("/")
    db_path = Path(_gat_db_path())
    return str(db_path.parent / "scenarios")


def _scenario_artifact_uri(project: str, scenario: str, filename: str) -> str:
    """Build the canonical URI for a single scenario artefact under
    ``GAT_DATA_ROOT``. Adds ``.gz`` only for S3 destinations."""
    from gridsight.extensions.storage import is_s3_uri

    root = _gat_data_root()
    suffix = ".gz" if is_s3_uri(root) else ""
    return f"{root}/{project}/{scenario}/{filename}{suffix}"


def _scenario_root_uri(project: str, scenario: str) -> str:
    return f"{_gat_data_root()}/{project}/{scenario}"


# Project-scoped sidecar layout lives in gat.server.system_geo so any GAT
# entry point (CLI, scripts, notebooks) can read/write it. Callers in this
# file invoke that module directly — no thin wrappers needed.


def _gat_db_path() -> str:
    """Where the GAT scenario DuckDB file lives.

    Override with ``GAT_DB_PATH``. Three accepted forms:

      - Plain path (``/data/gat/gat_server.duckdb``): used as-is.
      - ``s3://bucket/key``: pulled to a local cache file on first call;
        the local file is pushed back to S3 at process exit. Single-
        replica deployments only — concurrent writers will corrupt
        DuckDB. SIGKILL bypasses the upload.
      - Default (dev-machine): ``~/.gat/server/gat_server.duckdb``.
        Not persistent in a container; set ``GAT_DB_PATH`` explicitly
        in any production deploy.
    """
    global _GAT_DB_RESOLVED
    if _GAT_DB_RESOLVED is not None:
        return str(_GAT_DB_RESOLVED)
    raw = os.environ.get(
        "GAT_DB_PATH",
        str(Path.home() / ".gat" / "server" / "gat_server.duckdb"),
    )
    # Lazy import: gridsight.extensions.storage lives in gridsight-sdk and
    # must already be installed for the extension to load. Resolve once
    # and memoize so the atexit upload only registers a single time.
    from gridsight.extensions.storage import resolve_path

    _GAT_DB_RESOLVED = resolve_path(raw)
    return str(_GAT_DB_RESOLVED)


from gridsight_gat._gateway import _DuckDBGateway


class GATExtension(GridSightExtensionBase):
    def __init__(self) -> None:
        self._context: ExtensionContext | None = None
        self._attached = False
        # Placeholder lock for pre-context use. Replaced in on_startup with
        # the shared engine lock (ExtensionContext.duckdb_lock) so THIS
        # extension and the server's DuckDBEngine serialize on the SAME
        # lock over the SAME connection. Using separate locks here was a
        # silent bug: concurrent chart queries + extension operations
        # (stream partitions, catmap materialization) could interleave on
        # the shared connection and produce empty/garbled results.
        self._lock = threading.RLock()
        # All DuckDB access funnels through ``self._db``. Direct
        # ``self._conn.execute(...)`` calls bypass the lock and crashed
        # the container under concurrent load — the gateway makes those
        # impossible by construction. Constructed in ``on_startup`` once
        # the shared connection is available.
        self._db: _DuckDBGateway | None = None

    def get_manifest(self) -> ExtensionManifest:
        return ExtensionManifest(
            name="gat",
            display_name="Grid",
            version="0.1.0",
            description="Grid Analysis Toolkit — power system simulation results and analytics.",
            capabilities=[
                Capability.DATA_PROVIDER,
                Capability.DUCKDB_TABLES,
                Capability.AI_QUERYABLE,
                Capability.FILE_UPLOAD,
                # GRAPH_PROVIDER intentionally commented out while
                # the Graph view is disabled in GridSight. The
                # list_graph_topologies / get_graph_topology methods
                # below stay in place so re-enabling is a one-line
                # change here.
            ],
            # Icon ships as `static/icon.svg`; the SDK's get_icon_bytes
            # override (below) hands it to the server, which exposes it
            # at /api/extensions/gat/icon.
            icon=None,
        )

    def get_icon_bytes(self) -> bytes | None:
        return (Path(__file__).parent / "static" / "icon.svg").read_bytes()

    def on_startup(self, context: ExtensionContext) -> None:
        self._context = context
        # Adopt the engine's shared lock so we serialize against the
        # engine's query_json / query calls on the same connection.
        if context.duckdb_lock is not None:
            self._lock = context.duckdb_lock
        self._db = _DuckDBGateway(context.duckdb_conn, self._lock)

        # Ensure the registry schema is up to date BEFORE any query path
        # hits ``_ensure_attached``. The gat_db file is attached
        # read-only there, which means schema migrations can't run from
        # the main connection. Open a separate writable handle on the
        # cached DB file, run ensure_registry (which detects pre-M2a
        # shapes and drops them so the CREATE installs the new one),
        # then close. The next _ensure_attached sees the fresh schema.
        try:
            import duckdb
            from gat.server.registry import ensure_registry

            db_path = _gat_db_path()
            if Path(db_path).exists():
                migrate_conn = duckdb.connect(db_path)
                try:
                    ensure_registry(migrate_conn)
                finally:
                    migrate_conn.close()
                logger.info("GAT registry verified at startup: %s", db_path)
        except Exception as e:
            logger.warning("Registry migration at startup failed: %s", e)

    # ── File Upload ────────────────────────────────────────────────────────

    def get_upload_specs(self) -> list[FileUploadSpec]:
        return [
            FileUploadSpec(
                name="sienna_scenario",
                display_name="Sienna Scenario",
                description=(
                    "Upload a Sienna system JSON and one or more HDF5 simulation "
                    "result files to create a new GAT scenario."
                ),
                file_groups=[
                    FileGroupSpec(
                        name="system_file",
                        display_name="System JSON",
                        accepted_extensions=[".json"],
                        min_files=0,
                        max_files=1,
                        description="Sienna PowerSystems.jl system definition file.",
                    ),
                    FileGroupSpec(
                        name="simulation_files",
                        display_name="Simulation HDF5",
                        accepted_extensions=[".h5", ".hdf5"],
                        min_files=1,
                        max_files=10,
                        description="One or more HDF5 result files from PowerSimulations.jl.",
                    ),
                ],
                form_fields=[
                    UploadFormField(
                        name="project_name",
                        display_name="Project Name",
                        required=True,
                    ),
                    UploadFormField(
                        name="scenario_name",
                        display_name="Scenario Name",
                        required=True,
                    ),
                ],
                existing_systems=self._get_existing_systems(),
            ),
            FileUploadSpec(
                name="bus_geometry",
                display_name="Bus Geometry",
                description=(
                    "Attach geographic coordinates to a GAT project. The "
                    "same physical system is typically used across many "
                    "scenarios in a project (different parameter sets, "
                    "contingencies, etc.), so bus coords are stored at "
                    "the project level and shared by every scenario. "
                    "Upload a CSV (with bus-ID + lat/lon columns) or a "
                    "GeoJSON FeatureCollection of Point features keyed "
                    "by a property. Generator and transmission-line "
                    "geometries are derived lazily per scenario from "
                    "the system's component graph."
                ),
                file_groups=[
                    FileGroupSpec(
                        name="geo_file",
                        display_name="Bus Geometry (CSV or GeoJSON)",
                        accepted_extensions=[".csv", ".geojson", ".json"],
                        min_files=1,
                        max_files=1,
                    ),
                ],
                form_fields=[
                    UploadFormField(
                        name="project",
                        display_name="Project",
                        required=True,
                        hidden=True,
                    ),
                    UploadFormField(
                        name="bus_id_column",
                        display_name="Bus ID column / property",
                        required=True,
                    ),
                    UploadFormField(
                        name="lat_column",
                        display_name="Latitude column (CSV)",
                        required=False,
                    ),
                    UploadFormField(
                        name="lon_column",
                        display_name="Longitude column (CSV)",
                        required=False,
                    ),
                    UploadFormField(
                        name="system_bus_id_column",
                        display_name="System bus column",
                        required=False,
                        default="name",
                    ),
                ],
                supports_preview=True,
                meta={
                    # No metadata needed for project scoping — the dialog
                    # already knows the active project from scenarioState
                    # and threads it directly into the hidden form field.
                },
            ),
        ]

    def _get_representative_system_for_project(self, project: str) -> str | None:
        """Pick any scenario's system_path under a project. Used by the
        bus_geometry preview/upload paths to validate the join — the
        persisted result is project-scoped (keyed by ACBus name/number),
        so any scenario's system file is a fine validator.

        Returns the registry-stored value (which may be an ``s3://``
        URI in production); callers that need to read bytes must run
        it through ``storage.resolve_path`` first.
        """
        from gridsight.extensions.storage import is_s3_uri

        if not project or not self._ensure_attached():
            return None
        try:
            rows = self._db.fetchall(
                "SELECT scenario, source_paths "
                "FROM gat_db._gat_registry.scenarios "
                "WHERE status = 'ready' AND source_paths IS NOT NULL "
                "  AND project = ?",
                [project],
            )
        except Exception:
            return None
        for _scenario, source_json in rows:
            try:
                info = json.loads(source_json)
                sp = info.get("system_path")
                if not sp:
                    continue
                # s3:// URIs aren't local files, so ``Path.exists()`` is
                # always False for them. Trust the registry — a
                # ``status='ready'`` row means the upload completed and
                # the object was committed to S3.
                if is_s3_uri(sp) or Path(sp).exists():
                    return sp
            except Exception:
                continue
        return None

    def _default_model_for(self, project: str, scenario: str) -> str:
        """Return the default model name for a (project, scenario), or
        ``"default"`` when the scenario hasn't been ingested yet (or
        the registry doesn't know about it). Used by ``_resolve_schema``
        when the caller didn't specify a model.
        """
        if not self._ensure_attached():
            return "default"
        try:
            row = self._db.fetchone(
                "SELECT model FROM gat_db._gat_registry.scenarios "
                "WHERE project = ? AND scenario = ? "
                "ORDER BY is_default DESC, ingested_at DESC LIMIT 1",
                [project, scenario],
            )
            return row[0] if row else "default"
        except Exception as e:
            logger.warning(
                "default-model lookup for %s/%s failed: %s", project, scenario, e
            )
            return "default"

    def _resolve_schema(
        self, project: str, scenario: str, model: str | None = None
    ) -> str:
        """Build the DuckDB schema name for a (project, scenario, model).

        When ``model`` is None, falls back to the scenario's default
        (the model flagged ``is_default=TRUE`` in the registry,
        typically the H5's emulation model). Until M3 lands the
        frontend dropdown, every call site passes None and gets the
        default — preserving the pre-M2a single-model UX while the
        underlying storage is already model-aware.
        """
        if model is None:
            model = self._default_model_for(project, scenario)
        return _schema_name(project, scenario, model)

    def _project_for_schema(self, schema: str) -> str | None:
        """Reverse-lookup a project name from a scenario's schema_name."""
        if not self._ensure_attached():
            return None
        try:
            row = self._db.fetchone(
                "SELECT project FROM gat_db._gat_registry.scenarios "
                "WHERE schema_name = ? LIMIT 1",
                [schema],
            )
        except Exception:
            return None
        return row[0] if row else None

    def _get_scenario_systems(self) -> dict[str, str]:
        """Map "{project}/{scenario}" → system_path for every ready scenario.

        Used by the bus_geometry dialog to resolve a scenario's system path
        without re-iterating the existing-systems list (which dedupes by
        path and so loses scenarios sharing a system).
        """
        if not self._ensure_attached():
            return {}
        try:
            rows = self._db.fetchall(
                "SELECT project, scenario, source_paths "
                "FROM gat_db._gat_registry.scenarios "
                "WHERE status = 'ready' AND source_paths IS NOT NULL"
            )
        except Exception:
            return {}
        out: dict[str, str] = {}
        for project, scenario, source_json in rows:
            try:
                info = json.loads(source_json)
                sp = info.get("system_path")
                if sp:
                    out[f"{project}/{scenario}"] = sp
            except Exception:
                continue
        return out

    def _get_existing_systems(self) -> list[dict]:
        """Return list of system JSON paths from previously ingested scenarios."""
        from gridsight.extensions.storage import is_s3_uri

        if not self._ensure_attached():
            return []
        try:
            rows = self._db.fetchall(
                "SELECT project, scenario, source_paths "
                "FROM gat_db._gat_registry.scenarios "
                "WHERE status = 'ready' AND source_paths IS NOT NULL"
            )
        except Exception:
            return []

        seen: set[str] = set()
        result: list[dict] = []
        for project, scenario, source_json in rows:
            try:
                info = json.loads(source_json)
                sp = info.get("system_path")
                # ``status='ready'`` rows mean the upload committed; for
                # s3:// URIs the registry is authoritative (no local
                # file to stat). Locally we still verify the file
                # exists so a stale entry doesn't pollute the dropdown.
                if not sp or sp in seen:
                    continue
                if not is_s3_uri(sp) and not Path(sp).exists():
                    continue
                seen.add(sp)
                result.append(
                    {
                        "label": f"{project}/{scenario} — {Path(sp).name}",
                        "system_path": sp,
                        # Project/scenario are exposed so callers can resolve
                        # a (project, scenario) → system_path without the
                        # awkward label parse. The first scenario seen for a
                        # given system_path wins; if more than one shares a
                        # system, look in the registry directly.
                        "project": project,
                        "scenario": scenario,
                    }
                )
            except Exception:
                continue
        return result

    def handle_upload(
        self,
        spec_name: str,
        file_paths: dict[str, list[str]],
        form_data: dict[str, str],
    ) -> UploadResult:
        if spec_name == "bus_geometry":
            return self._handle_bus_geometry_upload(file_paths, form_data)
        if spec_name != "sienna_scenario":
            return UploadResult(
                success=False, error=f"Unknown upload spec: {spec_name}"
            )

        project = form_data.get("project_name", "").strip()
        scenario = form_data.get("scenario_name", "").strip()
        if not project or not scenario:
            return UploadResult(
                success=False, error="Project and scenario names are required."
            )

        system_files = file_paths.get("system_file", [])
        sim_files = file_paths.get("simulation_files", [])
        existing_system = form_data.get("existing_system_path", "").strip()

        # Determine system path: uploaded file or existing path
        if system_files:
            system_path = system_files[0]
        elif existing_system and Path(existing_system).exists():
            system_path = existing_system
        else:
            return UploadResult(
                success=False,
                error="System JSON file is required (upload or select existing).",
            )

        if not sim_files:
            return UploadResult(
                success=False, error="At least one simulation HDF5 file is required."
            )

        try:
            from gat.backends.duckdb_backend import GATDatabase
            from gat.server.ingest import ingest_scenario
            from gat.server.registry import ensure_registry

            # Build a state-only GATDatabase (in-memory backing conn
            # that's never written to). All real DB ops are routed
            # through ``self._with_write_conn`` via the write provider,
            # which briefly takes ``self._lock``, detaches the shared
            # ``gat_db`` attachment, opens an ephemeral writable handle,
            # runs the caller's ``fn(conn)``, closes the handle, and
            # reattaches. Each lock window is milliseconds — the long
            # parquet writes that dominate ingest happen entirely
            # outside the lock (see GATDatabase.ingest_simulation's
            # two-phase split).
            db = GATDatabase(None)
            db.set_write_provider(self._with_write_conn)
            db.set_parquet_root(f"{_scenario_root_uri(project, scenario)}/parquet")

            db.with_write_conn(ensure_registry)

            ingest_result = ingest_scenario(
                conn=None,  # unused; ingest_scenario routes through db.with_write_conn
                db=db,
                project=project,
                scenario=scenario,
                handler="sienna",
                system_path=system_path,
                simulation_paths=sim_files,
                scenario_root_uri=_scenario_root_uri(project, scenario),
                # dataset_filter omitted — ingest everything.
            )

            # Persist source artefacts to the configured data root
            # (local dir, NFS mount, S3, …) and rewrite the registry's
            # source_paths so a fresh process can rebuild transmission
            # geometry without depending on the temp_dir this upload
            # arrived in. The artefact copy is filesystem-only (no DB,
            # no lock); only the registry UPDATE goes through
            # with_write_conn.
            from gridsight.extensions.storage import commit_path

            schema = ingest_result["schema"]
            sys_uri = _scenario_artifact_uri(
                project,
                scenario,
                Path(system_path).name,
            )
            sim_uris: list[str] = []
            try:
                commit_path(system_path, sys_uri)
                for f in sim_files:
                    u = _scenario_artifact_uri(
                        project,
                        scenario,
                        Path(f).name,
                    )
                    commit_path(f, u)
                    sim_uris.append(u)
                source_paths_json = json.dumps(
                    {
                        "system_path": sys_uri,
                        "simulation_paths": sim_uris,
                    }
                )
                db.with_write_conn(
                    lambda c: c.execute(
                        "UPDATE _gat_registry.scenarios "
                        "SET source_paths = ? "
                        "WHERE schema_name = ?",
                        [source_paths_json, schema],
                    )
                )
                logger.info(
                    "Persisted scenario artefacts under %s",
                    _scenario_root_uri(project, scenario),
                )
            except Exception as e:
                logger.warning(
                    "Could not persist scenario artefacts for %s/%s: %s",
                    project,
                    scenario,
                    e,
                )

            logger.info("Successfully ingested scenario %s/%s", project, scenario)
            # Tier-2 background dispatch + M4 auto-ingest of other
            # models can now be safely re-enabled — see
            # _auto_ingest_other_models — because the per-call lock
            # window is milliseconds, no longer ~30s.
            return UploadResult(
                success=True,
                message=f"Scenario '{project}/{scenario}' created successfully.",
                project_name=project,
                scenario_name=scenario,
            )
        except Exception as e:
            logger.error("Ingestion failed for %s/%s: %s", project, scenario, e)
            return UploadResult(success=False, error=f"Ingestion failed: {e}")

    def _auto_ingest_other_models(
        self,
        project: str,
        scenario: str,
        system_path: str,
        sim_files: list[str],
        already_ingested: str,
    ) -> None:
        """After the default model finishes tier-2, kick off tier-1
        ingest jobs for every other optimization stage in the H5.

        Each non-default model gets only the tier-1 essentials so the
        background work isn't unbounded — the user can request tier-2
        for a specific non-default model later via the M3 ingest_model
        endpoint. Models that already have a registry row are skipped
        (re-upload safety).
        """
        try:
            from gat.server.ingest import list_available_models, _sanitize_identifier

            all_models = [
                _sanitize_identifier(m)
                for m in list_available_models("sienna", sim_files)
            ]
        except Exception as e:
            logger.warning("Could not enumerate models for auto-ingest: %s", e)
            return

        if not self._ensure_attached():
            return
        try:
            existing_rows = self._db.fetchall(
                "SELECT model FROM gat_db._gat_registry.scenarios "
                "WHERE project = ? AND scenario = ?",
                [project, scenario],
            )
            existing = {r[0] for r in existing_rows}
        except Exception:
            existing = {already_ingested}

        candidates = [
            m for m in all_models if m not in existing and m != already_ingested
        ]
        if not candidates:
            logger.info(
                "No additional models to auto-ingest for %s/%s",
                project,
                scenario,
            )
            return

        logger.info(
            "Auto-ingesting %d additional model(s) for %s/%s: %s",
            len(candidates),
            project,
            scenario,
            candidates,
        )
        # Dispatch sequentially in a single follow-up thread so they
        # don't all contend for the write lock at once. Each model's
        # tier-1 + tier-2 runs inside _dispatch_ingest, which already
        # serializes via self._lock — but kicking off N parallel
        # threads would just queue them on the lock anyway, so we
        # explicitly chain them here for clarity.
        import threading

        def _chain():
            for m in candidates:
                try:
                    self._dispatch_ingest(
                        project=project,
                        scenario=scenario,
                        system_path=system_path,
                        sim_files=sim_files,
                        model=m,
                        is_default=False,
                    )
                except Exception as e:
                    logger.error("Auto-ingest of model %s failed: %s", m, e)

        threading.Thread(
            target=_chain,
            name=f"gat-auto-ingest-{project}-{scenario}",
            daemon=True,
        ).start()

    def _dispatch_ingest(
        self,
        project: str,
        scenario: str,
        system_path: str,
        sim_files: list[str],
        model: str,
        is_default: bool,
    ) -> None:
        """Background thread: ingest ``model`` for (project, scenario)
        with the same tier-1/tier-2 split the upload handler uses.

        Reused for both the on-demand M3 lazy-ingest endpoint and the
        M4 auto-ingest of additional models. Source files are local
        (passed in by the caller after resolve_path).
        """
        import threading, shutil, tempfile

        # Stage source files independently of any caller-owned temp
        # directory — both M3 (resolve_path's cache dir) and M4
        # (handle_upload's temp_dir) can disappear before this thread
        # finishes.
        persist_dir = tempfile.mkdtemp(prefix=f"gat-ingest-{model}-")
        try:
            persist_sys = shutil.copy2(system_path, persist_dir)
            persist_sims = [shutil.copy2(f, persist_dir) for f in sim_files]
        except Exception as e:
            logger.error("Could not stage ingest source files: %s", e)
            shutil.rmtree(persist_dir, ignore_errors=True)
            return

        def _run():
            from gat.backends.duckdb_backend import GATDatabase
            from gat.server.ingest import ingest_scenario
            from gat.server.registry import ensure_registry

            try:
                with self._lock:
                    self._db.execute_silent("DETACH gat_db")
                    self._attached = False
                    db_path = _gat_db_path()
                    try:
                        write_db = GATDatabase(db_path)
                        write_conn = write_db.get_connection()
                        ensure_registry(write_conn)
                        try:
                            ingest_scenario(
                                conn=write_conn,
                                db=write_db,
                                project=project,
                                scenario=scenario,
                                handler="sienna",
                                system_path=persist_sys,
                                simulation_paths=persist_sims,
                                scenario_root_uri=_scenario_root_uri(project, scenario),
                                model=model,
                                is_default=is_default,
                                dataset_filter=_tier1_dataset_filter,
                            )
                        finally:
                            write_db.close()
                    finally:
                        self._ensure_attached()
                logger.info(
                    "Tier-1 ingest complete for %s/%s model=%s; dispatching tier-2",
                    project,
                    scenario,
                    model,
                )
                # Tier-2 runs as a separate thread so we exit this one.
                self._dispatch_tier2(
                    project=project,
                    scenario=scenario,
                    system_path=persist_sys,
                    sim_files=persist_sims,
                    model=model,
                )
            except Exception as e:
                logger.error(
                    "Background ingest failed for %s/%s model=%s: %s",
                    project,
                    scenario,
                    model,
                    e,
                )
                shutil.rmtree(persist_dir, ignore_errors=True)
                return
            # Note: persist_dir is cleaned up by _dispatch_tier2's
            # _run_tier2 (it copies the files again into its own
            # persist_dir). This caller's persist_dir leaks after
            # _dispatch_tier2 returns — clean it up there.

        threading.Thread(
            target=_run,
            name=f"gat-ingest-{project}-{scenario}-{model}",
            daemon=True,
        ).start()

    def _dispatch_tier2(
        self,
        project: str,
        scenario: str,
        system_path: str,
        sim_files: list[str],
        model: str | None,
    ) -> None:
        """Background thread that ingests the rest of the simulation
        datasets (Tier-2) for ``model`` after Tier-1 has returned ready.

        Uses the same detach-write-attach dance as the upload path so
        DuckDB doesn't reject the second writable handle. The source
        files (system_path + sim_files) are still on local disk because
        the upload handler's temp_dir survives until the upload-job
        thread tears it down — see app.py's `_run`.
        """
        import threading

        # The source files are inside the upload-job's temp_dir, which
        # gets cleaned up after handle_upload returns. The temp_dir
        # cleanup is triggered by app.py's _run, *not* by us — it
        # happens AFTER this method returns. So we have to make our own
        # local copies that survive the cleanup.
        import shutil, tempfile, os

        persist_dir = tempfile.mkdtemp(prefix="gat-tier2-")
        try:
            persist_sys = shutil.copy2(system_path, persist_dir)
            persist_sims = [shutil.copy2(f, persist_dir) for f in sim_files]
        except Exception as e:
            logger.error("Could not stage tier-2 source files: %s", e)
            shutil.rmtree(persist_dir, ignore_errors=True)
            return

        def _run_tier2():
            from gat.backends.duckdb_backend import GATDatabase
            from gat.server.ingest import ingest_scenario
            from gat.server.registry import ensure_registry

            try:
                import time as _t

                _t0 = _t.perf_counter()
                with self._lock:
                    self._db.execute_silent("DETACH gat_db")
                    self._attached = False
                    db_path = _gat_db_path()
                    try:
                        write_db = GATDatabase(db_path)
                        write_conn = write_db.get_connection()
                        ensure_registry(write_conn)
                        try:
                            # ``include_system=False`` skips re-running
                            # the cheap system-table writes (tier-1
                            # already did them and they're idempotent
                            # CREATE TABLE/VIEW anyway).
                            ingest_scenario(
                                conn=write_conn,
                                db=write_db,
                                project=project,
                                scenario=scenario,
                                handler="sienna",
                                system_path=persist_sys,
                                simulation_paths=persist_sims,
                                scenario_root_uri=_scenario_root_uri(project, scenario),
                                model=model,
                                dataset_filter=_tier2_dataset_filter,
                                include_system=False,
                            )
                        finally:
                            write_db.close()
                    finally:
                        self._ensure_attached()
                logger.info(
                    "Tier-2 ingest complete for %s/%s model=%s in %.1fs",
                    project,
                    scenario,
                    model,
                    _t.perf_counter() - _t0,
                )
                # M4: auto-ingest the H5's other optimization stages
                # (UC, RAUC, etc.) sequentially, tier-1 only, so the
                # model dropdown light up without the user clicking
                # "ingest UC". Skip models that are already in the
                # registry (e.g. on re-uploads).
                self._auto_ingest_other_models(
                    project=project,
                    scenario=scenario,
                    system_path=persist_sys,
                    sim_files=persist_sims,
                    already_ingested=model,
                )
            except Exception as e:
                logger.error(
                    "Tier-2 ingest failed for %s/%s model=%s: %s",
                    project,
                    scenario,
                    model,
                    e,
                )
            finally:
                shutil.rmtree(persist_dir, ignore_errors=True)

        threading.Thread(
            target=_run_tier2,
            name=f"gat-tier2-{project}-{scenario}",
            daemon=True,
        ).start()

    # ── Bus-geometry upload (post-ingest geo attach) ──

    def handle_preview(
        self,
        spec_name: str,
        file_paths: dict[str, list[str]],
        form_data: dict[str, str],
    ) -> PreviewResult:
        if spec_name != "bus_geometry":
            return PreviewResult(
                success=False, error=f"Preview not supported for spec '{spec_name}'."
            )
        files = file_paths.get("geo_file") or []
        if not files:
            return PreviewResult(success=False, error="No geo_file uploaded.")
        from gat.datahelpers.geo.bus_upload import inspect_geo_file

        # Project scope: pick any ready scenario's system file under the
        # project to validate the join. The persisted result is keyed on
        # ACBus name/number, so any system file in the project works.
        project = (form_data.get("project") or "").strip()
        system_path = (
            self._get_representative_system_for_project(project) if project else None
        )
        # Production stores ``s3://...`` URIs in the registry. Resolve
        # to a local cache file so ``inspect_geo_file`` can read bytes.
        if system_path:
            from gridsight.extensions.storage import is_s3_uri, resolve_path

            if is_s3_uri(system_path):
                system_path = str(resolve_path(system_path))
        try:
            data = inspect_geo_file(
                Path(files[0]),
                system_path=system_path,
                bus_id_column=(form_data.get("bus_id_column") or "").strip() or None,
                lat_column=(form_data.get("lat_column") or "").strip() or None,
                lon_column=(form_data.get("lon_column") or "").strip() or None,
                system_bus_id_column=(
                    form_data.get("system_bus_id_column") or ""
                ).strip()
                or None,
            )
            return PreviewResult(success=True, data=data)
        except Exception as e:  # noqa: BLE001
            logger.exception("bus_geometry preview failed")
            return PreviewResult(success=False, error=str(e))

    def _handle_bus_geometry_upload(
        self,
        file_paths: dict[str, list[str]],
        form_data: dict[str, str],
    ) -> UploadResult:
        from gat.datahelpers.geo.bus_upload import compute_bus_geometry

        files = file_paths.get("geo_file") or []
        if not files:
            return UploadResult(success=False, error="A bus-geometry file is required.")
        user_geo_path = Path(files[0])

        project = (form_data.get("project") or "").strip()
        if not project:
            return UploadResult(success=False, error="project is required.")
        system_path = self._get_representative_system_for_project(project)
        if not system_path:
            return UploadResult(
                success=False,
                error=(
                    f"No ready scenario found under project '{project}' to "
                    f"validate the join against. Create a scenario first, "
                    f"then attach bus geometry."
                ),
            )
        # Same s3:// → local resolve as the preview path.
        from gridsight.extensions.storage import is_s3_uri, resolve_path

        if is_s3_uri(system_path):
            system_path = str(resolve_path(system_path))

        bus_id_column = (form_data.get("bus_id_column") or "").strip()
        if not bus_id_column:
            return UploadResult(success=False, error="bus_id_column is required.")
        lat_column = (form_data.get("lat_column") or "").strip() or None
        lon_column = (form_data.get("lon_column") or "").strip() or None
        system_bus_id_column = (
            form_data.get("system_bus_id_column") or ""
        ).strip() or None

        try:
            result = compute_bus_geometry(
                system_path=system_path,
                user_geo_path=user_geo_path,
                bus_id_column=bus_id_column,
                lat_column=lat_column,
                lon_column=lon_column,
                system_bus_id_column=system_bus_id_column,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("bus_geometry compute failed")
            return UploadResult(success=False, error=f"Could not compute geometry: {e}")

        stats = result["stats"]
        bus_id_field = result.get("bus_id_field") or system_bus_id_column or "name"
        # Guardrail: refuse low-match commits so the user has a chance to
        # fix the column choice. Threshold is 50% of system buses; small
        # systems (≤10 buses) bypass the threshold to avoid false alarms.
        sysn = max(1, stats.get("system_bus_count", 1))
        if sysn >= 10 and stats["bus_count"] < 0.5 * sysn:
            return UploadResult(
                success=False,
                error=(
                    f"Only {stats['bus_count']} of {sysn} system buses matched — "
                    f"the bus-ID column may be wrong. Re-run preview with a "
                    f"different column, or remove the guardrail if the partial "
                    f"join is intentional."
                ),
            )

        # Persist project-scoped buses + metadata. Delegated to
        # gat.server.system_geo so any GAT entry point (CLI, scripts) can
        # produce the same artefacts.
        from gat.server import system_geo as system_geo_store

        try:
            system_geo_store.write_project_buses(
                _gat_data_root(),
                project,
                result["buses"],
                bus_id_field=bus_id_field,
                bus_id_column=bus_id_column,
                lat_column=lat_column,
                lon_column=lon_column,
                source_filename=user_geo_path.name,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("bus_geometry sidecar write failed")
            return UploadResult(
                success=False, error=f"Could not write project geo: {e}"
            )

        # Detach/reattach mirrors the catmap-write path; we need a writable
        # handle while the read-only `gat_db` attachment is in use.
        try:
            from gat.backends.duckdb_backend import GATDatabase
            from gat.server.registry import ensure_registry

            db_path = _gat_db_path()
            with self._lock:
                self._db.execute_silent("DETACH gat_db")
                self._attached = False
                try:
                    write_db = GATDatabase(db_path)
                    write_conn = write_db.get_connection()
                    ensure_registry(write_conn)
                    system_geo_store.register(
                        write_conn,
                        project=project,
                        bus_id_field=bus_id_field,
                        bus_id_column=bus_id_column,
                        lat_column=lat_column,
                        lon_column=lon_column,
                        source_filename=user_geo_path.name,
                        bus_count=stats["bus_count"],
                        unmatched_count=stats["unmatched_buses_input"],
                    )
                    write_db.close()
                finally:
                    self._ensure_attached()
        except Exception as e:  # noqa: BLE001
            logger.exception("bus_geometry registry upsert failed")
            return UploadResult(
                success=False,
                error=f"Geometry written but registry update failed: {e}",
            )

        msg = (
            f"Mapped {stats['bus_count']}/{stats['system_bus_count']} buses "
            f"by ACBus.{bus_id_field} for project '{project}'. "
            f"Unmatched: {stats['unmatched_buses_input']} input rows."
        )
        logger.debug("bus_geometry: %s", msg)
        return UploadResult(success=True, message=msg)

    # ── System inspection (handle_query) ──
    # Read-only diagnostic queries used by the SystemViewerDialog. Cache
    # the SiennaSystemParser per system_path so paginated row requests
    # don't re-parse the JSON each call. mtime-keyed so a system file
    # being replaced invalidates the cache automatically.

    def _system_parser(self, system_path: str):
        """Return a (possibly cached) SiennaSystemParser for system_path."""
        from gat.datahelpers.sienna import SiennaSystemParser

        cache = getattr(self, "_sienna_parser_cache", None)
        if cache is None:
            cache = {}
            self._sienna_parser_cache = cache
        try:
            mtime = Path(system_path).stat().st_mtime
        except OSError:
            mtime = 0
        cached = cache.get(system_path)
        if cached and cached[0] == mtime:
            return cached[1]
        parser = SiennaSystemParser(system_path)
        cache[system_path] = (mtime, parser)
        return parser

    def _resolve_system_path(self, params: dict) -> str | None:
        """Either an explicit system_path or (project, scenario) lookup."""
        sp = (params.get("system_path") or "").strip()
        if sp:
            return sp
        project = (params.get("project") or "").strip()
        scenario = (params.get("scenario") or "").strip()
        if not project or not scenario:
            return None
        return self._get_scenario_systems().get(f"{project}/{scenario}")

    def handle_query(self, kind: str, params: dict[str, Any]) -> Any:
        if kind == "system_components":
            # Return an empty, well-shaped response on any "no system here"
            # condition (no scenario picked, scenario isn't GAT, system file
            # gone). The UI shows a friendly empty state. Genuine errors
            # like a malformed JSON still raise.
            system_path = self._resolve_system_path(params)
            if not system_path or not Path(system_path).exists():
                return {
                    "system_path": system_path or "",
                    "components": [],
                    "available": False,
                }
            parser = self._system_parser(system_path)
            types = sorted(parser.list_components() or [])
            out = []
            for t in types:
                try:
                    df = parser.get_component(t)
                    cnt = int(len(df)) if df is not None else 0
                    cols = list(df.columns) if df is not None else []
                except Exception as e:  # noqa: BLE001
                    logger.debug("get_component(%s) failed: %s", t, e)
                    cnt = 0
                    cols = []
                out.append({"name": t, "count": cnt, "columns": cols})
            return {"system_path": system_path, "components": out, "available": True}

        if kind == "system_component_rows":
            system_path = self._resolve_system_path(params)
            empty = {"columns": [], "rows": [], "total": 0, "offset": 0, "limit": 0}
            if not system_path or not Path(system_path).exists():
                return empty
            component_type = (params.get("component_type") or "").strip()
            if not component_type:
                return empty
            limit = int(params.get("limit") or 100)
            offset = int(params.get("offset") or 0)
            limit = max(1, min(limit, 1000))  # clamp; UI doesn't need more
            offset = max(0, offset)
            parser = self._system_parser(system_path)
            df = parser.get_component(component_type)
            if df is None:
                return {
                    "columns": [],
                    "rows": [],
                    "total": 0,
                    "offset": offset,
                    "limit": limit,
                }
            total = int(len(df))
            page = df.iloc[offset : offset + limit]
            # JSON-safe: pandas → list[dict]. Coerce non-serializable values
            # (NaN, Timestamps, numpy types) via the records-to-json loop.
            try:
                records = json.loads(page.to_json(orient="records", date_format="iso"))
            except Exception:
                records = (
                    page.astype(object)
                    .where(page.notnull(), None)
                    .to_dict(orient="records")
                )
            return {
                "columns": list(df.columns),
                "rows": records,
                "total": total,
                "offset": offset,
                "limit": limit,
            }

        if kind == "set_default_model":
            # POST /api/extensions/gat/query/set_default_model
            # body: {project, scenario, model}
            #
            # Flip the registry's ``is_default`` to the requested model.
            # All gridsight-gat queries that don't specify a model
            # explicitly will then resolve to this one — that's how
            # the frontend's model dropdown switches the active view
            # without threading ``model`` through every API path.
            project = (params.get("project") or "").strip()
            scenario = (params.get("scenario") or "").strip()
            model = (params.get("model") or "").strip()
            if not project or not scenario or not model:
                return {"ok": False, "error": "project, scenario, model required"}
            with self._lock:
                self._db.execute_silent("DETACH gat_db")
                self._attached = False
                try:
                    import duckdb as _duckdb

                    write_conn = _duckdb.connect(_gat_db_path())
                    try:
                        # Verify the row exists before flipping.
                        existing = write_conn.execute(
                            "SELECT 1 FROM _gat_registry.scenarios "
                            "WHERE project = ? AND scenario = ? AND model = ?",
                            [project, scenario, model],
                        ).fetchone()
                        if not existing:
                            return {
                                "ok": False,
                                "error": "model not ingested for this scenario",
                            }
                        write_conn.execute(
                            "UPDATE _gat_registry.scenarios SET is_default = FALSE "
                            "WHERE project = ? AND scenario = ?",
                            [project, scenario],
                        )
                        write_conn.execute(
                            "UPDATE _gat_registry.scenarios SET is_default = TRUE "
                            "WHERE project = ? AND scenario = ? AND model = ?",
                            [project, scenario, model],
                        )
                    finally:
                        write_conn.close()
                finally:
                    self._ensure_attached()
            logger.info(
                "Default model set to %s for %s/%s",
                model,
                project,
                scenario,
            )
            return {
                "ok": True,
                "project": project,
                "scenario": scenario,
                "model": model,
            }

        if kind == "ingest_model":
            # POST /api/extensions/gat/query/ingest_model
            # body: {project, scenario, model}
            #
            # Ingest a non-default optimization stage from the H5 that
            # was previously uploaded for this (project, scenario).
            # The H5 sits in S3 — we resolve_path it into the local
            # cache and run the same tier-1-then-tier-2 pipeline that
            # the upload handler uses. Returns immediately with a
            # job_id; the registry row appears once tier-1 finishes.
            from gridsight.extensions.storage import resolve_path

            project = (params.get("project") or "").strip()
            scenario = (params.get("scenario") or "").strip()
            model = (params.get("model") or "").strip()
            if not project or not scenario or not model:
                return {"ok": False, "error": "project, scenario, model required"}
            if not self._ensure_attached():
                return {"ok": False, "error": "GAT database not attached"}
            try:
                row = self._db.fetchone(
                    "SELECT source_paths FROM gat_db._gat_registry.scenarios "
                    "WHERE project = ? AND scenario = ? LIMIT 1",
                    [project, scenario],
                )
            except Exception as e:
                return {"ok": False, "error": f"registry lookup: {e}"}
            if not row or not row[0]:
                return {"ok": False, "error": "no source_paths for scenario"}
            try:
                info = json.loads(row[0])
                sys_uri = info["system_path"]
                sim_uris = info["simulation_paths"]
            except Exception as e:
                return {"ok": False, "error": f"bad source_paths: {e}"}
            try:
                local_sys = str(resolve_path(sys_uri))
                local_sims = [str(resolve_path(u)) for u in sim_uris]
            except Exception as e:
                return {"ok": False, "error": f"resolve sources: {e}"}
            self._dispatch_ingest(
                project=project,
                scenario=scenario,
                system_path=local_sys,
                sim_files=local_sims,
                model=model,
                is_default=False,
            )
            return {
                "ok": True,
                "project": project,
                "scenario": scenario,
                "model": model,
            }

        if kind == "available_models":
            # Per-scenario list of ingested optimization stages, for the
            # M3 model-dropdown UI. Empty list if scenario unknown.
            project = (params.get("project") or "").strip()
            scenario = (params.get("scenario") or "").strip()
            if not project or not scenario or not self._ensure_attached():
                return {"models": []}
            try:
                rows = self._db.fetchall(
                    "SELECT model, status, is_default "
                    "FROM gat_db._gat_registry.scenarios "
                    "WHERE project = ? AND scenario = ? "
                    "ORDER BY is_default DESC, ingested_at ASC",
                    [project, scenario],
                )
            except Exception as e:
                logger.warning("available_models lookup failed: %s", e)
                return {"models": []}
            models = [
                {"model": r[0], "status": r[1], "is_default": bool(r[2])} for r in rows
            ]
            return {"models": models}

        raise NotImplementedError(f"Unknown query kind: {kind!r}")

    # Project-scoped bus geometry plumbs through `_get_bus_coords` directly
    # (see above). Layer rendering goes via `get_layer_geometry` →
    # `_build_generation_geojson` / `_build_branch_geojson`, both of which
    # consult `_get_bus_coords`. There's no value in also exposing the raw
    # buses as a GeometryDescriptor — we'd just be duplicating the same
    # data through a second pipeline.

    def _reattach_readonly(self) -> None:
        """Detach and reattach GAT DuckDB in READ_ONLY mode to see new data."""
        if self._attached:
            self._db.execute_silent("DETACH gat_db")
            self._attached = False
        self._ensure_attached()

    def delete_scenario(self, project: str, scenario: str) -> bool:
        """Drop the scenario's DuckDB schema and remove its registry row.

        Same detach/reattach dance as handle_upload — DuckDB rejects a
        second handle to the file while the read-only attachment is
        live, so we drop the RO attachment, open a writable handle to
        do the destructive work, then reattach RO.
        """
        from gat.backends.duckdb_backend import GATDatabase

        schema = self._resolve_schema(project, scenario)
        db_path = _gat_db_path()

        with self._lock:
            self._db.execute_silent("DETACH gat_db")
            self._attached = False

            deleted = False
            try:
                write_db = GATDatabase(db_path)
                write_conn = write_db.get_connection()
                try:
                    row = write_conn.execute(
                        "SELECT 1 FROM _gat_registry.scenarios "
                        "WHERE project = ? AND scenario = ?",
                        [project, scenario],
                    ).fetchone()
                    if row is not None:
                        write_conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                        write_conn.execute(
                            "DELETE FROM _gat_registry.scenarios "
                            "WHERE project = ? AND scenario = ?",
                            [project, scenario],
                        )
                        deleted = True
                finally:
                    write_db.close()
            finally:
                self._ensure_attached()

        if deleted:
            # Clean up the persisted source artefacts (system JSON +
            # HDF5s) under the configured data root. Failure here is
            # non-fatal — the DB-side delete already succeeded, and an
            # orphaned blob just wastes storage rather than breaking
            # the application.
            try:
                from gridsight.extensions.storage import delete_prefix

                root_uri = _scenario_root_uri(project, scenario)
                removed = delete_prefix(root_uri)
                if removed:
                    logger.info(
                        "Cleared %d artefact(s) under %s",
                        removed,
                        root_uri,
                    )
            except Exception as e:
                logger.warning(
                    "Could not clear artefact root for %s/%s: %s",
                    project,
                    scenario,
                    e,
                )
            logger.info(
                "Deleted GAT scenario %s/%s (schema %s)", project, scenario, schema
            )
        return deleted

    # ── Helpers ────────────────────────────────────────────────────────────

    def _with_write_conn(self, fn):
        """Briefly open a writable handle to the GAT database file, run
        ``fn(conn)`` against it, then close it. The shared read-side
        attachment is detached for the duration of ``fn`` and
        reattached on the way out.

        Each call holds ``self._lock`` for only the duration of ``fn``
        — so for a "register N views" or "write small native table"
        block that's milliseconds. The slow parquet writes that
        dominate Sienna ingest happen between these calls, lock-free.

        Wired into ``GATDatabase.set_write_provider`` so server-side
        ingest code can transparently use this without knowing about
        the extension's locking model.
        """
        from gat.backends.duckdb_backend import GATDatabase

        db_path = _gat_db_path()
        with self._lock:
            self._db.execute_silent("DETACH gat_db")
            self._attached = False
            try:
                wdb = GATDatabase(db_path)
                try:
                    return fn(wdb.get_connection())
                finally:
                    wdb.close()
            finally:
                self._ensure_attached()

    def _ensure_attached(self) -> bool:
        """Attach GAT's DuckDB file if not already attached. Returns True if available."""
        if self._attached:
            return True
        db_path = _gat_db_path()
        if not Path(db_path).exists():
            logger.warning("GAT database not found at %s", db_path)
            return False
        try:
            self._db.execute(f"ATTACH '{db_path}' AS gat_db (READ_ONLY)")
            self._attached = True
            logger.info("Attached GAT database from %s", db_path)
            # The attached gat_db contains views that reference s3:// URIs
            # (per-scenario parquet files in SeaweedFS). DuckDB httpfs
            # settings are per-connection, so the shared gridsight
            # connection that gat_db is attached to needs them too —
            # otherwise SELECT against a view fails with the stock
            # "see s3api.html" message. Re-configure on every attach
            # so credential rotations get picked up.
            from gat.backends.duckdb_backend import configure_httpfs

            with self._db.transaction() as conn:
                configure_httpfs(conn)
            return True
        except Exception as e:
            # Already attached or other error
            if "already" in str(e).lower():
                self._attached = True
                return True
            logger.error("Failed to attach GAT database: %s", e)
            return False

    def _list_registry_scenarios(self) -> list[dict]:
        """Query the GAT registry for available scenarios."""
        if not self._ensure_attached():
            return []
        try:
            rows = self._db.fetchall(
                "SELECT project, scenario, handler, schema_name, status "
                "FROM gat_db._gat_registry.scenarios "
                "WHERE status = 'ready'"
            )
            return [
                {
                    "project": r[0],
                    "scenario": r[1],
                    "handler": r[2],
                    "schema_name": r[3],
                    "status": r[4],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Failed to query GAT registry: %s", e)
            return []

    def _get_schema_tables(self, schema: str) -> list[str]:
        """List table names in a GAT schema.

        A single DuckDB connection can't run queries concurrently — calling
        these helpers from one method while another method already has a
        query pending on the same connection raises
        "Attempting to execute an unsuccessful or closed pending query
        result". The lock is reentrant so callers that already hold it
        (e.g. streaming partitions) won't deadlock.
        """
        try:
            rows = self._db.fetchall(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'gat_db' AND table_schema = ?",
                [schema],
            )
            return [r[0] for r in rows]
        except Exception as e:
            logger.error("Failed to list tables in schema %s: %s", schema, e)
            return []

    def _get_columns(self, schema: str, table: str) -> list[str]:
        """Get column names for a table. See `_get_schema_tables` for locking."""
        try:
            rows = self._db.fetchall(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_catalog = 'gat_db' AND table_schema = ? "
                "AND table_name = ? ORDER BY ordinal_position",
                [schema, table],
            )
            return [r[0] for r in rows]
        except Exception:
            return []

    # ── Discovery ──────────────────────────────────────────────────────────

    def list_projects(self) -> list[ExtensionProject]:
        scenarios = self._list_registry_scenarios()
        projects: dict[str, ExtensionProject] = {}
        for s in scenarios:
            name = s["project"]
            if name not in projects:
                projects[name] = ExtensionProject(
                    name=name,
                    display_name=name.replace("_", " ").replace("-", " ").title(),
                    description=f"Power system project: {name}",
                    tags=["power-systems", s["handler"]],
                )
        return list(projects.values())

    def list_scenarios(self, project: str) -> list[ExtensionScenario]:
        scenarios = self._list_registry_scenarios()
        return [
            ExtensionScenario(
                name=s["scenario"],
                display_name=s["scenario"].replace("_", " ").replace("-", " ").title(),
                project_name=project,
                description=f"{s['handler'].title()} simulation: {s['scenario']}",
                tags=[s["handler"]],
            )
            for s in scenarios
            if s["project"] == project
        ]

    # ── Layers ──────────────────────────────────────────────────────────────

    def list_layers(
        self, project: str | None = None, scenario: str | None = None
    ) -> list[LayerDefinition]:
        if not project or not scenario:
            return []
        schema = self._resolve_schema(project, scenario)
        tables = self._get_schema_tables(schema)
        # Layer names are namespaced by schema so distinct
        # (project, scenario, model) combos don't collide on the wire
        # when the frontend has multiple scenarios loaded.
        prefix = schema
        layers: list[LayerDefinition] = []
        display_group_colors: dict[str, list[int]] = {}

        # Renewable GeneratorLayer — dual-radius (generation + availability)
        if "generation" in tables and "availability" in tables:
            if not display_group_colors:
                display_group_colors = self._get_display_group_colors(schema, tables)
            layers.append(
                LayerDefinition(
                    name=f"{prefix}__renewable",
                    display_name=f"Renewable Generation ({scenario})",
                    deck_layer_type="GeneratorLayer",
                    geom_join_key="name",
                    dataset_ref=f"{prefix}__generation",
                    data_join_key="entity_id",
                    dataset_refs=[
                        {
                            "ref": f"{prefix}__availability",
                            "join_key": "entity_id",
                            "role": "availability",
                        }
                    ],
                    style_mappings=[
                        {
                            "visual_property": "getRadius",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                            "dataset_role": "primary",
                        },
                        {
                            "visual_property": "getOuterRadius",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                            "dataset_role": "availability",
                        },
                    ],
                    default_style={
                        "geoMappings": {
                            "getFillColor": {
                                "property": "display_group",
                                "scale_type": "categorical",
                                "categoryColors": display_group_colors,
                            },
                        },
                        # Use nameplate (static, MW) as outer radius. Curtailment
                        # is rendered as a grey band between gen and nameplate
                        # when the user toggles the "X" chip in the layers panel
                        # — interpretation is "wasted nameplate capacity" until
                        # the availability dataset drives the outer radius too.
                        "capacityProperty": "nameplate_mw",
                        # Pixel units render at a fixed on-screen size regardless
                        # of zoom — far better default for GW-scale generators
                        # than meters, where a 100 MW dot can be sub-pixel zoomed
                        # out and a 1 GW dot blows past the visible region zoomed
                        # in. With pixels, scale ≈ 0.05 puts a 100 MW dot at ~5 px.
                        "radiusUnits": "pixels",
                        "radiusScale": 0.05,
                        # `radiusMinPixels` is intentionally absent — the layer
                        # factory derives a sensible default from the active
                        # gen/cap/curt visibility (gen-only: 0, cap-only: 1,
                        # else 0). Setting it here would freeze that default and
                        # block the smart fallback.
                        "generationVisible": True,
                        "capacityVisible": False,
                        "curtailmentVisible": False,
                        # Renewable generators curtail (oversupply, transmission
                        # limits, must-take constraints). The "X" chip in the
                        # layer panel is gated on this flag so layers like
                        # thermal — where curtailment isn't meaningful in the
                        # dispatch sense — don't show it.
                        "curtailmentApplicable": True,
                        # UI grouping: render alongside the thermal layer as
                        # one "Generation" row in the layer panel. The styler
                        # broadcasts to both, the panel adds T/R sub-toggles
                        # for hiding one tech family at a time. Per-scenario
                        # key so two scenarios don't accidentally merge.
                        "group_key": f"{prefix}__generation",
                        "group_display_name": f"Generation ({scenario})",
                        "group_role": "renewable",
                        "group_role_label": "R",
                    },
                )
            )

        # Thermal GeneratorLayer — generation timeseries + static nameplate.
        # Filtered to ThermalStandard entities only.
        if "generation" in tables and "sys__ThermalStandard" in tables:
            if not display_group_colors:
                display_group_colors = self._get_display_group_colors(schema, tables)
            layers.append(
                LayerDefinition(
                    name=f"{prefix}__thermal",
                    display_name=f"Thermal Generation ({scenario})",
                    deck_layer_type="GeneratorLayer",
                    geom_join_key="name",
                    dataset_ref=f"{prefix}__generation",
                    data_join_key="entity_id",
                    style_mappings=[
                        {
                            "visual_property": "getRadius",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                            "dataset_role": "primary",
                        },
                    ],
                    default_style={
                        "geoMappings": {
                            "getFillColor": {
                                "property": "display_group",
                                "scale_type": "categorical",
                                "categoryColors": display_group_colors,
                            },
                        },
                        "capacityProperty": "nameplate_mw",
                        # See renewable layer comment above for unit/scale rationale.
                        "radiusUnits": "pixels",
                        "radiusScale": 0.05,
                        "generationVisible": True,
                        "capacityVisible": False,
                        # UI grouping — see renewable layer for context. Same
                        # key per scenario means thermal + renewable collapse
                        # into one "Generation" row.
                        "group_key": f"{prefix}__generation",
                        "group_display_name": f"Generation ({scenario})",
                        "group_role": "thermal",
                        "group_role_label": "T",
                    },
                )
            )

        if "line_flow" in tables:
            layers.append(
                LayerDefinition(
                    name=f"{prefix}__transmission",
                    display_name=f"Transmission Lines ({scenario})",
                    deck_layer_type="TransmissionLayer",
                    geom_join_key="name",
                    dataset_ref=f"{prefix}__line_flow",
                    data_join_key="entity_id",
                    style_mappings=[
                        {
                            "visual_property": "getColor",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                        },
                        {
                            "visual_property": "getLineWidth",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                        },
                    ],
                    default_style={
                        "capacityProperty": "capacity",
                        "lineWidthMinPixels": 0.5,
                        "lineWidthMaxPixels": 14,
                    },
                )
            )

            layers.append(
                LayerDefinition(
                    name=f"{prefix}__transformers",
                    display_name=f"Transformers ({scenario})",
                    deck_layer_type="ScatterplotLayer",
                    geom_join_key="name",
                    dataset_ref=f"{prefix}__line_flow",
                    data_join_key="entity_id",
                    style_mappings=[
                        {
                            "visual_property": "getFillColor",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                            "colormap": "loading",
                            "domain_min": 0,
                            "domain_max": 500,
                        },
                        {
                            "visual_property": "getRadius",
                            "column": "__timeseries__",
                            "scale_type": "linear",
                            "domain_min": 0,
                            "domain_max": 500,
                        },
                    ],
                    default_style={
                        "radiusMinPixels": 2,
                        "radiusMaxPixels": 12,
                        "radiusScale": 1,
                        "radiusUnits": "pixels",
                        "default_visible": False,
                    },
                )
            )

        return layers

    def get_layer_geometry(self, layer_name: str) -> bytes:
        """Build GeoJSON for a layer lazily.

        For the generation layer: reads bus coordinates from the Sienna system
        JSON (supplemental_attribute_manager), maps generators to buses, and
        includes fuel category as a feature property.
        For the transmission layer: builds LineString features from Arc topology
        (bus-to-bus) with capacity as a property.
        """
        logger.debug("[get_layer_geometry] called with layer_name=%s", layer_name)
        # Layer names are emitted by ``list_layers`` as
        # ``{schema}__{layer_type}`` where schema is the M2a
        # ``{project}__{scenario}__{model}``. So a 4-part split:
        #   parts[0]=project, parts[1]=scenario, parts[2]=model, parts[3]=type.
        parts = layer_name.split("__")
        if len(parts) < 4:
            logger.error(
                "[get_layer_geometry] cannot parse layer_name into project/scenario/model/type: %s",
                layer_name,
            )
            raise NotImplementedError(f"Unknown layer: {layer_name}")
        project, scenario, model, layer_type = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)
        logger.debug(
            "[get_layer_geometry] project=%s scenario=%s model=%s type=%s schema=%s",
            project,
            scenario,
            model,
            layer_type,
            schema,
        )

        with self._lock:
            # Ensure gat_db is attached before any catalog-qualified queries
            # run. Upload / delete / reattach paths DETACH gat_db transiently
            # under this same lock, so the check has to sit inside the lock
            # too — otherwise a geometry fetch arriving mid-detach errors with
            #   Binder Error: Catalog "gat_db" does not exist!
            if not self._ensure_attached():
                raise RuntimeError("GAT database is not attached")
            if layer_type == "renewable":
                return self._build_generation_geojson(
                    schema, entity_table="availability"
                )
            if layer_type == "thermal":
                return self._build_generation_geojson(
                    schema, entity_table="sys__ThermalStandard", entity_column="name"
                )
            if layer_type == "transmission":
                return self._build_branch_geojson(schema, "lines")
            if layer_type == "transformers":
                return self._build_branch_geojson(schema, "transformers")
        logger.error("[get_layer_geometry] unknown layer type: %s", layer_type)
        raise NotImplementedError(f"Unknown layer type: {layer_type}")

    def _get_display_group_colors(
        self, schema: str, tables: list[str]
    ) -> dict[str, list[int]]:
        """Compute display_group → [r,g,b,a] color mapping from catmap data at runtime.

        Builds display groups from catmap__prime_mover + catmap__fuel using
        GAT's sienna_standard_map, then looks up colors from the standard palette.
        Returns RGBA arrays for deck.gl compatibility.
        """
        pm_map: dict[str, str] = {}
        fuel_map: dict[str, str] = {}
        if "catmap__prime_mover" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT entity_id, category FROM gat_db.{schema}.catmap__prime_mover"
                )
                pm_map = {r[0]: r[1] for r in rows}
            except Exception:
                pass
        if "catmap__fuel" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT entity_id, category FROM gat_db.{schema}.catmap__fuel"
                )
                fuel_map = {r[0]: r[1] for r in rows}
            except Exception:
                pass

        # Compute all display groups that will appear
        display_groups: set[str] = set()
        for eid, pm in pm_map.items():
            fl = fuel_map.get(eid, "")
            display_groups.add(_resolve_display_group(pm, fl))

        # Look up colors from the standard palette, convert to RGBA for deck.gl
        colors: dict[str, list[int]] = {}
        for dg in sorted(display_groups):
            hex_color = _lookup_color(dg) or "#888888"
            colors[dg] = _hex_to_rgba(hex_color)

        logger.debug("[display_colors] %d display groups with colors", len(colors))
        return colors

    def _ensure_catmap_display_group(self, schema: str, prefix: str) -> bool:
        """Lazily materialize a catmap__display_group table for a scenario.

        Reads catmap__prime_mover (and optionally catmap__fuel), computes the
        per-entity display group via _resolve_display_group, and persists it
        as catmap__display_group. Also ensures the corresponding ext_gat view
        exists so chart SQL can join it directly. Idempotent.

        Writes via a temporary read-write reattachment of gat_db, since
        DuckDB's process-level file lock prevents opening a second connection
        to the same file.

        IMPORTANT: callers must hold self._lock — this method may detach/reattach
        gat_db, which would race with any concurrent query against the database.
        """
        view_sql = (
            f"CREATE OR REPLACE VIEW ext_gat.{prefix}__catmap__display_group "
            f"AS SELECT * FROM gat_db.{schema}.catmap__display_group"
        )

        # Cheap path: if the table is already present in gat_db, just ensure
        # the ext_gat view points at it. No reattach needed.
        tables = self._get_schema_tables(schema)
        if "catmap__display_group" in tables:
            try:
                self._db.execute(view_sql)
            except Exception:
                pass
            return True

        if "catmap__prime_mover" not in tables:
            logger.warning(
                "[catmap_dg] cannot materialize for %s: catmap__prime_mover missing",
                schema,
            )
            return False

        # Source rows from existing catmaps
        pm_map: dict[str, str] = {}
        fuel_map: dict[str, str] = {}
        try:
            rows = self._db.fetchall(
                f"SELECT entity_id, category FROM gat_db.{schema}.catmap__prime_mover"
            )
            pm_map = {r[0]: r[1] for r in rows}
        except Exception as e:
            logger.warning("[catmap_dg] read catmap__prime_mover failed: %s", e)
            return False
        if "catmap__fuel" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT entity_id, category FROM gat_db.{schema}.catmap__fuel"
                )
                fuel_map = {r[0]: r[1] for r in rows}
            except Exception:
                pass

        entries = [
            (eid, _resolve_display_group(pm, fuel_map.get(eid, "")))
            for eid, pm in pm_map.items()
        ]
        if not entries:
            logger.warning("[catmap_dg] no entries to materialize for %s", schema)
            return False

        # Write by temporarily reattaching gat_db read-write on the same
        # connection. DuckDB rejects opening a second connection to a file
        # already attached in the same process, so we can't use a separate
        # GATDatabase() handle.
        db_path = _gat_db_path()
        try:
            import pandas as pd

            df = pd.DataFrame(entries, columns=["entity_id", "category"])
            # Detach the read-only attachment, reattach read-write, do the
            # write, then restore the read-only attachment in the finally block.
            with self._db.transaction() as conn:
                try:
                    conn.execute("DETACH gat_db")
                except Exception:
                    pass
                self._attached = False
                try:
                    conn.execute(f"ATTACH '{db_path}' AS gat_db")
                    conn.execute(
                        f"CREATE OR REPLACE TABLE gat_db.{schema}.catmap__display_group "
                        f"AS SELECT * FROM df"
                    )
                    logger.debug(
                        "[catmap_dg] materialized catmap__display_group: %d rows in %s",
                        len(entries),
                        schema,
                    )
                finally:
                    # Always restore the read-only attachment, even on failure.
                    try:
                        conn.execute("DETACH gat_db")
                    except Exception:
                        pass
                    self._attached = False
                    self._ensure_attached()
        except Exception as e:
            logger.warning("[catmap_dg] write failed for %s: %s", schema, e)
            return False

        # Create the ext_gat view so chart SQL can reference it
        try:
            self._db.execute(view_sql)
        except Exception as e:
            logger.warning("[catmap_dg] failed to create ext_gat view: %s", e)

        return True

    def _get_bus_coords(self, schema: str) -> dict[str, tuple[float, float]]:
        """Get bus UUID → (lon, lat) mapping for layer rendering.

        Priority order:
          1. **Project-scoped external geo** (`bus_geometry` upload) —
             explicit user input wins over whatever was embedded in the
             system JSON. UUIDs are resolved per-scenario from
             `sys__ACBus` since they're not stable across system files.
          2. `bus_coordinates` DuckDB table (populated during GAT ingest
             from Sienna's supplemental_attribute_manager).
          3. `sys__ACBus.latitude`/`longitude` (older ingestion path).
          4. Live read of the system JSON's supplemental_attribute_manager.
        """
        # 1. Project-scoped external geo. The store keys coords by
        # ACBus.name or .number; we resolve to UUID via the scenario's
        # sys__ACBus table so coords drop in next to the existing
        # bus_coordinates path without changing downstream callers.
        from gat.server import system_geo as system_geo_store

        project = self._project_for_schema(schema)
        if project:
            loaded = system_geo_store.load_project_bus_coords(_gat_data_root(), project)
            if loaded:
                coords_by_id, bus_id_field = loaded
                # Defensive — only the safe ACBus columns we know are well-typed.
                if bus_id_field in ("name", "number"):
                    try:
                        rows = self._db.fetchall(
                            f"SELECT UUID, {bus_id_field} FROM gat_db.{schema}.sys__ACBus"
                        )
                        uuid_map: dict[str, tuple[float, float]] = {}
                        for uuid, val in rows:
                            if uuid is None or val is None:
                                continue
                            c = coords_by_id.get(str(val).strip())
                            if c:
                                uuid_map[uuid] = c
                        if uuid_map:
                            logger.debug(
                                "[bus_coords] %d bus coords from project '%s' geo (key=%s)",
                                len(uuid_map),
                                project,
                                bus_id_field,
                            )
                            return uuid_map
                    except Exception as e:
                        logger.warning(
                            "[bus_coords] project-geo UUID resolution failed for %s/%s: %s",
                            project,
                            schema,
                            e,
                        )

        tables = self._get_schema_tables(schema)

        if "bus_coordinates" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT UUID, latitude, longitude FROM gat_db.{schema}.bus_coordinates "
                    f"WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
                )
                coords = {r[0]: (float(r[2]), float(r[1])) for r in rows}
                logger.debug(
                    "[bus_coords] %d bus coords from bus_coordinates table", len(coords)
                )
                return coords
            except Exception as e:
                logger.error("[bus_coords] Failed to query bus_coordinates: %s", e)

        # Fallback: check if sys__ACBus has lat/lon columns (older ingestion)
        if "sys__ACBus" in tables:
            cols = self._get_columns(schema, "sys__ACBus")
            if "latitude" in cols and "longitude" in cols:
                try:
                    rows = self._db.fetchall(
                        f"SELECT UUID, latitude, longitude FROM gat_db.{schema}.sys__ACBus "
                        f"WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
                    )
                    coords = {r[0]: (float(r[2]), float(r[1])) for r in rows}
                    logger.debug(
                        "[bus_coords] %d bus coords from sys__ACBus (fallback)",
                        len(coords),
                    )
                    return coords
                except Exception as e:
                    logger.error("[bus_coords] Failed to query sys__ACBus: %s", e)

        # Fallback: extract coords from system JSON via source_paths or data directory scan
        coords = self._extract_coords_from_system_json(schema)
        if coords:
            return coords

        logger.warning(
            "[bus_coords] No bus coordinates available for schema %s. "
            "Re-ingest the scenario with the latest GAT version to add coordinates.",
            schema,
        )
        return {}

    def _extract_coords_from_system_json(
        self, schema: str
    ) -> dict[str, tuple[float, float]]:
        """Extract bus UUID → (lon, lat) by reading the Sienna system JSON directly."""
        system_path = self._find_system_json(schema)
        if not system_path:
            return {}

        try:
            with open(system_path) as f:
                system_data = json.load(f)
        except Exception as e:
            logger.error(
                "[bus_coords] Failed to read system JSON %s: %s", system_path, e
            )
            return {}

        sup_mgr = system_data.get("data", {}).get("supplemental_attribute_manager", {})
        attributes = sup_mgr.get("attributes", [])
        associations = sup_mgr.get("associations", [])

        # attribute_uuid → (lon, lat)
        attr_geo: dict[str, tuple[float, float]] = {}
        for attr in attributes:
            geo = attr.get("geo_json")
            if not geo:
                continue
            uuid_val = attr.get("internal", {}).get("uuid", {}).get("value")
            if uuid_val and "Latitude" in geo and "Longitude" in geo:
                attr_geo[uuid_val] = (float(geo["Longitude"]), float(geo["Latitude"]))

        # attribute_uuid → component_uuid
        attr_to_comp: dict[str, str] = {}
        for assoc in associations:
            attr_to_comp[assoc.get("attribute_uuid", "")] = assoc.get(
                "component_uuid", ""
            )

        # component_uuid → (lon, lat)
        comp_coords: dict[str, tuple[float, float]] = {}
        for attr_uuid, coords in attr_geo.items():
            comp_uuid = attr_to_comp.get(attr_uuid)
            if comp_uuid:
                comp_coords[comp_uuid] = coords

        # Map bus UUIDs to coords
        bus_coords: dict[str, tuple[float, float]] = {}
        try:
            bus_rows = self._db.fetchall(
                f"SELECT name, UUID FROM gat_db.{schema}.sys__ACBus"
            )
            for name, uuid_val in bus_rows:
                if uuid_val in comp_coords:
                    bus_coords[uuid_val] = comp_coords[uuid_val]
        except Exception as e:
            logger.error("[bus_coords] Failed to query sys__ACBus UUIDs: %s", e)
            return {}

        logger.debug(
            "[bus_coords] Extracted %d bus coords from system JSON %s",
            len(bus_coords),
            system_path,
        )
        return bus_coords

    def _get_base_power(self, schema: str) -> float:
        """Get the simulation base_power (MW) for per-unit → MW conversion.

        Reads from the H5 file's simulation attributes. Falls back to 100 MW
        (the Sienna/PowerSimulations.jl default).
        """
        # Find simulation H5 path from registry
        try:
            row = self._db.fetchone(
                "SELECT source_paths FROM gat_db._gat_registry.scenarios "
                "WHERE schema_name = ?",
                [schema],
            )
            if row and row[0]:
                source_info = json.loads(row[0])
                sim_paths = source_info.get("simulation_paths", [])
                if isinstance(sim_paths, str):
                    sim_paths = [sim_paths]
                for sp in sim_paths or []:
                    if Path(sp).exists():
                        try:
                            import h5py

                            with h5py.File(sp, "r") as f:
                                # Check decision models for base_power attribute
                                dm = f.get("simulation/decision_models", {})
                                for model_name in dm:
                                    bp = dm[model_name].attrs.get("base_power")
                                    if bp is not None:
                                        logger.debug(
                                            "[base_power] %.0f MW from %s/%s",
                                            float(bp),
                                            sp,
                                            model_name,
                                        )
                                        return float(bp)
                        except Exception as e:
                            logger.warning(
                                "[base_power] failed to read H5 %s: %s", sp, e
                            )
        except Exception:
            pass

        logger.debug("[base_power] using default 100 MW")
        return 100.0

    def _find_system_json(self, schema: str) -> str | None:
        """Locate the Sienna system JSON file for a schema."""
        # Try source_paths from registry. The URI is whatever
        # `commit_path` wrote during handle_upload — local path or
        # s3:// — and `resolve_path` returns a usable local Path
        # either way (downloading + gunzipping for S3, no-op for a
        # local path).
        try:
            row = self._db.fetchone(
                "SELECT source_paths FROM gat_db._gat_registry.scenarios "
                "WHERE schema_name = ?",
                [schema],
            )
            if row and row[0]:
                source_info = json.loads(row[0])
                sp = source_info.get("system_path")
                if sp:
                    from gridsight.extensions.storage import resolve_path

                    try:
                        local = resolve_path(sp, persist_on_exit=False)
                        if local.exists():
                            logger.debug(
                                "[bus_coords] Resolved system JSON: %s → %s",
                                sp,
                                local,
                            )
                            return str(local)
                    except Exception as e:
                        logger.warning(
                            "[bus_coords] Could not resolve system JSON %s: %s",
                            sp,
                            e,
                        )
        except Exception:
            pass

        # Try common GAT data directories
        # Schema format: Project__scenario → look for Project/sys.json
        parts = schema.split("__", 1)
        project = parts[0] if parts else schema

        search_dirs = [
            Path(os.environ.get("GAT_DATA_PATH", "")) / project,
            Path.home() / ".gat" / "data" / project,
            Path.home() / "code" / "GAT" / "data" / project,
        ]
        for d in search_dirs:
            for name in ("sys.json", "system.json"):
                candidate = d / name
                if candidate.exists():
                    logger.debug("[bus_coords] Found system JSON at %s", candidate)
                    return str(candidate)

        logger.warning("[bus_coords] Could not find system JSON for schema %s", schema)
        return None

    def _build_generation_geojson(
        self,
        schema: str,
        entity_table: str = "generation",
        entity_column: str = "entity_id",
    ) -> bytes:
        """Build Point GeoJSON with one feature per generator at its bus coordinates.

        Args:
            schema: DuckDB schema name.
            entity_table: Table to source entity IDs from. Composed tables
                (generation, availability) use entity_column="entity_id".
                System tables (sys__ThermalStandard, etc.) use "name".
            entity_column: Column holding the entity identifier in entity_table.
        """
        # bus_coords is keyed by bus UUID (not name)
        bus_coords = self._get_bus_coords(schema)
        logger.debug(
            "[gen_geojson] %d bus coords available (keyed by UUID)", len(bus_coords)
        )

        # Entity IDs from the specified table/column
        gen_rows = self._db.fetchall(
            f"SELECT {entity_column} FROM gat_db.{schema}.{entity_table}"
        )
        gen_ids = {r[0] for r in gen_rows}
        logger.debug(
            "[gen_geojson] %d entity IDs from %s.%s",
            len(gen_ids),
            entity_table,
            entity_column,
        )

        # Canonical generator ratings (MW), persisted by gat.scenario.ingest()
        # via SiennaSystem.get_generator_ratings(). Single source of truth for
        # per-generator capacity — no per-extension nameplate computation.
        generator_ratings: dict[str, float] = {}
        schema_tables = self._get_schema_tables(schema)
        if "generator_ratings" in schema_tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT name, rating_mw FROM gat_db.{schema}.generator_ratings"
                )
                generator_ratings = {
                    str(r[0]): float(r[1]) for r in rows if r[1] is not None
                }
                logger.debug(
                    "[gen_geojson] loaded %d generator ratings", len(generator_ratings)
                )
            except Exception as e:
                logger.warning("[gen_geojson] could not load generator_ratings: %s", e)

        # Entity → bus mapping from system component tables
        entity_bus: dict[str, str] = {}
        entity_props: dict[str, dict] = {}
        tables = self._get_schema_tables(schema)

        sys_tables = (
            ["sys__generators"]
            if "sys__generators" in tables
            else [
                t
                for t in tables
                if t.startswith("sys__")
                and t not in ("sys__ACBus", "sys__Arc", "sys__Area")
            ]
        )
        logger.debug("[gen_geojson] sys_tables to scan for bus mapping: %s", sys_tables)

        for sys_table in sys_tables:
            cols = self._get_columns(schema, sys_table)
            if "name" not in cols:
                logger.debug("[gen_geojson] %s: no 'name' column, skipping", sys_table)
                continue
            bus_col = None
            for candidate in ("bus", "bus.name"):
                if candidate in cols:
                    bus_col = candidate
                    break
            if not bus_col:
                logger.debug(
                    "[gen_geojson] %s: no bus column (cols=%s), skipping",
                    sys_table,
                    cols[:8],
                )
                continue

            rows = self._db.fetchall(f"SELECT * FROM gat_db.{schema}.{sys_table}")
            matched = 0
            for row in rows:
                props = dict(zip(cols, row))
                name = props.get("name", "")
                if name not in gen_ids:
                    continue
                entity_bus[name] = str(props.get(bus_col, ""))
                entity_props[name] = {k: _json_safe(v) for k, v in props.items()}
                matched += 1
            logger.debug(
                "[gen_geojson] %s: %d rows, %d matched gen_ids, bus_col=%s",
                sys_table,
                len(rows),
                matched,
                bus_col,
            )

        # Build entity → display_group from catmap__prime_mover + catmap__fuel
        entity_pm: dict[str, str] = {}
        entity_fuel: dict[str, str] = {}
        if "catmap__prime_mover" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT entity_id, category FROM gat_db.{schema}.catmap__prime_mover"
                )
                for eid, cat in rows:
                    if eid in gen_ids:
                        entity_pm[eid] = cat
            except Exception:
                pass
        if "catmap__fuel" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT entity_id, category FROM gat_db.{schema}.catmap__fuel"
                )
                for eid, cat in rows:
                    if eid in gen_ids:
                        entity_fuel[eid] = cat
            except Exception:
                pass

        entity_dg: dict[str, str] = {}
        for eid in gen_ids:
            pm = entity_pm.get(eid, "")
            fl = entity_fuel.get(eid, "")
            entity_dg[eid] = _resolve_display_group(pm, fl)
        logger.debug(
            "[gen_geojson] %d display_group mappings from pm+fuel", len(entity_dg)
        )

        logger.debug(
            "[gen_geojson] entity_bus: %d, entity_dg: %d",
            len(entity_bus),
            len(entity_dg),
        )
        if entity_bus:
            sample_name = next(iter(entity_bus))
            sample_bus = entity_bus[sample_name]
            logger.debug(
                "[gen_geojson] sample: gen=%s -> bus=%s -> coords=%s, dg=%s",
                sample_name,
                sample_bus,
                bus_coords.get(sample_bus),
                entity_dg.get(sample_name),
            )

        # Count why generators might be missing
        no_bus_mapping = 0
        no_coords = 0

        # Build features
        features = []
        for gen_id in sorted(gen_ids):
            bus_uuid = entity_bus.get(gen_id)
            if not bus_uuid:
                no_bus_mapping += 1
                continue
            coords = bus_coords.get(bus_uuid)
            if not coords:
                no_coords += 1
                continue
            props = entity_props.get(gen_id, {"name": gen_id})
            dg = entity_dg.get(gen_id, "Other")
            props["display_group"] = dg
            # Per-feature flag — only VRE generators physically curtail
            # (max(0, availability - generation) is meaningful only for
            # weather-driven units). The shader gates the curtailment
            # band on this flag so a thermal/storage feature in the same
            # layer doesn't render a fake "wasted nameplate" ring.
            props["curtailable"] = dg in _VRE_DISPLAY_GROUPS
            # Capacity comes from GAT's unified generator_ratings table
            # (computed by SiennaSystem.get_generator_ratings() at ingestion time
            # using Sienna's canonical active_power_limits.max * base_power).
            cap_mw = generator_ratings.get(gen_id)
            if cap_mw is not None:
                props["nameplate_mw"] = cap_mw
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [coords[0], coords[1]],
                    },
                    "properties": props,
                }
            )

        logger.debug(
            "[gen_geojson] result: %d features, %d no_bus_mapping, %d no_coords (of %d generators)",
            len(features),
            no_bus_mapping,
            no_coords,
            len(gen_ids),
        )
        geojson = {"type": "FeatureCollection", "features": features}
        return json.dumps(geojson).encode()

    # Component types that are true transmission lines (LineString geometry)
    _LINE_TYPES = {"Line", "MonitoredLine", "TwoTerminalHVDCLine", "AreaInterchange"}
    # Component types that are transformers (Point geometry at substation)
    _TRANSFORMER_TYPES = {"TapTransformer", "Transformer2W", "PhaseShiftingTransformer"}

    # ── Graph topology (non-geospatial network view) ───────────────────────────

    def list_graph_topologies(self, project=None, scenario=None):
        """One topology per loaded scenario: the system's bus/branch graph.

        Returns nothing when the project/scenario isn't loaded — the
        caller (GridSight's catalog endpoint) catches that gracefully.
        The frontend's GraphPanel calls this with the active project +
        scenario already filled in.
        """
        if not project or not scenario:
            return []
        try:
            schema = self._resolve_schema(project, scenario)
        except Exception:
            return []
        if not schema:
            return []
        return [
            GraphTopologyDescriptor(
                name=scenario,
                display_name=f"{scenario} (buses + branches)",
                description="Sienna bus topology with branches and transformers.",
                node_join_key="id",
                has_precomputed_layout=False,
            )
        ]

    def get_graph_topology(self, topology_name, project=None, scenario=None):
        """Return the bus/branch graph for the named scenario.

        ``stratum`` on each node is the rounded base voltage so the
        renderer can tint by voltage class without imposing a
        stratified layout — the force-directed default layout is
        applied server-side by GridSight core regardless.
        ``is_inter_stratum`` on transformer edges is left True so the
        renderer highlights transformer connections.
        """
        if not project or not scenario:
            return None
        if topology_name not in (scenario, "topology"):
            return None
        try:
            schema = self._resolve_schema(project, scenario)
        except Exception as e:
            logger.warning("[graph_topology] resolve_schema failed: %s", e)
            return None
        if not schema:
            return None

        with self._lock:
            tables = self._get_schema_tables(schema)
            if "sys__ACBus" not in tables:
                logger.debug("[graph_topology] no sys__ACBus in %s", schema)
                return None

            cols = self._get_columns(schema, "sys__ACBus")
            has_name = "name" in cols
            has_v = "base_voltage" in cols
            has_area = "area" in cols
            select_cols = ["UUID"]
            if has_name:
                select_cols.append("name")
            if has_v:
                select_cols.append("base_voltage")
            if has_area:
                select_cols.append("area")
            try:
                bus_rows = self._db.fetchall(
                    f"SELECT {', '.join(select_cols)} FROM gat_db.{schema}.sys__ACBus"
                )
            except Exception as e:
                logger.warning("[graph_topology] bus query failed: %s", e)
                return None

            # Build node list. Stratum = rounded base voltage as string,
            # which gives the renderer a stable key to color by.
            nodes: list[GraphNode] = []
            voltages_seen: set[float] = set()
            for row in bus_rows:
                uuid_val = row[0]
                if uuid_val is None:
                    continue
                rec = dict(zip(select_cols, row))
                bv = rec.get("base_voltage")
                try:
                    bv_f = float(bv) if bv is not None else None
                except (TypeError, ValueError):
                    bv_f = None
                stratum = f"{round(bv_f)}" if bv_f is not None else None
                if bv_f is not None:
                    voltages_seen.add(round(bv_f))
                nodes.append(
                    GraphNode(
                        id=str(uuid_val),
                        label=str(rec.get("name") or uuid_val),
                        stratum=stratum,
                        kind="bus",
                        attrs={
                            "base_voltage_kv": bv_f,
                            "area": (
                                str(rec["area"])
                                if has_area and rec.get("area")
                                else None
                            ),
                        },
                    )
                )

            line_eps = (
                self._load_branch_endpoints(
                    schema,
                    tables,
                    self._LINE_TYPES,
                )
                or []
            )
            xfmr_eps = (
                self._load_branch_endpoints(
                    schema,
                    tables,
                    self._TRANSFORMER_TYPES,
                )
                or []
            )

        bus_v = {n.id: n.attrs.get("base_voltage_kv") for n in nodes}
        edges: list[GraphEdge] = []
        for name, comp_type, from_uuid, to_uuid in line_eps:
            edges.append(
                GraphEdge(
                    id=f"line:{name}",
                    source=from_uuid,
                    target=to_uuid,
                    kind="branch",
                    attrs={
                        "type": comp_type,
                        "name": name,
                        "from_kv": bus_v.get(from_uuid),
                        "to_kv": bus_v.get(to_uuid),
                    },
                )
            )
        for name, comp_type, from_uuid, to_uuid in xfmr_eps:
            edges.append(
                GraphEdge(
                    id=f"xfmr:{name}",
                    source=from_uuid,
                    target=to_uuid,
                    kind="transformer",
                    is_inter_stratum=True,
                    attrs={
                        "type": comp_type,
                        "name": name,
                        "from_kv": bus_v.get(from_uuid),
                        "to_kv": bus_v.get(to_uuid),
                    },
                )
            )

        strata = [
            GraphStratum(id=f"{v}", label=f"{v} kV", order=i)
            for i, v in enumerate(sorted(voltages_seen))
        ]
        return GraphTopology(nodes=nodes, edges=edges, strata=strata)

    def _build_branch_geojson(self, schema: str, mode: str = "lines") -> bytes:
        """Build GeoJSON for branches — either lines (LineString) or transformers (Point).

        Resolves topology from the `branch_endpoints` table (populated by
        GAT ingestion). Falls back to parsing the source system JSON for
        scenarios ingested before that table existed; once those are
        re-ingested, the JSON path can be removed.

        Args:
            schema: DuckDB schema name.
            mode: "lines" for transmission lines, "transformers" for transformer points.
        """
        bus_coords = self._get_bus_coords(schema)
        tables = self._get_schema_tables(schema)
        logger.debug(
            "[branch_geojson:%s] %d bus coords available", mode, len(bus_coords)
        )

        include_types = (
            self._TRANSFORMER_TYPES if mode == "transformers" else self._LINE_TYPES
        )
        ratings = self._load_branch_ratings(schema, tables)
        logger.debug("[branch_geojson:%s] %d ratings", mode, len(ratings))

        endpoints = self._load_branch_endpoints(schema, tables, include_types)
        if endpoints is None:
            # Legacy fallback for pre-branch_endpoints scenarios.
            endpoints = self._load_branch_endpoints_from_system_json(
                schema, include_types
            )
        if not endpoints:
            return json.dumps({"type": "FeatureCollection", "features": []}).encode()

        bus_voltage = self._load_bus_voltages(schema, tables)

        # Real multi-vertex line paths (HIFLD-derived) from the system's
        # `Line_Geometry` column, keyed by branch name. When a branch has a
        # true polyline we trace the actual corridor instead of a straight
        # bus-to-bus segment; transformers (Point mode) never use this.
        line_geoms = (
            self._load_line_geometries(schema, tables) if mode == "lines" else {}
        )

        features = []
        no_coords = 0
        real_paths = 0
        for name, comp_type, from_uuid, to_uuid in endpoints:
            from_coords = bus_coords.get(from_uuid)
            to_coords = bus_coords.get(to_uuid)
            if not from_coords or not to_coords:
                no_coords += 1
                continue

            voltage_kv = round(
                max(bus_voltage.get(from_uuid, 0.0), bus_voltage.get(to_uuid, 0.0)), 1
            )
            if voltage_kv >= 345:
                voltage_class = "345+ kV"
            elif voltage_kv >= 230:
                voltage_class = "230 kV"
            elif voltage_kv >= 138:
                voltage_class = "138 kV"
            elif voltage_kv >= 115:
                voltage_class = "115 kV"
            elif voltage_kv >= 69:
                voltage_class = "69 kV"
            else:
                voltage_class = "<69 kV"

            props = {
                "name": name,
                "capacity": ratings.get(name, 0.0),
                "type": comp_type,
                "voltage_kv": voltage_kv,
                "voltage_class": voltage_class,
            }

            if mode == "transformers":
                mid_lon = (from_coords[0] + to_coords[0]) / 2
                mid_lat = (from_coords[1] + to_coords[1]) / 2
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [mid_lon, mid_lat],
                        },
                        "properties": props,
                    }
                )
            else:
                # Prefer the real multi-vertex path when we have one; otherwise
                # fall back to a straight bus-to-bus segment (covers branches
                # with no Line_Geometry and 2-point source geometries).
                coords = self._wkt_linestring_coords(line_geoms.get(name))
                if coords and len(coords) > 2:
                    # Orient the path from_bus → to_bus so the flow-direction
                    # gradient matches the signed flow value. The stored path
                    # may be digitized in either order relative to the buses.
                    d_fwd = (
                        (coords[0][0] - from_coords[0]) ** 2
                        + (coords[0][1] - from_coords[1]) ** 2
                        + (coords[-1][0] - to_coords[0]) ** 2
                        + (coords[-1][1] - to_coords[1]) ** 2
                    )
                    d_rev = (
                        (coords[0][0] - to_coords[0]) ** 2
                        + (coords[0][1] - to_coords[1]) ** 2
                        + (coords[-1][0] - from_coords[0]) ** 2
                        + (coords[-1][1] - from_coords[1]) ** 2
                    )
                    if d_rev < d_fwd:
                        coords = coords[::-1]
                    real_paths += 1
                else:
                    coords = [
                        [from_coords[0], from_coords[1]],
                        [to_coords[0], to_coords[1]],
                    ]
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {"type": "LineString", "coordinates": coords},
                        "properties": props,
                    }
                )

        logger.debug(
            "[branch_geojson:%s] %d features (%d real paths), %d no_coords (of %d candidates)",
            mode,
            len(features),
            real_paths,
            no_coords,
            len(endpoints),
        )
        geojson = {"type": "FeatureCollection", "features": features}
        return json.dumps(geojson).encode()

    def _load_line_geometries(self, schema: str, tables: list[str]) -> dict[str, str]:
        """Map branch ``name`` → WKT ``LINESTRING`` from the system's
        ``Line_Geometry`` column (real HIFLD-derived routes), when present.
        Empty dict if the column/table isn't available."""
        if "sys__branches" not in tables:
            return {}
        # Not every system carries the HIFLD-derived Line_Geometry column
        # (emulator schemas, for instance, only have flow columns), so probe for
        # it before querying. Without this, systems lacking the column raised a
        # BinderException on every branch load and logged a full traceback —
        # here we just fall back to straight bus-to-bus segments.
        if "Line_Geometry" not in self._get_columns(schema, "sys__branches"):
            return {}
        try:
            rows = self._db.fetchall(
                f'SELECT name, "Line_Geometry" FROM gat_db.{schema}.sys__branches '
                f"WHERE \"Line_Geometry\" LIKE 'LINESTRING%'"
            )
        except Exception:
            logger.debug("[branch_geojson] Line_Geometry query failed", exc_info=True)
            return {}
        return {str(r[0]): str(r[1]) for r in rows if r[0] is not None and r[1]}

    @staticmethod
    def _wkt_linestring_coords(wkt: str | None) -> list[list[float]] | None:
        """Parse ``LINESTRING (x y, x y, ...)`` into ``[[x, y], ...]``.

        Returns None for anything that isn't a usable 2+ point linestring.
        Tolerates an optional ``Z``/``M`` tag and extra ordinates per vertex
        (only the first two — lon, lat — are kept).
        """
        if not wkt:
            return None
        stripped = wkt.lstrip()
        if not stripped[:10].upper().startswith("LINESTRING"):
            return None
        try:
            inner = wkt[wkt.index("(") + 1 : wkt.rindex(")")]
        except ValueError:
            return None
        coords: list[list[float]] = []
        for pair in inner.split(","):
            parts = pair.split()
            if len(parts) >= 2:
                try:
                    coords.append([float(parts[0]), float(parts[1])])
                except ValueError:
                    return None
        return coords if len(coords) >= 2 else None

    def _load_branch_ratings(self, schema: str, tables: list[str]) -> dict[str, float]:
        ratings: dict[str, float] = {}
        if "branch_ratings" in tables:
            try:
                rows = self._db.fetchall(
                    f"SELECT name, rating_mw FROM gat_db.{schema}.branch_ratings"
                )
                ratings = {str(r[0]): float(r[1]) for r in rows if r[1] is not None}
            except Exception:
                pass
        if ratings:
            return ratings

        base_power = self._get_base_power(schema)
        for table_name in ("sys__Line", "sys__MonitoredLine", "sys__branches"):
            if table_name not in tables:
                continue
            cols = self._get_columns(schema, table_name)
            if "name" not in cols:
                continue
            rating_col = next((c for c in cols if c in ("rating", "rate")), None)
            if not rating_col:
                continue
            try:
                rows = self._db.fetchall(
                    f"SELECT name, {rating_col} FROM gat_db.{schema}.{table_name}"
                )
                for name, val in rows:
                    if name and val is not None:
                        try:
                            ratings[str(name)] = float(val) * base_power
                        except (TypeError, ValueError):
                            pass
            except Exception:
                pass
        return ratings

    def _load_branch_endpoints(
        self,
        schema: str,
        tables: list[str],
        include_types: set[str],
    ) -> list[tuple[str, str, str, str]] | None:
        """Read (name, type, from_uuid, to_uuid) from `branch_endpoints`.

        Returns None when the table doesn't exist in this schema, signalling
        the caller to fall back to the legacy system-JSON parser.
        """
        if "branch_endpoints" not in tables:
            return None
        try:
            placeholders = ",".join(["?"] * len(include_types))
            rows = self._db.fetchall(
                f"SELECT name, type, from_bus_uuid, to_bus_uuid "
                f"FROM gat_db.{schema}.branch_endpoints "
                f"WHERE type IN ({placeholders})",
                list(include_types),
            )
        except Exception as e:
            logger.warning("[branch_geojson] branch_endpoints read failed: %s", e)
            return None
        return [
            (str(n), str(t), str(f), str(to)) for n, t, f, to in rows if n and f and to
        ]

    def _load_bus_voltages(self, schema: str, tables: list[str]) -> dict[str, float]:
        if "sys__ACBus" not in tables:
            return {}
        cols = self._get_columns(schema, "sys__ACBus")
        if "UUID" not in cols or "base_voltage" not in cols:
            return {}
        try:
            rows = self._db.fetchall(
                f"SELECT UUID, base_voltage FROM gat_db.{schema}.sys__ACBus"
            )
        except Exception:
            return {}
        out: dict[str, float] = {}
        for uuid_val, bv in rows:
            if uuid_val and bv is not None:
                try:
                    out[str(uuid_val)] = float(bv)
                except (TypeError, ValueError):
                    pass
        return out

    def _load_branch_endpoints_from_system_json(
        self,
        schema: str,
        include_types: set[str],
    ) -> list[tuple[str, str, str, str]]:
        """Legacy path: parse Arc topology out of the source system JSON."""
        system_path = self._find_system_json(schema)
        if not system_path:
            return []
        try:
            with open(system_path) as f:
                system_data = json.load(f)
        except Exception as e:
            logger.error("[branch_geojson] Failed to read system JSON: %s", e)
            return []

        components = system_data.get("data", {}).get("components", [])
        comp_by_uuid: dict[str, dict] = {}
        for comp in components:
            uuid_val = comp.get("internal", {}).get("uuid", {}).get("value")
            if uuid_val:
                comp_by_uuid[uuid_val] = comp

        out: list[tuple[str, str, str, str]] = []
        for comp in components:
            comp_type = comp.get("__metadata__", {}).get("type", "")
            if comp_type not in include_types:
                continue
            name = comp.get("name", "")
            if not name:
                continue
            arc_ref = comp.get("arc")
            if not isinstance(arc_ref, dict):
                continue
            arc_uuid = (
                arc_ref.get("internal", {}).get("uuid", {}).get("value")
                or arc_ref.get("value")
                or arc_ref.get("uuid", "")
            )
            arc_data = (
                arc_ref
                if arc_ref.get("from") or arc_ref.get("to")
                else comp_by_uuid.get(arc_uuid)
            )
            if not arc_data:
                continue
            from_ref = arc_data.get("from", arc_data.get("from_bus", {}))
            to_ref = arc_data.get("to", arc_data.get("to_bus", {}))
            from_uuid = (
                from_ref.get("value", "")
                if isinstance(from_ref, dict)
                else str(from_ref)
            )
            to_uuid = (
                to_ref.get("value", "") if isinstance(to_ref, dict) else str(to_ref)
            )
            if from_uuid and to_uuid:
                out.append((name, comp_type, from_uuid, to_uuid))
        return out

    # ── Datasets ───────────────────────────────────────────────────────────

    def list_datasets(
        self, project: str | None = None, scenario: str | None = None
    ) -> list[DatasetDescriptor]:
        if not project or not scenario:
            return []
        schema = self._resolve_schema(project, scenario)
        tables = self._get_schema_tables(schema)
        # Datasets are addressed by ``{schema}__{table_name}`` so the
        # M2a per-model schema is encoded in the dataset name. The
        # round-trip parsers below split on ``__`` and read the
        # corresponding parts. Schema is already lowercased project/
        # scenario/model, so the wire-level dataset name is stable
        # against user-typed casing.
        datasets: list[DatasetDescriptor] = []

        # Composed simulation tables: generation, load, line_flow, availability
        for table_name in (
            "generation",
            "load",
            "line_flow",
            "availability",
            "charging",
        ):
            if table_name not in tables:
                continue
            cols = self._get_columns(schema, table_name)
            # First col is entity_id, rest are timestamps
            ts_cols = [c for c in cols if c != "entity_id"]
            datasets.append(
                DatasetDescriptor(
                    name=f"{schema}__{table_name}",
                    display_name=f"{table_name.replace('_', ' ').title()} ({scenario})",
                    format="parquet",
                    join_key="entity_id",
                    timestamp_col="datetime",
                    columns=cols,
                    description=(
                        f"{table_name.title()} timeseries: "
                        f"{len(ts_cols)} timesteps, entity × timestamp format."
                    ),
                )
            )

        return datasets

    def list_dataset_partitions(self, dataset_name: str) -> list[str]:
        """Return daily partition date strings for a GAT timeseries dataset."""
        parts = dataset_name.split("__")
        if len(parts) < 4:
            return []
        project, scenario, model, table_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        try:
            # Get all timestamp columns (they ARE the date partitions in GAT's entity×timestamp format)
            cols = self._get_columns(schema, table_name)
            ts_cols = sorted(c for c in cols if c != "entity_id")
            # Group by date (extract YYYY-MM-DD from ISO timestamps)
            dates = sorted(set(c[:10] for c in ts_cols if len(c) >= 10))
            return dates
        except Exception as e:
            logger.error("Failed to list partitions for %s: %s", dataset_name, e)
            return []

    def get_dataset_metadata(self, dataset_name: str) -> DatasetTimeInfo | None:
        """Return fast time-range metadata from DuckDB column names.

        GAT stores timeseries as entity_id rows × ISO timestamp columns,
        so all metadata is derivable from the schema without reading data.
        """
        parts = dataset_name.split("__")
        if len(parts) < 4:
            return None
        project, scenario, model, table_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        try:
            with self._lock:
                cols = self._get_columns(schema, table_name)
                entity_count = self._db.fetchone(
                    f"SELECT COUNT(*) FROM gat_db.{schema}.{table_name}"
                )[0]
        except Exception as e:
            logger.error("Failed to get metadata for %s: %s", dataset_name, e)
            return None

        ts_cols = sorted(c for c in cols if c != "entity_id")
        if not ts_cols:
            return None

        # Group timestamps by date for partition info
        date_counts: dict[str, int] = {}
        for c in ts_cols:
            date = c[:10]
            date_counts[date] = date_counts.get(date, 0) + 1
        dates = sorted(date_counts.keys())

        # Entity columns are the entity IDs (row names in the wide table)
        # We need to fetch them from the entity_id column
        entity_columns: list[str] = []
        try:
            with self._lock:
                rows = self._db.fetchall(
                    f"SELECT entity_id FROM gat_db.{schema}.{table_name}"
                )
                entity_columns = [str(r[0]) for r in rows]
        except Exception:
            pass

        # Detect resolution from first two timestamps
        resolution = None
        if len(ts_cols) >= 2:
            try:
                from datetime import datetime

                t0 = datetime.fromisoformat(ts_cols[0])
                t1 = datetime.fromisoformat(ts_cols[1])
                resolution = int((t1 - t0).total_seconds())
            except Exception:
                pass

        return DatasetTimeInfo(
            dates=dates,
            row_counts=date_counts,  # timestamps per day (= rows in the transposed partition)
            entity_columns=entity_columns,
            start=ts_cols[0],
            end=ts_cols[-1],
            total_rows=len(ts_cols),  # total timesteps
            resolution_seconds=resolution,
        )

    def get_entity_timeseries(self, dataset_name: str, entity_id: str) -> dict | None:
        """Fast single-entity timeseries fetch.

        The native GAT table is wide format: rows = entities, columns =
        timestamps. To pull one entity's full series we just SELECT the
        matching row — no UNPIVOT/PIVOT, no per-day iteration. Returns
        ``{"timestamps": [...], "values": [...]}`` or None on miss.
        """
        parts = dataset_name.split("__")
        if len(parts) < 4:
            return None
        project, scenario, model, table_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        with self._lock:
            cols = self._get_columns(schema, table_name)
            if "entity_id" not in cols:
                return None
            ts_cols = sorted(c for c in cols if c != "entity_id")
            if not ts_cols:
                return {"timestamps": [], "values": []}
            try:
                row = self._db.fetchone(
                    f"SELECT * FROM gat_db.{schema}.{table_name} WHERE entity_id = ? LIMIT 1",
                    [entity_id],
                )
            except Exception as e:
                logger.warning(
                    "[get_entity_timeseries] query failed for %s/%s: %s",
                    schema,
                    entity_id,
                    e,
                )
                return None
            if row is None:
                return {"timestamps": [], "values": []}
            # row is tuple aligned to `cols` — find each ts column's value.
            col_index = {c: i for i, c in enumerate(cols)}
            values = [
                None if (v := row[col_index[c]]) is None else float(v) for c in ts_cols
            ]
            return {"timestamps": ts_cols, "values": values}

    def get_entity_series(
        self,
        dataset_name: str,
        entity_id: str,
        from_ts: str | None = None,
        to_ts: str | None = None,
        max_points: int | None = None,
    ) -> bytes | None:
        """Windowed single-entity series as Arrow IPC bytes.

        Wide-format table: columns are ISO timestamp strings, rows are
        entities. To return a window we project only the timestamp
        columns inside ``[from_ts, to_ts]`` — for a 72 h slice that's
        ~864 columns out of 105k for 5-min data, so SELECT cost is
        proportional to the window size, not the dataset size.

        Beats ``get_entity_timeseries`` (which does ``SELECT *``) by
        more than 100× on annual 5-min datasets.
        """
        import pyarrow as pa

        parts = dataset_name.split("__")
        if len(parts) < 4:
            return None
        project, scenario, model, table_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        with self._lock:
            cols = self._get_columns(schema, table_name)
            if "entity_id" not in cols:
                return None
            # Timestamp columns are sortable as strings (ISO 8601).
            ts_cols = sorted(c for c in cols if c != "entity_id")
            if from_ts:
                ts_cols = [c for c in ts_cols if c >= from_ts]
            if to_ts:
                ts_cols = [c for c in ts_cols if c <= to_ts]
            if not ts_cols:
                return self._empty_series_ipc()

            # Optional pre-projection downsample: if the requested
            # window has more points than ``max_points``, stride through
            # ts_cols so we only read what we need. Keeps the SQL small
            # and the Arrow table small.
            if max_points and len(ts_cols) > max_points:
                stride = max(1, len(ts_cols) // max_points)
                ts_cols = ts_cols[::stride]

            col_list = ", ".join(f'"{c}"' for c in ts_cols)
            try:
                row = self._db.fetchone(
                    f"SELECT {col_list} FROM gat_db.{schema}.{table_name} "
                    f"WHERE entity_id = ? LIMIT 1",
                    [entity_id],
                )
            except Exception as e:
                logger.warning(
                    "[get_entity_series] query failed for %s/%s: %s",
                    schema,
                    entity_id,
                    e,
                )
                return None
            if row is None:
                return self._empty_series_ipc()

            values = [None if v is None else float(v) for v in row]

        ts_arr = pa.array(ts_cols, type=pa.string())
        val_arr = pa.array(values, type=pa.float64())
        table = pa.table({"timestamp": ts_arr, "value": val_arr})
        sink = io.BytesIO()
        w = pa.ipc.new_stream(sink, table.schema)
        w.write_table(table)
        w.close()
        return sink.getvalue()

    @staticmethod
    def _empty_series_ipc() -> bytes:
        import pyarrow as pa

        schema = pa.schema([("timestamp", pa.string()), ("value", pa.float64())])
        sink = io.BytesIO()
        w = pa.ipc.new_stream(sink, schema)
        w.close()
        return sink.getvalue()

    def get_dataset_partition(self, dataset_name: str, date_str: str) -> bytes:
        """Return a daily partition as Arrow IPC bytes (wide format: timestamp rows × entity cols)."""
        import pyarrow as pa

        parts = dataset_name.split("__")
        if len(parts) < 4:
            raise NotImplementedError(f"Unknown dataset: {dataset_name}")
        project, scenario, model, table_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        with self._lock:
            # Get timestamp columns for this date
            cols = self._get_columns(schema, table_name)
            ts_cols = sorted(
                c for c in cols if c != "entity_id" and c.startswith(date_str)
            )
            if not ts_cols:
                raise FileNotFoundError(
                    f"No data for date {date_str} in {dataset_name}"
                )

            # Transpose via UNPIVOT + PIVOT
            unpivot_cols = ", ".join(f'"{c}"' for c in ts_cols)
            sql = (
                f"WITH unpivoted AS ("
                f"  SELECT entity_id, ts AS datetime, CAST(val AS DOUBLE) AS val "
                f"  FROM gat_db.{schema}.{table_name} "
                f"  UNPIVOT (val FOR ts IN ({unpivot_cols}))"
                f"  WHERE ts >= '{date_str}' AND ts < '{date_str}T99'"
                f") "
                f"PIVOT unpivoted ON entity_id USING first(val) "
                f"ORDER BY datetime"
            )

            table = self._db.fetch_arrow(sql)

        # Serialize to Arrow IPC (no lock needed)
        sink = io.BytesIO()
        writer = pa.ipc.new_file(sink, table.schema)
        writer.write_table(table)
        writer.close()
        return sink.getvalue()

    def get_dataset_data(self, dataset_name: str) -> bytes:
        """Return full dataset as Parquet bytes."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        parts = dataset_name.split("__")
        if len(parts) < 4:
            raise NotImplementedError(f"Unknown dataset: {dataset_name}")
        project, scenario, model, table_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        table = self._db.fetch_arrow(f"SELECT * FROM gat_db.{schema}.{table_name}")
        sink = io.BytesIO()
        pq.write_table(table, sink)
        return sink.getvalue()

    # ── Category Maps ──────────────────────────────────────────────────────

    def list_category_maps(
        self, project: str | None = None, scenario: str | None = None
    ) -> list[CategoryMapDescriptor]:
        if not project or not scenario:
            return []
        schema = self._resolve_schema(project, scenario)
        tables = self._get_schema_tables(schema)
        catmaps: list[CategoryMapDescriptor] = []

        for table_name in tables:
            if not table_name.startswith("catmap__"):
                continue
            map_name = table_name.removeprefix("catmap__")

            # Populate colors from GAT's standard palette
            colors_dict: dict[str, str] = {}
            try:
                rows = self._db.fetchall(
                    f"SELECT DISTINCT category FROM gat_db.{schema}.catmap__{map_name}"
                )
                for (cat,) in rows:
                    color = _lookup_color(cat)
                    if color:
                        colors_dict[cat] = color
            except Exception:
                pass

            catmaps.append(
                CategoryMapDescriptor(
                    name=f"{schema}__{map_name}",
                    display_name=map_name.replace("_", " ").title(),
                    entity_column="entity_id",
                    category_column="category",
                    description=f"Category map: {map_name} (from GAT)",
                    applies_to=["generation", "load", "line_flow"],
                    colors=colors_dict,
                )
            )

        return catmaps

    def get_category_map_data(self, category_map_name: str) -> bytes:
        """Return category map as Parquet bytes."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        parts = category_map_name.split("__")
        if len(parts) < 4:
            raise NotImplementedError(f"Unknown category map: {category_map_name}")
        project, scenario, model, map_name = parts[0], parts[1], parts[2], parts[3]
        schema = self._resolve_schema(project, scenario, model=model)

        table = self._db.fetch_arrow(
            f"SELECT entity_id, category FROM gat_db.{schema}.catmap__{map_name}"
        )
        sink = io.BytesIO()
        pq.write_table(table, sink)
        return sink.getvalue()

    # ── DuckDB Tables ──────────────────────────────────────────────────────

    def register_duckdb_tables(self, conn: Any) -> list[DuckDBTableInfo]:
        if not self._ensure_attached():
            return []

        scenarios = self._list_registry_scenarios()
        tables_info: list[DuckDBTableInfo] = []

        # Create extension schema
        conn.execute("CREATE SCHEMA IF NOT EXISTS ext_gat")

        # Eagerly materialize derived tables (catmap__display_group) once at
        # startup so list_chart_specs / chart-data requests later are pure
        # reads — no detach/reattach needed during the FE's hot path.
        # Safe to do here because register_duckdb_tables runs before the FE
        # has a chance to issue concurrent gat_db queries.
        for s in scenarios:
            schema = s["schema_name"]
            prefix = f"{s['project']}_{s['scenario']}".replace("-", "_")
            try:
                self._ensure_catmap_display_group(schema, prefix)
            except Exception as e:
                logger.warning(
                    "[register_duckdb_tables] catmap_dg materialize failed for %s: %s",
                    schema,
                    e,
                )

        for s in scenarios:
            schema = s["schema_name"]
            prefix = f"{s['project']}_{s['scenario']}".replace("-", "_")
            gat_tables = self._get_schema_tables(schema)

            for table_name in gat_tables:
                view_name = f"ext_gat.{prefix}__{table_name}"
                try:
                    conn.execute(
                        f"CREATE OR REPLACE VIEW {view_name} "
                        f"AS SELECT * FROM gat_db.{schema}.{table_name}"
                    )
                except Exception as e:
                    logger.warning("Failed to create view %s: %s", view_name, e)
                    continue

                # Categorize for description
                if table_name.startswith("sys__"):
                    desc = f"System data: {table_name.removeprefix('sys__')}"
                elif table_name.startswith("sim__"):
                    desc = f"Raw simulation: {table_name.removeprefix('sim__')}"
                elif table_name.startswith("catmap__"):
                    desc = f"Category map: {table_name.removeprefix('catmap__')}"
                elif table_name in ("generation", "load", "line_flow"):
                    desc = f"Composed {table_name} timeseries (entity × timestamp)"
                else:
                    desc = f"GAT table: {table_name}"

                tables_info.append(
                    DuckDBTableInfo(
                        table_name=view_name,
                        description=f"[{s['project']}/{s['scenario']}] {desc}",
                        extension_name="gat",
                    )
                )

        return tables_info

    # ── AI ─────────────────────────────────────────────────────────────────

    def get_ai_schema(self) -> AISchema | None:
        scenarios = self._list_registry_scenarios()
        if not scenarios:
            return None

        tables: list[AITableSchema] = []
        for s in scenarios:
            schema = s["schema_name"]
            prefix = f"{s['project']}_{s['scenario']}".replace("-", "_")
            gat_tables = self._get_schema_tables(schema)

            for table_name in ("generation", "load", "line_flow"):
                if table_name not in gat_tables:
                    continue
                view = f"ext_gat.{prefix}__{table_name}"
                tables.append(
                    AITableSchema(
                        table_name=view,
                        description=(
                            f"[{s['project']}/{s['scenario']}] "
                            f"Composed {table_name} data. "
                            f"Entity rows × timestamp columns format. "
                            f"entity_id column + ISO timestamp columns with MW values."
                        ),
                        example_queries=[
                            f"SELECT entity_id FROM {view} LIMIT 10",
                        ],
                    )
                )

            # Category maps
            for table_name in gat_tables:
                if not table_name.startswith("catmap__"):
                    continue
                view = f"ext_gat.{prefix}__{table_name}"
                map_name = table_name.removeprefix("catmap__")
                tables.append(
                    AITableSchema(
                        table_name=view,
                        description=(
                            f"[{s['project']}/{s['scenario']}] "
                            f"Category map '{map_name}': maps entity_id → category. "
                            f"JOIN with generation/load/line_flow on entity_id for grouped analysis."
                        ),
                        example_queries=[
                            f"SELECT DISTINCT category FROM {view} ORDER BY category",
                        ],
                    )
                )

            # System tables for generator/line properties
            for sys_table in (
                "sys__generators",
                "sys__ThermalStandard",
                "sys__RenewableDispatch",
                "sys__Line",
            ):
                if sys_table not in gat_tables:
                    continue
                view = f"ext_gat.{prefix}__{sys_table}"
                tables.append(
                    AITableSchema(
                        table_name=view,
                        description=(
                            f"[{s['project']}/{s['scenario']}] "
                            f"System properties: {sys_table.removeprefix('sys__')}. "
                            f"Contains name, bus, area, fuel, capacity, etc."
                        ),
                    )
                )

        return AISchema(
            description=(
                "GAT (Grid Analysis Toolkit) extension providing power system simulation results. "
                "Data includes generation dispatch, load profiles, transmission line flows, "
                "and category maps for grouping (by technology, fuel type, area). "
                "To analyze dispatch by category, JOIN a generation table with a catmap__ table "
                "on entity_id, then GROUP BY category. "
                "Timestamp columns in composed tables are ISO 8601 strings representing MW values."
            ),
            tables=tables,
            example_prompts=[
                "What generators are in this system?",
                "Show total generation by technology type",
                "What is the peak load?",
                "Show a stacked area chart of generation by fuel type over time",
                "Which transmission lines are most congested?",
                "Compare wind vs solar generation",
            ],
        )

    # ── Charts ─────────────────────────────────────────────────────────────

    def list_chart_specs(self) -> list[ChartSpec]:
        # Hold the extension lock for the whole iteration. _ensure_catmap_display_group
        # may temporarily detach gat_db to do a write — without serializing this
        # against concurrent layer/dataset queries (which also use self._conn),
        # those queries would fail mid-flight.
        with self._lock:
            return self._list_chart_specs_locked()

    def _list_chart_specs_locked(self) -> list[ChartSpec]:
        scenarios = self._list_registry_scenarios()
        charts: list[ChartSpec] = []

        for s in scenarios:
            schema = s["schema_name"]
            prefix = f"{s['project']}_{s['scenario']}".replace("-", "_")
            # Track where this scenario's specs start so we can stamp
            # project/scenario on them in one shot at the end (lets the
            # frontend filter the charts menu by active scenario).
            _scenario_start = len(charts)
            try:
                gat_tables = self._get_schema_tables(schema)
            except Exception as e:
                logger.warning(
                    "[list_chart_specs] schema %s scan failed: %s", schema, e
                )
                continue

            if "generation" not in gat_tables:
                continue

            # Find a technology category map
            tech_catmap = None
            for t in gat_tables:
                if t.startswith("catmap__") and ("tech" in t or "fuel" in t):
                    tech_catmap = f"ext_gat.{prefix}__{t}"
                    break

            if tech_catmap:
                charts.append(
                    ChartSpec(
                        name=f"{prefix}__generation_mix",
                        display_name=f"Generation Mix ({s['scenario']})",
                        chart_type="pie",
                        sql_template=(
                            f"SELECT cm.category, "
                            f"SUM(COLUMNS(* EXCLUDE (entity_id)))::DOUBLE AS total_mw "
                            f"FROM ext_gat.{prefix}__generation g "
                            f"JOIN {tech_catmap} cm ON g.entity_id = cm.entity_id "
                            f"GROUP BY cm.category ORDER BY total_mw DESC"
                        ),
                        chart_options={},
                        datasets=["generation"],
                        format="plotly",
                    )
                )

            # ── Scenario-scoped: system-wide stacked-area generation by display_group ──
            #
            # Materialize catmap__display_group on demand (idempotent), then emit
            # a long-format SQL ready for the FE's stacked-area scrubber chart.
            # One bad scenario shouldn't take down the whole list.
            try:
                if self._ensure_catmap_display_group(schema, prefix):
                    rgba_colors = self._get_display_group_colors(schema, gat_tables)
                    hex_colors = {
                        dg: _rgba_to_hex(rgba) for dg, rgba in rgba_colors.items()
                    }
                    # Canonical display order = order of keys in _STANDARD_COLORS
                    # (Nuclear → Coal → Gas → ... → Wind/PV/Storage). Filter to
                    # display groups actually present in this scenario; FE uses
                    # this as the bottom-to-top stack order in "Display" mode.
                    present_dgs = set(hex_colors.keys())
                    canonical_order = [
                        k for k in _STANDARD_COLORS.keys() if k in present_dgs
                    ]
                    leftover = sorted(present_dgs - set(canonical_order))
                    category_order = canonical_order + leftover

                    # Append a "Curtailment" series only when availability
                    # data is on hand. Visually it sits at the top of the
                    # stack (last in canonical order) with the standard
                    # GAT curtailment grey, and toggles on/off via the
                    # legend like any other category.
                    has_avail = "availability" in gat_tables
                    curt_color = "#E1E1E1"  # GAT standard "Curtailment" grey
                    cat_colors = dict(hex_colors)
                    cat_order = list(category_order)
                    if has_avail:
                        cat_colors["Curtailment"] = curt_color
                        # Top of stack — appended after the canonical order.
                        if "Curtailment" not in cat_order:
                            cat_order = cat_order + ["Curtailment"]

                    if has_avail:
                        vre_list = _vre_groups_sql_list()
                        sql_template = (
                            # Wide-form aggregation per display_group (existing
                            # path), UNION'd with a long-form curtailment row.
                            # Curtailment is restricted to VRE entities only —
                            # max(0, avail - gen) for a thermal unit is just
                            # "unused dispatchable capacity", not curtailment
                            # in the dispatch sense.
                            f"WITH gen_by_dg AS ("
                            f"  SELECT cm.category AS display_group, "
                            f"         SUM(COLUMNS(* EXCLUDE (entity_id, category))) "
                            f"  FROM ext_gat.{prefix}__generation g "
                            f"  JOIN ext_gat.{prefix}__catmap__display_group cm "
                            f"    ON g.entity_id = cm.entity_id "
                            f"  GROUP BY cm.category"
                            f"), gen_long AS ("
                            f"  SELECT * FROM gen_by_dg "
                            f"  UNPIVOT (mw FOR timestamp IN (COLUMNS(* EXCLUDE display_group)))"
                            f"), vre_entities AS ("
                            f"  SELECT entity_id FROM ext_gat.{prefix}__catmap__display_group "
                            f"  WHERE category IN ({vre_list})"
                            f"), gen_unpivot AS ("
                            f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__generation "
                            f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id))) "
                            f"  WHERE entity_id IN (SELECT entity_id FROM vre_entities)"
                            f"), avail_unpivot AS ("
                            f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__availability "
                            f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id))) "
                            f"  WHERE entity_id IN (SELECT entity_id FROM vre_entities)"
                            f"), curt_long AS ("
                            f"  SELECT 'Curtailment' AS display_group, "
                            f"         g.ts AS timestamp, "
                            f"         SUM(GREATEST(0, a.val - g.val))::DOUBLE AS mw "
                            f"  FROM gen_unpivot g "
                            f"  JOIN avail_unpivot a "
                            f"    ON g.entity_id = a.entity_id AND g.ts = a.ts "
                            f"  GROUP BY g.ts"
                            f") "
                            f"SELECT display_group, timestamp, mw FROM gen_long "
                            f"UNION ALL "
                            f"SELECT display_group, timestamp, mw FROM curt_long "
                            f"ORDER BY timestamp, display_group"
                        )
                    else:
                        sql_template = (
                            # Legacy path — no availability dataset means no
                            # curtailment series. Keep the original wide-form
                            # aggregation for compatibility.
                            f"WITH gen_by_dg AS ("
                            f"  SELECT cm.category AS display_group, "
                            f"         SUM(COLUMNS(* EXCLUDE (entity_id, category))) "
                            f"  FROM ext_gat.{prefix}__generation g "
                            f"  JOIN ext_gat.{prefix}__catmap__display_group cm "
                            f"    ON g.entity_id = cm.entity_id "
                            f"  GROUP BY cm.category"
                            f") "
                            f"UNPIVOT gen_by_dg "
                            f"  ON COLUMNS(* EXCLUDE display_group) "
                            f"  INTO NAME timestamp VALUE mw "
                            f"ORDER BY timestamp, display_group"
                        )

                    charts.append(
                        ChartSpec(
                            name=f"{prefix}__system_generation_stacked",
                            display_name=f"System Generation by Tech ({s['scenario']})",
                            chart_type="scrubber-stacked-area",
                            sql_template=sql_template,
                            chart_options={
                                "time_axis": "timestamp",
                                "category_axis": "display_group",
                                "value_axis": "mw",
                                "category_colors": cat_colors,
                                "category_order": cat_order,
                            },
                            datasets=(
                                ["generation", "availability"]
                                if has_avail
                                else ["generation"]
                            ),
                            format="custom",
                            scope="scenario",
                            width=600,
                            height=300,
                        )
                    )
            except Exception as e:
                logger.warning(
                    "[list_chart_specs] failed to build stacked-area spec for %s: %s",
                    schema,
                    e,
                )

            # ── Curtailment total (single-line scrubber) ────────────────────
            # Per-timestamp Σ max(0, availability - generation) across VRE
            # entities only — curtailment is only meaningful for weather-
            # driven generators. Thermals with availability data showing as
            # "curtailment" was wrong (it's just unused dispatchable headroom).
            if (
                "availability" in gat_tables
                and "generation" in gat_tables
                and "catmap__display_group" in gat_tables
            ):
                try:
                    vre_list = _vre_groups_sql_list()
                    charts.append(
                        ChartSpec(
                            name=f"{prefix}__curtailment_total",
                            display_name=f"Curtailment ({s['scenario']})",
                            chart_type="scrubber-line",
                            sql_template=(
                                f"WITH vre_entities AS ("
                                f"  SELECT entity_id FROM ext_gat.{prefix}__catmap__display_group "
                                f"  WHERE category IN ({vre_list})"
                                f"), gen_long AS ("
                                f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__generation "
                                f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id))) "
                                f"  WHERE entity_id IN (SELECT entity_id FROM vre_entities)"
                                f"), avail_long AS ("
                                f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__availability "
                                f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id))) "
                                f"  WHERE entity_id IN (SELECT entity_id FROM vre_entities)"
                                f") "
                                f"SELECT g.ts AS timestamp, "
                                f"       SUM(GREATEST(0, a.val - g.val))::DOUBLE AS mw "
                                f"FROM gen_long g "
                                f"JOIN avail_long a ON g.entity_id = a.entity_id AND g.ts = a.ts "
                                f"GROUP BY g.ts "
                                f"ORDER BY g.ts"
                            ),
                            chart_options={
                                "time_axis": "timestamp",
                                "value_axis": "mw",
                                "value_unit": "MW",
                                "value_label": "Curtailment",
                                "line_color": "#E1E1E1",  # GAT standard "Curtailment" grey
                            },
                            datasets=["generation", "availability"],
                            format="custom",
                            scope="scenario",
                            width=600,
                            height=240,
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "[list_chart_specs] failed to build curtailment spec for %s: %s",
                        schema,
                        e,
                    )

            # ── System demand breakdown (multi-line scrubber) ──────────────
            # Three concurrent lines per GAT's load decomposition convention:
            #   • Native Load  = end-use demand (StandardLoad/Admittance).
            #     Stored negative in DuckDB by consumption convention → flip sign.
            #   • Charging Load = power flowing INTO storage (batteries,
            #     pumped hydro). Requires the `charging` composed table
            #     (added in gat/simulations/sienna_v1.py; re-ingest needed).
            #   • Net Load = (Native + Charging) - VRE generation → the load
            #     the dispatchable fleet has to cover.
            # VRE groups match gat.config's `curtailable_tech` default.
            if (
                "load" in gat_tables
                and "generation" in gat_tables
                and "catmap__display_group" in gat_tables
            ):
                try:
                    vre_groups = _vre_groups_sql_list()
                    has_charging = "charging" in gat_tables
                    charging_cte = (
                        (
                            f", charging_long AS ("
                            f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__charging "
                            f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id)))"
                            f"), charging_total AS ("
                            f"  SELECT ts, SUM(val) AS mw FROM charging_long GROUP BY ts"
                            f")"
                        )
                        if has_charging
                        else ""
                    )

                    # Three UNION-ALL'd series in long format: (timestamp, series, mw)
                    # scrubber-multi-line picks up `series_axis` and draws one line per.
                    charging_series_sql = (
                        (
                            f"UNION ALL "
                            f"SELECT ts AS timestamp, 'Charging Load' AS series, mw::DOUBLE AS mw "
                            f"FROM charging_total "
                        )
                        if has_charging
                        else ""
                    )

                    # Net Load formula depends on whether charging exists
                    net_load_expr = (
                        "d.demand_mw + COALESCE(c.mw, 0) - COALESCE(v.vre_mw, 0)"
                        if has_charging
                        else "d.demand_mw - COALESCE(v.vre_mw, 0)"
                    )
                    net_load_join = (
                        ("LEFT JOIN charging_total c ON d.ts = c.ts ")
                        if has_charging
                        else ""
                    )

                    charts.append(
                        ChartSpec(
                            name=f"{prefix}__system_demand",
                            display_name=f"System Demand ({s['scenario']})",
                            chart_type="scrubber-multi-line",
                            sql_template=(
                                f"WITH load_long AS ("
                                f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__load "
                                f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id)))"
                                f"), gen_long AS ("
                                f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__generation "
                                f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id)))"
                                f"), total_demand AS ("
                                f"  SELECT ts, -SUM(val) AS demand_mw "
                                f"  FROM load_long GROUP BY ts"
                                f"), vre_gen AS ("
                                f"  SELECT g.ts, SUM(g.val) AS vre_mw "
                                f"  FROM gen_long g "
                                f"  JOIN ext_gat.{prefix}__catmap__display_group cm "
                                f"    ON g.entity_id = cm.entity_id "
                                f"  WHERE cm.category IN ({vre_groups}) "
                                f"  GROUP BY g.ts"
                                f"){charging_cte} "
                                # Series 1: Native Load
                                f"SELECT ts AS timestamp, 'Native Load' AS series, demand_mw::DOUBLE AS mw "
                                f"FROM total_demand "
                                # Series 2: Charging Load (only if composed table exists)
                                f"{charging_series_sql}"
                                # Series 3: Net Load
                                f"UNION ALL "
                                f"SELECT d.ts AS timestamp, 'Net Load' AS series, "
                                f"       ({net_load_expr})::DOUBLE AS mw "
                                f"FROM total_demand d "
                                f"LEFT JOIN vre_gen v ON d.ts = v.ts "
                                f"{net_load_join}"
                                f"ORDER BY timestamp, series"
                            ),
                            chart_options={
                                "time_axis": "timestamp",
                                "value_axis": "mw",
                                "series_axis": "series",
                                "value_unit": "MW",
                                # No y_axis_name — let the chart derive it from
                                # the live `unit` prop so the axis label tracks
                                # the MW/GW/TW selector.
                                "series_colors": {
                                    # Match GAT standard palette
                                    "Native Load": "#000000",  # Demand black
                                    "Charging Load": "#FF4A88",  # Battery pink
                                    "Net Load": "#3F51B5",  # Indigo
                                },
                            },
                            datasets=(
                                ["load", "generation", "charging"]
                                if has_charging
                                else ["load", "generation"]
                            ),
                            format="custom",
                            scope="scenario",
                            width=600,
                            height=260,
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "[list_chart_specs] failed to build system-demand spec for %s: %s",
                        schema,
                        e,
                    )

            # ── Transmission loading average (single-line scrubber) ────────
            # Per-timestamp AVG(|flow|/capacity) across all monitored lines.
            # branch_ratings is materialized at ingest (gat/scenario.py).
            if "line_flow" in gat_tables and "branch_ratings" in gat_tables:
                try:
                    charts.append(
                        ChartSpec(
                            name=f"{prefix}__loading_avg",
                            display_name=f"Avg Transmission Loading ({s['scenario']})",
                            chart_type="scrubber-line",
                            sql_template=(
                                f"WITH flow_long AS ("
                                f"  SELECT entity_id, ts, val FROM ext_gat.{prefix}__line_flow "
                                f"  UNPIVOT (val FOR ts IN (COLUMNS(* EXCLUDE entity_id)))"
                                f") "
                                f"SELECT f.ts AS timestamp, "
                                f"       (AVG(ABS(f.val) / r.rating_mw) * 100)::DOUBLE AS pct "
                                f"FROM flow_long f "
                                f"JOIN ext_gat.{prefix}__branch_ratings r ON f.entity_id = r.name "
                                f"WHERE r.rating_mw > 0 "
                                f"GROUP BY f.ts "
                                f"ORDER BY f.ts"
                            ),
                            chart_options={
                                "time_axis": "timestamp",
                                "value_axis": "pct",
                                "value_unit": "%",
                                "value_label": "Avg Loading",
                                "y_axis_name": "Loading %",
                                "line_color": "#FF7043",  # warm orange
                            },
                            datasets=["line_flow"],
                            format="custom",
                            scope="scenario",
                            width=600,
                            height=240,
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "[list_chart_specs] failed to build loading-avg spec for %s: %s",
                        schema,
                        e,
                    )

            # Stamp project/scenario on every spec built in this iteration so
            # the frontend can filter the charts menu by the active scenario.
            for c in charts[_scenario_start:]:
                c.project = s["project"]
                c.scenario = s["scenario"]

        return charts


def _json_safe(v: Any) -> Any:
    """Convert values to JSON-safe types."""
    if v is None:
        return None
    if isinstance(v, float):
        if v != v:  # NaN
            return None
        return v
    if isinstance(v, (int, str, bool)):
        return v
    return str(v)
