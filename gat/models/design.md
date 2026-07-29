# GAT configuration design for reusable configs.

The goal of the configuration Pydantic Model is to provide a common configuration that users initialize once, and then override the system and simulation file paths to work with multiple scenarios.

## Definitions

**Display Group**: The name for a group of generators or loads that are aggregated together in order to be displayed in a dataframe or plot. A set of display groups has a particular ordering to display for stack charts. Display groups also have a corresponding color that can be configured. Display groups can be a superset of a given scenarios set of technologies. (Useful for multi-scenario analysis where you might swap out different technologies.)

**System Technology to Display Group Map**: A map of generators types found natively in the model to their gat display group. Should Include Whether that generator is curtailable (e.g. the pv portion of pv-battery which gets combined later.). This is scenario specific and not necessarily applied to GAT visualizations.

**System Load Names to Display Group Map**: A map of load types found natively in the system/simulation and how they should be displayed.

**Scenario Name**: A shortened scenario name to display in the case of multi-scenario analysis and general logging.

**System File**: The full path to the system file.

**Simulation Files**: The full path to the simulation file(s)

**System Type**: Plexos, Sienna, ReEDS etc.

**System Config**: Type specific configuration for reading system files. For example, Sienna needs additional configuration to determine where the certain datasets and properties are depending on the version of Sienna used.

**Simulation Config**: Similar to system config. Should include additional data for determining path(s) or key lookups to particular data.

## Desired Features

- Saves the model specific technology to display group. (formerly saved in _tech_simple). Should be a small key value map, where the key is the native generation technology and the values are "display_group": {value}, "curtailable": {True/False},

- Methods to add new technologies/loads/generation types to a configuration in order to extend a previous configuration.

- Warnings when a given technology doesn't have a display group. Defaults to technology-technology.

- Able to use the a common function to load a GAT scenario from a config file. Reads the System file and simulation files to load the data, initializes the mapping properties in BaseScenario/PlexosScenario etc. The common function should be able to override the system and simulation files with new file paths to create a new scenario while keeping the Display group configuration.

- Should have a display group for loads and another for generation. Loads should also include additional styling options for how line graphs are displayed (dashed vs solid etc.)

- Users should be able to initialize a scenario the original way, modify the configurations like _tech_simple, etc. and then save the model to a configuration file to be used later. Users can also load a configuration file and use a new system. Doing so will display any unmapped configurations that the user should update. Then the user can resave the config again.


## Tricky parts

Currently the quickplots and scenariohandlers aren't directly linked but need to be. If the display group names and colors change for a scenario, so should the quickplots.

For multi-scenario plots, we may want to take a union of display groups to determine the legend. For example, if one scenario has hydrogen and another doesn't how will display order be determined.

In some sense, the DisplayGroup is a global setting in a multi-scenario analysis setting.


## Other helpful functions.

- The DisplayGroup config should be used to create legends in the correct order every time. When charging and generation are plotted in the same plot, the legend gets repeated for the charging technologies, making the legend cluttered. It also requires a lengthy section of code to remake the legend. The helper function should also reduce the legend of a given display group is not present.