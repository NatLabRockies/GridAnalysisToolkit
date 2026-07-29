"""
Per-Area Dispatch Facets
------------------------

Faceted view: one annual stack subplot per area in the system. Each
facet shows the same generation-by-tech stack as the system-wide view,
restricted to a single area.

Useful for comparing resource mix across regions in a multi-area model
(e.g., RTS-GMLC's three areas).
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

qp.facet_area_annual_dispatch(dispatch)

plt.tight_layout()
plt.show()
