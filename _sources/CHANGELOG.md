# Changelog

## [v1.0.0] - 2026-05-29

### Fixed

- **`BaseScenario.get_area_dispatch` raised `ValueError` on Plexos scenarios
  with no unserved energy or empty storage charging.** The include-flag gates
  used `df == NotImplemented` and `type(x) == type(NotImplemented)`, which
  evaluate element-wise on a DataFrame and then fail the truthiness check.
  Replaced with a `_missing()` helper using `is NotImplemented` plus an
  empty-DataFrame check; the same fix applies to the `get_area_unserved`
  return-value test.

### Added

#### Sienna scaling — h5 group attrs as the source of truth

- `SiennaSimulationParser.get_decision_model_base_power(model_name)` reads
  `base_power` from the per-decision-model h5 group attrs. Falls back to
  `sys.json` `units_settings.base_value`, then `100.0`. Decision models can
  legitimately differ from the system-level base; the simulation file is
  authoritative for simulation results.
- `SiennaSimulationParser.get_raw_dataset(key)` and
  `SiennaScenario.get_raw_dataset(key)` — return an h5 dataset as an
  unscaled DataFrame, accepting either a short alias or a full h5 path. Use
  the high-level `get_*` methods for scaled (MW) values; this API is for
  inspection or callers who want to apply their own scaling.

See [Sienna scaling and raw dataset access](sienna_scaling.md).

#### v1 architecture scaffolding for Plexos

- `gat.systems.PlexosSystem` and `gat.simulations.PlexosSimulation`
  implement the v1 `BaseSystem` / `BaseSimulation` interfaces, wrapping the
  existing `PlexosParser`. `PlexosSystem.get_default_category_maps()` exposes
  generator → area (and optionally generator → tech) `CategoryMap`s; the
  simulation surfaces a `generation` composed dataset.
- End-to-end POC test in `tests/handlers/test_plexos_v1_migration.py`
  ingests plexos data into `GATDatabase`, queries via `query_grouped`, and
  asserts area-aggregated generation matches the legacy pandas path within
  `rel=1e-4`. This locks in the migration pattern; remaining `get_*`
  methods on the legacy handlers will follow the same shape.

See [v1 migration pattern](architecture/v1_migration_pattern.md).

#### Testing pipeline

- `pytest-regressions` snapshot tests for handler outputs:
  `tests/handlers/test_plexos_regression.py` and
  `tests/handlers/test_sienna_regression.py`. Snapshots define the contract
  the future duckdb migration must match. Regenerate with `--force-regen`.
- CI matrix (Python 3.10 / 3.12) with cached Sienna fixture generation via
  Docker (`make sienna-fixture-v4`). Release workflow builds and uploads
  wheels to GitHub Releases.
- `tests/conftest.py` — shared fixture-root resolution
  (`plexos_fixture_root`, `sienna_v4_fixture_root`) with environment
  override and skip-if-missing semantics.

#### Configuration backwards-compatibility

- `SiennaScenarioConfig` now accepts both the structured v1 API
  (`system=SystemConfig(path=...)`, `simulation=SimulationConfig(paths=...)`)
  and the legacy flat API (`system_path=`, `simulation_paths=`). A
  `@model_validator(mode="before")` rewrites flat kwargs to the structured
  form on input; read-side `system_path` / `simulation_paths` properties
  expose the structured fields for callers that still expect flat.
- Legacy aliases on handler constructors: `SiennaScenario(metadata_file=)`,
  `ReEDsScenario(path=)`, `PlexosScenario(solution_path=)` — all map to
  `simulation_files=` internally.

#### CLI and project management

- Hierarchical CLI command structure for project, scenario, and palette management
- Project-based workflow with git collaboration support
- Scenario management: `add`, `remove`, `list`, `show` subcommands
- Palette management: `add`, `remove`, `list`, `show` subcommands
- `gat project scenario list` lists all scenarios across all projects or
  filters by a specific project ID
- User metadata system for lightweight project references
- Support for Sienna, ReEDS, and Plexos scenarios

#### Simulation and system abstraction

- Scenarios now distinguish between simulation types (UC, ED, PF) within
  a single H5 file; `simulation_type` field added to `SiennaScenarioConfig`
- CLI auto-discovers all simulation types in an H5 file and creates
  separate scenarios (`base_UC`, `base_ED`, etc.)
- `SiennaScenarioConfig.discover_simulations()` and
  `create_scenarios_for_all_simulations()` for programmatic discovery
- `SimulationAggregator` — generic aggregator for any `BaseSimulationParser`
  with parallel loading (multiprocessing) and configurable merge strategies
  for overlapping time windows

### Changed

- Migrated CLI from flat command structure to hierarchical subcommands
  (`gat project add-scenario` → `gat project scenario add`, etc.)
- All scenario paths stored as absolute paths instead of relative paths
- Scenario listing displays simulation type for Sienna scenarios:
  `base_UC  base (UC)  [sienna] [UC]`

### Deprecated

- Direct instantiation of `SiennaScenario`, `PlexosScenario`,
  `ReEDsScenario`, `FileScenario`, `MultiScenario` now emits a
  `DeprecationWarning` recommending `gat.load(...)`. The classes still work
  and their public DataFrame-returning API is preserved across the
  migration; only the construction path is changing.

See [Legacy scenario handler deprecation](legacy_handler_deprecation.md).

### Removed

- **`example_data/` is no longer tracked.** The directory is now in
  `.gitignore` (~795 MB of binaries). Sienna fixtures regenerate via
  `make sienna-fixture-v4` (requires Docker; see
  `docker/sienna/README.md`). For Plexos, set the
  `GAT_PLEXOS_FIXTURE` environment variable to a directory containing
  your own `.h5` solution files.
- **`docs/source/api/cli/extensions.md`** — content rolled into the
  new [Custom plots and the reporting framework](extending_plots.md) page.
- **8 stale top-level `docs/*.md`** files predating the current
  `AggregateDataset`/`DatasetConfig` schemas.

---

## Prior Versions

See git history for changes prior to v1.0.0.
