import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
import calendar
from .config import standard_color_dict
import gat.config as gc
from gat.models.base import Technology
from typing import Dict, List
from math import sqrt, ceil
from loguru import logger

# random_color moved to gat.colors (dependency-free); re-exported here
# under its original name for backward compatibility.
from gat.colors import random_color  # noqa: F401

color_map = {}
month_map = {index: month for index, month in enumerate(calendar.month_name) if month}


def set_colormap(custom_colors):
    color_map.update(custom_colors)


def get_colormap():
    new_colors = {}
    new_colors.update(color_map)
    new_colors.update(standard_color_dict)
    return new_colors


def set_default_font(fontfamily):
    matplotlib.rcParams["font.family"] = fontfamily


# Prefer Arial when present, fall back to DejaVu Sans (matplotlib's default).
# matplotlib's font_manager resolves this chain lazily against its cached
# font index — single ms, no system-wide font scan. The previous code called
# `fm.findSystemFonts(fontpaths=None, fontext='ttf')` at import time, which
# walks every TTF on disk and takes ~8 s on macOS (where 400+ system fonts
# live in multiple directories), inflating every `import gat.quickplots`.
matplotlib.rcParams["font.family"] = ["Arial", "DejaVu Sans"]


def get_gen_color_map(file):
    """
    Opens a .css file and parses it to get a color mapping.
    Open the css file in VSCode to quickly update mapping with built in Color Wheel.
    """
    color_dict = {}
    with open(file, "r") as f:

        for line in f:

            temp = line.strip().split(" ")
            gen_type = temp[0].replace("#", "")
            color = temp[1].split(":")[1].replace("}", "")
            color_dict[gen_type] = color
    return color_dict


def prepare_tech_legend(unique_tech):

    ordered_techs, ordered_colors = order_columns_colors(unique_tech)
    patches = []
    for i, tech in enumerate(ordered_techs):

        ipatch = mpatches.Patch(color=ordered_colors[i], label=tech)

        patches.append(ipatch)
    patches.reverse()
    return patches


def rank_series_values(series):

    series_sorted = series.sort_values(ascending=False).to_frame()
    series_sorted["rank"] = np.arange(len(series_sorted))

    return series_sorted


def above_threshold(x, threshold=90):
    if x >= threshold:
        return 1.0
    else:
        return 0.0


def scale_up_down(df):
    """
    Not fully implemented
    """
    max_val = df.max().max()  # Get max value of dataframe

    return NotImplemented


def trim_axs(axs, N):
    """
    Reduce *axs* to *N* Axes. All further Axes are removed from the figure.
    """
    if hasattr(axs, "flat"):
        axs = axs.flat
        for ax in axs[N:]:
            ax.remove()
        return axs[:N]
    else:
        return axs


def create_flat_facet_axes(N):
    """
    Create an almost square axes based on number of components.

    Returns:
        Flattened axes array for convenient looping
    """
    if N > 4:
        num_rows = ceil(sqrt(N))

        fig, axs = plt.subplots(num_rows, num_rows)

        flat_axs = trim_axs(axs, N)
        return fig, flat_axs
    else:
        fig, axs = plt.subplots(N, 1)
        return fig, axs


def scale_marker(input_arr, max_size=5, min_size=0):

    max_val = max(input_arr)

    output_arr = (input_arr / max_val) * max_size
    output_arr = [val if val > min_size else min_size for val in output_arr]

    return output_arr


def order_columns_colors(columns, load_cols=None):
    """
    Reorders the columns and returns the corresponding sequence of colors
    If a column is not mapped to a color, assigns a random color.
    Unassigned columns are first (bottom of the dispatch stack)
    """

    if load_cols == None:
        load_cols = gc.config.load_columns

    # TODO warn users if Tech is not in color map.
    temp_colors = get_colormap()

    columns_ordered = [val for val in temp_colors.keys() if val not in load_cols]

    sub_cols_ordered = [
        col for col in columns if col not in columns_ordered + load_cols
    ] + [col for col in columns_ordered if col in columns]
    sub_colors = [
        random_color() for col in columns if col not in columns_ordered + load_cols
    ] + [temp_colors[col] for col in columns_ordered if col in columns]

    return sub_cols_ordered, sub_colors


