"""
Author: Micah Webb
Date: 2025-06-09

Description: Contains plotting functions that take a single Scenario Object and **optional** keyword arguments.
The keyword arguments will be inspected by the report or plugin management system to generate additional configuration parameters for a given plot.

A function may also take a specific Concrete implementation of Scenario Object and the report init command will only generate plot functions that are
compatible.

"""

from gat.scenariohandlers import *
import gat.quickplots as qp
from gat.registry import plot_function
from gat.quickplots.utils import scale_marker, create_marker_legend, create_tech_legend
import matplotlib.pyplot as plt
from typing import List, Optional, Union, Dict, Any
import matplotlib.patches as mpatches
import numpy as np


@plot_function("BaseScenario", plot_type="system")
def plot_generation_capacities(scenario: "BaseScenario", **kwargs):
    """
    Plots a donut charts of system generation capacity.

    Args:
        scenario: MultiScenario object containing scenarios to compare
        **kwargs: Additional arguments passed to plot_component_donut

    Returns:
        Generator yielding tuples of (display_name, matplotlib_axis, dataframe)
    """

    total_capacity = scenario.get_generation_capacity()

    fig, ax = plt.subplots()
    qp.plot_component_donut(total_capacity.sum() * 1e-3, unit="GW", ax=ax, **kwargs)
    ax.set_title(f"Generation Capacity")

    return ("generation capacity", ax, total_capacity)


