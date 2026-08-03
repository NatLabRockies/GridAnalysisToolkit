import os
import sys
import warnings
from pathlib import Path

try:
    import orjson as _json

    def _loads(data):
        return _json.loads(data)

except ImportError:
    import json as _json

    def _loads(data):
        return _json.loads(data)


from typing import TYPE_CHECKING, List, Optional, Union

# TODO move to a relative import since geopandas isn't always required.
import geopandas as gpd
import h5py
import pandas as pd
from loguru import logger
from pydantic import BaseModel

from gat.datahelpers.parsers import combine_frames_skip_prev


class SiennaModelConfig(BaseModel):
    base_power: int
    horizon_count: int
    interval_ms: int
    num_executions: int
    resolution_ms: int
    system_uuid: str
    name: Optional[str] = None


class SiennaSimulationConfig(BaseModel):
    """
    This class holds the attributes for a given set of Simulation attributes
    This class is responsible for generating the timestamps of decision and emulation models

    """

    initial_time: str  # should be a datetime object
    num_steps: int
    problem_order: Union[
        str, List[str]
    ]  # These values will be used to look up h5 group attributes
    step_resolution_ms: int

    decision_models: dict[
        str, SiennaModelConfig
    ]  # must match the values in problem_order? (Could have a partially run model)

    emulation_model: SiennaModelConfig  # This could be multiple? DC-OPF, vs AC-OPF?

    def __init__(path: Union[str, Path]):
        """initializes the simulation and model configs from an h5 file input"""
        pass


