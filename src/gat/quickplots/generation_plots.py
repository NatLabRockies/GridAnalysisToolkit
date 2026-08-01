"""
Author: Micah Webb
Date: 2025-06-09

Description: Contains plotting functions for generation reporting that take a single Scenario Object and **optional** keyword arguments. Designed for Scenarios with attached simulation data.
The keyword arguments will be inspected by the report or plugin management system to generate additional configuration parameters for a given plot.

A function may also take a specific Concrete implementation of Scenario Object and the report init command will only generate plot functions that are
compatible.

"""

from gat.scenariohandlers import PlexosScenario, SiennaScenario, BaseScenario
import gat.quickplots as qp
from gat.quickplots.core import *
from gat.registry import plot_function
import matplotlib.pyplot as plt
from loguru import logger

def convert_units(data, from_unit='MWh', to_unit='GWh'):
    """
    Convert data from one energy unit to another.

    Parameters
    ----------
    data : array-like
        Data to convert
    from_unit : str, default 'Wh'
        Original unit of the data
    to_unit : str, default 'GWh'
        Target unit for conversion

    Returns
    -------
    tuple
        (converted_data, unit_string)
    """

    is_power_unit=False
    if to_unit.endswith('W'):
        to_unit = to_unit+'h'
        is_power_unit=True

    units = {
        'kWh': 1e3,
        'MWh': 1e6,
        'GWh': 1e9,
        'TWh': 1e12
    }

    if from_unit not in units or to_unit not in units:
        raise ValueError(f"Unit must be one of: {', '.join(units.keys())}")

    conversion_factor = units[from_unit] / units[to_unit]
    if is_power_unit:
        to_unit=to_unit.replace('h','')
    return data * conversion_factor, to_unit



@plot_function("BaseScenario", plot_type="generation")
def plot_total_system_dispatch(scenario: BaseScenario, units='TWh', threshold=3, subpath="generation/system/total_dispatch",
                               palette=None, backend=None):
    logger.info("plotting total system dispatch")
    dispatch = scenario.get_system_dispatch(include_load=False, include_charging=False).sum()
    scaled_dispatch, unit_label = convert_units(dispatch, to_unit=units)
    ax = plot_component_donut(scaled_dispatch, unit=' '+unit_label, threshold=threshold,
                              palette=palette, backend=backend)

    return (subpath, ax, scaled_dispatch)

@plot_function("BaseScenario", plot_type="generation")
def plot_monthly_system_dispatch(scenario: BaseScenario, subpath="generation/system/monthly_dispatch",
                                 palette=None, backend=None):
    logger.info("plotting monthly system dispatch")
    dispatch = scenario.get_system_dispatch(include_charging=False)
    ax, out_df = qp.plot_monthly_system_dispatch_stack(dispatch, return_frame=True,
                                                        palette=palette, backend=backend)

    return (subpath, ax, out_df)

@plot_function("BaseScenario", plot_type="generation")
def plot_total_area_dispatch(scenario: BaseScenario, subpath="generation/system/area_total_dispatch",
                             palette=None, backend=None):
    logger.info("plotting total area dispatch")
    dispatch = scenario.get_area_dispatch(include_charging=False)
    ax, out_df = qp.plot_annual_area_dispatch_stack(dispatch, return_frame=True,
                                                     palette=palette, backend=backend)

    return (subpath, ax, out_df)

@plot_function("BaseScenario", plot_type="generation")
def plot_monthly_area_dispatch(scenario: BaseScenario, subpath="generation/area",
                               palette=None, backend=None):
    dispatch = scenario.get_area_dispatch(include_charging=False)

    for a in dispatch.columns.get_level_values(level='Area').unique():
        logger.info(f"plotting monthly dispatch for {a}")
        chart, out_df = qp.plot_monthly_system_dispatch_stack(dispatch[a], return_frame=True,
                                                               palette=palette, backend=backend)
        from gat.quickplots.backends import get_backend
        be = get_backend(backend)
        be.set_title(chart, f"{a} - Monthly Generation")
        area_subpath = f"{subpath}/monthly-generation-{a}"
        yield (area_subpath, chart, out_df)

@plot_function("BaseScenario", plot_type='generation')
def plot_area_dispatch(scenario: BaseScenario, subpath="generation/area",
                       palette=None, backend=None):
    dispatch = scenario.get_area_dispatch(include_charging=False)

    for a in dispatch.columns.get_level_values(level='Area').unique():
        logger.info("plotting dispatch for {a} and every timestep")
        out_df = dispatch[a]
        chart = qp.plot_stacked_area_window(dispatch[a], palette=palette, backend=backend)
        from gat.quickplots.backends import get_backend
        be = get_backend(backend)
        be.set_title(chart, f"{a} - Generation")
        area_subpath = f"{subpath}/Stacked_Gen-{a}"
        yield (area_subpath, chart, out_df)

