from gat.scenariohandlers import SiennaScenario, PlexosScenario, BaseScenario
import gat.quickplots as qp
from gat.quickplots.core import *
from gat.registry import plot_function
from gat.quickplots.utils import scale_marker, create_marker_legend, create_tech_legend
import matplotlib.pyplot as plt


@plot_function("BaseScenario", plot_type="transmission")
def line_loading(scenario: "BaseScenario", subpath="transmission/system/flow-loading"):


    loading_df = scenario.get_line_loading()

    ax = qp.plot_loading_ranked(loading_df)

    return (subpath, ax, loading_df)


@plot_function("BaseScenario", plot_type="transmission")
def line_utilization(scenario: "BaseScenario", subpath="transmission/system/flow-utilization"):

    utilization_df = scenario.get_line_utilization()

    ax = qp.plot_lines_utilization(utilization_df)

    return (subpath, ax, utilization_df)


@plot_function("BaseScenario", plot_type="transmission")
def line_congestion(scenario: "BaseScenario", congestion_threshold=100, subpath="transmission/system/flow-congestion"):

    congestion_df = scenario.get_line_congestion_hours(congestion_threshold).sum()

    ax = qp.plot_ranked_series(congestion_df)
    ax.set_title("Congestion")
    return(subpath, ax, congestion_df)


@plot_function("SiennaScenario", plot_type="transmission")
def area_interchange_all(scenario: "SiennaScenario", start_date:str=None, end_date:str=None, filter_columns:Optional[List[str]]=None, subpath:str="transmission/system/area-interchange"):


    interchange = scenario.get_area_interchange()


    if filter_columns is not None:
        interchange = interchange[filter_columns]

    if start_date is None:
        start_date = interchange.index.min()

    if end_date is None:
        end_date = interchange.index.max()

    # filter time.

    interchange = interchange.loc[start_date:end_date]

    fig, ax = plt.subplots()
    interchange.plot(ax=ax)

    return (subpath, ax, interchange)

@plot_function("SiennaScenario", plot_type="transmission")
def area_interchange_flow_duration_curve(scenario: "SiennaScenario", start_date:str=None, end_date:str=None, filter_columns:Optional[List[str]]=None, subpath:str="transmission/system/flow-{}"):

    interchange = scenario.get_area_interchange()

    if filter_columns is not None:
        interchange = interchange[filter_columns]

    if start_date is None:
        start_date = interchange.index.min()

    if end_date is None:
        end_date = interchange.index.max()

    # filter time.

    interchange = interchange.loc[start_date:end_date]

    for interface in interchange.columns:
        ax = qp.plot_flow(interchange, interface, label=f'Interface: {interface}')
        interface_subpath = subpath.format(interface)

        yield (interface_subpath, ax, None)


@plot_function("SiennaScenario", plot_type="transmission")
def area_interchange_boxplot(
    scenario: "SiennaScenario",
    start_date:str=None,
    end_date:str=None,
    filter_columns:Optional[List[str]]=None,
    subpath:str="transmission/system/boxplot-area-interchange-{}"):

    interchange = scenario.get_area_interchange()

    if filter_columns is not None:
        interchange = interchange[filter_columns]

    if start_date is None:
        start_date = interchange.index.min()

    if end_date is None:
        end_date = interchange.index.max()

    for interface in interchange.columns:

        ax, df = qp.plot_hourly_boxplot(interchange[interface], return_frame=True)

        interface_subpath = subpath.format(interface)

        yield (interface_subpath,ax, df)


@plot_function("SiennaScenario", plot_type="transmission")
def area_interchange_boxplot_monthly(scenario: "SiennaScenario", start_date:str=None, end_date:str=None, filter_columns:Optional[List[str]]=None, subpath:str="transmission/system/boxplot-monthly-area-interchange-{}"):

    interchange = scenario.get_area_interchange()

    if filter_columns is not None:
        interchange = interchange[filter_columns]

    if start_date is None:
        start_date = interchange.index.min()

    if end_date is None:
        end_date = interchange.index.max()

    for interface in interchange.columns:

        ax = qp.plot_hourly_box_monthly(interchange[interface])
        interface_subpath = subpath.format(interface)

        yield (interface_subpath, ax, None)