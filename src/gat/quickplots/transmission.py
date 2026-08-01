import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patheffects as path_effects
import pandas as pd
import numpy as np
import random
import calendar
from .utils import *
import warnings

# TODO move to config
curt_tech = ['Land-based Wind',"Offshore Wind", 'PV','dPV','VRE']
#columns_ordered = [val for val in color_dict.keys()]

color_map = {}

month_map = {index:month for index, month in enumerate(calendar.month_name) if month}

MW_to_TW = 1000000
MW_to_GW = 1000

### FLOW PLOTS
def plot_loading_ranked(loading_df, palette=None, backend=None, **kwargs):

    """
    Calculated the mean and max loading and plots the line loading in ranked order.

    Expects a line loading dataframe.
    Can plot a raw flow dataframe, but labels/legend would not be accurate.

    y-axis: Loading %
    x-axis: Rank of line (0 - # of lines)
    """


    ax = kwargs.get("ax", plt.gca())

    load_ave_sorted = rank_series_values(loading_df.mean())
    load_max_sorted = rank_series_values(loading_df.max())

    load_ave_sorted.rename(columns={0: "Mean Load"}, inplace=True)
    load_max_sorted.rename(columns={0: "Max Load"}, inplace=True)


    load_ave_sorted.plot.line(x='rank', y='Mean Load', ax=ax, color='Blue', label="Loading (ave)")
    load_max_sorted.plot.line(x='rank', y='Max Load', ax=ax, color='Gold',label = "Loading (max)",grid=True)

    ax.set_ylabel("Loading %")
    ax.set_xlabel("Number of Lines")

    return ax


# TODO clean up this.

def plot_lines_utilization(utilization, palette=None, backend=None, **kwargs):

    """
    Expects a dataframe with MultiIndex columns
    Top level should be U75, U90, U95, U99
    Bottom level should be a column for each line.

    Plots the line utilization in Descending order for each
    Utilization value.

    y-axis: % of time above Utilization
    x-axis: rank of line (from 0 to # of lines)
    """

    ax = kwargs.get("ax", plt.gca())

    #TODO be more flexible with possibly more threshold values
    # Will need a color map to map U99, etc.
    thresholds = utilization.columns.get_level_values(level='Utilization').unique()
    grid = True
    for t in thresholds:
        plot_ranked_series(utilization[t].sum().rename(t),ax=ax, grid=grid)
        grid=False
    #plot_ranked_series(utilization['U90'].sum().rename("U90"),ax=ax, color='Gold')
    #plot_ranked_series(utilization['U95'].sum().rename("U95"),ax=ax, color='Green')
    #plot_ranked_series(utilization['U99'].sum().rename("U99"),ax=ax, color='Red', grid=True)

    ax.set_ylabel("Hours Above Utilization (%)")
    ax.set_xlabel("Number of Lines")

    return ax

# Assumes a series
def plot_flow(flow, column, label, ax=None, annotate=True, palette=None, backend=None):

    """
    Plots Sorted flow of an individual column in a flow dataset.
    This could be an interface between superzones.
    An interface between regions, or any line or subset of transmission lines.
    """

    if ax == None:
        ax = plt.axes()

    flow[column].sort_values(ascending=False).reset_index().plot.line(y=column, ax=ax, label=label, color='Green', grid=True)

    if annotate:

        flow_stats = flow[column].apply(lambda x: x if x>=0 else 0.0).agg(['sum','max'])
        rflow_stats = flow[column].apply(lambda x: abs(x) if x<0 else 0.0).agg(['sum','max'])
        posFlow, posPeak = flow_stats['sum']/MW_to_TW, flow_stats['max']/MW_to_GW
        negFlow, negPeak = rflow_stats['sum']/MW_to_TW, rflow_stats['max']/MW_to_GW

        an_text = f'+{posFlow:.3g} | -{negFlow:.3g} TWh \n +{posPeak:.3g} | -{negPeak:.3g} GW'

        ax.annotate(an_text,xy=(0.8,0.8),xycoords='axes fraction',fontsize=12, bbox=dict(boxstyle="round", fc="0.8", alpha=0.6,path_effects=[path_effects.withStroke()]))


    ax.axhline(0, 0,1, color="Grey")
    ax.set_ylabel("Flow (MW)")
    ax.set_xlabel("")
    ax.set_title(f"Interface: {column}")


    return ax


def plot_ranked_series(series, ax=None, **kwargs):

    """
    Takes a series as input and plots the values in ranked order
    Useful as a base for building plots like
    1. Load Duration Curve.
    2. Line Flow.

    """


    ax = kwargs.pop("ax",plt.gca())


    series_name = series.name
    series.sort_values(ascending=False).reset_index()[[series_name]].plot.line(ax=ax, **kwargs)


def plot_hourly_boxplot(flow: pd.Series, ax=None, return_frame=False, palette=None, backend=None, **kwargs):

    """
    Input: Timeseries of Flow data or Loading data
    Output: Boxplot with box for each hour of the day
    """

    cflow = flow.copy().to_frame()
    cflow['hour'] = cflow.index.hour+1
    cflow['date'] = cflow.index.date

    cflow_pivot = cflow.pivot(columns='hour', index='date').droplevel(0, axis=1)

    ax = cflow_pivot.plot.box(ax=ax,
            #color=dict(boxes='darkgreen', whiskers='blue', medians='black', caps='black'),
            boxprops=dict(color='darkgreen',linestyle='-', linewidth=1.5, alpha=0.5),
            flierprops=dict(linestyle='-', linewidth=1.5),
            medianprops=dict(color='black',linestyle='-', linewidth=2.5),
            whiskerprops=dict(linestyle='-', linewidth=1.5),
            capprops=dict(linestyle='-', linewidth=1.5),
            patch_artist=True,
            showfliers=False, grid=False, rot=0,zorder=2,
            **kwargs
    )

    all_ticks = ax.get_xticks()
    major_ticks = []
    for i in range(len(all_ticks)):
        if i % 2 == 1:
            major_ticks.append(all_ticks[i])
    ax.set_xticks(major_ticks, minor=False)

    ax.hlines(0,xmin=0,xmax=24, color='grey', linestyle='--',linewidth=0.5,zorder=1)

    ax.set_title('Mean Hourly Flow Profile')
    ax.spines[['right', 'top']].set_visible(False)
    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Flow Distribution (MW)')

    if return_frame:
        return ax, cflow_pivot
    else:
        return ax


def plot_hourly_box_monthly(flow: pd.Series, palette=None, backend=None):

    """Creates a facet of hourly boxplots"""

    months = flow.index.month.unique()

    fig, axs = plt.subplots(4,3, figsize=(18,12), sharex=False, sharey=True)

    axs = trim_axs(axs, len(months))

    i = 0
    for ax in axs.reshape(-1)[0:len(months)]:

        month = months[i]


        sub_flow = flow.loc[flow.index.month == month].copy()

        plot_hourly_boxplot(sub_flow, ax=ax)
        ax.set_title(month_map[month])

        if i <= 4*3 - 4:
            ax.set_xlabel(None)
            ax.set_xticks([])
            ax.spines[['right', 'top', 'bottom']].set_visible(False)
        i = i + 1

    return fig, axs