# Changelog

## [0.1.1](https://github.com/NatLabRockies/GridAnalysisToolkit/compare/nlr-gat-v0.1.0...nlr-gat-v0.1.1) (2026-08-04)


### Features

* per-format install extras (nlr-gat[sienna|plexos|reeds|...]) ([3fa7d90](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/3fa7d90acc2b94768fc708f9296e88a74f3ffaff))
* PJM 5-bus long-horizon fixture (SIM_SYSTEM=pjm5) ([6c9d379](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/6c9d37964f01dfa9c3872d3581d184dbfea94a51))
* solve the sienna fixture with DCPPowerModel to produce line flows ([d2da7fe](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/d2da7fe1019b5b4422099b4151cd83cfa10a52ec)), closes [#4](https://github.com/NatLabRockies/GridAnalysisToolkit/issues/4)


### Bug Fixes

* add pyarrow to the plexos extra (needed by the duckdb engine) ([d4818ec](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/d4818ec752d913476dba324a52eb5eaf90a2912b))
* enable balance slacks for the DCP network model ([a2db2eb](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/a2db2ebae1698228099253c0fc179a75dd77e1ce))
* expand '~' in solution-file paths; fail clearly when nothing resolves ([9eac893](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/9eac8938bc2c3cdc80de437e37db356e8884bcdc)), closes [#25](https://github.com/NatLabRockies/GridAnalysisToolkit/issues/25)
* route component-list diagnostics through the logger ([fa7f159](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/fa7f15998860196ef2f07861ee25ddafb6ec94f3))


### Refactoring

* adopt src layout (gat/ -&gt; src/gat/) ([1840f76](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/1840f761aed265fca1589293fee6114af34c5484))


### Documentation

* add API-stability and H5PLEXOS.jl deprecation warning boxes to README ([407ea72](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/407ea72c0828bb319850ae3236ccc5fd7e521799))
* add model-vs-model comparison gallery example (UC / ED / Emulator) ([e1f9b84](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/e1f9b84946ea0a0071779a04c36e864d1f0693c4))
* add status badges to README ([d6e1c24](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/d6e1c24c7735f02691a99c5b7496d4bf8ffae380))
* add v0.1.1 changelog entry ([bfe5754](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/bfe5754bb005baeed8844887b38e96a7b9e99291))
* consistent Toolkit branding and lab naming; disclaimer section ([3c62084](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/3c62084bbae9610f88ee295d53a4330a95f4a75e))
* guard Plexos gallery example when no fixture is available ([b48b4cf](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/b48b4cf3155575053f32a646b2e09906dcbfaed8))
* README warning boxes — API stability + H5PLEXOS.jl deprecation ([b1353f4](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/b1353f4a1a103f3fa17eb1e3c54f59101b0fa9cb))
* update repository URLs after rename to GridAnalysisToolkit ([d993fcf](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/d993fcf957aa9cb10fb6dc111d565862a18f0d30))


### CI/CD

* automated releases via release-please (modeled on R2X) ([2fd9724](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/2fd972451d23d0a71546035bac40a85e9e6c9dab))
* automated releases via release-please (modeled on R2X) ([2eea598](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/2eea5984e4a841b63f7c5e1eeab197e698919e9d))
* enforce black formatting and minimal ruff lint gate ([2158ccf](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/2158ccf055d656128261f97963992a2cdb5c12e3)), closes [#2](https://github.com/NatLabRockies/GridAnalysisToolkit/issues/2)
* exclude README from the sienna fixture cache key ([f9f8b5d](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/f9f8b5d37e576a4b7e25ec578c19bd72c66c2c2b))
* install the 'all' extra for the Sphinx docs build ([bbc1172](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/bbc1172c2fdb86ab2c5fdb2da44cde91640b0bcb))
* publish to PyPI via trusted publishing on release ([4653d0e](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/4653d0e3dc1b72700b6a8e06c0fd00525f8f7f4b))


### Tests

* regenerate baselines against main's refreshed fixture cache ([8a86c3a](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/8a86c3ace49978d8ccb218248e426b3e857badd7))
* regenerate baselines against the DCP-solved fixture ([509ebcc](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/509ebcc01179e2cf233fd0e044d8bf45f9a115a1))
* regenerate sienna v4 baselines against the public repo's CI fixture ([e9d1a59](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/e9d1a593e4e366778fffa53184d305a5bc72fbdb))
* regenerate sienna v4 baselines against the refreshed CI fixture ([e4b1dcb](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/e4b1dcb5819c73a108776c7b9def1c4bf31c1682))
* regenerate v4 baselines against main's refreshed fixture cache ([452e1f9](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/452e1f9dcb65a9c0c57d6a29b7e1962f531740c6))
* regenerate v4 baselines against this PR's fixture build ([4f7616a](https://github.com/NatLabRockies/GridAnalysisToolkit/commit/4f7616a30a071241e6821cefcacaadff63da7f8c))

## [v0.1.1] - Unreleased

First changelog entry since the public release split — entries before
this point (including the "v1.0.0" one below) are from GAT's internal
pre-OSS versioning and don't correspond to a published PyPI release.
Public releases are versioned from `v0.1.0` onward.

### Changed — breaking

- **Install extras split by format.** `pip install nlr-gat` alone now
  installs only the format-agnostic core — no scenario handler is
  usable until you also install `sienna`, `plexos`, and/or `reeds`
  (plus `plots` for `gat.quickplots`). Previously every dependency
  (h5py, geopandas, duckdb, polars, matplotlib, pyarrow) was installed
  unconditionally. See the README's install table, or use
  `pip install "nlr-gat[all]"` to keep the old everything-installed
  behavior.

### Fixed

- **`PlexosScenario`/`SiennaScenario`/`ReEDsScenario` silently failed to
  resolve `~`-prefixed paths.** `os.path.isdir`/`isfile`/`glob` never
  expand `~` — a literal `"~/..."` string resolved to zero files, and
  `PlexosScenario` then crashed later with a confusing, unrelated
  `AttributeError` instead of a clear error. Fixed in every
  `_find_solution_files` implementation; `PlexosScenario` now raises
  `FileNotFoundError` immediately, naming the input, when nothing
  resolves.
- Two dead, shadowed `_find_solution_files` method definitions removed
  (`base.py`, `reeds.py` each defined the method twice in one class).

### Deprecated

- Support for PLEXOS solution files produced by H5PLEXOS.jl (`.h5`)
  will be removed in **v0.2.0**. Load native PLEXOS `Solution.zip`
  files through the DuckDB-backed engine instead
  (`pip install "nlr-gat[plexos]"`).

### Removed

- `EGRETScenario` and its documentation page — unmaintained, zero test
  coverage, and no consumers beyond its own module.

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
