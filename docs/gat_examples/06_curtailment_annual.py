"""
Curtailment — Annual and Monthly
--------------------------------

Stacked time series of curtailed VRE energy by technology. The annual
view shows total curtailed MWh; the monthly view shows seasonality.

Curtailment is computed as the difference between renewable
*availability* (the time series parameter) and renewable *dispatch*
(the variable). It's only meaningful for technologies in
``gc.config.curtailable_tech`` — typically PV, Wind, RTPV.
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

fig, axs = plt.subplots(1, 2, figsize=(14, 5))

qp.plot_annual_system_curtailment_stack(dispatch, ax=axs[0])
axs[0].set_title("Annual Curtailment by Technology")

qp.plot_monthly_system_curtailment_stack(dispatch, ax=axs[1])
axs[1].set_title("Monthly Curtailment")

plt.tight_layout()
plt.show()