@plot_function("SiennaScenario", plot_type="system")
def map_system_capacity(
    scenario: SiennaScenario,
    boundary_map=None,
    marker_scale=0.5,
    marker_alpha=0.8,
    marker_legend_cap=[100, 1000],
    marker_legend_edgecolor="black",
    marker_label_xpad=1.5,
    marker_label_ypad=2,
    marker_title_ypad=2,
    background_facecolor="black",
    background_edgecolor="white",
    background_alpha=0.5,
    padding=0.15,
    dpi=150,
    figsize=[20, 20],
):
    """maps the system capacity"""

    fig, ax = plt.subplots(dpi=dpi, figsize=figsize)

    gen_gdf = scenario.system.get_component_geo(
        scenario.config.system_config.generation_components
    )

    # Filter to available generators
    gen_gdf = gen_gdf[gen_gdf.available == True]

    agg_levels = scenario.list_aggregation_levels()
    available_areas = []
    if agg_levels is not None:
        available_areas = [k for k in agg_levels.values()]
    default_area = None

    if len(available_areas) > 0:

        default_area = available_areas[0]
    if boundary_map is None and len(available_areas) > 0:

        lookup_group, lookup_value = default_area[0], default_area[1]
        area_gdf = scenario.config.area_lookups.get(lookup_group).get_layer_gdf(
            lookup_value
        )
    elif boundary_map is not None:
        lookup_group, lookup_value = scenario.list_aggregation_levels().get(
            boundary_map, default_area[1]
        )
        area_gdf = scenario.config.area_lookups.get(lookup_group).get_layer_gdf(
            lookup_value
        )
    else:
        area_gdf = None

    cmap = scenario.config.get_technology_cmap()

    gen_gdf["Technology"] = (
        gen_gdf["name"]
        .map(scenario._tech_map)
        .map(scenario._tech_simple)
        .fillna("Other")
    )
    gen_gdf["capacity"] = gen_gdf["base_power"] * gen_gdf["rating"]
    gen_gdf["color"] = gen_gdf["Technology"].map(cmap)

    # Calculate capacity statistics
    cap_min = gen_gdf["capacity"].min()
    cap_mean = gen_gdf["capacity"].mean()
    cap_median = gen_gdf["capacity"].median()
    cap_max = gen_gdf["capacity"].max()
    stats_subtitle = f"Capacity (MW): Min = {cap_min:.2f}, Mean = {cap_mean:.2f}, Median = {cap_median:.2f}, Max = {cap_max:.2f}"

    unique_tech = {v for v in gen_gdf["Technology"].unique()}
    cmap = {t: v for t, v in cmap.items() if t in unique_tech}

    if area_gdf is not None:
        area_gdf.plot(
            facecolor=background_facecolor,
            edgecolor=background_edgecolor,
            alpha=background_alpha,
            ax=ax,
        )
        crs = area_gdf.crs
    else:
        crs = gen_gdf.crs

    gen_gdf = gen_gdf.to_crs(crs)

    # Get the bounds of the GeoDataFrame
    bounds = gen_gdf.total_bounds
    # Add some padding (e.g., 5% of the range)
    x_padding = (bounds[2] - bounds[0]) * padding
    y_padding = (bounds[3] - bounds[1]) * padding

    ax.set_xlim(bounds[0] - x_padding, bounds[2] + x_padding)
    ax.set_ylim(bounds[1] - y_padding, bounds[3] + y_padding)

    ax.set_xticks([])
    ax.set_yticks([])

    gen_gdf.plot(
        color=gen_gdf["color"],
        markersize=gen_gdf["capacity"] * marker_scale,
        linewidth=1.5,
        ax=ax,
        alpha=marker_alpha,
    )

    # Create a separate figure-level axis for the tech legend
    legend_ax = fig.add_axes([0.85, 0.5, 0.1, 0.4])  # [left, bottom, width, height]
    legend_ax.axis("off")  # Hide this axis - it's just for the legend

    # add the legends
    tech_legend = create_tech_legend(cmap, title="Gen Type", loc="upper right")
    legend_ax.add_artist(tech_legend)

    # Position for the marker legend (bottom right with some padding)
    legend_x = bounds[2] - x_padding * 0.85
    legend_y = bounds[1] + y_padding * 0.05

    # Create marker capacity values and their positions
    marker_legend_cap.sort()  # Sort in ascending order
    from math import sqrt

    max_cap = max(marker_legend_cap)

    for i, cap in enumerate(marker_legend_cap):
        # Calculate size based on the same scaling used for actual data points
        # size = max_marker_size * (cap / max_capacity)
        size = cap * marker_scale

        radius_in_points = sqrt(size)

        # Convert points to data units (approximate conversion)
        bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
        data_range = bounds[3] - bounds[1]
        display_range = bbox.height * fig.dpi
        radius_in_data_units = radius_in_points * data_range / display_range
        max_radius_in_data_units = (
            sqrt(max_cap * marker_scale) * data_range / display_range
        )

        # Define marker and text positions
        marker_x = legend_x
        marker_y = (
            legend_y + radius_in_data_units
        )  # (i * radius_in_data_units * 3)  # Space markers vertically

        # Position text with offset
        text_x = legend_x + max_cap * marker_scale * 100 * marker_label_xpad
        text_y = marker_y + radius_in_data_units * 1.5  # Position text above the marker

        # Plot marker
        ax.scatter(
            marker_x,
            marker_y,
            s=size,
            facecolor="none",
            edgecolor=marker_legend_edgecolor,
            linewidth=1,
            alpha=0.7,
            zorder=1000,  # Ensure it's on top
        )

        # Calculate connection point on top of the circle
        connection_x = marker_x
        connection_y = marker_y + radius_in_data_units

        # Draw annotation line connecting marker to text
        ax.annotate(
            f"{cap} MW",
            xy=(connection_x, connection_y),  # Start point (top of circle)
            xytext=(text_x, text_y),  # End point (text position)
            fontsize=14,
            ha="right",
            va="center",
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=2),
            arrowprops=dict(
                arrowstyle="-",  # Simple line without arrow
                color="black",
                linewidth=1,
                alpha=0.7,
                connectionstyle="angle,angleA=0,angleB=90,rad=0",  # Elbow style (90-degree angle)
            ),
            zorder=1000,
        )

    # Add a title for the marker legend
    ax.text(
        legend_x,
        # legend_y + len(marker_legend_cap) * (y_range * 0.03),
        legend_y + radius_in_data_units * 4 + marker_title_ypad,
        "Capacity",
        fontsize=18,
        fontweight="bold",
        verticalalignment="center",
        bbox=dict(facecolor="none", alpha=0.7, edgecolor="none", pad=2),
        zorder=1000,
    )
    ax.set_title(f"Generator Capacity Map \n {stats_subtitle}", fontsize=20)
    # Add statistics as subtitle
    # ax.set_title(stats_subtitle, fontsize=14, pad=10, loc='center', style='italic', color='dimgray')

    return ("map_generation_capacity", ax, gen_gdf)


