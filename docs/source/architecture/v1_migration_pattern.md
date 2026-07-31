# v1 migration pattern: wrapping a tool for `GATDatabase`

This page documents the pattern for getting a power-system tool's data into
GAT's v1 duckdb-backed pipeline (`GATDatabase`). Use it when adding support
for a new tool, or when migrating an existing legacy scenario handler from
the pandas/h5py path to the v1 path.

The Plexos POC ([`gat/systems/plexos.py`][plexos-system],
[`gat/simulations/plexos_v1.py`][plexos-sim],
[`tests/handlers/test_plexos_v1_migration.py`][plexos-test]) is the worked
example. The Sienna implementation
([`gat/systems/sienna.py`][sienna-system],
[`gat/simulations/sienna_v1.py`][sienna-sim]) is the second reference point;
read both if you're adding a third tool.

## The contract

The v1 architecture has three pieces:

```
              ┌─────────────────────┐
              │  BaseSystem (your   │
              │  tool wraps it)    ─┼─── default CategoryMap[s]
              │                     │
              │  list_datasets()    │── DatasetInfo[]
              │  get_dataset(name) ─┼─── pd.DataFrame
              └──────────┬──────────┘
                         │
                         │  ingest_system()
                         ▼
              ┌─────────────────────┐
              │   GATDatabase       │── query_grouped(schema, dataset, group_by)
              │   (DuckDB engine)   │
              └──────────▲──────────┘
                         │
                         │  ingest_simulation()
                         │
              ┌──────────┴──────────┐
              │  BaseSimulation     │
              │  (your tool wraps) │── DatasetInfo[]
              │                     │
              │  list_datasets()    │── (raw + composed)
              │  get_dataset(name) ─┼─── pd.DataFrame
              └─────────────────────┘    (timestamp × entity)
```

Three things to implement:

1. **A `BaseSystem` subclass** that exposes generators/loads/lines as
   datasets and provides default `CategoryMap`s for the relations needed
   for `GROUP BY` (e.g. `gen_area`, `gen_tech`).
2. **A `BaseSimulation` subclass** that exposes raw simulation datasets
   (timestamp × entity) and at least one composed dataset (the union you
   want to be able to group by).
3. **Smoke + parity tests** that ingest into `GATDatabase`, run
   `query_grouped`, and confirm the result matches the legacy pandas path
   within tolerance.

## The Plexos POC, walked end-to-end

### `PlexosSystem`

`gat/systems/plexos.py` wraps the existing `PlexosParser`. Two things it
exposes:

- `list_datasets()` returns `[]` for now (POC scope — no system component
  tables ingested yet; Plexos relations are sufficient for the migration
  POC).
- `get_default_category_maps()` returns a `gen_area` `CategoryMap`
  populated from `parser.get_metadata("metadata/relations/regions_generators",
  reverse=True)`. Optionally a `gen_tech` map if a tech-simplified mapping
  was passed in.

```python
from gat.categories import CategoryMap

class PlexosSystem(BaseSystem):
    def list_datasets(self) -> list[DatasetInfo]:
        return []

    def get_default_category_maps(self) -> list[CategoryMap]:
        gen_area = self._parser.get_metadata(
            "metadata/relations/regions_generators", reverse=True
        )
        return [CategoryMap(
            name="gen_area",
            description="Generator → region/area",
            mapping={str(k): str(v) for k, v in gen_area.items()},
        )]
```

`CategoryMap` supports three sources: in-memory `mapping`, an external
`mapping_file` (CSV/Excel), or a `geometry_file` for spatial joins. The
POC uses the in-memory dict form.

### `PlexosSimulation`

`gat/simulations/plexos_v1.py` exposes one raw and one composed dataset:

