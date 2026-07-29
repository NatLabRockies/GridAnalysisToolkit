"""
Peak and Minimum Demand Windows
-------------------------------

Side-by-side stacked-area views around the timestamps of system-wide peak
and minimum demand. Each subplot shows a ±3-day window centered on the
event so you can see the dispatch ramp into and out of the peak/trough.

`plot_peak_demand_window` and `plot_min_demand_window` look up
``config.total_load_alias`` (default ``"Total Demand"``) in the dispatch
columns. The Sienna fixture has no storage charging, so the load is
labelled ``"Native Demand"`` by default — set
``scenario.load_includes_charging = True`` so the dispatch is labelled
``"Total Demand"`` and the window plots can find it.
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt
from gat.scenariohandlers import SiennaScenario
import gat.quickplots as qp

sienna_v4 = "../../example_data/sienna/v4"
scenario = SiennaScenario(
    simulation_files=f"{sienna_v4}/simulation_store.h5",
    system_file=f"{sienna_v4}/sys.json",
)
scenario.load_includes_charging = True

dispatch = scenario.get_area_dispatch(include_charging=False, include_use=False)

fig, axs = plt.subplots(1, 2, figsize=(14, 5), sharey=True)

qp.plot_peak_demand_window(dispatch, ax=axs[0])
qp.plot_min_demand_window(dispatch, ax=axs[1])

plt.tight_layout()
plt.show()
