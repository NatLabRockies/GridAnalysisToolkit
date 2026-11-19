# Building the GridSight Wheel

This directory holds `gridsight-gat`, the GridSight
extension that surfaces GAT scenarios (Sienna H5 + system JSON) as
GridSight layers, charts, and timeseries.

For GridSight desktop users, the extension can be:

- **Bundled in the installer** (default — no action needed; the installer
  builds these wheels as part of the release).
- **Side-loaded** into an existing GridSight desktop app via Settings →
  "Choose wheel…". This doc covers building the side-loadable artifact.

---

## TL;DR

From the repo root:

```bash
make gridsight-bundle
```

Produces `dist/gridsight-gat-bundle-<version>.zip`. Hand that file to a
user; they pick it in Settings → "Choose wheel…" and click **Restart
backend**. Done.

---

## What's inside the bundle

```
gridsight-gat-bundle-1.0.0.zip
├── nlr_gat-<gat-version>-py3-none-any.whl
└── gridsight_gat-<ext-version>-py3-none-any.whl
```

Both wheels are in the bundle so it installs offline. `gridsight-gat`
depends on `nlr-gat` (also on PyPI), and the bundled wheel pins the GAT
version that the extension was built against. The desktop's installer
extracts the zip, then passes both wheels to `uv pip install` in a
single invocation — uv resolves the install order from wheel metadata.

The bundle version (in the zip filename) tracks
`gridsight-ext/pyproject.toml`'s `version` field, not GAT's own. So a
GAT-only release that doesn't change the extension keeps the same
bundle name.

---

## Prerequisites

- **uv** ≥ 0.4 ([install](https://docs.astral.sh/uv/getting-started/installation/)).
- A clean checkout of this repo.
- `zip` on PATH (default on macOS/Linux; Git Bash on Windows provides it).

No virtual environment needed — `uv build` runs in isolation.

---

## Building from a tagged release

For a reproducible bundle, build from a worktree pinned to the tag
rather than your live checkout:

```bash
git worktree add /tmp/gat-release nlr-gat-vX.Y.Z
cd /tmp/gat-release
make gridsight-bundle
cp dist/gridsight-gat-bundle-*.zip ~/Desktop/
git worktree remove /tmp/gat-release
```

This guarantees the wheels match the tag exactly — no stray edits or
unstaged files.

---

## Verify before shipping

```bash
make gridsight-bundle
unzip -l dist/gridsight-gat-bundle-*.zip
```

You should see exactly two `.whl` files. Optionally smoke-test the
contents in a throwaway venv:

```bash
unzip -d /tmp/bundle-check dist/gridsight-gat-bundle-*.zip
uv venv /tmp/gat-check
source /tmp/gat-check/bin/activate
uv pip install /tmp/bundle-check/*.whl
python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='gridsight.extensions')])"
```

Expect `['gat']` — that's the entry-point GridSight's sidecar discovers
at startup.

---

## Installing into GridSight desktop

1. Open GridSight desktop → Settings.
2. Click **Choose wheel…** under "Install extension".
3. Pick the bundle zip. Wait for "Install succeeded".
4. Click **Restart backend**.

The window reloads and `gat` appears in the extensions list. To
upgrade later, rebuild the bundle at the new tag and repeat — `uv pip
install` upgrades in place.

---

## Manual build (if you can't run `make`)

The Makefile target is equivalent to:

```bash
mkdir -p dist/gridsight-bundle
uv build --wheel --out-dir dist/gridsight-bundle .              # nlr-gat
uv build --wheel --out-dir dist/gridsight-bundle gridsight-ext   # gridsight-gat
version=$(grep -m1 '^version' gridsight-ext/pyproject.toml | sed -E 's/.*"([^"]+)".*/\1/')
(cd dist/gridsight-bundle && zip -j "../gridsight-gat-bundle-${version}.zip" *.whl)
```

---

## Troubleshooting

**`uv: command not found`**
Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh` (macOS/Linux)
or `irm https://astral.sh/uv/install.ps1 | iex` (Windows PowerShell).

**`uv build` fails on the gridsight-ext target**
The `gridsight-ext/pyproject.toml` declares `nlr-gat` as a `path = "../"`
dependency for editable installs. `uv build` ignores that at wheel-build
time (the path dep becomes a plain `nlr-gat` requirement in the wheel's
metadata), so this should just work. If it doesn't, check that
`uv --version` is recent enough.

**Desktop "Restart backend" shows no new extension**
Check `~/Library/Logs/GridSight/backend.log` (macOS) for entry-point
discovery errors. The most common cause is a version conflict with the
bundled `nlr-gat`/`gridsight-gat`. If the venv is in a stuck state, wipe it
(`rm -rf ~/Library/Caches/GridSight/venv`) and GridSight will reprovision
from scratch on next launch.