```python
class PlexosSimulation(BaseSimulation):
    def list_datasets(self) -> list[DatasetInfo]:
        return [
            DatasetInfo(
                name="generation_raw",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="entity_id",
                ...
            ),
            DatasetInfo(
                name="generation",
                kind=DatasetKind.COMPOSED,
                entity_column="entity_id",
                source_datasets=["generation_raw"],
                ...
            ),
        ]

    def get_dataset(self, name: str) -> pd.DataFrame:
        # Plexos parser returns entity-rows × timestamp-cols with a
        # MultiIndex (generator, category) on the rows. Transpose to the
        # v1 contract (timestamp-rows × entity-cols) and flatten the index
        # to just the generator name.
        raw = self._parser.get_h5dataset("ST", "interval", "generators", "Generation")
        if isinstance(raw.index, pd.MultiIndex):
            raw = raw.copy()
            raw.index = raw.index.get_level_values(0)
        df = raw.T
        df.index = pd.to_datetime(df.index)
        df.index.name = "DATETIME"
        return df.astype("float32", errors="ignore")
```

**Orientation matters.** The contract is timestamp-rows × entity-cols, with
a `DatetimeIndex`. `GATDatabase.ingest_simulation` calls
`_prepare_sim_dataframe` which converts the index to an ISO string column
named `datetime` and casts floats to f32. Composed datasets are then built
by UNPIVOTing the raw tables and PIVOTing back as entity-rows ×
timestamp-cols (for efficient GROUP BY across many timestamps).

### Driving it end-to-end

```python
from gat.backends import GATDatabase
from gat.systems import PlexosSystem
from gat.simulations import PlexosSimulation

db = GATDatabase()
system = PlexosSystem(solution_dir="example_data/plexos")
sim = PlexosSimulation(solution_dir="example_data/plexos")

db.ingest_system("plexos", system)
db.ingest_simulation("plexos", sim)
for cmap in system.get_default_category_maps():
    db.register_category_map("plexos", cmap)

# Area-aggregated generation, summed across all timestamps:
df = db.query_grouped("plexos", "generation", group_by=["gen_area"])
# → wide DataFrame: gen_area | t0 | t1 | … | tN
```

### Parity test

`tests/handlers/test_plexos_v1_migration.py::test_v1_area_aggregation_matches_legacy`
asserts that the duckdb path produces the same area totals as the legacy
`PlexosScenario.get_generation()` aggregated by area, within `rel=1e-4`.
This is the load-bearing test — every `get_*` method migrated from the
legacy handler should add a similar parity check before flipping its
implementation to use duckdb.

## A third tool, and a shortcut for already-relational sources

