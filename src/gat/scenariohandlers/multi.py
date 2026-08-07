"""
Provides a multi-scenario handler for comparing multiple scenarios.

This module defines the MultiScenario class, which provides methods for
accessing and processing data from multiple scenario objects at once,
presenting the combined data in a single DataFrame with an additional
'Scenario' index level.
"""

import pandas as pd
from .base import BaseScenario
from typing import TYPE_CHECKING, Dict, Optional, Union, List

if TYPE_CHECKING:
    from .base import BaseScenario


class MultiScenario:
    """
    Class for handling multiple scenarios with a familiar API.

    This class aggregates data from multiple `BaseScenario` objects, allowing for
    comparative analysis across different scenarios. Methods in this class mirror
    those in `BaseScenario` but return DataFrames that include a 'Scenario'
    level in the column index to distinguish data from different scenarios.

    :param scenarios: A dictionary mapping a display name (str) to a scenario object (BaseScenario).
    """

    def __init__(self, scenarios: Dict[str, BaseScenario] = {}):
        """
        Initializes the MultiScenario object.

        :param scenarios: A dictionary mapping a display name (str) to a scenario object (BaseScenario).
        """
        from ._deprecation import warn_legacy_handler

        warn_legacy_handler(self)
        self.scenarios = scenarios  # Dict of scenario display name, scenario obj

        pass

    # multi-scenario functions

    def add_scenario(
        self, scenario_obj: "BaseScenario", display_name: Optional[str] = None
    ):
        """
        Adds a scenario to the MultiScenario object.

        :param scenario_obj: The scenario object to add.
        :param display_name: Optional name to identify the scenario. If not provided, uses scenario's display_name.
        """
        if display_name is None:
            if not scenario_obj.display_name:
                raise ValueError(
                    "Cannot add scenario: no display_name provided and scenario has no display_name attribute"
                )
            display_name = scenario_obj.display_name

        self.scenarios[display_name] = scenario_obj

    def __add__(self, other):
        """Add another scenario or MultiScenario to this MultiScenario"""
        from .base import BaseScenario

        if isinstance(other, BaseScenario):
            # Adding a single scenario
            if not other.display_name:
                raise ValueError("Cannot add scenario: it has no display_name")

            new_scenarios = self.scenarios.copy()
            new_scenarios[other.display_name] = other
            return MultiScenario(new_scenarios)

        elif isinstance(other, MultiScenario):
            # Adding another MultiScenario
            new_scenarios = self.scenarios.copy()
            new_scenarios.update(other.scenarios)
            return MultiScenario(new_scenarios)

        else:
            return NotImplemented

    def __radd__(self, other):
        """Support right-hand addition (scenario + multi_scenario)"""
        return self.__add__(other)

    # functions
    """Methods, we want to have the same api as an individual scenario, but return a dataframe with an extra index level for each scenario."""

    def _concat_gat_df(self, method_name):
        """
        Generic function to call a method on each scenario and combine results with scenario as an index level.

        Parameters:
        -----------
        method_name : str
            Name of the method to call on each scenario object (e.g., 'get_generation', 'get_generators_tech')

        Returns:
        --------
        pd.DataFrame
            Combined DataFrame with scenario as an additional index level
        """
        frames = []
        frame_names = []
        for display_name, sobj in self.scenarios.items():
            # Get the method from the scenario object
            method = getattr(sobj, method_name)
            # Call the method
            result_df = method()

            if result_df is not NotImplemented and result_df is not None:
                # Make a copy to avoid modifying original data
                result_df = result_df.copy()

                # Handle MultiIndex columns differently
                if isinstance(result_df.columns, pd.MultiIndex):
                    # Add scenario as the outermost level to the existing MultiIndex
                    new_columns = pd.MultiIndex.from_tuples(
                        [
                            (
                                (display_name,) + col
                                if isinstance(col, tuple)
                                else (display_name, col)
                            )
                            for col in result_df.columns
                        ],
                        names=["Scenario"] + list(result_df.columns.names),
                    )
                    result_df.columns = new_columns
                else:
                    # For simple column indexes, create new MultiIndex with scenario as first level
                    new_columns = pd.MultiIndex.from_tuples(
                        [(display_name, col) for col in result_df.columns],
                        names=["Scenario", "Component"],
                    )
                    result_df.columns = new_columns

                frames.append(result_df)
                frame_names.append(display_name)
            else:
                import warnings

                warnings.warn(
                    f"Scenario '{display_name}' returned no data for method '{method_name}'"
                )

        if frames:
            # Combine all DataFrames along columns (axis=1)
            # This preserves the timestamp index and avoids duplicate timestamps with different values
            result = pd.concat(frames, axis=1)

            # Ensure datetime index for time-series methods
            if method_name not in {"get_generation_capacity"}:
                try:
                    result.index = pd.to_datetime(result.index)
                except (ValueError, TypeError):
                    # If conversion fails, keep original index
                    pass

                # pd.concat(axis=1) unions each scenario's index, silently
                # introducing NaN rows for any scenario missing a timestamp
                # the others have -- e.g. scenarios covering different date
                # ranges or resolutions. Flag it rather than let it show up
                # only as unexplained NaNs downstream.
                misaligned = [
                    (name, df.index.min(), df.index.max(), len(df))
                    for name, df in zip(frame_names, frames)
                    if len(df) != len(result)
                ]
                if misaligned:
                    import warnings

                    details = "; ".join(
                        f"'{name}' has {n} timestamps ({start} to {end})"
                        for name, start, end, n in misaligned
                    )
                    warnings.warn(
                        f"Scenarios have misaligned time ranges for "
                        f"'{method_name}' -- {details}; the combined result "
                        f"has {len(result)} timestamps, so scenarios that "
                        f"don't cover the full range will have NaN there. "
                        f"Check that scenarios represent the same period/"
                        f"resolution before comparing."
                    )

            return result
        else:
            return NotImplemented

    def get_generation(self):
        """
        Gets generation data for all scenarios.

        :returns:
            A DataFrame of generation data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_generation")

    def get_generators_tech(self):
        """
        Gets generation data with technology information for all scenarios.

        :returns:
            A DataFrame of generation data with technology for all scenarios,
            with an added 'Scenario' level in the column index.
        """
        return self._concat_gat_df("get_generators_tech")

    # Similarly for other methods
    def get_availability(self):
        """
        Gets availability data for all scenarios.

        :returns:
            A DataFrame of availability data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_availability")

    def get_load(self):
        """
        Gets load data for all scenarios.

        :returns:
            A DataFrame of load data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_load")

    def get_production_cost(self):
        """
        Gets production cost data for all scenarios.

        :returns:
            A DataFrame of production cost data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_production_cost")

    def get_generation_capacity(self):
        """
        Gets generation capacity data for all scenarios.

        :returns:
            A DataFrame of generation capacity data for all scenarios, with 'Scenario'
            as an additional column.
        """
        return self._concat_gat_df("get_generation_capacity").stack(
            level="Scenario", future_stack=True
        )

    def get_line_flow(self):
        """
        Gets line flow data for all scenarios.

        :returns:
            A DataFrame of line flow data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_line_flow")

    def get_storage_charging(self):
        """
        Gets storage charging data for all scenarios.

        :returns:
            A DataFrame of storage charging data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_storage_charging")

    def get_unserved(self):
        """
        Gets unserved energy data for all scenarios.

        :returns:
            A DataFrame of unserved energy data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_unserved")

    def get_area_dispatch(self):
        """
        Gets area dispatch data for all scenarios.

        :returns:
            A DataFrame of area dispatch data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_area_dispatch")

    def get_area_charging(self):
        """
        Gets area charging data for all scenarios.

        :returns:
            A DataFrame of area charging data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_area_charging")

    def get_area_unserved(self):
        """
        Gets area unserved energy data for all scenarios.

        :returns:
            A DataFrame of area unserved energy data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_area_unserved")

    def get_system_dispatch(self):
        """
        Gets system dispatch data for all scenarios.

        :returns:
            A DataFrame of system dispatch data for all scenarios, with an added 'Scenario'
            level in the column index.
        """
        return self._concat_gat_df("get_system_dispatch")
