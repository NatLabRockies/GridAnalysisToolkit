"""
Monthly System Dispatch
-----------------------

Stacked monthly totals of generation by technology. Useful for spotting
seasonality in dispatch (e.g., gas peaking in summer, hydro spring runoff)
without the high-frequency noise of an hourly view.

The fixture covers one week, so this plot will show a single bar — but
the same call works against full-year fixtures.
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

dispatch = scenario.get_area_dispatch(include_charging=False, include_use=False)

ax = qp.plot_monthly_system_dispatch_stack(dispatch)
ax.set_title("RTS-GMLC — Monthly System Dispatch")

plt.tight_layout()
plt.show()