@plot_function("SiennaScenario", plot_type="system")
def map_transmission_capacity(
    scenario: SiennaScenario,
    available_only: bool = True,  # filter to available lines only.
    min_voltage: float = 138,
    max_voltage: float = 745,
    cmap: Optional[Union[str, Dict[Any, str]]] = {
        345.0: "red",
        230.0: "green",
        138.0: "blue",
        69.0: "purple",
    },  # can be a matplotlib cmap or user provided categorical.
    max_linewdith: float = 10,
    min_linewidth: float = 0,
    linewidth_scale: float = 1,
    line_alpha: float = 0.7,
    background_facecolor="black",
    background_edgecolor="white",
    background_alpha=0.5,
    padding=0.15,
    dpi=150,
    figsize=[20, 20],
    boundary_map: Optional[str] = None,
    capacity_legend_values: List[float] = [
        10,
        50,
        100,
    ],  # capacity values to show in the legend
    legend_fontsize: int = 12,  # font size for legend text
    legend_position: str = "lower right",  # position for the unified legend
    legend_alpha: float = 0.8,  # alpha for the legend elements
    capacity_legend_title: str = "Capacity (MW)",
    voltage_legend_title: str = "Voltage (kV)",
    line_legend_length: float = 0.5,  # length of the capacity legend lines in data units
    line_legend_spacing: Optional[
        float
    ] = None,  # vertical spacing between legend lines, auto-calculated if None
    line_legend_padding: float = 0.02,  # padding around the legend in data units
    spacing_factor: float = 2.0,  # multiplier for spacing between legend lines relative to max line width
    legend_text_spacing: float = 0.03,  # spacing between legend line and text as percentage of x bounds
    voltage_section_spacing: float = 0.03,  # additional spacing between capacity and voltage sections
    legend_corner_radius: float = 0.01,  # radius for rounded corners of the legend box
    legend_width_padding: float = 0.1,  # additional width padding as percentage of the legend width
    legend_bottom_padding: float = 0.2,  # additional padding at the bottom as percentage of line spacing
):
    import pandas as pd
    import geopandas as gpd
    from matplotlib.patches import Rectangle

    fig, ax = plt.subplots(dpi=dpi, figsize=figsize)

    bus_df = scenario.system.get_component_data("ACBus")
    arc_geo = scenario.system._get_arc_geo()

    bus_df = bus_df[["base_voltage", "name", "area"]].reset_index()

    arc_geo_meta = arc_geo.merge(
        bus_df, left_on="from_uuid", right_on="UUID", suffixes=["_arc", ""]
    ).merge(bus_df, left_on="to_uuid", right_on="UUID", suffixes=["_from", "_to"])
    arc_geo_meta = arc_geo_meta[
        [
            "UUID_arc",
            "base_voltage_from",
            "base_voltage_to",
            "area_from",
            "area_to",
            "name_from",
            "name_to",
            "geometry",
        ]
    ]

    # Get line data and
    line_df = scenario.system.get_component_data("Line")
    line_df["UUID_arc"] = line_df["arc"].apply(lambda x: x["value"] if x else None)
    line_df = line_df[["UUID_arc", "name", "r", "x", "rating", "available"]]
    line_df["capacity"] = line_df["rating"] * scenario.unit_base_value

    # merge with geometry
    line_geo = pd.merge(line_df.reset_index(), arc_geo_meta, on="UUID_arc")
    line_gdf = gpd.GeoDataFrame(
        line_geo[line_geo.available == available_only], crs="EPSG:4326"
    )
    line_gdf = line_gdf[
        line_gdf["base_voltage_from"].between(
            min_voltage, max_voltage, inclusive="both"
        )
    ]
    line_gdf["linewidth"] = scale_marker(
        line_gdf["capacity"], max_size=max_linewdith, min_size=min_linewidth
    )

    # Calculate capacity statistics
    cap_min = line_gdf["capacity"].min()
    cap_mean = line_gdf["capacity"].mean()
    cap_median = line_gdf["capacity"].median()
    cap_max = line_gdf["capacity"].max()
    stats_subtitle = f"Capacity (MW): Min = {cap_min:.2f}, Mean = {cap_mean:.2f}, Median = {cap_median:.2f}, Max = {cap_max:.2f}"

    ## plotting

    # plot base map
    agg_levels = scenario.list_aggregation_levels()
    available_areas = []
    if agg_levels is not None:
        available_areas = [k for k in agg_levels.values()]
    default_area = None

    if len(available_areas) > 0:

        default_area = available_areas[0]
    if boundary_map is None and len(available_areas) > 0:

        lookup_group, lookup_value = default_area[0], default_area[1]
        area_gdf = scenario.config.area_lookups.get(lookup_group).get_layer_gdf(
            lookup_value
        )
    elif boundary_map is not None:
        lookup_group, lookup_value = scenario.list_aggregation_levels().get(
            boundary_map, default_area[1]
        )
        area_gdf = scenario.config.area_lookups.get(lookup_group).get_layer_gdf(
            lookup_value
        )
    else:
        area_gdf = None

    if area_gdf is not None:
        area_gdf.plot(
            facecolor=background_facecolor,
            edgecolor=background_edgecolor,
            alpha=background_alpha,
            ax=ax,
        )
        crs = area_gdf.crs
    else:
        crs = line_gdf.crs

    line_gdf = line_gdf.to_crs(crs)

    # Get the bounds of the GeoDataFrame
    bounds = line_gdf.total_bounds
    # Add some padding (e.g., 5% of the range)
    x_padding = (bounds[2] - bounds[0]) * padding
    y_padding = (bounds[3] - bounds[1]) * padding

    ax.set_xlim(bounds[0] - x_padding, bounds[2] + x_padding)
    ax.set_ylim(bounds[1] - y_padding, bounds[3] + y_padding)

    ax.set_xticks([])
    ax.set_yticks([])

    line_gdf.plot(
        color=line_gdf["base_voltage_from"].apply(lambda x: cmap.get(x, "grey")),
        linewidth=line_gdf["linewidth"] * linewidth_scale,
        alpha=line_alpha,
        ax=ax,
    )

    max_linewdith = line_gdf["linewidth"].max()

    # Create a unified legend for both capacity and voltage
    # Sort capacity values in ascending order
    capacity_legend_values.sort()

    # Get sorted voltage values for legend
    voltage_values = sorted(cmap.keys())

    # Determine position of the unified legend
    if legend_position == "lower right":
        legend_x = bounds[2] - x_padding * 0.3
        legend_y = bounds[1] + y_padding * 0.3
    elif legend_position == "lower left":
        legend_x = bounds[0] + x_padding * 0.2
        legend_y = bounds[1] + y_padding * 0.3
    elif legend_position == "upper right":
        legend_x = bounds[2] - x_padding * 0.3
        legend_y = bounds[3] - y_padding * 0.3
    elif legend_position == "upper left":
        legend_x = bounds[0] + x_padding * 0.2
        legend_y = bounds[3] - y_padding * 0.3
    else:
        legend_x = bounds[2] - x_padding * 0.3
        legend_y = bounds[1] + y_padding * 0.3

    # Calculate the line length in data units
    line_length = x_padding * line_legend_length

    # Calculate line widths for the capacity legend
    legend_widths = [
        linewidth_scale * capacity / capacity_legend_values[-1] * max_linewdith
        for capacity in capacity_legend_values
    ]

    # Calculate spacing based on the maximum linewidth if not specified
    max_legend_width = max(legend_widths)
    if line_legend_spacing is None:
        line_legend_spacing = (
            max_legend_width * spacing_factor * (bounds[3] - bounds[1]) / 1000
        )

    # Calculate positions for all legend elements
    capacity_positions = [
        legend_y - (i + 1) * line_legend_spacing
        for i in range(len(capacity_legend_values))
    ]
    voltage_title_y = (
        legend_y
        - len(capacity_positions) * line_legend_spacing
        - line_legend_spacing * 1.5
        - y_padding * voltage_section_spacing / 2
    )
    voltage_positions = [
        voltage_title_y - (i + 1) * line_legend_spacing - line_legend_spacing / 2
        for i in range(len(voltage_values))
    ]

    # Get the position of the last item (lowest point in legend)
    last_item_y = voltage_positions[-1] if voltage_positions else capacity_positions[-1]

    # Add extra padding at the bottom
    bottom_padding = line_legend_spacing * legend_bottom_padding

    # Calculate top and bottom of the legend box
    legend_top = legend_y + line_legend_spacing * 0.5  # Top of the legend
    legend_bottom = last_item_y - bottom_padding  # Bottom with padding

    # Calculate the total height of the legend
    total_legend_height = legend_top - legend_bottom

    # Width with extra space for text
    text_offset = legend_x + line_length + x_padding * legend_text_spacing
    legend_width = (line_length + 4 * line_legend_padding + line_length) * (
        1 + legend_width_padding
    )  # Add extra width padding

    # Calculate the corner radius for rounded corners (in data units)
    corner_radius = x_padding * legend_corner_radius

    # Create a background rectangle for the unified legend with rounded corners
    from matplotlib.patches import FancyBboxPatch

    rect = FancyBboxPatch(
        (
            legend_x - line_legend_padding,
            legend_bottom,
        ),  # Start at the bottom of the legend
        legend_width,
        total_legend_height,
        boxstyle=f"round,pad=0,rounding_size={corner_radius}",
        facecolor="white",
        alpha=0.7,
        edgecolor="gray",
        linewidth=0.5,
        zorder=999,
    )
    ax.add_patch(rect)

    # Add the capacity legend title
    ax.text(
        legend_x + legend_width / 2,
        legend_y,
        capacity_legend_title,
        fontsize=legend_fontsize + 2,
        fontweight="bold",
        horizontalalignment="center",
        verticalalignment="center",
        zorder=1000,
    )

    # Draw capacity lines and labels
    for i, capacity in enumerate(capacity_legend_values):
        y_pos = capacity_positions[i]
        width = legend_widths[i]

        # Draw the line - black line for capacity
        ax.plot(
            [legend_x, legend_x + line_length],
            [y_pos, y_pos],
            color="black",
            linewidth=width,
            solid_capstyle="butt",
            alpha=legend_alpha,
            zorder=1000,
        )

        # Add the capacity label
        ax.text(
            text_offset,
            y_pos,
            f"{capacity} MVA",
            fontsize=legend_fontsize,
            horizontalalignment="left",
            verticalalignment="center",
            zorder=1000,
        )

    # Add the voltage legend title - positioned below capacity section
    ax.text(
        legend_x + legend_width / 2,
        voltage_title_y,
        voltage_legend_title,
        fontsize=legend_fontsize + 2,
        fontweight="bold",
        horizontalalignment="center",
        verticalalignment="center",
        zorder=1000,
    )

    # Set a consistent linewidth for all voltage legend lines
    voltage_line_width = (
        max_legend_width * 0.6
    )  # Slightly smaller than max capacity line

    # Draw voltage lines and labels
    for i, voltage in enumerate(voltage_values):
        y_pos = voltage_positions[i]
        color = cmap.get(voltage, "grey")

        # Draw the line - colored by voltage
        ax.plot(
            [legend_x, legend_x + line_length],
            [y_pos, y_pos],
            color=color,
            linewidth=voltage_line_width,
            solid_capstyle="butt",
            alpha=legend_alpha,
            zorder=1000,
        )

        # Add the voltage label
        ax.text(
            text_offset,
            y_pos,
            f"{voltage} kV",
            fontsize=legend_fontsize,
            horizontalalignment="left",
            verticalalignment="center",
            zorder=1000,
        )

    ax.set_title(f"Transmission Capacity Map \n {stats_subtitle}", fontsize=20)

    return ("map_transmission_capacity", ax, line_gdf)
