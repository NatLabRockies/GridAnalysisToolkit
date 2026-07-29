"""
Annual System Dispatch Stack
----------------------------

A stacked area plot of system-wide generation by technology over the
fixture's full horizon, with the load curve overlaid.

This is the most common at-a-glance view of a production cost simulation.
Generation is grouped by display technology (Coal, Gas-CC, Gas-CT, PV,
Wind, etc.) and stacked from the bottom up; the line on top is the load.
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import matplotlib.pyplot as plt
from gat.scenariohandlers import SiennaScenario
import gat.quickplots as qp

# These examples use the in-repo Sienna RTS-GMLC fixture. Regenerate it via
# `make sienna-fixture-v4`. For project-based workflows, use `gat.load(...)`
# instead — see docs/source/python_api_load.md.
sienna_v4 = "../../example_data/sienna/v4"
scenario = SiennaScenario(
    simulation_files=f"{sienna_v4}/simulation_store.h5",
    system_file=f"{sienna_v4}/sys.json",
)

dispatch = scenario.get_area_dispatch(include_charging=False, include_use=False)

ax = qp.plot_annual_system_dispatch_stack(dispatch)
ax.set_title("RTS-GMLC — Annual System Dispatch")

plt.tight_layout()
plt.show()
