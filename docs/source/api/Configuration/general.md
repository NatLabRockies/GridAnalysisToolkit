# Configuring GAT

GAT provides some simple configuration APIs to set your alias for Load types, and curtailable technologies

You must import and configure the config object before importing quickplots or a scenario handler.

<pre class="brush: python">

from gat.config import config

# update the name for unserved energy
config.unserved_energy_alias =  'Dropped Load'

# now import quickplots and Scenario Objects.
import gat.quickplots as qp
from gat.scenariohandlers import SiennaScenario, PlexosScenario

# Further updates to the config object aren't reflected in quickplots or Scenario Objects

</pre>

```{eval-rst}
.. automodule:: gat.config
    :members:

```