class SiennaH5Parser:
    """
    Sienna H5 Parser
    -----------------

    Low-level reader for a Sienna simulation h5 file. Renamed from
    `SiennaSimulationParser` in Phase 10 to disambiguate from the v1
    `gat.simulations.sienna.SiennaSimulationParser` (which subclasses
    `BaseSimulationParser`). The legacy name still resolves via a
    module-level `__getattr__` deprecation alias at the bottom of this
    file.

    Reads data from a given Sienna Simulation h5 file.

    Creates timestamps based on attribute data and automatically attaches columns.

    Used as a core class for aggregating across multiple h5 files via
    `gat.simulations.SimulationAggregator(parser_class=...)`.

    Internal Properties:
    ---------------------
    :self.file_path: The path to the h5 file used to initialize the object.

    :self.sim_attr: Attributes under the /simulation path. Used for creating the timestamps.

    :self.uc_attr: Attributes for the /simulation/decision_model/UC path.

    :self.em_attr: Attributes for the /simulation/emulation_model path. Also used in creating the timestamps.
    """

    def __init__(self, simulation_store_path):
        if os.path.isfile(os.path.normpath(simulation_store_path)):
            print(f"{simulation_store_path}")
        else:
            print(f"{simulation_store_path} not found")
            raise FileNotFoundError

        self.file_path = os.path.normpath(simulation_store_path)

        # If properly initialized, generate other properties.
        self.sim_attr = self.get_attributes("/simulation")

        # assume we are only dealing with unit commitment for now
        self.uc_attr = self.get_attributes("/simulation/decision_models/UC")

        # assume emulation model contains what we want
        self.em_attr = self.get_attributes("/simulation/emulation_model")
        pass

    @property
    def timestamps(self) -> pd.DatetimeIndex:
        """
        The timestamps for the emulation model of the simulation file
        """

        try:
            # Timestamps for the Simulation model.
            simulation_start = self.sim_attr["initial_time"].decode()
            step_resolution_ms = self.sim_attr["step_resolution_ms"]
            num_steps = self.sim_attr["num_steps"]

            # TODO might have different resolution between UC and emulation model
            resolution_ms = self.em_attr["resolution_ms"]

            periods_per_step = step_resolution_ms / resolution_ms

            num_periods = int(periods_per_step * num_steps)
            raw_index = pd.date_range(
                start=simulation_start, freq=f"{resolution_ms}ms", periods=num_periods
            )
            inferred_index = pd.date_range(
                start=simulation_start,
                freq=raw_index.inferred_freq,
                periods=num_periods,
            )
            return inferred_index
        except Exception as e:
            print(f"An exception has occured while creating timestampes: {e}")

    def get_attributes(self, key) -> Union[dict, None]:
        """
        reads the attribute metadata of a given certain key.

        :param key: The dataset name to read.

        """

        try:
            with h5py.File(
                self.file_path, "r", driver="core", backing_store=False
            ) as h5data:
                metadata = h5data[key].attrs

                keys = metadata.items()

                meta_dict = {val[0]: val[1] for val in keys}
                return meta_dict
        except ValueError as e:
            if "Unknown driver" in str(e):
                print("Core driver is not available, using default")
                with h5py.File(self.file_path, "r") as h5data:
                    metadata = h5data[key].attrs

                    keys = metadata.items()

                    meta_dict = {val[0]: val[1] for val in keys}
                    return meta_dict
            else:
                print(f"An error occured while reading attributes: {e}")
                return None

        except KeyError:
            warnings.warn(f"{key} attribute not found", UserWarning)
            return None
        except FileNotFoundError:
            raise FileNotFoundError
        except Exception as e:
            print(f"An exception occured in get_attributes: {e}")

    def get_dataset(self, key) -> Union[pd.DataFrame, None]:
        """
        creates the dataframe based on dataset alias or h5 path.

        :param key: Creates a dataframe based on a key found in self.list_datasets() or a full h5 path. (e.g. ActivePowerTimeSeriesParameter__RenewableDispatch)

        """

        try:
            datasets = self.list_datasets()
            if key in datasets.keys():
                key = datasets[key]

            with h5py.File(
                self.file_path, "r", driver="core", backing_store=False
            ) as h5data:
                data = h5data[key][:]
                columns = [c.decode() for c in h5data[key + "__columns"]]

            df = pd.DataFrame(data.T, columns=columns, index=self.timestamps)

            df.index.name = "DATETIME"
            return df
        except ValueError as e:
            if "Unknown driver" in str(e):
                print("Core driver is not available, using default")
                with h5py.File(self.file_path, "r") as h5data:
                    data = h5data[key][:]
                    columns = [c.decode() for c in h5data[key + "__columns"]]

                df = pd.DataFrame(data.T, columns=columns, index=self.timestamps)

                df.index.name = "DATETIME"
                return df
            else:
                print(f"An error occured while reading attributes: {e}")
                return None

        except KeyError:
            warnings.warn(
                f"{key} dataset not found in h5 file, use one of the following datasets"
            )
            print("----- Available Datasets -----", file=sys.stderr)
            for k in self.list_datasets().keys():
                print(k, file=sys.stderr)
            return None

        except FileNotFoundError:
            raise FileNotFoundError

        except Exception as e:
            print(f"An exception has occured in get_attributes: {e}")

    def list_datasets(self) -> dict:
        """
        :returns:
            A dictionary of the dataset names and corresponding h5 paths.
            Ignores the additional "__columns" datasets

        """

        try:
            with h5py.File(self.file_path, "r") as h5data:
                categories = h5data["/simulation/emulation_model"].keys()

                datasets = {}
                for c in categories:
                    subsets = h5data[f"/simulation/emulation_model/{c}"].keys()

                    for s in subsets:
                        if s.endswith("__columns") == False:
                            datasets[s] = f"/simulation/emulation_model/{c}/{s}"
                return datasets
        except Exception as e:
            print(f"An exception has occured in get_attributes: {e}")

    def get_decision_model_base_power(self, model_name: str = "UC") -> Optional[float]:
        """Read base_power from a decision model's h5 group attrs.

        This is the authoritative source of the simulation-side scale factor;
        sys.json's units_settings.base_value can disagree if a simulation was
        run with a different per-unit base than the system was serialized with.
        """
        attrs = self.get_attributes(f"/simulation/decision_models/{model_name}")
        if attrs is None:
            return None
        bp = attrs.get("base_power")
        return float(bp) if bp is not None else None

    def get_raw_dataset(self, key: str) -> Optional[pd.DataFrame]:
        """Return an h5 dataset as an unscaled DataFrame.

        Accepts either a short alias (matched against ``list_datasets()``) or a
        full h5 path (e.g.
        ``/simulation/decision_models/UC/variables/ActivePowerVariable__ThermalStandard``).
        No base_power scaling is applied — values are exactly what's on disk.
        Use the high-level ``get_*`` methods on ``SiennaScenario`` if you want
        scaled (MW) values.
        """
        return self.get_dataset(key)


