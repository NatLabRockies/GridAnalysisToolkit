"""DuckDB analytical engine for GAT v1.0.0.

GATDatabase manages:
- Ingestion of system and simulation datasets into DuckDB tables
- Transposition of raw simulation tables into composed entity-row tables
- Registration of category maps for GROUP BY operations
- Query building with COLUMNS(* EXCLUDE ...) for efficient aggregation

Storage formats:
- Raw simulation tables: datetime (VARCHAR ISO 8601) | entity_col1 | entity_col2 | ...
  (timestamp rows × entity columns, FLOAT values)
- Composed simulation tables: entity_id | timestamp_col1 | timestamp_col2 | ...
  (entity rows × timestamp columns, FLOAT values — transposed + stacked)
- System tables: entity_id | property_1 | property_2 | ...
- Category map tables: entity_id (VARCHAR) | category (VARCHAR)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
from loguru import logger

from ..categories import CategoryMap, CategoryMapRegistry
from ..datasets import DatasetComposition, DatasetInfo, DatasetKind
from ..interfaces import BaseSimulation, BaseSystem

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore[assignment]


def _require_duckdb() -> None:
    if duckdb is None:
        raise ImportError(
            "duckdb is required for GATDatabase. "
            "Install it with: pip install duckdb"
        )


def _sanitize_table_name(name: str) -> str:
    """Sanitize a dataset name for use as a DuckDB table name."""
    return name.replace("-", "_").replace(".", "_").replace("{", "_").replace("}", "_").replace(" ", "_")


def _create_table_from_df(conn: Any, table_name: str, df: pd.DataFrame) -> None:
    """Materialize a pandas DataFrame into a DuckDB native table.

    Used for small reference data (category maps, etc.) where the storage
    is in DuckDB's native format. Wide simulation outputs use the
    Parquet+view path on GATDatabase instead (see _write_parquet_and_view).
    """
    conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM df")


def _is_s3_uri(uri: str) -> bool:
    return uri.startswith("s3://") or uri.startswith("s3a://")


def _strip_scheme(url: str) -> str:
    """DuckDB's ``s3_endpoint`` expects ``host:port`` without the URL
    scheme. Callers typically supply the full URL — normalize."""
    for prefix in ("https://", "http://"):
        if url.startswith(prefix):
            return url[len(prefix):].rstrip("/")
    return url.rstrip("/")


def configure_httpfs(conn: Any) -> None:
    """Load DuckDB's httpfs extension on ``conn`` and apply the S3
    credentials from the standard AWS env vars.

    Must be called on **every** DuckDB connection that needs to query
    s3:// URIs — settings are per-connection in DuckDB. The write
    connection used during ingest (GATDatabase) calls this in its
    __init__; any long-lived read connection that ATTACHes the GAT DB
    needs to call it too, otherwise SELECT against a view pointing at
    s3:// fails.

    Server deployments can pre-stage the httpfs extension in their
    image so the LOAD doesn't trigger a runtime download from
    extensions.duckdb.org. Otherwise the first call may install on
    demand; subsequent calls use the cache.
    """
    import os
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    access = os.environ.get("AWS_ACCESS_KEY_ID")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
    # Skip the LOAD entirely when no S3 backend is configured (desktop /
    # local dev). httpfs is only useful for reading s3:// view URIs and
    # the INSTALL touches extensions.duckdb.org — that's wasted work
    # offline and may emit a confusing warning.
    if not (endpoint and access and secret):
        logger.debug("DuckDB httpfs skipped (no S3 credentials configured)")
        return
    try:
        conn.execute("INSTALL httpfs")
        conn.execute("LOAD httpfs")
    except Exception as e:
        logger.warning("Could not load DuckDB httpfs extension: {}", e)
        return

    conn.execute(f"SET s3_endpoint='{_strip_scheme(endpoint)}'")
    conn.execute("SET s3_url_style='path'")
    conn.execute(
        f"SET s3_use_ssl={'true' if endpoint.startswith('https://') else 'false'}"
    )
    conn.execute(f"SET s3_access_key_id='{access}'")
    conn.execute(f"SET s3_secret_access_key='{secret}'")
    conn.execute("SET s3_region='us-east-1'")
    logger.info("DuckDB httpfs configured for {}", endpoint)


def _s3_storage_options() -> dict[str, Any]:
    """Pandas/fsspec-style options for writing to S3-compatible storage.

    Reads the standard AWS env vars (AWS_ACCESS_KEY_ID /
    AWS_SECRET_ACCESS_KEY / AWS_ENDPOINT_URL_S3), which S3-compatible
    deployments are expected to provide so boto3 picks them up by
    convention. Returns an empty dict when no S3 config is present
    (e.g. local dev) so callers can blindly pass it through.
    """
    import os
    access = os.environ.get("AWS_ACCESS_KEY_ID")
    secret = os.environ.get("AWS_SECRET_ACCESS_KEY")
    if not (access and secret):
        return {}
    opts: dict[str, Any] = {
        "key": access,
        "secret": secret,
        # Some S3-compatible object stores return 500 on PutObject when
        # aiobotocore sends the newer ``x-amz-checksum-crc32`` /
        # ``x-amz-sdk-checksum-algorithm`` headers (botocore >=1.36
        # default). Tell the client to only compute integrity hashes
        # when the request *requires* them (multipart, etc.) rather
        # than on every PUT.
        "config_kwargs": {
            "request_checksum_calculation": "when_required",
            "response_checksum_validation": "when_required",
        },
    }
    endpoint = os.environ.get("AWS_ENDPOINT_URL_S3")
    if endpoint:
        opts["client_kwargs"] = {"endpoint_url": endpoint}
    return opts


def _write_parquet(view_uri: str, df: pd.DataFrame) -> None:
    """Materialize a wide DataFrame to Parquet at ``view_uri``.

    Why not a native DuckDB table: each native column carries its own
    metadata, dictionary, and zonemap. For wide simulation outputs
    (10k entity columns) that bookkeeping dominates ingest time —
    seconds per dataset. Parquet's wide-table writer pays a similar
    per-column cost but in C with much tighter constants, and on the
    read side DuckDB's Parquet scanner pushes column projection down
    to the file so `SELECT datetime, ACBus_1 FROM view` reads only
    those two columns' pages off disk.

    ``view_uri`` may be a local filesystem path or an ``s3://`` URI.
    For S3, pandas auto-detects via fsspec/s3fs.

    This function is **lock-free by design**: it takes no DuckDB
    connection and performs only file I/O. Callers that serialize DB
    access (the server's ingest path under a shared write lock) can
    invoke this without holding the lock, then briefly take the lock
    to register a view over the resulting file via ``_register_view``.
    """
    if _is_s3_uri(view_uri):
        df.to_parquet(
            view_uri,
            compression="zstd",
            index=False,
            storage_options=_s3_storage_options(),
        )
    else:
        # Local filesystem — make sure the directory exists.
        out_path = Path(view_uri)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(out_path, compression="zstd", index=False)


def _register_view(conn: Any, schema: str, view_name: str, view_uri: str) -> None:
    """Register ``{schema}.{view_name}`` as a DuckDB view over the parquet
    file at ``view_uri``. Fast (sub-millisecond) DB-only operation —
    pair with ``_write_parquet`` to do the slow I/O outside any lock.

    DuckDB's httpfs extension handles the reads at query time for s3:// URIs.
    No local copy lives on the pod's disk — pod-restart-safe by construction.
    """
    qualified = _quote_qualified(schema, view_name)
    conn.execute(
        f"CREATE OR REPLACE VIEW {qualified} AS SELECT * FROM '{view_uri}'"
    )


def _write_parquet_and_view(
    conn: Any,
    schema: str,
    view_name: str,
    view_uri: str,
    df: pd.DataFrame,
) -> None:
    """Legacy combined helper — writes parquet then registers view.

    Kept for callers that already hold a write connection for the
    full ingest and don't care about lock granularity (CLI, tests).
    New code should call ``_write_parquet`` lock-free and batch
    ``_register_view`` calls into a brief locked window.
    """
    _write_parquet(view_uri, df)
    _register_view(conn, schema, view_name, view_uri)


def _quote_ident(name: str) -> str:
    """Quote a SQL identifier for DuckDB, escaping embedded double quotes.

    Dataset names sourced from PLEXOS properties (e.g. "Start & Shutdown
    Cost") land here after sanitization and can still contain characters
    that aren't valid in a bare identifier — quoting keeps them from
    breaking CREATE/SELECT statements built via f-string interpolation.
    """
    return '"' + name.replace('"', '""') + '"'


def _quote_qualified(schema: str, name: str) -> str:
    """Build a schema-qualified, quoted DuckDB identifier: "schema"."name"."""
    return f"{_quote_ident(schema)}.{_quote_ident(name)}"


_quote_col = _quote_ident


class GATDatabase:
    """DuckDB analytical engine for GAT.

    Manages ingestion of parsed datasets, transposition of composed tables,
    category map registration, and grouped query execution.

    Args:
        path: Path to a DuckDB database file. None for in-memory.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        _require_duckdb()
        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = duckdb.connect(str(path))
            # Local fallback location for parquet files when no canonical
            # URI is set via ``set_parquet_root``. Sibling to the DB so it
            # lives and dies with it. In K8s/S3 deployments, callers should
            # supply an s3:// URI via set_parquet_root; this path is used
            # as a default only for local dev / tests.
            self._local_parquet_root: Path = path.parent / f"{path.name}.parquet"
        else:
            self._conn = duckdb.connect()
            import tempfile
            self._local_parquet_root = Path(tempfile.mkdtemp(prefix="gat_parquet_"))
        self._local_parquet_root.mkdir(parents=True, exist_ok=True)

        # Canonical parquet root for the active ingest, set by callers via
        # set_parquet_root() before each Scenario.ingest(). Typically an
        # s3:// URI in production or a local path in dev. ``None`` means
        # "use the local fallback".
        self._parquet_root_uri: str | None = None

        # Optional pluggable write-connection provider. When the server
        # runs ingest under a shared lock, it sets this to a callable
        # that briefly acquires the lock, detaches the read attachment,
        # opens a writable handle, runs the user's ``fn(conn)`` against
        # it, then closes and reattaches. Net effect: each DB-touching
        # block is locked for milliseconds, not for the whole ingest.
        # When unset (CLI, tests, notebooks) we fall back to executing
        # against ``self._conn`` directly — single-tenant behavior is
        # preserved.
        self._write_provider: "Callable[[Callable[[Any], Any]], Any] | None" = None

        configure_httpfs(self._conn)
        self._category_registries: dict[str, CategoryMapRegistry] = {}

    def set_write_provider(
        self,
        provider: "Callable[[Callable[[Any], Any]], Any] | None",
    ) -> None:
        """Inject a callable that supplies a writable DuckDB connection
        for the duration of a single ``fn(conn)`` invocation.

        Server callers wrap this around their lock + detach/reattach
        dance so each call ends up holding the lock only briefly. CLI
        and test callers leave it unset; writes then go through
        ``self._conn`` directly.
        """
        self._write_provider = provider

    def with_write_conn(self, fn: "Callable[[Any], Any]") -> Any:
        """Execute ``fn(conn)`` against a writable connection. When a
        provider is set, it owns lifecycle (locking, detach/reattach,
        open/close). Otherwise ``self._conn`` is used directly.

        Group related DB operations into one ``with_write_conn`` call
        so the provider's lock-acquire / detach / reattach overhead
        amortizes — many small calls multiply that overhead.
        """
        if self._write_provider is not None:
            return self._write_provider(fn)
        return fn(self._conn)

    def set_parquet_root(self, root: str | None) -> None:
        """Override the parquet write location for subsequent ingest calls.

        ``root`` is the URI under which dataset files are written and
        referenced. Pass ``None`` to fall back to the local DB-sibling
        directory (dev mode). Should be set fresh per (scenario, model)
        ingest — typically ``{scenario_root}/parquet/{model_name}``.
        """
        self._parquet_root_uri = root.rstrip("/") if root else None

    def _parquet_uri_for(self, view_name: str) -> str:
        """Build the absolute URI for a single parquet file."""
        if self._parquet_root_uri is None:
            return (self._local_parquet_root / f"{view_name}.parquet").as_posix()
        return f"{self._parquet_root_uri}/{view_name}.parquet"


    def get_connection(self) -> Any:
        """Return the raw DuckDB connection for direct SQL access."""
        return self._conn

    def close(self) -> None:
        """Close the DuckDB connection."""
        self._conn.close()

    # ------------------------------------------------------------------ #
    # Schema management
    # ------------------------------------------------------------------ #

    def _ensure_schema(self, schema: str) -> None:
        self._conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}")

    # ------------------------------------------------------------------ #
    # System ingestion
    # ------------------------------------------------------------------ #

    def ingest_system(self, schema: str, system: BaseSystem) -> None:
        """Ingest all system datasets into DuckDB.

        Raw system datasets → {schema}.sys__{name}
        Composed system datasets → {schema}.sys__{name} (concatenation)

        Two-phase: read every DataFrame from the parser first (no DB),
        then a single ``with_write_conn`` invocation creates the schema
        and all tables. Server callers hold the shared write lock only
        for the brief Phase B; the (HDF5 / JSON / spatial) parser work
        in Phase A is lock-free.
        """
        import time as _time
        datasets = system.list_datasets()

        # Phase A — read everything from the system parser (no DB). Each
        # entry is (timing-label, kind, ds_name, df). Order matters: raw
        # before composed (so composed materializations can reference
        # the raw tables in Phase B).
        raw_entries: list[tuple[str, pd.DataFrame, float, float]] = []
        for ds in datasets:
            if ds.kind == DatasetKind.RAW_SYSTEM:
                _t_read = _time.perf_counter()
                df = system.get_dataset(ds.name)
                df = _cast_floats_to_f32(df)
                _t_after_read = _time.perf_counter()
                raw_entries.append((ds.name, df, _t_read, _t_after_read))

        composed_entries: list[tuple[str, pd.DataFrame, float, float]] = []
        for ds in datasets:
            if ds.kind == DatasetKind.COMPOSED:
                _t_read = _time.perf_counter()
                df = system.get_dataset(ds.name)
                df = _cast_floats_to_f32(df)
                _t_after_read = _time.perf_counter()
                composed_entries.append((ds.name, df, _t_read, _t_after_read))

        bus_coords_df: pd.DataFrame | None = None
        try:
            bc = system.get_bus_coordinates()
            if len(bc) > 0:
                bus_coords_df = bc
        except Exception as e:
            logger.debug("Could not read bus coordinates: {}", e)

        branch_endpoints_df: pd.DataFrame | None = None
        try:
            get_endpoints = getattr(system, "get_branch_endpoints", None)
            if get_endpoints is not None:
                be = get_endpoints()
                if len(be) > 0:
                    branch_endpoints_df = be
        except Exception as e:
            logger.debug("Could not read branch endpoints: {}", e)

        # Phase B — one locked window: schema + every native table.
        def _do_db_ops(conn: Any) -> None:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}")

            for ds_name, df, t_read, t_after_read in raw_entries:
                t_write = _time.perf_counter()
                table_name = _quote_qualified(schema, f"sys__{_sanitize_table_name(ds_name)}")
                _create_table_from_df(conn, table_name, df)
                t_done = _time.perf_counter()
                logger.info(
                    "[ingest-timing] sys raw '{}' rows={} read={:.2f}s write={:.2f}s",
                    ds_name, len(df), t_after_read - t_read, t_done - t_write,
                )

            for ds_name, df, t_read, t_after_read in composed_entries:
                t_write = _time.perf_counter()
                table_name = _quote_qualified(schema, f"sys__{_sanitize_table_name(ds_name)}")
                _create_table_from_df(conn, table_name, df)
                t_done = _time.perf_counter()
                logger.info(
                    "[ingest-timing] sys composed '{}' rows={} read={:.2f}s write={:.2f}s",
                    ds_name, len(df), t_after_read - t_read, t_done - t_write,
                )

            if bus_coords_df is not None:
                table_name = _quote_qualified(schema, "bus_coordinates")
                _create_table_from_df(conn, table_name, bus_coords_df)
                logger.info(
                    "Stored {} bus coordinates → {}",
                    len(bus_coords_df), table_name,
                )

            if branch_endpoints_df is not None:
                table_name = _quote_qualified(schema, "branch_endpoints")
                _create_table_from_df(conn, table_name, branch_endpoints_df)
                logger.info(
                    "Stored {} branch endpoints → {}",
                    len(branch_endpoints_df), table_name,
                )

        self.with_write_conn(_do_db_ops)

    # ------------------------------------------------------------------ #
    # Simulation ingestion
    # ------------------------------------------------------------------ #

    def ingest_simulation(
        self,
        schema: str,
        sim: BaseSimulation,
        dataset_filter: "Callable[[DatasetInfo], bool] | None" = None,
    ) -> None:
        """Ingest simulation datasets into DuckDB.

        Raw simulation datasets → {schema}.sim__{name}
          (timestamp rows × entity columns, natural parser format)

        Composed simulation datasets → {schema}.{name}
          (entity rows × timestamp columns, transposed + stacked)

        ``dataset_filter`` selects which datasets get ingested in this
        call. Defaults to "everything". Callers in the upload path use
        it to split work across tiers — tier-1 ingests just the
        datasets a client needs for its initial view, tier-2 picks up
        the rest in a background job.

        Structure: parquet writes are pure file I/O and run **outside**
        ``with_write_conn`` so server callers don't hold the shared
        write lock across the slow part. DB-side work (schema + view
        registrations, composed table builds) is batched into a single
        ``with_write_conn`` invocation so the provider's per-call
        overhead amortizes.
        """
        import time as _time
        datasets = sim.list_datasets()
        keep = dataset_filter if dataset_filter is not None else (lambda _ds: True)

        # Phase A — lock-free parquet writes for raw datasets. An earlier
        # experiment with a depth-2 read/write pipeline (1 reader thread,
        # main thread writes) was a wash — reads and writes contend for
        # the same physical disk (HDF5 in, Parquet out) so overlap gains
        # are cancelled by slower individual ops. Kept simple here.
        raw_plans: list[tuple[str, str, str, int, int, float, float, float]] = []
        for ds in datasets:
            if ds.kind != DatasetKind.RAW_SIMULATION:
                continue
            if not keep(ds):
                continue
            _t_read = _time.perf_counter()
            df = sim.get_dataset(ds.name)
            df = _prepare_sim_dataframe(df)
            _t_write = _time.perf_counter()
            view_name = f"sim__{_sanitize_table_name(ds.name)}"
            uri = self._parquet_uri_for(view_name)
            _write_parquet(uri, df)
            _t_done = _time.perf_counter()
            raw_plans.append((
                ds.name, view_name, uri,
                len(df), len(df.columns),
                _t_read, _t_write, _t_done,
            ))

        for ds_name, _vn, _u, n_rows, n_cols, t_read, t_write, t_done in raw_plans:
            logger.info(
                "[ingest-timing] sim raw '{}' rows={} cols={} read={:.2f}s write={:.2f}s",
                ds_name, n_rows, n_cols, t_write - t_read, t_done - t_write,
            )

        # Phase B — one locked window: schema + view registrations +
        # composed table builds. All DB-side, no slow I/O.
        ingested_raw_names = {p[0] for p in raw_plans}
        composed_to_build: list[DatasetInfo] = []
        for ds in datasets:
            if ds.kind != DatasetKind.COMPOSED or not ds.source_datasets:
                continue
            if not keep(ds):
                continue
            missing = [s for s in ds.source_datasets if s not in ingested_raw_names]
            if missing:
                logger.info(
                    "[ingest-timing] sim composed '{}' skipped (sources not in this tier: {})",
                    ds.name, missing,
                )
                continue
            composed_to_build.append(ds)

        def _do_db_ops(conn: Any) -> None:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}")
            for _ds_name, view_name, uri, *_ in raw_plans:
                _register_view(conn, schema, view_name, uri)
            for ds in composed_to_build:
                _t_start = _time.perf_counter()
                self._build_composed_simulation_on(conn, schema, ds)
                logger.info(
                    "[ingest-timing] sim composed '{}' sources={} pivot={:.2f}s",
                    ds.name, len(ds.source_datasets),
                    _time.perf_counter() - _t_start,
                )

        self.with_write_conn(_do_db_ops)

    def _build_composed_simulation(
        self, schema: str, ds: DatasetInfo
    ) -> None:
        """Public-ish entry point preserved for direct callers (CLI,
        tests). Routes through ``with_write_conn`` so server callers
        still get lock-aware execution; CLI callers fall through to
        ``self._conn``."""
        self.with_write_conn(
            lambda conn: self._build_composed_simulation_on(conn, schema, ds)
        )

    def _build_composed_simulation_on(
        self, conn: Any, schema: str, ds: DatasetInfo
    ) -> None:
        """Build a composed simulation table by transposing and stacking
        raw simulation tables, against an explicit ``conn``. Pulled out
        of ``_build_composed_simulation`` so the batched ingest path
        can call it inside a single ``with_write_conn`` window without
        re-acquiring the lock per composed dataset.

        Steps:
        1. UNPIVOT each source table → (datetime, entity_id, value)
        2. UNION ALL across sources
        3. PIVOT on datetime → entity_id | t0 | t1 | ...
        4. Store as materialized table
        """
        composed_name = _quote_qualified(schema, _sanitize_table_name(ds.name))
        source_tables = [
            _quote_qualified(schema, f"sim__{_sanitize_table_name(s)}")
            for s in ds.source_datasets  # type: ignore[union-attr]
        ]

        existing = []
        for st in source_tables:
            try:
                conn.execute(f"SELECT 1 FROM {st} LIMIT 0")
                existing.append(st)
            except Exception:
                logger.warning(
                    "Source table '{}' not found for composed dataset '{}'",
                    st, ds.name,
                )

        if not existing:
            logger.warning(
                "No source tables found for composed dataset '{}'", ds.name
            )
            return

        unpivot_parts = []
        for st in existing:
            unpivot_parts.append(
                f"SELECT * FROM ("
                f"  UNPIVOT {st}"
                f"  ON COLUMNS(* EXCLUDE (datetime))"
                f"  INTO NAME entity_id VALUE value"
                f")"
            )
        union_sql = " UNION ALL ".join(unpivot_parts)

        pivot_sql = (
            f"CREATE OR REPLACE TABLE {composed_name} AS "
            f"PIVOT ({union_sql}) "
            f"ON datetime USING FIRST(value) "
            f"GROUP BY entity_id "
            f"ORDER BY entity_id"
        )

        try:
            conn.execute(pivot_sql)
            count = conn.execute(
                f"SELECT COUNT(*) FROM {composed_name}"
            ).fetchone()[0]
            logger.debug(
                "Built composed dataset '{}' → {} ({} entities)",
                ds.name, composed_name, count,
            )
        except Exception as e:
            logger.error(
                "Failed to build composed dataset '{}': {}", ds.name, e
            )
            raise

    # ------------------------------------------------------------------ #
    # Category maps
    # ------------------------------------------------------------------ #

    def register_category_map(
        self, schema: str, cat_map: CategoryMap
    ) -> None:
        """Register a category map as a DuckDB table.

        The table is stored as {schema}.catmap__{name} with columns
        (entity_id VARCHAR, category VARCHAR).

        Wraps the file/dict/spatial path + count-check in a single
        ``with_write_conn`` window so each cat-map registration costs
        one brief lock acquire (server mode), not one per inner SQL.
        """
        table_name = _quote_qualified(schema, f"catmap__{_sanitize_table_name(cat_map.name)}")

        def _do(conn: Any) -> None:
            conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote_ident(schema)}")
            if cat_map.mapping is not None:
                self._register_dict_map(conn, table_name, cat_map.mapping)
            elif cat_map.mapping_file is not None:
                self._register_file_map(
                    conn, table_name, cat_map.mapping_file,
                    cat_map.entity_column, cat_map.category_column,
                )
            elif cat_map.geometry_file is not None:
                self._register_spatial_map(
                    conn, schema, table_name, cat_map,
                )
            else:
                raise ValueError(
                    f"CategoryMap '{cat_map.name}' has no source "
                    "(mapping, mapping_file, or geometry_file)"
                )
            count = conn.execute(
                f"SELECT COUNT(*) FROM {table_name}"
            ).fetchone()[0]
            logger.debug(
                "Registered category map '{}' → {} ({} entries)",
                cat_map.name, table_name, count,
            )

        self.with_write_conn(_do)

        # Track in the per-schema registry (Python-side, no DB).
        if schema not in self._category_registries:
            self._category_registries[schema] = CategoryMapRegistry()
        self._category_registries[schema].register(cat_map)

    def _register_dict_map(
        self, conn: Any, table_name: str, mapping: dict[str, str]
    ) -> None:
        df = pd.DataFrame(
            list(mapping.items()), columns=["entity_id", "category"]
        )
        _create_table_from_df(conn, table_name, df)

    def _register_file_map(
        self,
        conn: Any,
        table_name: str,
        file_path: str,
        entity_col: str,
        category_col: str,
    ) -> None:
        path = Path(file_path)
        if path.suffix.lower() in (".csv", ".tsv"):
            df = pd.read_csv(path)
        elif path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")

        df = df[[entity_col, category_col]].rename(
            columns={entity_col: "entity_id", category_col: "category"}
        )
        _create_table_from_df(conn, table_name, df)

    def _register_spatial_map(
        self,
        conn: Any,
        schema: str,
        table_name: str,
        cat_map: CategoryMap,
    ) -> None:
        """Register a spatial category map via DuckDB spatial extension.

        Requires:
        - A geometry file (shapefile/GeoJSON)
        - A system dataset with lat/lon columns (specified by join_via)
        - A key column in the geometry to use as the category label
        """
        conn.execute("INSTALL spatial")
        conn.execute("LOAD spatial")

        geom_path = cat_map.geometry_file
        geom_key = cat_map.geometry_key
        join_table = _quote_qualified(schema, f"sys__{_sanitize_table_name(cat_map.join_via)}")

        conn.execute(
            f"CREATE OR REPLACE TEMP TABLE _spatial_geom AS "
            f"SELECT * FROM ST_Read('{geom_path}')"
        )

        conn.execute(f"""
            CREATE OR REPLACE TABLE {table_name} AS
            SELECT j.entity_id, g.{_quote_col(geom_key)} as category
            FROM {join_table} j
            JOIN _spatial_geom g
            ON ST_Contains(g.geom, ST_Point(j.longitude, j.latitude))
        """)

        conn.execute("DROP TABLE IF EXISTS _spatial_geom")

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #

    def query(self, sql: str) -> pd.DataFrame:
        """Execute arbitrary SQL and return a DataFrame."""
        return self._conn.execute(sql).fetchdf()

    def query_grouped(
        self,
        schema: str,
        dataset: str,
        group_by: list[str],
    ) -> pd.DataFrame:
        """Query a composed dataset with category map grouping.

        Builds a CTE that JOINs the dataset with category maps, then
        uses COLUMNS(* EXCLUDE ...) for efficient SUM across all
        timestamp columns.

        Args:
            schema: DuckDB schema name
            dataset: Composed dataset name (e.g. "generation")
            group_by: List of category map names to group by

        Returns:
            Wide DataFrame: category columns + timestamp columns with SUMs
        """
        table = _quote_qualified(schema, _sanitize_table_name(dataset))

        # Build JOIN clauses and select aliases for category columns
        join_clauses = []
        select_aliases = []
        exclude_cols = ["entity_id"]

        for i, cat_name in enumerate(group_by):
            cat_table = _quote_qualified(schema, f"catmap__{_sanitize_table_name(cat_name)}")
            alias = f"cm{i}"
            col_alias = _sanitize_table_name(cat_name)
            join_clauses.append(
                f"JOIN {cat_table} {alias} ON g.entity_id = {alias}.entity_id"
            )
            select_aliases.append(f"{alias}.category AS {_quote_col(col_alias)}")
            exclude_cols.append(col_alias)

        joins = "\n    ".join(join_clauses)
        cat_selects = ", ".join(select_aliases)
        exclude = ", ".join(_quote_col(c) for c in exclude_cols)
        group_cols = ", ".join(_quote_col(_sanitize_table_name(c)) for c in group_by)

        sql = f"""
WITH joined AS (
    SELECT {cat_selects}, g.*
    FROM {table} g
    {joins}
)
SELECT {group_cols}, SUM(COLUMNS(* EXCLUDE ({exclude})))
FROM joined
GROUP BY {group_cols}
ORDER BY {group_cols}
"""
        logger.trace("Grouped query:\n{}", sql)
        return self._conn.execute(sql).fetchdf()

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def list_tables(self, schema: str) -> list[str]:
        """List all tables in a schema."""
        result = self._conn.execute(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema = '{schema}'"
        ).fetchdf()
        return result["table_name"].tolist()

    def list_category_maps(self, schema: str) -> list[str]:
        """List registered category map names for a schema."""
        if schema in self._category_registries:
            return self._category_registries[schema].list_maps()
        return []

    def get_category_registry(self, schema: str) -> CategoryMapRegistry:
        """Get the CategoryMapRegistry for a schema."""
        if schema not in self._category_registries:
            self._category_registries[schema] = CategoryMapRegistry()
        return self._category_registries[schema]

    def get_timestamp_columns(self, schema: str, table: str) -> list[str]:
        """Return timestamp column names for a composed simulation table.

        These are all columns except entity_id.
        """
        table_name = f"{schema}.{_sanitize_table_name(table)}"
        result = self._conn.execute(
            f"SELECT column_name FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' "
            f"AND table_name = '{_sanitize_table_name(table)}' "
            f"AND column_name != 'entity_id'"
        ).fetchdf()
        return result["column_name"].tolist()


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _cast_floats_to_f32(df: pd.DataFrame) -> pd.DataFrame:
    """Cast float64 columns to float32 to reduce memory."""
    float_cols = df.select_dtypes(include=[np.float64]).columns
    if len(float_cols) > 0:
        df = df.copy()
        df[float_cols] = df[float_cols].astype(np.float32)
    return df


def _prepare_sim_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Prepare a simulation DataFrame for DuckDB ingestion.

    - Converts DatetimeIndex to an ISO 8601 string 'datetime' column
    - Casts float64 values to float32
    """
    df = df.copy()

    # Convert DatetimeIndex to ISO string column
    if isinstance(df.index, pd.DatetimeIndex):
        df.index.name = "datetime"
        df = df.reset_index()
        df["datetime"] = df["datetime"].dt.strftime("%Y-%m-%dT%H:%M:%S")
        # Preserve timezone if present
        if hasattr(df.index, "tz") and df.index.tz is not None:
            # Already handled by strftime with tz-aware datetimes
            pass

    # Cast floats to float32
    float_cols = df.select_dtypes(include=[np.float64]).columns
    if len(float_cols) > 0:
        df[float_cols] = df[float_cols].astype(np.float32)

    return df
