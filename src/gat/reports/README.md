# Reporting Architecture

The reporting system is designed for ease of use, ease of code contribution, and extendability. Each report instance loops through the available plots
and attempts, via try/except, to make the available plot, save the corresponding dataframe if avialable, and finally wrap the plots up into a powerpoint if desired.

For end users, gat will automatically discover available plots, via a decorator either internally or externally via plugins with entry_points. The discovery
mechanism verifies that each plotting function takes a Scenario handler, (BaseScenario, SiennaScenario, PlexosScenario, MultiScenario, etc), and parses the function signature
into the reporting configuration. In this way, users can see the available options and update the default values through the configurations yaml file.

By standardizing the plotting interface around Scenario objects, like BaseScenario, internal and external visualization contributors are empowered to design and contribute their own plots without
having to understand the internal discovery mechanisms or the gat data modeling system. GAT can then be extended by external contributors tailoring solution to their projects, and enabling other users to reuse
their contributions if desired.

The primary reporting mechanism looks at the input type of report or scenario configuration to determine which plots are available. For example, all BaseScenario plots are available to
any Scenario Object that can implement the BaseScenario, at least partially. Some plots may be written for specific Scenario objects, indicated in the function signature. Plots can also be
structured with an arbitrary number of optional arguments that will show up in the report configuration after running the init command. If any additional arguments besides the Scenario Object are
left blank, the configuration will display that the plot is disabled and it won't run.

## Discovery Mechanism

With v0.9.0 of GAT, an plugin/plot management system is added to manage which plots are available. The plugin manager defines a function decorator to indicate which functions should be available,
and the discovery mechanism verifies and tracks the function signature. For external plugins, the management system will load modules with the "gat_ext" entry point and perform the same verification.
The management system also avoids using external plugin management system packages, like pluggy, as they don't meet the needs of arbitrary function signatures. **The only required function argument is the Scenario Object**.
External contributors merely need to import the management system decorator and decorate their functions.

## Parallelism

The reporting mechanism aims to provide multiprocessing of various plots so that users can leverage multi-core machines without needing to implement it on their own. However, there is still the option
for single-threaded workloads.

## Function Return

The functions should return a pydantic instance with the following:

- display_name: determining how to save the file name. (Usually hardcoded or formatted inside the plotting function)
- ax: the matplotlib axes object to save as a png
- data: a dataframe representing the processed and formatted data used for the plot.




