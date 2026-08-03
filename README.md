# GAT - Grid Analysis Toolkit

[![tests](https://github.com/NatLabRockies/GridAnalysisToolkit/actions/workflows/tests.yml/badge.svg)](https://github.com/NatLabRockies/GridAnalysisToolkit/actions/workflows/tests.yml)
[![lint](https://github.com/NatLabRockies/GridAnalysisToolkit/actions/workflows/lint.yml/badge.svg)](https://github.com/NatLabRockies/GridAnalysisToolkit/actions/workflows/lint.yml)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![docs](https://github.com/NatLabRockies/GridAnalysisToolkit/actions/workflows/sphinx.yml/badge.svg)](https://natlabrockies.github.io/GridAnalysisToolkit/)
[![PyPI](https://img.shields.io/pypi/v/nlr-gat)](https://pypi.org/project/nlr-gat/)
[![Python](https://img.shields.io/pypi/pyversions/nlr-gat)](https://pypi.org/project/nlr-gat/)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](LICENSE)

A toolkit for wrangling data for Bulk Grid Dispatch and Transmission Analysis.

GAT aims to provide simplified access to PCM and CEM results in a standard format while also allowing raw data access to underlying datasets specific to the model.

For plotting, GAT defaults to standard National Lab of the Rockies (NLR) color schemes and standard styles while allowing customization.

> [!WARNING]
> GAT's public API is still evolving. Expect breaking changes between
> releases before v1.0 — pin an exact version (e.g. `nlr-gat==0.1.0`) if
> you need stability.

> [!WARNING]
> Support for PLEXOS solution files produced by **H5PLEXOS.jl** (`.h5`)
> will be removed in **v0.2.0**. Load native PLEXOS `Solution.zip` files
> through the DuckDB-backed engine instead: install with
> `pip install "nlr-gat[plexos]"` and pass the `.zip` path directly to
> `PlexosScenario` — backend selection is automatic.

## Installation

It is recommended to create a virtual environment for installing GAT.

In your desired directory, run one of the following.

`python -m venv .venv`

`python3 -m venv .venv`

Then activate your virtual environment by running.

`. .venv/bin/activate` on MacOS or Linux

or `.venv/Scripts/Activate` on Windows. If you are having trouble activating the virtual environment on Windows, you may need to update your execution policy. More can be read [here](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-executionpolicy?view=powershell-7.4).

Install the latest release from PyPI:

`pip install nlr-gat`

> **Note:** the distribution is named `nlr-gat` because `gat` on PyPI is
> an unrelated genomics package. The import package and CLI are still `gat`,
> which also means `nlr-gat` cannot share an environment with that
> genomics package.

### Choosing extras

The bare install above pulls in only the format-agnostic core — no
scenario handler is usable yet. Each simulation/model format has its own
extra, so you only install the (often large, native-code) dependencies
you actually need:

| Extra | Adds | Installs |
|---|---|---|
| `sienna` | `SiennaScenario` | h5py, polars, geopandas |
| `plexos` | `PlexosScenario` (both backends, for now — see the H5PLEXOS.jl deprecation notice above) | h5py, duckdb, plexos2duckdb |
| `reeds` | `ReEDsScenario` | *(base deps only)* |
| `plots` | `gat.quickplots` / the `.plot` property on any scenario | matplotlib (+ PySide6 on macOS) |
| `server` | `gat.server` (the data server) | fastapi, uvicorn, duckdb, pyarrow |
| `client` | `gat.client` (remote scenario access) | httpx, pyarrow |
| `all` | everything above | — |

Combine as needed, e.g.:

`pip install "nlr-gat[sienna,plots]"`

`pip install "nlr-gat[plexos,server]"`

`pip install "nlr-gat[all]"`

Or install from GitHub — the latest, a specific release, or a branch:

`pip install git+https://github.com/NatLabRockies/GridAnalysisToolkit`

`pip install git+https://github.com/NatLabRockies/GridAnalysisToolkit@v0.1.0`

`pip install git+https://github.com/NatLabRockies/GridAnalysisToolkit@{branch_name}`

## Documentation

The latest stable documentation lives at
[natlabrockies.github.io/GridAnalysisToolkit](https://natlabrockies.github.io/GridAnalysisToolkit/).
The example
[gallery](https://natlabrockies.github.io/GridAnalysisToolkit/gat_plot_examples/index.html)
is a good starting point for visual capability.

Highest-traffic doc pages (also readable directly in the repo):

- [Quickstart: scenarios and palettes](docs/source/scenario_quickstart.md)
- [Python API: `gat.load(...)`](docs/source/python_api_load.md)
- [Sienna scaling and raw dataset access](docs/source/sienna_scaling.md)
- [Custom plots and the reporting framework](docs/source/extending_plots.md)
- [v1 architecture & migration pattern](docs/source/architecture/v1_migration_pattern.md)
- [Legacy scenario handler deprecation](docs/source/legacy_handler_deprecation.md)
- [Migrating from v0.x to v1.0](docs/source/migration_v1.md)
- [Changelog](docs/source/CHANGELOG.md)

## Example data

`example_data/` is gitignored — the binaries are too large to track
in-tree. Sienna fixtures regenerate via `make sienna-fixture-v4`
(requires Docker; see `docker/sienna/README.md`). For Plexos (`pip
install nlr-gat[plexos]`), point the `GAT_PLEXOS_FIXTURE` environment
variable at a directory of `.h5` solution files of your own, or
`GAT_PLEXOS_ZIP_FIXTURE` at a native PLEXOS `Solution.zip`.

## Contributing

If you wish to contribute to the development of GAT, please clone the repo and install the dev dependencies as follows.

`git clone https://github.com/NatLabRockies/GridAnalysisToolkit.git`

`cd GridAnalysisToolkit`

Follow the instructions for creating a virtual environment above, then:

`pip install -e ".[dev]"`

When you are ready, please open a pull request for review.

If you plan to contribute to documentation, install the documentation dependencies as well.

`pip install -e ".[dev,doc]"`

Commit messages and PR titles should follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat: ...`, `fix: ...`, `docs: ...`, etc.) — releases are generated
automatically from these (see `.github/workflows/release.yml`).

## Building the documentation

After installing the doc dependencies:

`cd docs && sphinx-build -b html source build/html`

Review documentation changes locally:

`open build/html/index.html`

## Software Record and Disclaimer

GAT is developed by the National Lab of the Rockies (NLR) and released
under software record SWR-25-41 "GAT (Grid Analysis Toolkit)".

See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer.