def make_cmap(techs: Dict[str, Technology]) -> dict:
    # Takes a dictionary of techs and creates an ordered technology map
    order = 0

    unordered_techs = []
    ordered_techs = {}
    for name, color in standard_color_dict.items():

        for tech in techs.values():
            if tech.display_group == name:
                tech.display_order = order
                tech.display_color = color
                ordered_techs[order] = tech
                order += 1

    for tech in techs.values():
        if tech.display_order == -1:
            unordered_techs.append(tech)

        else:
            ordered_techs[tech.display_order] = tech

    new_cmap = {}
    for tech in unordered_techs:
        new_cmap[tech.display_group] = tech.display_color

    for tech in ordered_techs.values():
        new_cmap[tech.display_group] = tech.display_color

    return new_cmap


def create_tech_legend(
    tech_map: Dict[str, str],
    reversed=True,
    title="",
    loc="upper left",
    bbox_to_anchor=None,
):
    """Creates a legend from a dictionary of name:color.

    Args:
        tech_map: Dictionary mapping technology names to their hex color codes
        reversed: If True, first item is plotted at the bottom of the legend
        title: Optional title for the legend
        loc: Location of legend ('right', 'left', 'top', 'bottom')
        bbox_to_anchor: Tuple (x, y) for custom legend positioning. When set, places legend
                        outside the axes at the specified position.
                        Example: (1.05, 1) places legend to the right of the plot.

    Returns:
        matplotlib.legend.Legend: Legend object that can be added to an axes
    """
    handles = []

    # Create patches for each technology
    for tech_name, color in tech_map.items():
        patch = mpatches.Patch(color=color, label=tech_name)
        handles.append(patch)

    # Reverse order if requested (default)
    if reversed:
        handles.reverse()

    # Set orientation based on location
    if loc in [
        "upper right",
        "upper left",
        "lower right",
        "lower left",
        "center right",
        "center left",
    ]:
        ncol = 1
    else:  # top or bottom
        ncol = min(3, len(handles))  # Limit to 3 columns max

    # Create legend with specified properties
    legend_kwargs = {
        "handles": handles,
        "title": title,
        "loc": loc,
        "ncol": ncol,
        "frameon": True,
        "framealpha": 0.8,
        "edgecolor": "lightgrey",
    }

    # Add bbox_to_anchor if provided
    if bbox_to_anchor is not None:
        legend_kwargs["bbox_to_anchor"] = bbox_to_anchor
        # When using bbox_to_anchor, it's usually good to set mode='expand' for side legends
        if loc in ["right", "left"]:
            legend_kwargs["mode"] = None
            legend_kwargs["borderaxespad"] = 0.0

    legend = plt.legend(**legend_kwargs)

    return legend


def create_marker_legend(marker_size: List[float], labels=None, title="", loc="right"):
    """Creates a legend for marker sizes indicating generator capacity on a map.

    Args:
        marker_size: List of marker sizes in descending order
        labels: Optional custom labels for each marker size, if None uses marker_size values
        title: Optional title for the legend
        loc: Location of legend ('right', 'left', 'top', 'bottom')

    Returns:
        matplotlib.legend.Legend: Legend object that can be added to an axes
    """
    # Sort marker sizes in descending order
    marker_size = sorted(marker_size, reverse=True)

    # Use provided labels or create default labels from marker sizes
    if labels is None:
        labels = [str(size) for size in marker_size]

    # Create handles for the legend
    handles = []
    for size, label in zip(marker_size, labels):
        # Create a scatter point for each size
        handle = plt.scatter(
            [], [], s=size, color="grey", alpha=0.7, edgecolor="black", linewidth=1
        )
        handles.append((handle, label))

    # Set orientation based on location
    if loc in [
        "upper right",
        "upper left",
        "lower right",
        "lower left",
        "center right",
        "center left",
    ]:
        ncol = 1
    else:  # top or bottom
        ncol = min(3, len(handles))  # Limit to 3 columns max

    # Create legend with specified properties
    legend = plt.legend(
        [h for h, l in handles],
        [l for h, l in handles],
        title=title,
        loc=loc,
        ncol=ncol,
        frameon=True,
        framealpha=0.8,
        edgecolor="lightgrey",
        scatterpoints=1,
        labelspacing=1.5,  # Add more space between legend items for marker visibility
    )

    return legend