@plot_function("BaseScenario", plot_type="generation")
def plot_minmax_system_demand_windows(scenario: BaseScenario, window_delta=3, subpath="generation/system",
                                      palette=None, backend=None):
    """Generator plot that plots the min and max total demand, net demand and min vre windows."""

    dispatch = scenario.get_system_dispatch()

    for e in ['min', 'max']:
        logger.info(f"plotting {e}-demand dispatch window for entire system")
        if e == 'min':
            chart, df_window = qp.plot_min_demand_window(dispatch, window_delta=window_delta, return_frame=True,
                                                          palette=palette, backend=backend)
            yield (f"{subpath}/Stacked_Gen-Min_Demand-{e}", chart, df_window)
        else:
            chart, df_window = qp.plot_peak_demand_window(dispatch, window_delta=window_delta, return_frame=True,
                                                           palette=palette, backend=backend)
            yield (f"{subpath}/Stacked_Gen-Peak_Demand-{e}", chart, df_window)

@plot_function("BaseScenario", plot_type="generation")
def plot_minmax_area_demand_windows(scenario: BaseScenario, window_delta=3, subpath="generation/area",
                                    palette=None, backend=None):
    """ Generator plot that plots the min and max total demand, net demand and min vre windows for each area."""

    dispatch = scenario.get_area_dispatch()

    for a in dispatch.columns.get_level_values(level='Area').unique():
        for e in ['min', 'max']:
            logger.info(f"plotting {e}-demand dispatch window for area={a}")
            if e == 'min':
                chart, df_window = qp.plot_min_demand_window(dispatch[a], window_delta=window_delta, return_frame=True,
                                                              palette=palette, backend=backend)
                yield (f"{subpath}/Stacked_Gen-Min_Demand_{e}", chart, df_window)
            else:
                chart, df_window = qp.plot_peak_demand_window(dispatch[a], window_delta=window_delta, return_frame=True,
                                                               palette=palette, backend=backend)
                yield (f"{subpath}/Stacked_Gen-Peak_Demand_{e}", chart, df_window)

@plot_function("BaseScenario", plot_type='generation')
def plot_mean_hourly_area(scenario: BaseScenario, subpath="generation/area",
                          palette=None, backend=None):

    dispatch = scenario.get_area_dispatch()
    for a in dispatch.columns.get_level_values(level='Area').unique():
        logger.info(f"plotting mean hourly dispatch for area={a}")
        chart, df = qp.plot_mean_hourly_dispatch(dispatch[a], return_frame=True,
                                                  palette=palette, backend=backend)

        yield (f"{subpath}/Stacked_Gen-Mean_Hourly-{a}", chart, df)


@plot_function("BaseScenario", plot_type='generation')
def plot_net_load_min_area(scenario: BaseScenario, window_delta=3, subpath="generation/area",
                           palette=None, backend=None):
    dispatch = scenario.get_area_dispatch()

    for a in dispatch.columns.get_level_values(level='Area').unique():
        logger.info(f"plotting min-net-load dispatch for area={a}")
        area_df = dispatch[a]
        datetime_end = area_df.index.max()
        datetime_start = area_df.index.min()

        min_net_idx = area_df[qp.config.net_load_alias].idxmin()

        window_start = min_net_idx - pd.Timedelta(days=window_delta)
        window_end = min_net_idx + pd.Timedelta(days=window_delta)

        if window_start < datetime_start:
            window_start = datetime_start

        if window_end > datetime_end:
            window_end = datetime_end

        out_df = area_df.loc[window_start:window_end]

        chart = qp.plot_stacked_area_window(out_df, palette=palette, backend=backend)

        yield (f"{subpath}/Net-Load-{a}-Minimum-Window", chart, out_df)


@plot_function("BaseScenario", plot_type="generation")
def plot_total_system_curtailment(scenario: BaseScenario, units='GWh', subpath="generation/system/total_curtailment",
                                  palette=None, backend=None):
    # use donut chart here.
    logger.info("Plotting total system curtailment by generation type")
    area_curt = scenario.get_area_curtailment_aggregates()

    tot_curt = area_curt.T.groupby(level="Technology").sum().T.sum()
    tot_curt_scaled, _ = convert_units(tot_curt, to_unit=units)
    ax = plot_component_donut(tot_curt_scaled, unit=units, palette=palette, backend=backend)

    return (subpath, ax, tot_curt)

@plot_function("BaseScenario", plot_type="generation")
def plot_monthly_system_curtailment(scenario: BaseScenario, subpath="generation/system/monthly_curtailment",
                                    palette=None, backend=None):

    logger.info("Plotting monthly system curtailment by generation type")
    area_curt = scenario.get_area_curtailment_aggregates()

    tot_curt = area_curt.T.groupby(level="Technology").sum().T

    #TODO this should be fixed in the BaseScenario class
    tot_curt.index = pd.to_datetime(tot_curt.index)
    chart, out_df = qp.plot_monthly_system_curtailment_stack(tot_curt, return_frame=True,
                                                              palette=palette, backend=backend)

    return (subpath, chart, out_df)


