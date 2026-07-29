# Sienna fixture generation

Generates RTS-GMLC outputs via Sienna (Julia) for GAT regression tests. Output
goes to `example_data/sienna/v{4,5}/{sys.json, simulation_store.h5, build.log}`,
which the test suite (`tests/handlers/test_sienna_regression.py`) snapshots.

## Layout

```
docker/sienna/
├── Dockerfile
├── Project.toml          # shared deps
├── Manifest.v4.toml      # locked deps that produce data_format_version=4.0.0
├── Manifest.v5.toml      # locked deps that produce data_format_version=5.0.0
├── generate.jl           # entrypoint: builds RTS-GMLC, runs UC, writes outputs
└── README.md
```

The Manifest files are version-pinned snapshots of the dependency graph; the
Dockerfile copies the right one at build time based on `SIENNA_VERSION`.

## Build & run

From the repo root:

```bash
make sienna-fixture-v4   # builds image then runs it, output → example_data/sienna/v4/
make sienna-fixture-v5
```

Or directly:

```bash
docker build --build-arg SIENNA_VERSION=4 -t gat-sienna:v4 docker/sienna
docker run --rm -v "$(pwd)/example_data/sienna/v4:/output" gat-sienna:v4
```

## Regenerating Manifest files

The Manifests are the source of truth for which PowerSystems version (and
therefore which `data_format_version`) gets baked into the fixture. To update:

```bash
# Drop into a Julia container with the project
docker run --rm -it -v "$(pwd)/docker/sienna:/work" -w /work \
    julia:1.11-bookworm \
    julia --project=. -e 'using Pkg; Pkg.add(["PowerSystems", "PowerSimulations", "PowerSystemCaseBuilder", "HiGHS", "JuMP", "HDF5"]); Pkg.resolve()'
mv docker/sienna/Manifest.toml docker/sienna/Manifest.v4.toml   # or v5
```

For v5 specifically, you may need to add upper bounds in `Project.toml` or pull
PowerSystems from a `#main` git ref if a v5-format release isn't on General yet.

## Tunables

- `SIM_STEPS` (env var, default `7`) — number of UC steps. RTS-GMLC's UC step
  is 24h with a 12h overlap, so 7 ≈ one week. Bump to 365 for an 8760
  approximation; expect runtime to scale linearly and `simulation_store.h5` to
  grow into the hundreds of MB.

```bash
docker run --rm -e SIM_STEPS=14 -v "$(pwd)/example_data/sienna/v4:/output" gat-sienna:v4
```

## Solver

HiGHS — open-source LP/MIP. Sufficient for the curated RTS-GMLC test case
shipped by `PowerSystemCaseBuilder.jl`. Swap to Gurobi/CPLEX in `generate.jl`
if you need realistic utility-scale problems.

## CI fixture cache and the manual refresh workflow

CI (`.github/workflows/tests.yml`) doesn't rebuild the Sienna Docker image on
every run. It caches the generated fixture (`example_data/sienna/v4/`) in
`actions/cache` under key `sienna-v4-${{ hashFiles('docker/sienna/**') }}`, and
only pays for a fresh Docker build when `docker/sienna/**` actually changed in
a PR. If nothing changed and no cache exists for the current key (e.g. after
the 7-day cache eviction, or a repo-wide cache-size eviction), CI **fails
fast on purpose** instead of silently rebuilding — see the "changes" job's
fail-fast step in `tests.yml`.

Why fail instead of auto-rebuilding: Sienna's UC solve isn't perfectly
bit-reproducible run-to-run (MIP tie-breaking among equally-optimal dispatch
solutions — much improved by pinning solver behavior, but not guaranteed
airtight forever across HDF5/solver version bumps). An automatic rebuild on
any cache miss means whichever build happens to "win" (including a race
between two concurrent PR runs that both hit a cache miss at once) silently
becomes the fixture every future run tests against, with no guarantee it
matches the committed regression CSV baselines
(`tests/handlers/test_sienna_regression/*.csv`). That's exactly what caused
CI failures on PR #8, unrelated to what that PR actually changed.

**Fix: run `.github/workflows/sienna-fixture-refresh.yml` manually**
(Actions tab → "Sienna fixture refresh" → "Run workflow"). Use it:

- before merging a PR that touches `docker/sienna/**`, once you're happy with
  the fixture it produces
- periodically as a safety refresh, or whenever CI's fail-fast step above
  tells you to

It picks a `version` (`v4` today; `v5` is offered too so it can be reused
once `test_sienna_regression.py`'s v5 support and `tests.yml`'s v5 wiring
land, without redesigning this workflow), rebuilds the Docker image, runs it,
and **writes the fixture to the same `actions/cache` key** the automatic CI
jobs read from — so the very next PR run picks up the refresh with no other
changes needed. Because `actions/cache` refuses to overwrite an existing key,
the workflow first deletes any existing entry for that key (`gh cache
delete`) so the write isn't silently skipped.

**Required follow-up — do not skip this:** refreshing the cache does *not*
update the committed regression baselines. After the workflow finishes
(check its job summary for the exact commands):

1. Download the `sienna-v4-fixture-refreshed` artifact from that workflow
   run (these are the exact bytes CI will now test against — a fresh local
   `make sienna-fixture-v4` won't reproduce them bit-for-bit).
2. Extract it to, e.g., `example_data/sienna/v4`.
3. Run `GAT_SIENNA_V4_FIXTURE=$(pwd)/example_data/sienna/v4 pytest
   tests/handlers/test_sienna_regression.py --force-regen`.
4. Review the resulting CSV diffs and commit them.

Skipping steps 3-4 means the regression tests will start failing on the very
next PR that restores the newly-cached fixture.