class SiennaSystemParser:
    """
    Sienna System Parser
    ---------------------

    Reads data from a given Sienna JSON file

    :param system_file_path: Path to the Sienna System JSON file

    Internal Properties:
    ---------------------
    :self.system_data: The python object representation of the given JSON file.


    """

    def __init__(self, system_file_path):
        if os.path.isfile(os.path.normpath(system_file_path)) == False:
            raise FileNotFoundError

        self.system_data = {}
        self.data_format_version = None
        try:
            import mmap

            with open(system_file_path, "r+b") as f:
                with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
                    jbytes = mm.read()

                    self.system_data = _loads(jbytes)
                    self.data_format_version = self.system_data["data_format_version"]
        except Exception as e:
            print("Failed to parse json system file")
            print(e)
            # TODO Should check to see what types of errors there are when parsing json.
            raise ValueError

        pass

    def list_components(self) -> Union[set, None]:
        """
        List all unique component types in the system.

        Returns:
            Set of component type names (e.g., 'ThermalStandard', 'ACBus', 'Line')
        """
        return {
            c["__metadata__"]["type"] for c in self.system_data["data"]["components"]
        }

    def get_component(
        self, component_type: str, expand_ext: bool = True
    ) -> Union[pd.DataFrame, None]:
        """
        Get component data for a given component type.

        Args:
            component_type: Component type name (must be in list_components())
            expand_ext: If True, expand 'ext' field into separate columns

        Returns:
            DataFrame with component data indexed by UUID, or None if not found
        """
        try:
            components = [
                c
                for c in self.system_data["data"]["components"]
                if c["__metadata__"]["type"] == component_type
            ]
            component_df = pd.DataFrame.from_records(components)
            component_df["UUID"] = component_df["internal"].apply(
                lambda x: x["uuid"]["value"]
            )
            component_df.set_index("UUID", inplace=True)

            if expand_ext and "ext" in component_df.columns:
                all_ext = {}
                for ext_val in component_df["ext"].values:
                    all_ext.update(ext_val)

                for k in all_ext.keys():
                    if k in component_df.columns:
                        component_df[f"ext_{k}"] = component_df["ext"].apply(
                            lambda x: x.get(k, None)
                        )
                    else:
                        component_df[k] = component_df["ext"].apply(
                            lambda x: x.get(k, None)
                        )

            return component_df
        except KeyError:
            message = (
                f"{component_type} was not found. Use one of the following components"
            )
            warnings.warn(message, UserWarning)
            logger.debug("Available components: {}", sorted(self.list_components()))
            return None
        except Exception as e:
            print(f"An unhandled exception has occurred in get_component: {e}")
            raise

    # Legacy API compatibility
    def list_component_types(self) -> Union[set, None]:
        """Deprecated: Use list_components() instead."""
        warnings.warn(
            "list_component_types() is deprecated, use list_components()",
            DeprecationWarning,
        )
        return self.list_components()

    def get_component_data(
        self, component_type, expand_ext=True
    ) -> Union[pd.DataFrame, None]:
        """Deprecated: Use get_component() instead."""
        warnings.warn(
            "get_component_data() is deprecated, use get_component()",
            DeprecationWarning,
        )
        return self.get_component(component_type, expand_ext)

    def get_component_bus_relation(
        self, component_type, index_column="name", value_col="bus"
    ) -> Union[dict, None]:
        """
        Get the bus relationship for components of a given type.

        Args:
            component_type: Component type name
            index_column: Column to use as the key in the returned dict
            value_col: Column to use as the value in the returned dict

        Returns:
            Dictionary mapping component names to bus UUIDs
        """
        try:
            component_df = self.get_component(component_type)

            if component_df is None:
                return None
            elif type(component_df) == pd.DataFrame and value_col == "bus":
                # Extract the bus UUID from the series.
                component_node_map = (
                    component_df.reset_index()
                    .set_index(index_column)["bus"]
                    .apply(lambda x: x["value"])
                    .to_dict()
                )
                return {str(k): str(v) for k, v in component_node_map.items()}
            elif type(component_df) == pd.DataFrame:
                component_node_map = (
                    component_df.reset_index()
                    .set_index(index_column)[value_col]
                    .to_dict()
                )
                return {str(k): str(v) for k, v in component_node_map.items()}
            else:
                print(f"no bus relationship found for component {component_type}")
                return None
        except KeyError:
            warnings.warn(
                f"{component_type} was not found in the list of components. Use one of the following",
                UserWarning,
            )
            logger.debug("Available components: {}", sorted(self.list_components()))
            return None
        except Exception as e:
            print(
                f"An unhandled exception has occured in get_component_bus_relation(): {e}"
            )
            raise

    def get_bus_area_relation(
        self, key_value: Optional[str] = None, area_column: Optional[str] = "area"
    ) -> Union[dict, None]:
        """
        Get the area relationship for buses.

        Args:
            key_value: Column name in ACBus to use as lookup key
            area_column: Column name containing area information

        Returns:
            Dictionary mapping bus identifiers to area names
        """
        try:
            ac_bus = self.get_component("ACBus")

            if area_column is None:
                ac_bus["area_uuid"] = ac_bus["area"].apply(
                    lambda x: x["value"] if x is not None else None
                )

                area_df = self.get_component("Area")

                if area_df is not None and ac_bus is not None:
                    if key_value is not None:
                        ac_bus = ac_bus.reset_index().set_index(key_value)

                    bus_area_df = pd.merge(
                        area_df[["name"]],
                        ac_bus[["area_uuid"]],
                        left_index=True,
                        right_on="area_uuid",
                    )

                    return bus_area_df["name"].to_dict()
                else:
                    warnings.warn(
                        "Failed to create bus->area relationship. Some Features may not be available",
                        RuntimeWarning,
                    )
                    return None
            elif area_column in ac_bus.columns:
                return ac_bus[area_column].to_dict()
            else:
                raise KeyError(f"Column '{area_column}' not found in ACBus dataframe")

        except KeyError as e:
            # Re-raise the KeyError to allow proper error handling in the caller
            warnings.warn(str(e))
            raise

        except Exception as e:
            warnings.warn(
                f"an error has occured in get_bus_area_relation: {e}", RuntimeWarning
            )
            return None

    def _get_component_geo(self) -> gpd.GeoDataFrame:
        import geopandas as gpd

        from gat.datahelpers.geo import convert_to_geonode

        attr_associations = pd.DataFrame.from_records(
            self.system_data["data"]["supplemental_attribute_manager"]["associations"]
        )

        geo_raw = pd.DataFrame.from_records(
            self.system_data["data"]["supplemental_attribute_manager"]["attributes"]
        )

        # Drop attributes that don't carry a geo_json payload — Sienna
        # systems often mix geographic and non-geographic supplemental
        # attributes (rpan/sys.json has ~200 of these out of ~6800), and
        # the lambdas below assume `x` is a dict. Without this filter,
        # the first None blows up the entire bus-coords pipeline and the
        # caller silently ends up with an empty bus_coordinates table.
        geo_raw = geo_raw[geo_raw["geo_json"].notna()].reset_index(drop=True)

        geo_raw["attribute_uuid"] = geo_raw["internal"].apply(
            lambda x: x["uuid"]["value"]
        )
        geo_raw["Latitude"] = geo_raw["geo_json"].apply(lambda x: x["Latitude"])
        geo_raw["Longitude"] = geo_raw["geo_json"].apply(lambda x: x["Longitude"])

        geo_raw["component_uuid"] = geo_raw["attribute_uuid"].map(
            attr_associations.set_index("attribute_uuid")["component_uuid"].to_dict()
        )

        node_geo = geo_raw[
            ["attribute_uuid", "component_uuid", "Latitude", "Longitude"]
        ].copy()

        node_geo = convert_to_geonode(node_geo)
        return node_geo

    def _get_bus_geo(self) -> gpd.GeoDataFrame:
        node_geo = self._get_component_geo()

        bus = self.get_component("ACBus").reset_index()
        bus_geo = pd.merge(node_geo, bus, left_on="component_uuid", right_on="UUID")
        bus_geo = gpd.GeoDataFrame(bus_geo)
        return bus_geo

    def _get_arc_geo(self) -> gpd.GeoDataFrame:
        from shapely import LineString

        node_geo = self._get_component_geo()

        arc_geo_raw = self.get_component("Arc").reset_index()
        arc_geo_raw["to_uuid"] = arc_geo_raw["to"].apply(lambda x: x["value"])
        arc_geo_raw["from_uuid"] = arc_geo_raw["from"].apply(lambda x: x["value"])

        arc_geo = pd.merge(
            arc_geo_raw[["UUID", "from_uuid", "to_uuid"]],
            node_geo[["component_uuid", "geometry"]],
            left_on="from_uuid",
            right_on="component_uuid",
        ).merge(
            node_geo[["component_uuid", "geometry"]],
            left_on="to_uuid",
            right_on="component_uuid",
            suffixes=["_from", "_to"],
        )

        arc_geo["geometry"] = arc_geo.apply(
            lambda row: LineString([row["geometry_from"], row["geometry_to"]]), axis=1
        )

        arc_geo = gpd.GeoDataFrame(arc_geo)

        return arc_geo

    def get_component_geo(self, component_types: Union[str, List[str]]):
        # allow for looking at multiple components

        # If component has ARC relationship, use arc
        # try looking in supplemental attributes first, if not available, look in extended attributes in ACBus (Extended attributes automatically un-nested)

        # if lat/lon found for ACBus, get

        # if all else fails, return NotImplemented or None.

        attribute_gdf = self._get_component_geo()[["component_uuid", "geometry"]]

        geom_map = attribute_gdf.set_index("component_uuid")["geometry"].to_dict()
        frames = []
        for c in component_types:
            if c in self.list_components():
                c_bus = self.get_component_bus_relation(c)

                cdf = self.get_component(c)
                cdf["BUS_UUID"] = cdf["name"].map(c_bus)

                # Map any components that have GIS info tied to the bus id
                c_gdf_bus = pd.merge(
                    cdf.reset_index(),
                    attribute_gdf,
                    left_on="BUS_UUID",
                    right_on="component_uuid",
                    how="left",
                )

                # Create a copy of the original dataframe to use for the second merge
                # This ensures we only process components that weren't successfully mapped in the first merge
                remaining_cdf = None

                # Filter out components that were successfully mapped (have non-null geometry)
                if len(c_gdf_bus) > 0:
                    # Get components that were successfully mapped
                    mapped_uuids = c_gdf_bus[~c_gdf_bus["geometry"].isna()][
                        "UUID"
                    ].tolist()

                    # Create dataframe of components that still need mapping
                    remaining_cdf = cdf[~cdf.index.isin(mapped_uuids)]
                else:
                    remaining_cdf = cdf

                # Map any remaining components that have GIS info tied to component UUID
                c_gdf_component = pd.merge(
                    remaining_cdf.reset_index(),
                    attribute_gdf,
                    left_on="UUID",
                    right_on="component_uuid",
                    how="left",
                )

                # Combine both mapping results

                c_gdf = pd.concat(
                    [df for df in [c_gdf_bus, c_gdf_component] if len(df) > 0]
                )
                if c_gdf.empty == False:
                    frames.append(c_gdf)

        all_gdf = pd.concat(frames)

        all_gdf = all_gdf.drop(
            columns=["component_uuid", "BUS_UUID", "UUID"], errors="ignore"
        )

        return gpd.GeoDataFrame(all_gdf)


# ----------------------------------------------------------------------------
# Deprecation alias: SiennaSimulationParser → SiennaH5Parser
#
# The v0 parser was renamed in Phase 10 to disambiguate from the v1
# `gat.simulations.sienna.SiennaSimulationParser` (which subclasses
# `BaseSimulationParser`). External callers using the old import still work
# but get a DeprecationWarning pointing at the new name.
# ----------------------------------------------------------------------------


def __getattr__(name):
    if name == "SiennaSimulationParser":
        import warnings as _w

        _w.warn(
            "gat.datahelpers.sienna.SiennaSimulationParser is renamed to "
            "SiennaH5Parser. The old name still resolves but will be removed "
            "in a future release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return SiennaH5Parser
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
