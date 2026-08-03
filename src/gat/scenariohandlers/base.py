"""
The Base Scenario Object Class. Do not import directly. Base class provides higher level aggregations for concrete classes that implement the core data extraction methods.

@author: Micah Webb
"""

from abc import ABC, abstractmethod
import json
import os
from gat.scenariohandlers.config_maps import *
from gat.models.base import *
from gat.models.scenario import ScenarioConfig
from gat.models.utils import create_tech_mappings
from glob import glob
from gat.datahelpers.parsers import *
import warnings
from .compute import *
import gat.config as gc
import pandas as pd
from typing import List, Optional, Union
from functools import lru_cache
from loguru import logger
from gat import __version__

# Import version
try:
    from gat._version import version as __version__
except ImportError:
    __version__ = "unknown"


def calc_curtailment(gen_tech, avail_tech):
    """Calculates the curtailment for generator technologies that fall under gc.config.curtailable_tech"""

    avail_curt_tech = [
        val
        for val in avail_tech.columns.get_level_values(level="Technology").unique()
        if val in gc.config.curtailable_tech
    ]
    gen_curt_tech = [
        val
        for val in gen_tech.columns.get_level_values(level="Technology").unique()
        if val in gc.config.curtailable_tech
    ]

    curt_gen = (
        pd.concat([avail_tech[avail_curt_tech], -1.0 * gen_tech[gen_curt_tech]])
        .groupby(level=0)
        .sum()
    )

    return curt_gen.map(lambda x: x if x >= 0.0 else 0.0)


def load_map(map):
    """Loads a dictionary/mapping from a JSON file or dictionary."""
    if type(map) == dict:
        return map
    elif type(map) == str:
        if os.path.exists(map):
            try:
                with open(map, "r") as f:
                    return json.loads(f.read())
            except Exception as e:
                print(f"failed to load json file {map}")
                print(e)
                return None
        else:
            print(f"path {map} does not exist")
            return None
    else:
        return None


def fill_missing_loads(
    dispatch: pd.DataFrame, charging: pd.DataFrame, load_includes_charging=False
):
    """Calculates missing load values of a dispatch dataframe if only Native Load or Total Load are present."""

    dispatch_areas = dispatch.columns.get_level_values(level="Area").unique()

    if charging is not None:
        charging_areas = charging.columns.get_level_values(level="Area").unique()

        area_charging = charging.T.groupby(level="Area").sum().T
        area_charging.columns = pd.MultiIndex.from_tuples(
            [(col, gc.config.storage_load_alias) for col in area_charging.columns]
        )
    else:
        charging_areas = []
        print("no charging areas")

    new_data = {}

    for area in dispatch_areas:
        if area in charging_areas:

            # If load includes charging, we have total load, else we have native load
            if load_includes_charging:
                if (area, gc.config.total_load_alias) in dispatch.columns:
                    new_data[(area, gc.config.native_load_alias)] = (
                        dispatch[(area, gc.config.total_load_alias)]
                        - area_charging[(area, gc.config.storage_load_alias)]
                    )

            # Load doesn't include charging. Total load = native load + pump/charging load
            else:
                if (area, gc.config.native_load_alias) in dispatch.columns:
                    new_data[(area, gc.config.total_load_alias)] = (
                        dispatch[(area, gc.config.native_load_alias)]
                        + area_charging[(area, gc.config.storage_load_alias)]
                    )

        else:
            # No pump/charging load in area, Native load = total load
            if load_includes_charging:
                if (area, gc.config.total_load_alias) in dispatch.columns:
                    new_data[(area, gc.config.native_load_alias)] = dispatch[
                        (area, gc.config.total_load_alias)
                    ]
            else:
                if (area, gc.config.native_load_alias) in dispatch.columns:
                    new_data[(area, gc.config.total_load_alias)] = dispatch[
                        (area, gc.config.native_load_alias)
                    ]

    filled_loads = pd.DataFrame(new_data, index=dispatch.index)
    dispatch = pd.concat([dispatch, filled_loads], axis=1)

    new_data = {}
    for area in dispatch_areas:
        if gc.config.total_load_alias in dispatch[area].columns:
            area_vre = [
                col
                for col in dispatch[area].columns
                if col in gc.config.curtailable_tech
            ]
            if len(area_vre) > 0:
                if (area, gc.config.total_load_alias) in dispatch.columns:
                    new_data[(area, gc.config.net_load_alias)] = dispatch[area][
                        gc.config.total_load_alias
                    ] - dispatch[area][area_vre].sum(axis=1)
            else:
                if (area, gc.config.native_load_alias) in dispatch.columns:
                    new_data[(area, gc.config.net_load_alias)] = dispatch[area][
                        gc.config.total_load_alias
                    ]

    filled_loads = pd.DataFrame(new_data, index=dispatch.index)
    filled_dispatch = pd.concat([dispatch, filled_loads], axis=1)
    filled_dispatch.columns.names = ["Area", "Technology"]
    return filled_dispatch.sort_index(axis=1)


