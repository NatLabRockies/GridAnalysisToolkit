# Legacy scenario handler deprecation

`SiennaScenario`, `PlexosScenario`, `ReEDsScenario`, `FileScenario`, and
`MultiScenario` are the original v0 scenario handler classes. They still work
and will continue to work for the v1 release cycle, but **direct
instantiation is deprecated**. Construct scenarios through `gat.load()`
instead.

## What changed

Each legacy handler now emits a `DeprecationWarning` from its `__init__`:

```text
DeprecationWarning: PlexosScenario is deprecated and will be migrated to a
duckdb-backed implementation in a future release. New code should use
`gat.load(...)` to obtain a scenario object via the supported v1 entry
point.
```

The warning's `stacklevel` is set so it points at the caller's line — your
`PlexosScenario(...)` call, not GAT internals.

## What to do

### Writing new code

Use `gat.load()`:

```python
import gat

scenario, palette, project = gat.load(
    project="my-analysis",
    scenario="base_2035",
)

# Same DataFrame-returning API as before.
dispatch = scenario.get_area_dispatch()
```

The returned `scenario` object exposes the same public methods (`get_load`,
`get_area_dispatch`, `get_generation`, etc.) you used to call directly on
`SiennaScenario`/`PlexosScenario`. The construction path is the only thing
changing now; the public DataFrame contract is preserved across the broader
duckdb migration that follows.

If you don't have a project set up yet, see
[Scenario quick start](scenario_quickstart.md).

### Maintaining existing code

No immediate action required. The legacy classes keep working until the
duckdb migration completes, at which point a future release will remove
them. The deprecation warning is your signal to start moving callers over
to `gat.load()` at a comfortable pace.

To silence the warning in code you don't own, use the standard
`warnings.simplefilter`:

```python
import warnings
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    module=r"gat\.scenariohandlers\..*",
)
```

The GAT test suite uses an autouse `pytest` fixture in `tests/conftest.py`
that does the same thing — tests intentionally instantiate the legacy
classes for regression coverage and don't want the warnings to clutter
output.

## Why deprecate now, before the duckdb migration is complete?

Two reasons:

1. **Signal direction.** The deprecation tells everyone (humans and IDEs)
   that `gat.load()` is the supported entry point. Without it, the parallel
   v1 architecture (in `gat.systems`, `gat.simulations`, `gat.backends`)
   isn't discoverable.
2. **Constraint on new code.** The deprecation makes it harder to
   accidentally build on top of the legacy path going forward, which keeps
   the migration scope bounded.

The legacy classes themselves still execute the same pandas/h5py code they
always have. Phase 5 of the migration replaced their construction story
without touching their internals; the duckdb-backed internals will land
incrementally, validated against the regression snapshots in
`tests/handlers/test_plexos_regression.py` and
`tests/handlers/test_sienna_regression.py`.

## Migration timeline (rough)

1. **Now (v1.x):** Legacy classes work, deprecation warns, `gat.load()` is
   the supported path. v1 architecture proven on Plexos via
   [`tests/handlers/test_plexos_v1_migration.py`][migration-poc].
2. **Subsequent v1.x releases:** Legacy `get_*` methods migrated to route
   through `GATDatabase` under the hood. Snapshots gate correctness. Public
   API unchanged.
3. **v2.0:** Legacy classes removed. `gat.load()` and the v1 architecture
   are the only path.

[migration-poc]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/tests/handlers/test_plexos_v1_migration.py
