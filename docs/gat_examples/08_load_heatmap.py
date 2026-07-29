"""
Load Heatmap and Duration Curve
-------------------------------

Two complementary views of the load shape:

1. **Heatmap** — hour-of-day × day-of-year, showing when load peaks
   typically occur (e.g., evening ramps, weekday vs. weekend).
2. **Sorted (load duration curve)** — load values sorted descending,
   showing how often demand exceeds a given level. Useful for sizing
   peaking capacity.

Both functions take a single ``pd.Series`` indexed by timestamp, so
you can apply them to any timeseries (load, net load, individual
generator output, etc.).
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt
from gat.scenariohandlers import SiennaScenario
from gat.quickplots.core import plot_series_heatmap, plot_series_sorted

sienna_v4 = "../../example_data/sienna/v4"
scenario = SiennaScenario(
    simulation_files=f"{sienna_v4}/simulation_store.h5",
    system_file=f"{sienna_v4}/sys.json",
)

# Build a system-wide load series by summing the area-aggregated load
dispatch = scenario.get_area_dispatch(include_charging=False, include_use=False)
load_cols = [c for c in dispatch.columns if c[1] == "Native Demand"]
total_load = dispatch[load_cols].sum(axis=1)
total_load.name = "system_load_mw"

fig, axs = plt.subplots(1, 2, figsize=(14, 5))
plt.sca(axs[0]); plot_series_heatmap(total_load); axs[0].set_title("Load Heatmap")
plt.sca(axs[1]); plot_series_sorted(total_load); axs[1].set_title("Load Duration Curve")

plt.tight_layout()
plt.show()