def get_peak_stats(dispatch, winter_months=[1, 2, 12]) -> pd.DataFrame:
    """

    Calculates the peak/min total and net load, split by winter and summer months

    :param dispatch: A dataframe with aggregate generation and load by technology and load type.

    :param winter_months: The month numbers to designate as winter months. Defaults to [1,2,12] (Jan, Feb, Dec)

    :returns: Dataframe of peak/min timestamps and corresponding load/net load, and vre values.

    """
    winter_mask = dispatch.index.month.isin(set(winter_months))
    summer_mask = ~winter_mask
    vre_cols = [tech for tech in gc.config.curtailable_tech if tech in dispatch.columns]
    total_demand = dispatch[gc.config.total_load_alias]
    total_vre = dispatch[vre_cols].sum(axis=1)
    total_net_load = total_demand - total_vre

    seasons = ["winter", "summer"]
    peak_types = ["min", "peak"]
    load_types = ["net", "total"]

    data = {
        "peak_type": [],
        "load_type": [],
        "season": [],
        "timestamp": [],
        "vre": [],
        "demand": [],
        "net load": [],
    }

    for season in seasons:
        mask = winter_mask | summer_mask
        if season == "winter":
            mask = winter_mask
        elif season == "summer":
            mask = summer_mask

        for load in load_types:
            load_df = total_demand[mask]
            if load_df.empty == False:
                if load == "net":
                    load_df = total_net_load[mask]

                for t in peak_types:

                    if t == "min":
                        timestamp = load_df.idxmin()
                    else:
                        timestamp = load_df.idxmax()

                    demand_val = total_demand.loc[timestamp]
                    vre_val = total_vre.loc[timestamp]
                    net_load_val = total_net_load.loc[timestamp]

                    data["peak_type"].append(t)
                    data["load_type"].append(load)
                    data["season"].append(season)
                    data["timestamp"].append(timestamp)
                    data["vre"].append(vre_val)
                    data["demand"].append(demand_val)
                    data["net load"].append(net_load_val)

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["description"] = (
        df["season"].str.capitalize()
        + " "
        + df["peak_type"].str.capitalize()
        + " "
        + df["load_type"].str.capitalize()
        + " Load"
    )
    return df


def _resolve_simulation_files(
    simulation_files=None, solution_data=None
) -> Optional[Union[str, List[str]]]:
    """Resolve the simulation_files / solution_data parameter pair.

    Accepts the new ``simulation_files`` parameter or the deprecated
    ``solution_data`` alias.  Raises if both are provided.
    """
    if simulation_files is not None and solution_data is not None:
        raise TypeError(
            "Cannot pass both 'simulation_files' and 'solution_data'. "
            "Use 'simulation_files' (solution_data is deprecated)."
        )
    if solution_data is not None:
        warnings.warn(
            "The 'solution_data' parameter is deprecated and will be removed "
            "in a future release. Use 'simulation_files' instead.",
            FutureWarning,
            stacklevel=3,
        )
        return solution_data
    return simulation_files


