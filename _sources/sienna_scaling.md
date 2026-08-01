# Sienna scaling and raw dataset access

Sienna writes simulation results in per-unit; GAT scales them to MW for the
high-level `get_*` API. This page documents where the scaling factor
(`base_power`) comes from and how to access unscaled data when you need it.

## Where `base_power` comes from

GAT resolves `base_power` for a scenario in this order:

1. **The h5 simulation file's group attrs** — `base_power` lives on each
   decision-model group (e.g.
   `/simulation/decision_models/UC/.attrs/base_power`). This is the
   authoritative source for simulation results because PowerSimulations
   serializes the value the model actually used.
2. **`sys.json`'s `units_settings.base_value`** — fallback when the h5 attr
   is missing. This is the system-level base; it usually matches the
   simulation but may not (e.g. when a single system is used to run
   simulations at different bases).
3. **`100.0`** — final fallback. `100 MVA` is the PowerSimulations.jl
   default, so this is almost always correct when the upstream sources are
   silent.

Why per-decision-model matters: a UC and an ED model in the same
simulation_store can in principle have different `base_power`. GAT looks at
the model attrs each time, not just at construction.

`SiennaScenario.unit_base_value` exposes the resolved value:

```python
import gat
scenario, _, _ = gat.load(scenario="my_uc_scenario")
print(scenario.unit_base_value)  # → 100.0 for an RTS-GMLC fixture
```

## Reading unscaled data

The high-level methods (`get_generation`, `get_area_dispatch`,
`get_line_flow`, etc.) return MW values (per-unit × `base_power`). For
unscaled data — the values exactly as they appear in the h5 file — use
`get_raw_dataset`:

```python
import gat

scenario, _, _ = gat.load(scenario="my_uc_scenario")

# Short alias (resolved against the parser's emulation_model index):
raw = scenario.get_raw_dataset("ActivePowerVariable__ThermalStandard")

# Or a full h5 path:
raw = scenario.get_raw_dataset(
    "/simulation/emulation_model/variables/ActivePowerVariable__ThermalStandard"
)
```

The DataFrame is timestamps × generators (no scaling applied). For an MW
view of the same data, use `scenario.get_generation()`.

## When to use which

| Task | Use |
|------|-----|
| Plotting MW dispatch, computing reserve margins, comparing across scenarios | High-level: `get_generation`, `get_area_dispatch`, `get_line_flow`, etc. |
| Inspecting exactly what PowerSimulations wrote to disk | `get_raw_dataset(key)` |
| Applying custom scaling (e.g. converting to GW, applying a different per-unit base) | `get_raw_dataset` then multiply yourself |
| Debugging a scaling discrepancy | `get_raw_dataset` to see the on-disk value, then `unit_base_value` to see what GAT will multiply by |

## Worked example with the v4 fixture

```python
import gat
from gat.scenariohandlers import SiennaScenario

# Skipping gat.load for a one-off path-based instantiation:
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

s = SiennaScenario(
    simulation_files="example_data/sienna/v4/simulation_store.h5",
    system_file="example_data/sienna/v4/sys.json",
)

raw_max = s.get_raw_dataset("ActivePowerVariable__ThermalStandard").max().max()
scaled_max = s.get_generation().max().max()

print(f"raw max:        {raw_max:.2f}  (per-unit)")
print(f"scaled max:     {scaled_max:.2f}  (MW)")
print(f"unit_base_value: {s.unit_base_value}")

assert scaled_max == raw_max * s.unit_base_value
```

## Notes

- `get_raw_dataset` works for any 2D h5 path. Decision-model paths can be
  3D (executions × entities × periods); those error in the current parser.
  Use the emulation model alias path for 2D access.
- The v1 `SiennaSimulation` class (`gat.simulations.sienna_v1`) exposes the
  same `base_power` resolution via its `base_power` property — the
  underlying parser is shared.
- For background on the broader Sienna data model, see
  [Scenarios and simulations](scenarios_and_simulations.md).
