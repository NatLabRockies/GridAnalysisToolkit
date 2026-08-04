# Agent notes for working on GAT

This file is for coding agents (and humans) *contributing to* GAT itself.
If you're looking for how to *use* GAT as a library, see the
[README](README.md) and the docs site instead — this file is repo-internal.

## What this is

GAT (`nlr-gat` on PyPI) is a format-agnostic API over grid-model
simulation outputs (Sienna, PLEXOS, ReEDS), with a thin core and
per-format extras so consumers only install the native-code dependencies
(h5py, duckdb, geopandas, polars, matplotlib) their format actually needs.

## Layout

- `src/gat/` — the package (src layout; import as `gat`)
- `src/gat/scenariohandlers/`, `src/gat/simulations/`, `src/gat/systems/`,
  `src/gat/datahelpers/` — package boundaries that use a lazy
  `__getattr__` pattern (PEP 562) instead of eager `from .x import *`.
  **If you add a new format module here, wire it into the `__getattr__`
  dispatch, don't add a blanket import** — that's what keeps
  `pip install nlr-gat[reeds]` from pulling in h5py/geopandas/duckdb.
- `docs/source/` — Sphinx docs (MyST markdown + autodoc); built and
  deployed to GitHub Pages on push to `main`.
- `tests/` — pytest; regression baselines under `tests/handlers/` use
  `pytest-regressions` snapshots.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

`dev` is deliberately self-referential (`nlr-gat[sienna,plexos,reeds,plots]`)
so the full test suite is runnable out of the box — see the comment above
it in `pyproject.toml` (issue #23) for why that matters.

## Running tests

```bash
make test          # pytest tests/ -v
```

Some tests need fixture data that isn't checked in:
- **Sienna**: `make sienna-fixture-v4` (needs Docker; see
  `docker/sienna/README.md`). Point `GAT_SIENNA_FIXTURE` or use the
  default resolution order in `tests/visual/generate_fixture_deck.py` if
  working with fixtures interactively.
- **PLEXOS**: set `GAT_PLEXOS_FIXTURE` (H5PLEXOS.jl `.h5` directory) or
  `GAT_PLEXOS_ZIP_FIXTURE` (native `Solution.zip`) to point at your own
  data. Tests needing fixtures that aren't present skip rather than fail.

After a change that should shift regression baselines intentionally:

```bash
make regen-snapshots
```

## Conventions

- **Formatting/lint**: `black` (line length 88) and a minimal `ruff`
  rule set (bug-catching only, not style). CI runs
  `black --check src/gat tests` and `ruff check src/gat tests`.
- **Commit messages and PR titles must follow [Conventional
  Commits](https://www.conventionalcommits.org/)** (`feat:`, `fix:`,
  `docs:`, `refactor:`, `perf:`, `ci:`, `build:`, `test:`, `chore:`,
  with `!` or a `BREAKING CHANGE:` footer for breaking changes). This is
  enforced (informationally, not yet a required check) by
  `.github/workflows/commit-lint.yml`, and it's not just style —
  **release-please parses these prefixes to compute version bumps and
  generate `docs/source/CHANGELOG.md`.** An unprefixed commit is
  invisible to it, not an error.
- **No static version string.** GAT uses `setuptools_scm` — version is
  derived from git tags at build time (`dynamic = ["version"]` in
  `pyproject.toml`). Never hand-edit a version number anywhere.

## Release process

Releases are automated via [release-please](https://github.com/googleapis/release-please)
(`.github/workflows/release.yml`), modeled on NatLabRockies/R2X:

1. Every push to `main` (i.e., every merged PR) updates a standing
   `chore(main): release nlr-gat X.Y.Z` PR with an auto-generated
   changelog, computed from Conventional Commits since the last release.
2. Merging that PR creates the git tag + GitHub Release.
3. That triggers build + publish to PyPI via Trusted Publishing (OIDC,
   no stored token). The `pypi` GitHub Environment has a required
   reviewer gate — publishing pauses for manual approval regardless of
   who merged the release PR.

You will not need to run `git tag` or upload to PyPI by hand.

## Known gotchas worth knowing before you dig for them

- `EGRETScenario` was removed entirely (issue #11) — if you find a
  reference to EGRET in an old branch or issue, it's gone, not moved.
- Support for PLEXOS `.h5` files (from H5PLEXOS.jl) is deprecated as of
  v0.1.1 and will be removed in v0.2.0 — new PLEXOS work should target
  the DuckDB-backed engine (`nlr-gat[plexos]`, native `Solution.zip`).
- Path arguments (`PlexosScenario(...)`, etc.) go through
  `os.path.expanduser()` before resolution — `~` is expanded, but shell
  globs and environment variables written literally in a Python string
  are not.
