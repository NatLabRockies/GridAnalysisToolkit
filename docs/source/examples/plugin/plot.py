"""
GAT External Plotting Plugin Example
====================================

This module demonstrates how to create an external plotting plugin for GAT.
External plugins allow developers to extend GAT's functionality by adding
custom plotting functions or generators without modifying the core GAT codebase.

Every plotting function should take a Scenario Object as an input along
with any specific keyword arguments for your plot. Specific keyword arguments will
be inspected and saved into the reporting configuration file. Any additional required arguments apart from scenario,
will default to None and the plot will be set to disabled in the reporting configuration yaml file.

Plotting functions are responsible any data querying, manipulation, and specific plotting needs. It is useful
to leverage the styling used in gat.quickplots, although it is not required.

Plot Function Requirements
--------------------------
The only required input for a plotting function is the scenario object. The output of the plotting function or generator
will be a tuple of (str, matplotlib.axes, DataFrame).

The first entry of the tuple signifies the name of the result, which
will be used as the file name when saving the plot or corrseponding data.

The second entry is the finalized matplotlib axes that will be saved directly to png.

The third entry is the dataframe used to generate the plot, often a result of aggregations or filtering.

Argument Types
--------------
Most argument types are allowed **with the exception of tuple**. (Arguments are saved to yaml)

How the External Plugin System Works
-------------------------------------

1. **Define Plotting Functions**:
   Create Python functions that accept a scenario object as their first argument.
   These functions will generate plots specific to the scenario type. BaseScenario plots
   should utilize apis that are common to all scenario objects.

2. **Use the `@plot_function` Decorator**:
   Use the `@plot_function` decorator from `gat.registry` to register your
   plotting functions. The decorator takes two arguments:
   - `scenario_type`: The scenario class name (e.g., "PlexosScenario",
     "SiennaScenario") that the plot function is designed for. Use "BaseScenario"
     for generic plots that apply to all scenarios.
   - `plot_type`: A string to categorize the plot (e.g., "plugin_example").

3. **Register the Plugin via Entry Points**:
   In your `setup.py`, define an entry point in the `gat_ext` group. This entry
   point tells GAT where to find your plugin module. For example:

   .. code-block:: python

       entry_points={
           'gat_ext': [
               'gat_plugin_example = plot',
           ],
       }

4. **Install the Plugin**:
   Once your plugin is packaged, install it using pip. GAT will automatically
   discover and load the plotting functions from your plugin.

Example Functions
-----------------

This module includes three example plotting functions:
- `plexos_example`: A plot specific to `PlexosScenario`.
- `sienna_example`: A plot specific to `SiennaScenario`.
- `generic_example`: A generic plot for all scenarios inheriting from `BaseScenario`.

"""

from gat.registry import plot_function
from typing import TYPE_CHECKING
import matplotlib.pyplot as plt

if TYPE_CHECKING:
    from gat.scenariohandlers import PlexosScenario, SiennaScenario, BaseScenario


@plot_function("PlexosScenario", "plugin_example")
def plexos_example(scenario: "PlexosScenario"):
    """
    Plexos specific plotting plugin. Only applies to PlexosScenario objects.


    :returns:
        Basic Plot with the word PLEXOS
    """

    fig, ax = plt.subplots()

    ax.text("PLEXOS")


    return ("plexos_plugin_example", ax, None)

@plot_function("SiennaScenario", "plugin_example")
def sienna_example(scenario: "SiennaScenario"):
    """
    Sienna specific plotting plugin. Only applies to SiennaScenario objects.


    :returns:
        Basic Plot with the word Sienna
    """

    fig, ax = plt.subplots()

    ax.text("Sienna")


    return ("sienna_plugin_example", ax, None)


@plot_function("BaseScenario", "plugin_example")
def generic_example(scenario: "BaseScenario"):
    """
    Generic plotting plugin. Applies to all implemnters of the BaseScenario.


    :returns:
        Basic Plot with the word Generic
    """

    fig, ax = plt.subplots()

    ax.text("Generic")


    return ("generic_plugin_example", ax, None)


