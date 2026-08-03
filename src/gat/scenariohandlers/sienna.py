"""
Provides a scenario handler for the Sienna simulation platform.

This module defines the SiennaScenario class, which provides methods for
accessing and processing data from Sienna system json files and simulation h5 files.
"""

import copy
import warnings
from fnmatch import fnmatch
from typing import Dict, List, Optional, Union

import pandas as pd
from loguru import logger

from gat.models.scenario import ScenarioConfig, load_config

from ..datahelpers.sienna import SiennaSystemParser
from ..simulations import (
    SimulationAggregator,
    SiennaSimulationParser as _SiennaSimParser,
)
from .base import BaseScenario, gc
from .config_maps import sienna_standard_map
from .multi import MultiScenario


class SiennaScenario(BaseScenario):
    """
    Class for providing holistic access to Sienna system and simulation data
    found in JSON and h5 files respectively

    :param simulation_files: List([str, path]) - A path or list of paths to the simulation h5 files produced by a Sienna simulation.
    :param system_files: [str, path] - A path or str to the Sienna system JSON file.

    Internals Properties
    -----------------------

    :self.parser: A `SimulationAggregator(parser_class=SiennaSimulationParser)` (multi-file) or a single `SiennaSimulationParser` for one h5 file.

    :self.system:  A SiennaSystemParser(system_file) for parsing the Sienna system JSON file.

    :self.config: A mutable configuration object that tells the handler where to look for certain types of data.

    :self.unit_base_value: The Sienna System base unit. Acts as a scaling multiplier for all the timeseries and capacity data. (See Sienna Documentation for more details)

    :self.unit_system: Natural or Per-Unit
    """

    _expected_model_type = "sienna"

    def _find_solution_files(
        self, solution_data: Union[str, List[str]], pattern: str = "*.h5"
    ) -> List[str]:
        """
        Find Sienna solution files (h5 format)

        Parameters:
        -----------
        solution_data : str or list of str
            Path to solution data or list of paths
        pattern : str, optional
            Glob pattern to use when searching for files (default: "*.h5")

        Returns:
        --------
        List[str]
            List of file paths to solution files
        """
        import os
        from glob import glob

        files = []

        if isinstance(solution_data, str):
            solution_data = os.path.expanduser(solution_data)
            if os.path.isdir(solution_data):
                # Non-recursive search for files matching pattern in the directory
                files = [file for file in glob(os.path.join(solution_data, pattern))]
                files.sort()
            elif os.path.isfile(solution_data):
                files = [os.path.normpath(solution_data)]
            elif "*" in solution_data:
                # If solution_data itself is a glob pattern
                files = [file for file in glob(solution_data)]
                files.sort()
        elif isinstance(solution_data, list):
            # For lists, expand any glob patterns
            expanded_files = []
            for item in solution_data:
                item = os.path.expanduser(item)
                if os.path.isfile(item):
                    expanded_files.append(os.path.normpath(item))
                elif "*" in item:
                    expanded_files.extend([file for file in glob(item)])
            files = expanded_files

        return files

    def __init__(
        self,
        simulation_files: Optional[Union[str, List[str]]] = None,
        system_file: Optional[str] = None,
        config: Optional[ScenarioConfig] = None,
        pattern: str = "*.h5",
        # Deprecated alias — use simulation_files instead
        solution_data: Optional[Union[str, List[str]]] = None,
        # Optional path to a metadata.json (passed by gat.loader for v1 configs;
        # legacy callers don't need to set this — sienna handlers locate it from
        # system_file's directory if absent).
        metadata_file: Optional[str] = None,
    ) -> None:
        """
        Initialize a SiennaScenario object with configuration, system data, and solution data.

        Parameters:
        -----------
        simulation_files : str or list of str, optional
            Path to simulation output data or list of paths to h5 files
        system_file : str, optional
            Path to system data file (Sienna JSON file)
        config : ScenarioConfig, optional
            Configuration object for the scenario
        pattern : str, optional
            Glob pattern to use when searching for files (default: "*.h5")
        solution_data : str or list of str, optional
            Deprecated. Use ``simulation_files`` instead.
        """
        from ._deprecation import warn_legacy_handler

        warn_legacy_handler(self)
        from .base import _resolve_simulation_files

        simulation_files = _resolve_simulation_files(simulation_files, solution_data)

        # Create a default config if none provided
        if config is not None:
            self.config = load_config(config)
        else:
            self.config = ScenarioConfig(model_type=self._expected_model_type)

        # Store system path if provided
        if system_file is not None:
            self.config.system_path = system_file

        # Initialize the parsers
        self.system = None
        if self.config.system_path is not None:
            self.system = SiennaSystemParser(self.config.system_path)

        # Initialize parser - use SiennaSimulationParser for single files, Aggregator for multiple
        self.parser = None
        if simulation_files is not None:
            self.config.simulation_paths = simulation_files

            # Convert to list to check length
            if isinstance(simulation_files, str):
                file_list = [simulation_files]
            else:
                file_list = simulation_files

            # Use appropriate parser based on number of files
            if len(file_list) == 1:
                # Single file - use SiennaSimulationParser directly
                self.parser = _SiennaSimParser(file_list[0])
            else:
                # Multiple files - use the generic SimulationAggregator,
                # parameterized with the Sienna parser. Replaces the old
                # Sienna-specific SiennaSimulationAggregator (sequential,
                # superseded by the generic one's ProcessPoolExecutor path).
                self.parser = SimulationAggregator(
                    file_paths=self.config.simulation_paths,
                    parser_class=_SiennaSimParser,
                )

            # Set simulation_type if specified in config
            if hasattr(self.config, "simulation") and self.config.simulation.type:
                self.parser.selected_model = self.config.simulation.type

            # Apply dataset configurations if available
            if hasattr(self.config, "dataset_configs") and self.config.dataset_configs:
                dataset_configs = self.config.get_dataset_configs()
                if dataset_configs:
                    self.parser.set_dataset_configs(dataset_configs)
                    logger.info(
                        f"Applied {len(dataset_configs)} dataset configurations from scenario config"
                    )

        # Initialize Sienna-specific configuration
        if self.config.system_config is None and self.system is not None:
            from gat.models.sienna import (
                initialize_sienna_system_config as initialize_sienna_config,
            )

            self.config.system_config = initialize_sienna_config(
                self.system.data_format_version
            )

        # Initialize dataset configuration (pattern-based dataset access)
        if self.config.dataset_config is None:
            from gat.models.sienna import initialize_sienna_dataset_config

            version = self.system.data_format_version if self.system else "4.0.0"
            self.config.dataset_config = initialize_sienna_dataset_config(version)

        # Set unit information if system data is available
        if self.system is not None:
            self.unit_base_value = self.system.system_data["units_settings"][
                "base_value"
            ]
            self.unit_system = self.system.system_data["units_settings"]["unit_system"]
        else:
            # Default values if no system data
            raise LookupError(
                "Unable to determine Unit base value and unit system from system file"
            )

        # Prefer h5 group attrs over sys.json for simulation-side scaling: the
        # simulation may have been run with a different per-unit base than the
        # system was serialized with. Fall back to the sys.json value (above).
        if self.parser is not None and hasattr(
            self.parser, "get_decision_model_base_power"
        ):
            try:
                bp = self.parser.get_decision_model_base_power("UC")
                if bp is not None:
                    self.unit_base_value = bp
            except Exception:
                pass

        # Generate mappings if system is available
        # These mappings are specific to whichever system is currently loaded
        # even if it is overriding a config.
        self._area = "area"
        self._tech_map = self.generator_technology_map if self.system else None
        self._gen_area_map = (
            self.get_gen_area_map(area_column=self.config.system_config.area_column)
            if self.system
            else None
        )
        self._load_area_map = (
            self.get_load_area_map(area_column=self.config.system_config.area_column)
            if self.system
            else None
        )
        self._line_rating_map = self.get_line_rating_map() if self.system else None
        self._tech_simple = sienna_standard_map
        # Call parent initialization to find files and set up config
        super().__init__(
            simulation_files=simulation_files,
            tech_map=self._tech_map,
            gen_area_map=self._gen_area_map,
            load_area_map=self._load_area_map,
            line_rating_map=self._line_rating_map,
            config=self.config,
            system_data=system_file,
            pattern=pattern,
        )

        # Set up technology mappings
        if len(self.config.technology_mappings) > 0:
            logger.debug("Updating technology simplification map from config")
            self._tech_simple = {
                model_name: config.display_group
                for model_name, config in self.config.technology_mappings.items()
            }
        elif self._tech_map:
            print("initializing config technologies")
            self.config.init_technologies(sienna_standard_map)

        self._load_includes_charging = False

    @property
    def area(self) -> Optional[str]:
        return self.config.system_config.area_column

    @area.setter
    def area(self, area):
        try:
            new_gen_area_map = (
                self.get_gen_area_map(area_column=area) if self.system else None
            )
            new_load_area_map = (
                self.get_load_area_map(area_column=area) if self.system else None
            )

            self._gen_area_map = new_gen_area_map
            self._load_area_map = new_load_area_map
            self.config.system_config.area_column = area

        except KeyError:
            msg = f"Unable to set new area {area}, reverting to default area topology."
            warnings.warn(msg)

        except Exception as e:
            warnings.warn(f"Unable to set area: {e}")

    @property
    def generator_technology_map(self) -> Dict[str, str]:
        """
        Creates the generator->technology mapping by parsing the system data using SiennaSystemParser.

        For thermal standards technology = **prime_mover_type + ext['fuel']**

        All other components in the self.config.generation_components list use **prime_mover_type** only.

        :returns: Dictionary of generator by id as keys and technology type as values.
        """

        components = self.system.list_component_types()
        tm = {}

        # TODO fix this hard-coded lookup
        if self.config.system_config.generation_components is None:
            warnings.warn(
                "Unable to generate generator->technology relationship. No configuration found.",
                UserWarning,
            )
            return None
        for c in self.config.system_config.generation_components:
            # TODO this should probably be a configuration to handle ThermalStandard and ThermalMultiStart or generically, when we want to combine prime_mover_type with another column.
            if c.startswith("Thermal") and c in components:
                therm_df = self.system.get_component_data(c)
                if "fuel" in therm_df.columns:
                    therm_df["Technology"] = (
                        therm_df["prime_mover_type"] + "_" + therm_df.fuel
                    )
                elif "ext" in therm_df.columns:
                    therm_df["Technology"] = therm_df[
                        "prime_mover_type"
                    ] + therm_df.ext.apply(
                        lambda x: "_" + x["fuel"] if "fuel" in x else "_OTHER"
                    )
                else:
                    therm_df["Technology"] = therm_df["prime_mover_type"]
                tm.update(therm_df.set_index("name")["Technology"].to_dict())
            elif c in components:
                component_df = self.system.get_component_data(c)
                tm.update(component_df.set_index("name")["prime_mover_type"])

        return tm

    def get_load_area_map(self, area_column=None) -> Union[dict, None]:
        """
        Creates the load bus->area relationship using the internal **SiennaSystemParser**

        1. Creates the load->node relationship using SiennaSystemParser.get_component_bus_relation for the **PowerLoad** component.
        2. Creats the node->area relationship using the SiennaSystemParser.get_bus_area_relation()

        :returns: Dictionary of Load bus name -> geographic area.
        """

        load_node_map = {}
        if self.config.system_config.load_components is None:
            warnings.warn(
                "Unable to generate load->area relationship. No configuration found for load_components.",
                UserWarning,
            )
            return None
        # TODO for some reason pydantic is wrapping a single list around
        for lc in self.config.system_config.load_components:
            lc_map = self.system.get_component_bus_relation(
                lc.component_type, lc.component_index_column, lc.component_value_column
            )
            if lc_map:
                load_node_map.update(lc_map)

        # Assuming ACBus component won't change much.
        if len(load_node_map) == 0:
            warnings.warn(
                "Load->Node relationship not available, update the config to point to an appropriate Load component."
            )

        node_area_map = self.system.get_bus_area_relation(area_column=area_column)

        if load_node_map is not None and node_area_map is not None:
            try:
                return {k: node_area_map.get(v, "NA") for k, v in load_node_map.items()}
            except KeyError as e:
                # Raise a more descriptive KeyError
                warnings.warn(
                    f"Area column {area_column} not found or node mapping issue: {str(e)}"
                )
                return None
        else:
            warnings.warn(
                "Unable to map loads to areas, aggregating load by area unavailable."
            )
            return None

    def get_gen_area_map(self, area_column=None) -> Union[dict, None]:
        """
        Creates the generator->area relationship using the SiennaSystemParser.get_bus_area_relation()
        and component->node relationships.

        :returns: Dictionary of Generator Name -> Geographic Area.
        """

        node_area_map = self.system.get_bus_area_relation(area_column=area_column)

        if node_area_map is None:
            warnings.warn(
                "node->area relationship not available, aggregation by area unavailable",
                UserWarning,
            )
            return None
        else:
            gen_area_map = {}
            if self.config.system_config.generation_components is None:
                warnings.warn(
                    "Unable to make generator->area relationship, no components found in config.generation_components",
                    UserWarning,
                )
                return None
            for c in self.config.system_config.generation_components:
                if c in self.system.list_component_types():
                    component_node_map = self.system.get_component_bus_relation(c)
                    if component_node_map:
                        component_area_map = {
                            k: node_area_map.get(v, "NA")
                            for k, v in component_node_map.items()
                        }
                        gen_area_map.update(component_area_map)
                    else:
                        message = f"component->node relationship not avaialble for {c}, {c} components will map to area='Other'."
                        warnings.warn(message, UserWarning)

            return gen_area_map

    def get_line_rating_map(self) -> Union[dict, None]:
        """
        Parses the line capacity by reading the SiennaSystemParser.get_component_data("Line")
        and scaling the rating by *unit_base_value*

        :returns: Dictionary of Line Id -> Line Capacity
        """
        if self.config.system_config.line_rate_relation is None:
            warnings.warn("No Line_rate_relation found in the configuration.")
            return None
        line_component = self.config.system_config.line_rate_relation.component_type
        line_component_index = (
            self.config.system_config.line_rate_relation.component_index_column
        )
        line_component_val = (
            self.config.system_config.line_rate_relation.component_value_column
        )
        if line_component:
            line_df = self.system.get_component_data(line_component)
            if line_df is None:
                message = f"Line component not found, update the config to point to an appropriate Line component."
                warnings.warn(message, UserWarning)
                return None
            else:
                try:
                    line_rating_scaled = (
                        line_df.set_index(line_component_index)[line_component_val]
                        * self.unit_base_value
                    )
                    return line_rating_scaled.to_dict()

                except Exception as e:
                    message = f"Unable to create line rating map, Line loading features are not available: Exception {e}"
                    warnings.warn(message, UserWarning)
                    return None

    def _get_dataset_patterns(self, name: str) -> Optional[List[str]]:
        """Get dataset patterns from dataset_config by name.

        Returns the list of glob patterns for a named aggregate dataset,
        or None if not configured.
        """
        if self.config.dataset_config is not None:
            defn = self.config.dataset_config.get_dataset_config(name)
            if defn is not None and hasattr(defn, "patterns"):
                return defn.patterns
        return None

    def get_raw_dataset(self, key: str) -> Optional[pd.DataFrame]:
        """Return an h5 dataset as an unscaled DataFrame.

        ``key`` may be a short alias (matched against the parser's
        ``list_datasets()``) or a full h5 path. Returns the values exactly
        as stored on disk — no base_power scaling applied. Use the high-level
        ``get_*`` methods (``get_generation``, ``get_load``, etc.) if you want
        scaled MW values.
        """
        if self.parser is None or not hasattr(self.parser, "get_raw_dataset"):
            return None
        return self.parser.get_raw_dataset(key)

    def __get_dataset(self, patterns: List[str], scale_base_value=True) -> pd.DataFrame:
        """
        Finds and parses all datasets that match a given pattern.

        :returns: Timeseries dataframe

        """
        all_datasets = self.parser.list_datasets().keys()

        matching_datasets = set()
        for p in patterns:
            has_match = False
            for d in all_datasets:
                if fnmatch(d, p):
                    has_match = True
                    matching_datasets.add(d)
            if has_match == False:
                # warn user that a particular pattern didn't have any matches.
                message = f"Could not find dataset with pattern {p}, consider updating the configuration or removing this pattern to avoid a warning."
                warnings.warn(message, UserWarning)

        if matching_datasets:  # if there are matches
            frames = []
            for d in matching_datasets:
                df = self.parser.get_dataset(d)
                frames.append(df.T)

            df = pd.concat(frames)
            if scale_base_value:
                return df.T * self.unit_base_value
            return df.T

        else:
            message = f"No matching datasets found for {patterns}, consider updating the configuration."
            warnings.warn(message, UserWarning)
            return None

    def get_line_flow(self) -> pd.DataFrame:
        """
        Parses and Aggregates the Line Flow data across multiple files by using the
        SiennaSystemAggregator.get_dataset("FlowActivePowerVariable__Line")

        Values are scaled by *unit_base_value*

        :returns: Timeseries dataframe of line flow scaled by unit base value.
        """
        flow_patterns = self._get_dataset_patterns("flow")
        if flow_patterns is None:
            warnings.warn("No flow dataset patterns configured.", UserWarning)
            return None
        flow_df = self.__get_dataset(flow_patterns)
        if flow_df is not None:
            return flow_df
        else:
            warnings.warn("Unable to generate flow dataset.", UserWarning)
            return None

    def get_area_interchange(self):
        """
        Parses the Area Interchange data found across multiple files using the
        SiennaSystemAggregator.get_dataset("FlowActivePowerVariable__AreaInterchange").

        dataset lookup value can be overridden with SiennaScenario.config.interchange_path

        :returns:
            Timeseries dataframe of flow across interchanges of the default Areas in
            the underlying Sienna system.
        """

        ## use the __get_dataset() so that the units are applied correctly.
        interchange_patterns = self._get_dataset_patterns("interchange")
        if interchange_patterns is None:
            warnings.warn("No interchange dataset patterns configured.", UserWarning)
            return None
        return self.__get_dataset(interchange_patterns)

    def get_hvdc_flow(self):
        dc_flow_patterns = self._get_dataset_patterns("dc_flow")
        if dc_flow_patterns is None:
            warnings.warn("No HVDC flow dataset patterns configured.", UserWarning)
            return None
        return self.__get_dataset(dc_flow_patterns)

    def get_generation(self) -> pd.DataFrame:
        """
        Parses and Aggregates the generation data across multiple simulation files.

        Uses the internal SiennaSimulation Aggregator and reads all datasets that start with "ActivePowerVariable*".

        Combines all the datasets and returns a dataframe scaled by *unit_base_value*

        :returns: Timeseries Dataframe of generation by generator id/name.
        """

        generation_patterns = self._get_dataset_patterns("generation")
        if generation_patterns is None:
            warnings.warn("No generation dataset patterns configured.", UserWarning)
            return None

        gen_df = self.__get_dataset(generation_patterns)

        if gen_df is not None:
            return gen_df
        else:
            warnings.warn("Unable to create generation dataset", UserWarning)
            return None

    def get_availability(self) -> pd.DataFrame:
        """
        **Sienna Dataset: ActivePowerTimeSeriesParameter__RenewableDispatch**

        :returns: Timeseries dataframe of RenewableDispatch Availability.
        """
        availability_patterns = self._get_dataset_patterns("availability")
        if availability_patterns is None:
            warnings.warn("No availability dataset patterns configured.", UserWarning)
            return None
        avail_df = self.__get_dataset(availability_patterns)
        if avail_df is not None:
            return avail_df
        else:
            warnings.warn(
                "Unable to create VRE availability timeseries, Curtailment data may not be calculated.",
                UserWarning,
            )
            return None

    def get_load(self) -> Union[pd.DataFrame, None]:
        """
        **Sienna Dataset: ActivePowerTimeSeriesParameter__StandardLoad**

        :returns: Timeseries Dataframe of the Standard Load dataset.
        """
        load_patterns = self._get_dataset_patterns("load")
        if load_patterns is None:
            warnings.warn(
                "No load dataset patterns configured. Update dataset_config with patterns from self.parser.list_datasets().",
                UserWarning,
            )
            return None
        load_df = self.__get_dataset(load_patterns)
        if load_df is not None:
            return load_df * -1
        else:
            warnings.warn("Unable to create load timeseries data", UserWarning)
            return None

    def get_generation_capacity(self):
        """
        Combines the base_power*rating of values of Sienna components found in self.config.generation_components

        :returns: A dataframe of aggregated generation capacity by Simplified Technogogy across each area.

        """

        frames = []
        for c in self.config.system_config.generation_components:
            ts = self.system.get_component_data(c)
            if ts is not None:
                ts = ts[ts["available"] == True]
                ts["capacity"] = ts["base_power"] * ts["rating"]
                frames.append(ts.reset_index().set_index("name")[["capacity"]])

        gen_cap = pd.concat(frames)

        gen_cap.index = pd.MultiIndex.from_tuples(
            [
                (self._map_gen_to_area(idx), self._map_gen_to_tech(idx), idx)
                for idx in gen_cap.index
            ],
            names=["Area", "Technology", "Generator"],
        )
        cap_totals = (
            gen_cap.groupby(level=["Area", "Technology"])
            .sum()
            .unstack()["capacity"]
            .fillna(0.0)
        )
        return cap_totals

    def get_production_cost(self):
        """
        Combines the cost expressions and and ActivePower Variables found in
        the self.config.cost_paths dand self.config.generation_paths to get the Production cost.


        :returns: Timeseries DataFrame of production cost by generator.
        """
        warnings.warn(
            "Experimental feature implementation, please verify results", UserWarning
        )
        cost_patterns = self._get_dataset_patterns("cost")
        if cost_patterns is None:
            warnings.warn("No cost dataset patterns configured.", UserWarning)
            return None
        return self.__get_dataset(cost_patterns, scale_base_value=False)

    def get_storage_charging(self) -> pd.DataFrame:
        """
        **Sienna Dataset: ActivePowerInVariable%**

        Creates the storage charging dataframe by finding any dataset with ActivePowerInVariable* pattern.
        Includes a combination of Battery Charging or Pump Load.

        Values are scaled by **unit_base_value**

        :returns: Timeseries Dataframe of charging load.
        """

        charging_patterns = self._get_dataset_patterns("charging")
        if charging_patterns is None:
            warnings.warn("No charging dataset patterns configured.", UserWarning)
            return None
        charging_df = self.__get_dataset(charging_patterns)
        if charging_df is not None:
            return charging_df
        else:
            warnings.warn(
                "Unable to create storage load timeseries data, additional calculated loads may not be available.",
                UserWarning,
            )
            return None

    def get_unserved(self):
        """Not Implemented"""
        return NotImplemented

    def get_area_unserved(self):
        """
        Not Implemented.
        """
        return NotImplemented

    def get_system_unserved(self) -> pd.Series:
        """
        Gets the system-wide unserved energy balance for a copper plate Sienna model.

        Sums the total energy balance across the system for each timestep.
        Only returns the negative balances as absolute values, otherwise 0.
        """
        power_balance_patterns = self._get_dataset_patterns("power_balance")
        if power_balance_patterns is None:
            warnings.warn("No power balance dataset patterns configured.", UserWarning)
            return None
        df = self.__get_dataset(power_balance_patterns)
        return df.T.sum().T.apply(lambda x: abs(x) if x < 0 else 0)

    def get_system_dispatch(
        self, include_load=True, include_use=False, include_charging=True, **kwargs
    ):
        """
        Gets the dispatch data for the entire system, optionally including load, use, and charging information.

        :param include_load: Boolean indicating whether to include load in the dispatch data.
        :param include_use: Boolean indicating whether to include use (e.g., unserved energy) in the dispatch data.
        :param include_charging: Boolean indicating whether to include charging data in the dispatch data.
        :param kwargs: Additional keyword arguments to be passed to the parent class's get_system_dispatch method.

        :returns: DataFrame containing the dispatch data for the entire system.
        """

        system_dispatch = super().get_system_dispatch(
            include_load=include_load,
            include_use=False,
            include_charging=include_charging,
            **kwargs,
        )

        # TODO This should be refactord to handle key errors in the case
        # of the column not existing, but also fall back to area or nodal unserved if
        # those methods are available.
        if include_use:
            system_dispatch[gc.config.unserved_energy_alias] = (
                self.get_system_unserved()
            )
        return system_dispatch

    def copy(
        self, selected_model: Optional[str] = None, display_name: Optional[str] = None
    ) -> "SiennaScenario":
        """
        Create a copy of this scenario with independent configuration and parser.

        Parameters:
        -----------
        selected_model : str, optional
            Model to select in the new scenario's parser. If None, uses current selected_model.
        display_name : str, optional
            Display name for the new scenario. If None, uses current display_name.

        Returns:
        --------
        SiennaScenario
            New scenario instance with independent configuration and parser
        """
        # Create new scenario instance
        new_scenario = SiennaScenario.__new__(SiennaScenario)

        # Deep copy the configuration to ensure independence
        new_scenario.config = copy.deepcopy(self.config)

        # Copy system parser (this is read-only, so shallow copy is fine)
        new_scenario.system = self.system

        # Create independent parser copy with selected model
        if self.parser is not None:
            new_scenario.parser = self.parser.copy(selected_model=selected_model)
        else:
            new_scenario.parser = None

        # Copy unit information
        new_scenario.unit_base_value = self.unit_base_value
        new_scenario.unit_system = self.unit_system

        # Copy internal mappings (these are derived from system data, so shallow copy is fine)
        new_scenario._area = self._area
        new_scenario._tech_map = self._tech_map
        new_scenario._gen_area_map = self._gen_area_map
        new_scenario._load_area_map = self._load_area_map
        new_scenario._line_rating_map = self._line_rating_map
        new_scenario._tech_simple = copy.deepcopy(self._tech_simple)
        new_scenario._load_includes_charging = self._load_includes_charging

        # Initialize internal plotter
        new_scenario._plotter = None

        # Set display name
        if display_name is not None:
            new_scenario.display_name = display_name
        else:
            new_scenario.display_name = self.display_name

        return new_scenario

    def to_multiscenario(self) -> "MultiScenario":
        """
        Create a MultiScenario from all simulation models in this scenario's h5 files.

        Returns:
        --------
        MultiScenario
            MultiScenario object with scenarios for each simulation model
        """
        from .multi import MultiScenario

        if not self.parser:
            raise ValueError("No parser available")

        available_models = self.parser.simulation_models
        scenarios = {}

        for model_name in available_models:
            # Create an independent copy of this scenario for each model
            scenario_copy = self.copy(
                selected_model=model_name, display_name=model_name
            )
            scenarios[model_name] = scenario_copy

        return MultiScenario(scenarios)

    @classmethod
    def from_simulation_models(
        cls,
        simulation_files: Union[str, List[str]],
        system_file: Optional[str] = None,
        config: Optional[ScenarioConfig] = None,
        pattern: str = "*.h5",
        # Deprecated alias
        solution_data: Optional[Union[str, List[str]]] = None,
    ) -> Dict[str, "SiennaScenario"]:
        """
        Create multiple SiennaScenario objects, one for each simulation model in the h5 files.

        Parameters:
        -----------
        simulation_files : str or list of str
            Path to simulation output data or list of paths to h5 files
        system_file : str, optional
            Path to system data file (Sienna JSON file)
        config : ScenarioConfig, optional
            Base configuration object for all scenarios
        pattern : str, optional
            Glob pattern to use when searching for files (default: "*.h5")

        Returns:
        --------
        Dict[str, SiennaScenario]
            Dictionary mapping simulation model names to scenario objects
        """
        from .base import _resolve_simulation_files
        from ..simulations import SiennaSimulationParser

        simulation_files = _resolve_simulation_files(simulation_files, solution_data)

        # Find solution files
        if isinstance(simulation_files, str):
            solution_files = cls._find_solution_files(cls, simulation_files, pattern)
        else:
            solution_files = simulation_files

        if not solution_files:
            raise ValueError("No solution files found")

        # Create a parser to get available simulation models
        parser = SiennaSimulationParser(solution_files[0])
        available_models = parser.simulation_models

        scenarios = {}

        for model_name in available_models:
            # Create a new scenario for each model
            scenario = cls(
                simulation_files=solution_files,
                system_file=system_file,
                config=config,
                pattern=pattern,
            )

            # Set the simulation model for the parser
            if hasattr(scenario, "parser") and scenario.parser:
                scenario.parser.selected_model = model_name

            # Set display name to model name
            scenario.display_name = model_name

            scenarios[model_name] = scenario

        return scenarios