class BaseScenario(ABC):
    """
    Initialize a scenario object with configuration, system data, and solution data.

    Parameters:
    -----------
    simulation_files : str or list of str, optional
        Path to simulation output data or directory containing such data.
        Can be a single file path, list of file paths, or a directory path.
    tech_map : dict, optional
        Mapping from generator IDs to technology types.
    gen_area_map : dict, optional
        Mapping from generator IDs to geographic areas.
    load_area_map : dict, optional
        Mapping from load IDs to geographic areas.
    line_rating_map : dict, optional
        Mapping from line IDs to line capacities.
    config : ScenarioConfig, optional
        Configuration object for the scenario.
    system_data : str, optional
        Path to system data file (e.g., Sienna JSON or Plexos XML)."""

    _expected_model_type = None
    _solution_file_pattern = "*.h5"  # works for both Sienna and Plexos

    def __init__(
        self,
        simulation_files: Optional[Union[str, List[str]]] = None,
        tech_map: Optional[dict] = None,
        gen_area_map: Optional[dict] = None,
        load_area_map: Optional[dict] = None,
        line_rating_map: Optional[dict] = None,
        config: Optional[ScenarioConfig] = None,
        system_data: Optional[str] = None,
        pattern: str = "*.h5",
        # Deprecated alias — use simulation_files instead
        solution_data: Optional[Union[str, List[str]]] = None,
    ) -> None:

        simulation_files = _resolve_simulation_files(simulation_files, solution_data)

        # Create a default config if none provided
        if config is None:
            self.config = ScenarioConfig(
                model_type=self._expected_model_type or "unknown"
            )
        else:
            self.config = config

        # Store system data path
        if system_data is not None:
            self.config.system_path = system_data

        # Store original solution data
        self._solution_data = simulation_files

        # Find solution files based on model type and pattern
        if simulation_files is not None:
            solution_files = self._find_solution_files(simulation_files, pattern)

            # If files were found, calculate hash and update config
            if solution_files:
                self.solution_hash = hash("_".join(solution_files))
                self.config.simulation_paths = solution_files

        # Initialize maps, handled by reading simulation files directly.
        self._tech_map = self.generator_technology_map
        self._gen_area_map = load_map(gen_area_map)
        self._load_area_map = load_map(load_area_map)
        self._line_rating_map = load_map(line_rating_map)
        self._line_rating_multiplier = 1

        if self.config and len(self.config.technology_mappings) > 0:
            # initialize

            self._tech_simple = {
                model_tech: config.display_group
                for model_tech, config in self.config.technology_mappings.items()
            }

        else:
            self.config.init_technologies(self._tech_simple)

        # Any remaining technologies will map from model_technology->model_technology
        remaining_model_tech = {
            tech: tech
            for tech in set(self._tech_map.values())
            if tech not in self._tech_simple
        }

        if len(remaining_model_tech) > 0:
            logger.debug("Attempting to map technologies to standard technology names")

            remaining_mappings = create_tech_mappings(remaining_model_tech)

            for model_tech, config in remaining_mappings.items():
                self.config.technology_mappings[model_tech] = config
                self._tech_simple[model_tech] = config.display_group

        # Whether the scenario's load timeseries already includes storage
        # charging (Total Demand) or is native-load-only (Native Demand).
        # Sourced from the scenario config; mutable post-construction via the
        # public `load_includes_charging` property.
        self._load_includes_charging = bool(
            getattr(self.config, "load_includes_charging", False)
        )

        # Internal Plotting Object
        self._plotter = None
        # initialize the plotter.
        self.plot

        # Aggregation levels for how to group generators into "Areas"
        self._aggregation_level = None

    @property
    def aggregation_level(self):
        return self._aggregation_level

    @aggregation_level.setter
    def set_aggregation_level(self):
        # determine if aggregation level is in list of aggregation_levels

        # if lookup type is node->area, remap gen_area_map based on dictionary key and new lookup value
        # if lookup type is area->area, remap values of gen_area_map based on value of dict
        # if lookup type is geospatial, use the geolookup method and concrete impl of get_generator_gis to get new value.
        pass

    def list_aggregation_levels(self) -> Optional[Dict[str, str]]:
        from gat.models.lookups import GeoAreaLookup

        available_area_maps = {}

        for k, lookup in self.config.area_lookups.items():

            if type(lookup) == GeoAreaLookup:
                for v in lookup.available_values:

                    lookup_key = f"{k}.{v}"
                    if v not in available_area_maps:
                        available_area_maps[v] = (k, v)
                    else:
                        available_area_maps[lookup_key] = (k, v)

        if len(available_area_maps) > 0:
            return available_area_maps
        else:
            return None

    @property
    def plot(self):
        if self._plotter is None:
            from gat.quickplots.scenario_plotter import ScenarioPlotter

            self._plotter = ScenarioPlotter(self)
            return self._plotter
        else:
            return self._plotter

    @property
    @abstractmethod
    def generator_technology_map() -> Dict[str, str]:
        """Abstract property representing the generation id to the technology name found in the underlying model.
        This property function should make no attempt to translate technology names into display names.
        """
        pass

    @property
    def line_rating_map(self) -> dict:
        """
        A dictionary/map of Transmission Line capacity
        """

        return {
            key: val * self._line_rating_multiplier
            for key, val in self._line_rating_map.items()
        }

    @property
    def tech_simple(self):
        """
        A dictionary/map that maps model specific technology names to simplified technology names for further aggregation and presentation.
        """
        return self._tech_simple

    @tech_simple.setter
    def tech_simple(self, value):
        """checks the coverage of the tech map and warns the users of any unmapped technologies."""

        solution_tech = {val for key, val in self._tech_map.items()}

        mapped_tech = {key for key in value.keys()}

        missing_tech = {key for key in solution_tech if key not in mapped_tech}
        if len(missing_tech) > 0:
            warnings.warn(
                "warning: the following technologies don't have a simplified mapping.",
                UserWarning,
            )
            print(missing_tech)

        self._tech_simple = load_map(value)

        self.get_system_dispatch.clear_cache()

    @property
    def load_includes_charging(self) -> bool:
        """Whether ``get_load()`` already includes storage charging.

        When True, the dispatch frame's load column is aliased as
        "Total Demand"; when False (the default), it's "Native Demand"
        and storage charging is added separately by `fill_missing_loads`.
        Backed by ``ScenarioConfig.load_includes_charging``.
        """
        return self._load_includes_charging

    @load_includes_charging.setter
    def load_includes_charging(self, value: bool) -> None:
        self._load_includes_charging = bool(value)

    @property
    def gen_area_map(self) -> dict:
        """Mapping of generator name → area. Populated from solution
        metadata at construction; can be overridden post-hoc."""
        return self._gen_area_map

    @gen_area_map.setter
    def gen_area_map(self, value: dict) -> None:
        self._gen_area_map = load_map(value)

    @property
    def load_area_map(self) -> dict:
        """Mapping of load/node name → area."""
        return self._load_area_map

    @load_area_map.setter
    def load_area_map(self, value: dict) -> None:
        self._load_area_map = load_map(value)

    @property
    def line_rating_map(self) -> dict:
        """Mapping of line name → rating in MW."""
        return self._line_rating_map

    @line_rating_map.setter
    def line_rating_map(self, value: dict) -> None:
        self._line_rating_map = load_map(value)

    @property
    def area(self) -> str:
        """Display label for the aggregation column (default: ``"area"``)."""
        return getattr(self, "_area", "area")

    @area.setter
    def area(self, value: str) -> None:
        self._area = str(value)

    def _find_solution_files(
        self, solution_data: Union[str, List[str]], pattern: str = "*.h5"
    ) -> List[str]:
        """
        Default implementation to find solution files based on pattern.

        Parameters:
        -----------
        solution_data : str or list of str
            Path to solution data or list of paths. ``~`` is expanded to
            the user's home directory (shells do this automatically, but
            Python's os.path functions do not — a literal ``"~/..."``
            string passed programmatically, e.g. from a REPL or script,
            would otherwise silently resolve to zero files).
        pattern : str, optional
            Glob pattern to use when searching for files (default: "*.h5")

        Returns:
        --------
        List[str]
            List of file paths to solution files
        """
        files = []

        if isinstance(solution_data, str):
            solution_data = os.path.expanduser(solution_data)
            if os.path.isdir(solution_data):
                # Search for files matching pattern in the directory (non-recursive)
                files = [file for file in glob(os.path.join(solution_data, pattern))]
                files.sort()
            elif os.path.isfile(solution_data):
                files = [os.path.normpath(solution_data)]
            elif "*" in solution_data:
                # If solution_data itself is a glob pattern
                files = [file for file in glob(solution_data)]
                files.sort()
        elif isinstance(solution_data, list):
            # For lists, keep all files but expand any glob patterns
            expanded_files = []
            for item in solution_data:
                item = os.path.expanduser(item)
                if os.path.isfile(item):
                    expanded_files.append(os.path.normpath(item))
                elif "*" in item:
                    expanded_files.extend([file for file in glob(item)])
            files = expanded_files

        return files

    # Implement abstract classes below to gain access to others.
    @abstractmethod
    def get_generation(self):
        """Abstract Method to be implemented by model specific classes to return generation by generator."""

        return NotImplemented

    def get_generators(self):
        warnings.warn(
            "The function get_generators has been renamed to get_generation()",
            DeprecationWarning,
        )
        return self.get_generation()

    @abstractmethod
    def get_availability(self):
        """Abstract Method to be implemented by model specific classes to return VRE availability by generator."""

        return NotImplemented

    @abstractmethod
    def get_load(self):
        """Abstract Method to be implemented by model specific classes to return load by node or area."""

        return NotImplemented

    @abstractmethod
    def get_unserved(self):
        """Abstract Method to be implemented by model specific classes to return unserved energy by node or area."""

        return NotImplemented

    @abstractmethod
    def get_generation_capacity(self):
        """Abstract Method to be implemented by model specific classes to return generation capacity."""
        return NotImplemented

    def get_flow(self):
        """Deprecated: Use Line flow instead."""
        warnings.warn(
            "get_flow() is deprecated and will be removed in a future version, use get_line_flow() instead.",
            DeprecationWarning,
        )
        return self.get_line_flow()

    @abstractmethod
    def get_line_flow(self):
        """Abstract function implemented by concrete classes to enable transmission specific calculations."""

        return NotImplemented

    @abstractmethod
    def get_production_cost(self, zone: Optional[str] = None):
        """Abstract function implemented by concrete classes to enable cost specific aggregations."""

        return NotImplemented

    @abstractmethod
    def get_storage_charging(self):
        """Abstract function implemented by concrete classes to enable charging specific aggregations."""

        return NotImplemented

    def to_config(self) -> ScenarioConfig:
        """Create a ScenarioConfig object from the current scenario"""
        from gat.models.scenario import TechnologyMapping
        from gat.colors import random_color, standard_color_dict
        from gat.config import config as gc

        # Create mappings from tech_simple
        tech_mappings = {}
        i = 0
        for tech_name, display_group in self._tech_simple.items():
            # Get display color from standard colors if available
            display_color = standard_color_dict.get(display_group, None)

            if display_color is None:
                display_color = random_color()
            # Determine if curtailable
            curtailable = display_group in gc.curtailable_tech

            tech_mappings[tech_name] = TechnologyMapping(
                display_group=display_group,
                display_color=display_color,
                display_order=i,
                curtailable=curtailable,
            )
            i += 1

        self.config.technology_mappings = tech_mappings

        # Ensure the config has the current GAT version
        self.config.gat_version = __version__

        return self.config

    def save_config(self, filepath: Optional[str] = None) -> None:
        """Save current configuration to a file"""

        config = self.to_config()
        if filepath is None and config.display_name is not None:
            config.save(output_path=f"{config.display_name}.yaml")
        elif filepath is not None:
            config.save(output_path=filepath)
        else:
            raise ValueError("No filepath or display_name given")

    @classmethod
    def from_config(
        cls,
        config_path: Union[str, ScenarioConfig],
        system_path: Optional[str] = None,
        simulation_paths: Optional[Union[str, List[str]]] = None,
        display_name: Optional[str] = None,
        pattern: str = "*.h5",
    ):
        """
        Create a scenario from a configuration file or object.

        Parameters:
        -----------
        config_path : str or ScenarioConfig
            Path to config file or config object
        system_path : str, optional
            Override system path in config
        simulation_paths : str or list of str, optional
            Override simulation paths in config
        display_name : str, optional
            Override display name in config
        pattern : str, optional
            Glob pattern for finding solution files

        Returns:
        --------
        BaseScenario
            Initialized scenario object
        """
        # Load config if string path provided
        if isinstance(config_path, str):
            from gat.models.scenario import load_config

            config = load_config(config_path)
        else:
            config = config_path

        # Validate config is for the expected model type
        if (
            cls._expected_model_type
            and config.model_type.lower() != cls._expected_model_type
        ):
            warnings.warn(
                f"Config is for {config.model_type}, but creating a {cls.__name__}"
            )

        # Use override paths if provided
        sim_files = simulation_paths or config.simulation_paths

        if system_path is not None:
            config.system_path = system_path

        if sim_files is None and config.system_path is None:
            raise ValueError("No simulation files provided in config or as override")

        if display_name is None and simulation_paths != config.simulation_paths:
            warnings.warn(
                f"Overriding config simulation paths without new display name."
            )
        elif display_name is not None:
            config.display_name = display_name

        # Create scenario with config and pattern
        return cls(simulation_files=sim_files, config=config, pattern=pattern)

    def __simplify_technology(self, tech):
        """Internal function that simplifies the technology provided by the model to a simplified technology for aggregation and plotting."""
        if tech in self._tech_simple:
            return self._tech_simple[tech]
        else:
            return tech

    def _map_gen_to_tech(self, generator_id):
        """
        Internal function that maps the generator to technology/type.
        If no area map is provided, defaults to 'Other' as technology
        """

        if self._tech_map:
            original_tech = self._tech_map.get(generator_id, "Other")
            return self._tech_simple.get(original_tech, original_tech)
        else:
            return "Other"

    def _map_gen_to_area(self, generator_id):
        """
        Internal function that maps the generator to geographic area.
        If no area map is provided, defaults to SYSTEM as area.
        """

        if self._gen_area_map is None:
            return "SYSTEM"
        else:
            return self._gen_area_map.get(generator_id, "Other")

    # Organized Data Functions
    def get_generators_tech(self) -> pd.DataFrame:
        """Returns a Dataframe with a column for each generator along with technology category"""

        gen_df = self.get_generation()

        # TODO replace simple tech map with standard EIA tech map
        if self._tech_simple != None:
            gen_df.columns = pd.MultiIndex.from_tuples(
                [(self._map_gen_to_tech(col), col) for col in gen_df.columns],
                names=["Technology", "Generator"],
            )
        else:
            gen_df.columns = pd.MultiIndex.from_tuples(
                [(self._tech_map[col], col) for col in gen_df.columns],
                names=["Technology", "Generator"],
            )

        gen_df.attrs["Units"] = "MW"
        return gen_df

    def get_availability_tech(self, simplify=True) -> pd.DataFrame:
        """Gets the availability for each generator and includes the technology type"""
        avail_df = self.get_availability()
        # TODO replace simple tech map with standard EIA tech map

        if self._tech_simple != None:
            avail_df.columns = pd.MultiIndex.from_tuples(
                [(self._map_gen_to_tech(col), col) for col in avail_df.columns],
                names=["Technology", "Generator"],
            )
        else:
            avail_df.columns = pd.MultiIndex.from_tuples(
                [(self._tech_map[col], col) for col in avail_df.columns],
                names=["Technology", "Generator"],
            )

        avail_df.attrs["Units"] = "MW"
        return avail_df

    def get_production_cost_tech(self) -> pd.DataFrame:
        """
        Gets the production cost aggregated by technology.

        :returns: Production cost timeseries with generation technology.
        """

        prod_cost = self.get_production_cost()

        if self._tech_simple is not None:
            prod_cost.columns = pd.MultiIndex.from_tuples(
                [(self._map_gen_to_tech(col), col) for col in prod_cost.columns],
                names=["Technology", "Generator"],
            )
        else:
            prod_cost.columns = pd.MultiIndex.from_tuples(
                [(self._tech_map[col], col) for col in prod_cost.columns],
                names=["Technology", "Generator"],
            )

        return prod_cost.sort_index(axis=1)

    def get_curtailment(self) -> pd.DataFrame:
        """Calculates the curtailment for each generator based on which technologies are configured as curtailable

        :returns: Timeseries Dataframe of curtailment for each generator.
        """
        gen_tech = self.get_generators_tech()
        avail_tech = self.get_availability_tech()

        curt_tech = calc_curtailment(gen_tech, avail_tech)
        return curt_tech

    def get_gen_and_curtailment(self) -> pd.DataFrame:
        """
        :returns: Timeseries Datafrom of generation and curtailment for each generator
        """

        gen_tech = self.get_generators_tech()
        avail_tech = self.get_availability_tech()

        curt_tech = calc_curtailment(gen_tech, avail_tech)

        curt_tech.columns = pd.MultiIndex.from_tuples(
            [("Curtailment", col[1]) for col in curt_tech.columns],
            names=["Technology", "Generator"],
        )

        return pd.merge(gen_tech, curt_tech, left_index=True, right_index=True)

    def get_system_dispatch(
        self, include_load=True, include_use=True, include_charging=True
    ) -> pd.DataFrame:
        """

        Gets interval generation, load, charging and unserved energy aggregated by technology for the entire system.

        :param include_load: boolean (whether to include load, skipped if not implemented)

        :param include_use: boolean (whether to include unserved energy, skipped if not implemented)

        :param include_charging: boolean (whether to include storage charging, skipped if not implemented)

        :param **kwargs: Arguments passed to get_area_load

        :returns: Timeseries DataFrame of generation, load, unserved energy and charging aggregated by technology and area.
        """

        area_dispatch = self.get_area_dispatch(
            include_load=include_load,
            include_use=include_use,
            include_charging=include_charging,
        )

        system_dispatch = area_dispatch.T.groupby(level="Technology").sum().T

        return system_dispatch

    def get_system_charging(self) -> Union[pd.DataFrame, None]:
        """
        Gets interval storage charging aggregated by technology for the entire system.

        :returns: Timeseries DataFrame of storage charging aggregated by technology.
                 Returns None if charging data is not available.
        """

        area_charging = self.get_area_charging()

        if area_charging is None:
            return None

        # Aggregate by technology across all areas
        system_charging = area_charging.T.groupby(level="Technology").sum().T
        system_charging.attrs["units"] = "MW"

        return system_charging

    # TODO, this needs to be reset every time the _gen_area_map changes or the _gen_tech_map changes.
    def get_area_dispatch(
        self, include_load=True, include_use=True, include_charging=True
    ) -> pd.DataFrame:
        """

        Gets interval generation, load, charging and unserved energy aggregated by technology and area

        :param include_load: boolean (whether to include load, skipped if not implemented)

        :param include_use: boolean (whether to include unserved energy, skipped if not implemented)

        :param include_charging: boolean (whether to include storage charging, skipped if not implemented)

        :param **kwargs: Arguments passed to get_area_load

        :returns: Timeseries DataFrame of generation, load, unserved energy and charging aggregated by technology and area.
        """

        def _missing(result):
            return (
                result is NotImplemented
                or result is None
                or (isinstance(result, pd.DataFrame) and result.empty)
            )

        if include_use and _missing(self.get_area_unserved()):
            logger.debug("Unserved energy not implemented")
            include_use = False
        if _missing(self.get_load()):
            logger.debug("Raw load not available")
            include_load = False
        if _missing(self.get_storage_charging()):
            logger.debug("Charging data not available")
            include_charging = False

        gen_curt_tech = self.get_gen_and_curtailment()

        gen_curt_tech.columns = pd.MultiIndex.from_tuples(
            [
                (self._map_gen_to_area(col[1]), col[0], col[1])
                for col in gen_curt_tech.columns
            ],
            names=["Area", "Technology", "Generator"],
        )

        gen_curt_tech = gen_curt_tech.T.groupby(level=["Area", "Technology"]).sum().T

        if include_load:
            regional_load = self.get_area_load()
            if regional_load is not None:
                load_alias = gc.config.native_load_alias
                if self._load_includes_charging:
                    load_alias = gc.config.total_load_alias
                regional_load_agg = regional_load.T.groupby(level=0).sum().T
                regional_load_agg.columns = pd.MultiIndex.from_tuples(
                    [(col, load_alias) for col in regional_load_agg.columns],
                    names=["Area", "Technology"],
                )

                gen_curt_tech = gen_curt_tech.merge(
                    regional_load_agg, left_index=True, right_index=True
                ).sort_index(axis=1)

        if include_use:
            regional_use = self.get_area_unserved()
            regional_use_agg = regional_use.T.groupby(level=0).sum().T
            regional_use_agg.columns = pd.MultiIndex.from_tuples(
                [
                    (col, gc.config.unserved_energy_alias)
                    for col in regional_use_agg.columns
                ],
                names=["Area", "Technology"],
            )

            gen_curt_tech = gen_curt_tech.merge(
                regional_use_agg, left_index=True, right_index=True
            ).sort_index(axis=1)

        if include_charging:
            area_charging = self.get_area_charging()

            gen_curt_tech = fill_missing_loads(
                gen_curt_tech,
                area_charging,
                load_includes_charging=self._load_includes_charging,
            )

        gen_curt_tech.attrs["units"] = "MW"
        gen_curt_tech = gen_curt_tech.sort_index()

        return gen_curt_tech

    # aggregates across generators
    def get_area_tech_aggregates(
        self,
    ) -> pd.DataFrame:  # TODO this does not do any aggregations
        """Gets the aggregated interval generation and curtailment by each area and technology"""

        gen_curt_tech = self.get_gen_and_curtailment()

        gen_curt_tech.columns = pd.MultiIndex.from_tuples(
            [
                (self._map_gen_to_area(col[1]), col[0], col[1])
                for col in gen_curt_tech.columns
            ],
            names=["Area", "Technology", "Generator"],
        )

        return gen_curt_tech

    def get_area_load(self) -> Union[pd.DataFrame, None]:
        """Gets the aggregated interval Load by Area"""
        df = self.get_load()
        if df is None:
            return None
        if self._load_area_map is None:
            warnings.warn(
                "No load-area mapping available. Load data cannot be grouped by area.",
                UserWarning,
            )
            return None
        df.columns = pd.MultiIndex.from_tuples(
            [
                (self._load_area_map.get(str(col), "other"), str(col))
                for col in df.columns
            ],
            names=["Area", "Node"],
        )
        return df.sort_index(axis=1)

    def get_area_unserved(self) -> pd.DataFrame:
        """Gets the Unserved Energy Aggregated by Area"""
        df = self.get_unserved()
        if df is NotImplemented:
            return NotImplemented

        df.columns = pd.MultiIndex.from_tuples(
            [
                (self._load_area_map.get(str(col), "other"), str(col))
                for col in df.columns
            ]
        )

        return df

    def get_area_charging(self) -> Union[pd.DataFrame, NotImplementedError]:
        """Aggregates the Energy Storage Charging by Area for each storage type (Pump Load, Battery Charging)"""

        df = self.get_storage_charging()

        if df is not None:
            df.columns = pd.MultiIndex.from_tuples(
                [
                    (self._map_gen_to_area(col), self._map_gen_to_tech(col), col)
                    for col in df.columns
                ],
                names=["Area", "Technology", "Generator"],
            )
            return df
        else:
            return None

    def get_area_curtailment_aggregates(self) -> pd.DataFrame:
        """Gets the curtailment aggregated for each available technology category and area"""

        curt_area = self.get_curtailment()
        curt_area.columns = pd.MultiIndex.from_tuples(
            [
                (self._map_gen_to_area(col[1]), col[0], col[1])
                for col in curt_area.columns
            ],
            names=["Area", "Technology", "Generator"],
        )

        return curt_area.T.groupby(level=["Area", "Technology"]).sum().T

    def get_peak_stats(self, winter_months=[1, 2, 12]) -> dict:
        """Gets the timestamp for winter and summer peaks for Net Load and Total Load.


        :param winter_months: The months defined as winter months to separate winter and summer peaks.

        :returns: A dataframe of winter summer peak/min load stats.

        """

        dispatch = self.get_system_dispatch()
        return get_peak_stats(dispatch, winter_months=winter_months)

    # Flow APIs
    def get_line_loading(self) -> pd.DataFrame:
        """
        Gets the line loading as a % of the lines capacity.
        Line Capacity is stored in based on _line_rating_map
        """

        flow = self.get_line_flow()
        line_r_map = self.line_rating_map
        ratings = np.array([line_r_map[line] for line in flow.columns])

        print("calculating loading")

        loading_matrix = calc_loading(flow.values, ratings)

        loading = pd.DataFrame(
            data=loading_matrix, columns=flow.columns, index=flow.index
        )

        return loading

    def get_line_utilization(self, threshold=[99, 95, 90, 75]) -> pd.DataFrame:
        """
        Calculates a flag for each hour on whether the line is overloaded by 75, 90, 95, or 99 percent

        :param threshold: List(float) - list of loading thresholds to determine if utilization is above or below.

        :returns: Dataframe with boolean flags for each timestamp that is over the threshold.

        """
        loading = self.get_line_loading()
        frames = []

        print("formatting dataframe")

        for t in threshold:
            ut_m = calc_congestion(loading.values, threshold=t)
            new_columns = pd.MultiIndex.from_tuples(
                [(f"U{t}", col) for col in loading.columns],
                names=["Utilization", "Line"],
            )
            ut_i = pd.DataFrame(data=ut_m, columns=new_columns, index=loading.index)
            frames.append(ut_i)

        utilization = pd.concat(frames, axis=1)
        return utilization

    def get_line_congestion_hours(self, threshold=100.0) -> pd.DataFrame:
        """Calculates a boolean flag for each hour and line congested"""
        loading = self.get_line_loading()

        congestion_matrix = calc_congestion(loading.values, threshold=threshold)
        congestion = pd.DataFrame(
            data=congestion_matrix, columns=loading.columns, index=loading.index
        )

        return congestion

    @property
    def display_name(self) -> Optional[str]:
        """Get the display name for this scenario"""
        return self.config.display_name if self.config else None

    @display_name.setter
    def display_name(self, name: str):
        """Set the display name for this scenario"""
        if self.config:
            self.config.display_name = name
        else:
            raise ValueError("Cannot set display name: scenario has no config")

    def __add__(self, other):
        """Add two scenarios together to create a MultiScenario"""
        from .multi import MultiScenario

        # Check if both scenarios have display names
        if not self.display_name:
            raise ValueError("Cannot add scenario: left operand has no display_name")
        if not other.display_name:
            raise ValueError("Cannot add scenario: right operand has no display_name")

        # Create MultiScenario with both scenarios
        return MultiScenario({self.display_name: self, other.display_name: other})
