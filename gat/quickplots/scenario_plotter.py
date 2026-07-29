from gat.scenariohandlers.base import BaseScenario
from gat.quickplots.core import *
import gat.quickplots as qp

available_plots = {
    'annual_system_dispatch': qp.plot_annual_system_dispatch_stack,
    'monthly_system_dispatch': qp.plot_monthly_system_dispatch_stack
}


class ScenarioPlotter():

    def __init__(self, scenario: BaseScenario):

        self.scenario = scenario
        self.available_plots = {
            'annual_system_dispatch': self.annual_system_dispatch,
            'monthly_system_dispatch': self.monthly_system_dispatch,
            'system_total_generation': self.system_total_generation,
            'system_total_capacity':self.system_total_capacity,
            'system_dispatch':self.system_dispatch,
            'line_loading':self.line_loading,
            'line_utilization': self.line_utilization,
        }
        pass


    def __call__(self, kind=None, **kwargs):
        """General Plot method mimicking pandas"""

        if kind is None:
            raise ValueError("Must specify 'kind' for plotting.")

        elif kind not in self.available_plots.keys():
            plot_msg = "\n".join([k for k in available_plots.keys()])
            message = f"Plots must be one of the following:\n{plot_msg}"
            raise ValueError(message)

        elif kind in self.available_plots.keys():
            plot_func = self.available_plots[kind]

            ax = plot_func(**kwargs)

            return ax
        else:
            raise(ValueError(f"Unable to generate plot for kind={kind}"))


    def annual_system_dispatch(
            self,
            **kwargs):

        system_dispatch = self.scenario.get_system_dispatch()
        ax=qp.plot_annual_system_dispatch_stack(
            system_dispatch,
            **kwargs)

        return ax

    def monthly_system_dispatch(
            self,
            **kwargs):

        system_dispatch = self.scenario.get_system_dispatch()
        ax=qp.plot_monthly_system_dispatch_stack(
            system_dispatch,
            **kwargs)

        return ax

    def system_dispatch(
            self,
            frequency=None,
            start_date=None,
            end_date=None,
            include_net_load=True,
            include_total_load=True,
            **kwargs):
        """
        plots the system dispatch after resampling the dispatch frame by frequency
        """

        system_dispatch = self.scenario.get_system_dispatch()

        system_dispatch = system_dispatch.loc[start_date:end_date]

        if frequency is not None:
            system_dispatch = system_dispatch.resample(frequency).sum()


        else:
            frequency = pd.infer_freq(system_dispatch.index)

        if frequency[0].isdigit() == False:
            frequency = f'1{frequency}'

        if pd.Timedelta(frequency) < pd.Timedelta(days=1):
            ax = qp.plot_stacked_area_window(
                system_dispatch,
                include_net_load=include_net_load,
                include_total_load=include_total_load,
                **kwargs)
        else:
            ax = qp.plot_dispatch_stack_bar(
                system_dispatch,
                include_net_load=include_net_load,
                include_total_load=include_total_load,
                **kwargs)

        return ax


    def system_total_generation(
        self,
        threshold=5.0,
        unit=' TWh',
        percent_tot_labels=None,
        percent_tot_text=None,
        startangle=25,
        horizontal_length=.5,
        radial_length=1.03,
        **kwargs):

        system_dispatch = self.scenario.get_system_dispatch(include_load=False, include_charging=False)
        total_dispatch = system_dispatch.sum()*1e-6

        ax = plot_component_donut(
            total_dispatch.drop(labels=['Curtailment']),
            threshold=threshold,
            unit=unit,
            percent_tot_labels=percent_tot_labels,
            percent_tot_text=percent_tot_text,
            startangle=startangle,
            horizontal_length=horizontal_length,
            radial_length=radial_length,
            **kwargs
        )

        ax.set_title("Total Generation", y=1.05)
        return ax

    def system_total_capacity(
            self,
            threshold=5.0,
            unit='GW',
            percent_tot_labels=None,
            percent_tot_text=None,
            startangle=25,
            horizontal_length=.5,
            radial_length=1.03,
            **kwargs):

        capacity = self.scenario.get_generation_capacity()
        total_capacity = capacity.sum()*1e-3

        ax = plot_component_donut(
            total_capacity,
            threshold=threshold,
            unit=unit,
            percent_tot_labels=percent_tot_labels,
            percent_tot_text=percent_tot_text,
            startangle=startangle,
            horizontal_length=horizontal_length,
            radial_length=radial_length,
            **kwargs
            )

        ax.set_title("Generation Capacity", y=1.05)

        return ax

    def generator(
            generator_ids,
            start_date=None,
            end_date=None,
            **kwargs,
    ):
        """ Plots an individual generators"""
        pass


    def line_flows(
            line_ids,
            start_date=None,
            end_date=None,
            **kwargs,
    ):
        """ Plots individual Line Flows"""

        pass

    def line_loading(
            self,
            start_date=None,
            end_date=None,
            **kwargs
    ):
        """Plots the Line Loading curves average and max"""

        line_loading = self.scenario.get_line_loading()
        line_loading = line_loading.loc[start_date:end_date]
        ax = qp.plot_loading_ranked(line_loading, **kwargs)

        return ax

    def line_utilization(
            self,
            start_date=None,
            end_date=None,
            threshold=[75,90,95,99],
            **kwargs
    ):
        line_utilization = self.scenario.get_line_utilization(threshold=threshold)
        line_utilization = line_utilization.loc[start_date:end_date]
        ax = qp.plot_lines_utilization(line_utilization, **kwargs)
        return ax

    def line_diurnal_flow(
            self,
            line_id,
            start_date=None,
            end_date=None,
            **kwargs,
    ):
        pass
        #line_flow = self.scenario.get_line_flow()[line_id]

        #line_flow = line_flow.loc[start_date:end_date]
