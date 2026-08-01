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
import glob
import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt

# PLEXOS solution files are proprietary and not distributed with GAT,
# so unlike the Sienna examples this one only executes when you point
# it at your own solution directory (GAT_PLEXOS_FIXTURE, or drop .h5
# files in example_data/plexos). The docs build renders the code
# without figures when no fixture is available.
plexos_dir = os.environ.get("GAT_PLEXOS_FIXTURE", "../../example_data/plexos")

if not glob.glob(os.path.join(plexos_dir, "*.h5")):
    print(
        "Plexos fixture not available — set GAT_PLEXOS_FIXTURE to a "
        "directory of PLEXOS .h5 solution files to run this example."
    )
else:
    from gat.scenariohandlers import PlexosScenario
    import gat.quickplots as qp

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
