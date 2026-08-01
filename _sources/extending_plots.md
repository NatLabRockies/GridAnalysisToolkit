# Custom plots and the reporting framework

GAT has two tiers of plotting API. This page explains both, when to use
which, and how to register your own plot so it shows up in the reporting
framework's automatic deck generation.

## The two-tier plot API

| Tier | Module | Input | Output | When you'd use it |
|------|--------|-------|--------|-------------------|
| **Low-level** | `gat.quickplots.*` | `pd.DataFrame` (already-aggregated dispatch, capacity, etc.) | `matplotlib.axes.Axes` | One-off analysis. The [gallery](gat_plot_examples/index.rst) is built on this tier. |
| **High-level** | `gat.quickplots.{generation,system,transmission}_plots` | `BaseScenario` (any handler) | `(name: str, ax: Axes, df: pd.DataFrame \| None)` | Batch reporting, scenario comparisons, plugin extensions. The [reporting framework](#the-reporting-framework) consumes this tier. |

The high-level functions are typically thin wrappers around the low-level
ones. For example:

```python
# Low-level (what the gallery shows)
import gat.quickplots as qp
dispatch = scenario.get_area_dispatch(include_charging=False)
ax = qp.plot_annual_area_dispatch_stack(dispatch)

# High-level (what the reporter calls)
from gat.quickplots.generation_plots import plot_total_area_dispatch
name, ax, df = plot_total_area_dispatch(scenario)
```

The high-level wrapper does three additional things:

1. **Pulls its own data** from the scenario, so the caller doesn't have to
   know which `get_*` method to use.
2. **Returns the dataframe** alongside the axes, so the reporter can save
   `name.csv` next to `name.png`.
3. **Owns its output filename** via the `name` (typically a path-like
   string with subfolders, e.g. `"generation/area/total_dispatch"`) — the
   reporter writes the PNG to `<output_path>/<name>.png`.

## The `@plot_function` decorator

`@plot_function` (from `gat.registry`) marks a function as a registered
high-level plot. The decorator captures the function's signature so the
reporting framework can show its options in the report config YAML, and
filters discovery by scenario type and plot category.

```python
from gat.registry import plot_function

@plot_function("BaseScenario", plot_type="generation")
def plot_my_thing(scenario, threshold_mw=100, **kwargs):
    """Docstring becomes the description in the report config."""
    df = compute_something(scenario, threshold_mw)
    fig, ax = plt.subplots()
    df.plot(ax=ax)
    return ("generation/my_thing", ax, df)
```

### Decorator arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `scenario_type` | `"BaseScenario"` | Filters discovery. `"BaseScenario"` plots run for any handler. `"SiennaScenario"` (etc.) plots only run for that handler. |
| `plot_type` | `"system"` | Free-form category. The reporter's `report_type` field filters by this — common values are `"generation"`, `"transmission"`, `"cost"`, `"emissions"`, `"system"`. |

### Return contract

The function must return a tuple of either two or three elements:

```python
(name: str, ax: matplotlib.axes.Axes)
(name: str, ax: matplotlib.axes.Axes, df: pd.DataFrame | None)
```

| Element | Used for |
|---------|----------|
| `name` | Filename for the saved PNG (and CSV, if `df` provided). Slashes are interpreted as subdirectories under the report's `output_path`. |
| `ax` | The matplotlib axes — saved as PNG via `plt.savefig(ax.figure)`. |
| `df` | Optional underlying data — saved as `<name>.csv` when the report config has `save_data=True`. |

### Generator-style plots

If a function yields tuples instead of returning one, the reporter
iterates over them — useful for "one plot per area" or "one plot per
month" styles. The yielded tuple shape is the same.

## The reporting framework

`gat.reports.scenario_single.run(config)` is the entry point. It:

1. Discovers all `@plot_function`-decorated callables (internal and
   external).
2. Loads a scenario via `gat.load(...)` from the `SystemReportConfig`'s
   `scenario` field.
3. Iterates `config.output_plots`, calling each plot via
   `gat.registry.utils.execute_plot`.
4. Writes `<output_path>/<name>.png` and (if `save_data=True`)
   `<output_path>/<name>.csv` for each.
5. Optionally bundles everything into a PowerPoint when
   `output_fmt='pptx'`.

```python
from gat.models.scenario import ScenarioConfig
from gat.reports.scenario_single import SystemReportConfig, run

config = SystemReportConfig(
    model_type="Sienna",
    output_path="./report_out",
    output_fmt="pptx",  # also creates report_out/system_comparison.pptx
    scenario=ScenarioConfig(
        model_type="Sienna",
        simulation_paths="example_data/sienna/v4/simulation_store.h5",
        system_path="example_data/sienna/v4/sys.json",
    ),
)
run(config)
```

`config.output_plots` is a list of plot-config dicts (one per plot) with
options pulled from each function's signature. When empty, the reporter
auto-discovers and runs everything that matches `model_type` /
`report_type`. To run a curated subset, populate it explicitly:

```python
config.output_plots = [
    {"name": "plot_total_system_dispatch", "options": {"units": "GWh"}},
    {"name": "plot_capacity_by_fuel", "options": {}},
]
run(config)
```

## Worked example: capacity by fuel

A custom plot that summarizes installed thermal and renewable capacity by
fuel type, sourced from the scenario's system file.

```python
"""Custom plot: total installed capacity by fuel."""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt
import pandas as pd

from gat.scenariohandlers import SiennaScenario
from gat.registry import plot_function, discover_all_plots


@plot_function("BaseScenario", plot_type="generation")
def plot_capacity_by_fuel(scenario, **kwargs):
    """Total installed capacity by fuel, drawn from the system definition.

    Walks ThermalStandard + RenewableDispatch + RenewableNonDispatch
    components, scales each unit's per-unit rating by its base_power,
    sums by fuel.
    """
    rows = []
    for ctype in ["ThermalStandard", "RenewableDispatch", "RenewableNonDispatch"]:
        try:
            df = scenario.system.get_component_data(ctype)
        except Exception:
            continue
        for _, comp in df.iterrows():
            if not comp.get("available", True):
                continue
            rating_pu = comp.get("rating") or 0
            base = comp.get("base_power") or 100
            mw = float(rating_pu) * float(base)
            rows.append({"fuel": comp.get("fuel") or ctype, "capacity_mw": mw})

    cap = (
        pd.DataFrame(rows)
        .groupby("fuel")["capacity_mw"]
        .sum()
        .sort_values(ascending=True)
    )

    fig, ax = plt.subplots(figsize=(7, 4))
    cap.plot.barh(ax=ax)
    ax.set_xlabel("Installed Capacity (MW)")
    ax.set_title("Installed Capacity by Fuel")
    fig.tight_layout()

    return ("generation/capacity_by_fuel", ax, cap.to_frame())


# Confirm the plot is discoverable
discover_all_plots()
from gat.registry import get_plot_names
assert "plot_capacity_by_fuel" in get_plot_names()

# Run it directly
scenario = SiennaScenario(
    simulation_files="example_data/sienna/v4/simulation_store.h5",
    system_file="example_data/sienna/v4/sys.json",
)
name, ax, df = plot_capacity_by_fuel(scenario)
print(name)
print(df)
plt.show()
```

Output:

```text
generation/capacity_by_fuel
                       capacity_mw
fuel
RenewableNonDispatch    348.42
NUCLEAR                 447.21
COAL                   2554.52
NATURAL_GAS            5448.21
RenewableDispatch      5616.90
```

To wire this into the reporting framework, drop the function definition
into a module that's imported (or registered as a plugin — see below)
before calling `gat.reports.scenario_single.run(...)`.

## External plugins

When your plot lives outside the GAT repo (in your own analysis package),
register it via the `gat_ext` entry-point group in your package's
`pyproject.toml`:

```toml
[project.entry-points."gat_ext"]
my_plots = "my_package.plots"
```

`my_package.plots` is a module that imports your `@plot_function`-
decorated callables. When GAT calls `discover_all_plots()`, it walks all
`gat_ext` entry points and imports them — your plot functions register
themselves on import.

The discovery mechanism is in
[`gat.registry.discover_external_plots`][external-discovery]. No further
setup is required.

[external-discovery]: https://github.com/NatLabRockies/GridAnalysisToolkit/blob/main/gat/registry/__init__.py

## Notes

- **Argument types in `**kwargs`** are introspected by the reporter and
  written into the report config YAML. Tuples are not supported because
  they don't round-trip through YAML cleanly — use lists or scalars.
- **Optional arguments without defaults** show up as disabled in the
  report config (the reporter won't run a plot whose required arg
  beyond `scenario` is unset).
- **Logging:** use `loguru` (`from loguru import logger`) inside plot
  functions for status messages — the reporter captures it into a
  per-run log file.
- **Avoid heavy state in plot functions** — they're called once per
  scenario in a fresh process when the reporter parallelizes (planned;
  serial today).
- The older `ScenarioPlotter` class in `gat.quickplots.scenario_plotter`
  is an experimental sketch; `@plot_function` is the supported path.
