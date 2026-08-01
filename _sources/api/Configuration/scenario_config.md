# Saving and Loading Scenario Configurations

In an effort to streamline configuration across multiple scenarios system and simulation files, you can modify a *"ScenarioObject"*
to save a config and either. This applies to any Scenariohandler object that implements the BaseScenario class.
- load the same scenario from the configuration file.
- load the configuration but override the **system_file** and **simulation_paths**

The latter particularly useful for analyzing multiple scenarios from the same project. The configuration can include a superset of all technologies you intend to work
with.

You can also override the system file used to create the config. However, if the systems differ in technologies warnings about unmapped technologies may appear. It is
generally a good idea to update the config to fix those warnings and save a new config that includes a broader list of technologies.


## Example: Creating a Configuration and reusing it for a new scenario.

```python
from gat.scenariohandlers import SiennaScenario

sys_file = r'/path/to/system.json'
scenario1 = SiennaScenario(system_file=sys_file)
scenario1.area = 'r' # Optional: Defines the area as values coming from the 'r' column in the extended attributes

# Update the config object via python or directly edit in the output yaml file.
#...

scenario1.config.save('sienna_config.yaml')

# For Sienna and Plexos, you can pass a h5 file glob pattern to discover and load relevant simulation files.
scenario2 = SiennaScenario.from_config('sienna_config.yaml',
    display_name="Scenario2", # The name used for system level plots and multi-system, multi-simulation comparisons.
    system_file="/path/to/system2.json",
    simulation_paths="/path/to/simulations/*/*.h5")

scenario2.get_generation_capacity()
```