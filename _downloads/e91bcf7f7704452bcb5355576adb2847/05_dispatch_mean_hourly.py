"""
Mean Hourly Dispatch Profile
----------------------------

The average dispatch shape over a 24-hour day, computed by grouping
the timeseries by hour-of-day and taking the mean. Useful for
characterizing typical daily ramps (morning load pickup, solar
midday, evening peak).
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

qp.plot_mean_hourly_dispatch(dispatch)

plt.tight_layout()
plt.show()