[`gat/systems/plexos_duckdb.py`][plexos-duckdb-system] /
[`gat/simulations/plexos_duckdb.py`][plexos-duckdb-sim] is a second Plexos
backend, alongside the H5-based POC above. It ingests native PLEXOS
`Solution.zip` files (not h5plexos-converted `.h5`) by shelling out to the
optional [`plexos2duckdb`](https://github.com/epri-dev/plexos2duckdb) tool
(`pip install nlr-gat[plexos-duckdb]` — a Rust CLI, beta as of this writing).

Quickest way to try it — `Scenario.from_plexos_duckdb` builds
`PlexosDuckDBSystem` + `PlexosDuckDBSimulation` + `GATDatabase` and ingests
in one call:

```python
from gat import Scenario

scenario = Scenario.from_plexos_duckdb("/path/to/Solution.zip")
scenario.query("generation", group_by=["gen_area"])
```

By default this only ingests what the `generation` composition needs
(one raw report table), not the 100+ report tables a real solution can
expose — pass `full_ingest=True` to pull everything, but expect it to be
slow (minutes on a multi-thousand-generator solution) and to hit the
identifier-quoting bug below on any property with a special character in
its name (real example: PLEXOS's "Start & Shutdown Cost").

The interesting bit for future plugin authors: `plexos2duckdb`'s output is
*already* a DuckDB file with a `report` schema — one view per
`(Phase, Period, Collection, Property)` triple, timestamp + entity-name +
value columns. So instead of parsing into pandas and letting
`GATDatabase.ingest_simulation` do the transpose, `get_dataset()` runs a
`PIVOT` directly against the source connection
([`gat/datahelpers/plexos_duckdb.py`][plexos-duckdb-source]) and only
crosses into pandas at the very end via `.fetchdf()`. Same
`BaseSystem`/`BaseSimulation` contract as every other backend — the
shortcut is internal to `get_dataset()`, not a new interface.

**Multi-file overlap is a shared primitive, not a per-backend concern.**
Before this backend, GAT had *three* independent implementations of
"combine multiple time-ordered files/blocks, earlier one wins": Sienna's
`SimulationAggregator._combine_frames`, the legacy Plexos h5 path's
`gat.datahelpers.parsers.combine_frames_skip_prev`, and (briefly, during
this backend's first pass) a bespoke SQL version here. They'd drifted —
`combine_frames_skip_prev` has a documented quirk where its output isn't
re-sorted chronologically if the input list wasn't already in order (see
`tests/datahelpers/test_combine_frames.py`), which surfaced as a real
~9% generation under-count when a 12-month real fixture exposed it.

The fix: `gat.simulations.utils.combine_overlapping_frames` is now the one
canonical function — sort input frames by first timestamp, dedupe via
`dedup_slices`, concatenate, sort the result. `SimulationAggregator.
_combine_frames` is a thin wrapper over it. `PlexosDuckDBSource.pivot_wide`
uses it too: each attached file gets pivoted **independently**
(`_pivot_one_file` — genuinely "parse one file, nothing else") into its
own timestamp × entity DataFrame, and only those per-file DataFrames get
handed to `combine_overlapping_frames`. `combine_frames_skip_prev` itself
hasn't been migrated yet (it's mid-investigation for the under-count bug;
migrating it is the natural follow-up once that's root-caused) — new
backends should use `combine_overlapping_frames` directly rather than
that one.

Composed datasets are also expressed the same way Sienna does it: a
`{composed_name: [glob_patterns]}` dict resolved against raw dataset names.
That resolution logic (`resolve_compositions`) was extracted from
`SiennaSimulation` into `gat/simulations/utils.py` so both backends (and any
future one) share it instead of reimplementing fnmatch-against-raw-names
each time.

## A legacy handler that speaks both formats

`PlexosScenario` ([`gat/scenariohandlers/plexos.py`][plexos-legacy]) now
detects its input format and routes internally to one of two engines —
the legacy pandas/h5py `PlexosParser` for h5plexos-converted `.h5` files
(unchanged), or `PlexosDuckDBSystem`/`PlexosDuckDBSimulation` for native
PLEXOS `Solution.zip`/`.duckdb` files. Same class, same public API either
way — `BaseScenario`'s higher-level methods (`get_system_dispatch()`,
`get_area_dispatch()`, curtailment, peak stats, line loading) work
unmodified on top of whichever engine is active:

```python
from gat.scenariohandlers import PlexosScenario

scenario = PlexosScenario("/path/to/Solution.zip")   # duckdb backend
# scenario = PlexosScenario("/path/to/h5_dir")       # h5 backend, unchanged
dispatch = scenario.get_system_dispatch()
```

This is a variant of step 7 below ("flip the legacy method's
implementation to delegate to the v1 path") — gated on input format
rather than a hard cutover, since native `.zip` and h5plexos `.h5` are
different upstream artifacts that must both keep working. Detection lives
in `_resolve_plexos_backend_and_files` (a free function, independently
tested in `tests/handlers/test_plexos_backend_detection.py`): explicit
file paths resolve regardless of extension and are classified by it;
directories/globs retry under `*.zip`/`*.duckdb` patterns only if the
default `*.h5` pattern found nothing. Every abstract method branches
`if self._backend == "duckdb": ... else: <existing h5 code, untouched>` —
the h5 branch is never touched, so the regression snapshots in
`tests/handlers/test_plexos_regression.py` gate zero `--force-regen`.

The duckdb branch talks straight to `PlexosDuckDBSystem`/
`PlexosDuckDBSimulation` — never `GATDatabase`/`Scenario` — which sidesteps
the identifier-quoting concern entirely (that bug lives in `GATDatabase`'s
view-registration path).

**A real-data surprise worth remembering**: PLEXOS `Storage`-class objects
looked, at first, like h5plexos's "batteries" group (which the legacy path
unions additively into `generation`/`gen_area` — see `gat/systems/
plexos.py`). They're not. Verified against a real converted solution:
`Storage` objects are named `<generator>_head`/`<generator>_tail`,
children of their `Generator` (not `Region`) via `Head Storage`/
`Tail Storage` membership collections, and their `Generation` is
bit-identical to the parent `Generator`'s own `Generation` — internal
reservoir bookkeeping for battery-capable generators, not a separate
generation source. Unioning it in would have double-counted. Only
`Storages__Pump_Load` (charging) is genuinely separate information, and
only its `_head` column carries a real value. Moral: h5plexos and
plexos2duckdb convert the *same* underlying PLEXOS solution but don't
necessarily share a data model — verify against real data before porting
a union/aggregation pattern from one to the other, don't assume it
transfers.

## Pattern to apply when adding a new tool

| Step | What to do |
|------|------------|
| 1 | List the raw datasets your tool emits (e.g. one per component type, one per output variable). |
| 2 | Decide which composed unions you need (`generation`, `load`, `line_flow`, …). Compositions are just a list of source dataset names; `GATDatabase` materializes them. |
| 3 | Implement `BaseSimulation.list_datasets()` and `get_dataset(name)` returning pandas DataFrames in the **timestamp-rows × entity-cols** orientation. |
| 4 | Implement `BaseSystem.get_default_category_maps()` for the relations needed for `GROUP BY`. Start with `gen_area`; add `gen_tech`, `gen_fuel`, etc. as needed. |
| 5 | Smoke-test: `db.ingest_system + db.ingest_simulation + db.list_tables + db.query_grouped`. Iterate until the round-trip works. |
| 6 | Parity-test against the legacy handler's equivalent method. Use `pytest.approx(..., rel=1e-4)` as a starting tolerance; tighten if your tool is deterministic. |
| 7 | Once parity holds, flip the legacy method's implementation to delegate to the v1 path. The regression snapshot tests (`test_*_regression.py`) gate the change. |

## When to skip a step

- **No legacy parity test target:** if you're adding support for a tool
  GAT didn't have before, skip step 6 — there's nothing to compare against.
  Use `test_v1_pipeline_ingests_and_groups` (smoke) as your only test;
  add snapshots once the output stabilizes.
- **No clean composition:** if your tool's data is already aggregated in a
  way that doesn't fit the raw-then-composed model, expose it as a single
  raw dataset and use `query()` (raw SQL) instead of `query_grouped` for
  one-off needs. The composition story is a convenience; not every dataset
  needs to fit it.

## Related reading

- [Sienna scaling and raw dataset access](../sienna_scaling.md) — how
  `base_power` is resolved across the legacy and v1 paths.
- [Legacy scenario handler deprecation](../legacy_handler_deprecation.md)
  — the user-facing migration story.
- [`gat.interfaces`][interfaces] — the `BaseSystem` / `BaseSimulation`
  abstract classes with full docstrings.
- [`gat.backends.GATDatabase`][backend] — the duckdb engine.

[plexos-system]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/systems/plexos.py
[plexos-sim]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/simulations/plexos_v1.py
[plexos-test]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/tests/handlers/test_plexos_v1_migration.py
[sienna-system]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/systems/sienna.py
[sienna-sim]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/simulations/sienna_v1.py
[interfaces]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/interfaces.py
[backend]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/backends/duckdb_backend.py
[plexos-duckdb-system]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/systems/plexos_duckdb.py
[plexos-duckdb-sim]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/simulations/plexos_duckdb.py
[plexos-duckdb-source]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/datahelpers/plexos_duckdb.py
[plexos-legacy]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/scenariohandlers/plexos.py
