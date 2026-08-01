"""
This module is intended to work with MultiScenario objects.

Each plotting function should take in a MultiScenario object as an argument along with **kwargs

"""

from gat.quickplots.utils import create_flat_facet_axes
from gat.quickplots.core import plot_component_donut, plot_stacked_component_bar
import matplotlib.pyplot as plt
from loguru import logger
from gat.registry import plot_function
from typing import TYPE_CHECKING, List
from warnings import warn

if TYPE_CHECKING:
    from gat.scenariohandlers import MultiScenario


@plot_function("MultiScenario", plot_type="system")
def plot_generation_capacities(multi_scenario: "MultiScenario", **kwargs):
    """
    Plots a set of donut charts to compare generation capacities.

    Args:
        multi_scenario: MultiScenario object containing scenarios to compare
        area_filter: Optional list of areas to include in the plots
        **kwargs: Additional arguments passed to plot_component_donut

    Returns:
        Generator yielding tuples of (display_name, matplotlib_axis, dataframe)
    """

    area_filter = kwargs.get("area_filter")

    for display_name, scenario in multi_scenario.scenarios.items():
        logger.info(f"Plotting system capacity for {display_name}")
        total_capacity = scenario.get_generation_capacity()

        if area_filter is not None:
            all_areas = total_capacity.index.get_level_values(level="Area").unique()
            valid_areas = [a for a in area_filter if a in all_areas]
            missing_areas = [a for a in area_filter if a not in all_areas]
            if missing_areas:
                warn(
                    f"MULTIPLOT: plot_generation_capacities - areas {missing_areas} not found in scenario '{display_name}'"
                )

            if not valid_areas and area_filter:
                warn(
                    f"MULTIPLOT: plot_generation_capacities - no valid areas from filter found for scenario '{display_name}'. Skipping filtering for this scenario."
                )
            elif valid_areas:
                total_capacity = total_capacity.loc[valid_areas]

        fig, ax = plt.subplots()
        plot_component_donut(total_capacity.sum() * 1e-3, unit="GW", ax=ax, **kwargs)
        ax.set_title(f"Generation Capacity: {display_name}")

        yield (display_name, ax, total_capacity)


@plot_function("MultiScenario", plot_type="system")
def compare_system_capacities(
    multi_scenario: "MultiScenario", area_filter=None, **kwargs
):
    """
    Compares the total generation capacity between scenarios.

    Args:
        multi_scenario: MultiScenario object containing scenarios to compare
        area_filter: Optional list of areas to include in the comparison
        **kwargs: Additional arguments passed to plot_stacked_component_bar

    Returns:
        Tuple of (display_name, matplotlib_axis, dataframe)
    """
    logger.info("Plotting system capacity comparison")
    filtered_area_cap = multi_scenario.get_generation_capacity().fillna(0)

    if area_filter is not None:
        filtered_area_cap = filtered_area_cap.loc[area_filter]

    total_cap = filtered_area_cap.groupby(level="Scenario").sum() * 1e-3

    fig, ax = plt.subplots()
    plot_stacked_component_bar(total_cap, horizontal=True, ax=ax)
    ax.set_xlabel("Capacity (GW)")
    display_name = "System"
    ax.set_title(f"Generation Capacity - {display_name}")

    return (display_name, ax, total_cap)


@plot_function("MultiScenario", plot_type="system")
def compare_area_capacities(
    multi_scenario: "MultiScenario", area_filter=None, **kwargs
):
    """
    Compares generation capacity by area between scenarios.

    Args:
        multi_scenario: MultiScenario object containing scenarios to compare
        area_filter: Optional dict or set of areas to include in the comparison
        **kwargs: Additional arguments passed to plot_stacked_component_bar

    Returns:
        Generator yielding tuples of (display_name, matplotlib_axis, dataframe)
    """

    filtered_area_cap = multi_scenario.get_generation_capacity()

    for display_name in filtered_area_cap.index.get_level_values(level="Area").unique():
        logger.info(f"Plotting area capacity for {display_name}")
        if not area_filter or display_name in area_filter:

            fig, ax = plt.subplots()
            plot_stacked_component_bar(
                filtered_area_cap.loc[display_name] * 1e-3, horizontal=True, ax=ax
            )

            ax.set_xlabel("Capacity (GW)")
            ax.set_title(f"Area Capacity Comparison - {display_name}")
            yield (display_name, ax, filtered_area_cap.loc[display_name] * 1e-3)
