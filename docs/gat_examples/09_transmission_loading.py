"""
Transmission Line Loading and Utilization (Plexos)
--------------------------------------------------

Two transmission views:

1. **Loading ranked** — line loading (% of rating) sorted descending,
   showing which lines hit the highest utilization across the horizon.
2. **Utilization** — distribution of hours each line operates above
   threshold percentiles (90/95/99% of rating).

This is the only example in the gallery using a Plexos fixture rather
than the Sienna RTS-GMLC fixture. Sienna's fixture is built with
``CopperPlatePowerModel`` so the simulation file has no
``FlowActivePowerVariable__Line`` data; switching the Sienna fixture's
generate.jl to ``DCPPowerModel`` would unlock these plots there too.
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt
from gat.scenariohandlers import PlexosScenario
import gat.quickplots as qp

plexos_dir = "../../example_data/plexos"
scenario = PlexosScenario(simulation_files=plexos_dir)

loading = scenario.get_line_loading()
utilization = scenario.get_line_utilization()

fig, axs = plt.subplots(1, 2, figsize=(14, 5))

qp.plot_loading_ranked(loading, ax=axs[0])
axs[0].set_title("Line Loading — Ranked")

qp.plot_lines_utilization(utilization, ax=axs[1])
axs[1].set_title("Line Utilization Distribution")

plt.tight_layout()
plt.show()
