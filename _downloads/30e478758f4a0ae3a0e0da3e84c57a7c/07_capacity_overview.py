"""
Generation Capacity Overview
----------------------------

Installed capacity by technology, sourced directly from the system
definition (not the simulation results). This is a useful sanity-check
view: what's actually in the model before any dispatch happens.

`plot_generation_capacities` returns ``(name, ax, dataframe)`` so you
can both render the chart and access the underlying capacity table for
further analysis.
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt
from gat.scenariohandlers import SiennaScenario
from gat.quickplots.system_plots import plot_generation_capacities

sienna_v4 = "../../example_data/sienna/v4"
scenario = SiennaScenario(
    simulation_files=f"{sienna_v4}/simulation_store.h5",
    system_file=f"{sienna_v4}/sys.json",
)

name, ax, capacity_df = plot_generation_capacities(scenario)
print(f"{name} — {len(capacity_df)} rows of capacity data")
print(capacity_df.head())

plt.tight_layout()
plt.show()
