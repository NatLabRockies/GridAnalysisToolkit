from .base import BaseScenario, load_map
import pandas as pd
import json
import os
from gat.scenariohandlers.config_maps import sienna_standard_map

class FileScenario(BaseScenario):



    def __init__(self, simulation_files=None, gen_area_map=None, load_area_map=None, line_rating_map=None,
                 # Deprecated alias — use simulation_files instead
                 solution_data=None) -> None:
        from .base import _resolve_simulation_files
        from ._deprecation import warn_legacy_handler
        warn_legacy_handler(self)

        simulation_files = _resolve_simulation_files(simulation_files, solution_data)

        self._tech_simple = sienna_standard_map

        self._solution_data = simulation_files
        self._sienna_metadata = load_map(os.path.join(simulation_files, "metadata.json"))
        self._metadata = self._sienna_metadata
        self._gat_metadata = self.load_gat_metadata()
        if self._gat_metadata:
            self._metadata = self._metadata | self._gat_metadata

        super().__init__(simulation_files, tech_map=None, gen_area_map=gen_area_map, load_area_map=load_area_map, line_rating_map=line_rating_map)


        if not gen_area_map:
            if 'Generator_region_mapping' in self._metadata:
                self._gen_area_map = self._metadata['Generator_region_mapping']
                print("using default generator-area map")
            else:
                print("no generator region map detected, methods using get_area* may not be available.")

        if not load_area_map:
            if 'Regions' in self._metadata:
                self._load_area_map = {val:val for val in self._metadata['Regions']}
                print("using default load-area map")
            else:
                print("no load area map detected, methods using get_area* may not be available.")

        self._lines_meta = self._metadata['Lines']

        self._line_rating_map = self.get_line_rating_map()
        self._use_cache = True
        self._load_file = 'nodal_load.pq.gz'

        # gat specific metadata meant for storing aux data outside of simulation data.
        # e.g. locations, extra groupings
        self._aggregation_levels = None # key names in gat_metadata for aggregations
        self._location_columns = None # typically {Latitude: lat, Longitude: lon}

    @property
    def generator_technology_map(self):
        return self._metadata['Generator_fuel_mapping']

    def get_line_rating_map(self):
        line_meta_df = pd.DataFrame.from_dict(self._lines_meta).transpose()
        if 'rate_to' in line_meta_df.columns:
            return pd.DataFrame.from_dict(self._lines_meta).transpose()[['rate','rate_to']].rate.fillna('rate_to').to_dict()
        else:
            return pd.DataFrame.from_dict(self._lines_meta).transpose().rate.to_dict()


    def load_gat_metadata(self):
        gat_meta_path = os.path.normpath(f'{self._solution_data}/gat_metadata.json')
        if os.path.exists(gat_meta_path):
            print("loading gat metadata")
            self._gat_metadata = load_map(gat_meta_path)
            self._metadata = self._metadata | self._gat_metadata
        else:
            self._gat_metadata = None
            print("gat metadata not available, using default simulation data")



    def save_gat_metadata(self, meta: dict):
        """This json file contains metadata pulled together from outside the
            simulation process. It is contained in a seperate file so we don't
            overwrite the default metadata.
        """
        with open(f'{self._solution_data}/gat_metadata.json','w') as f:
            json.dump(meta, f, indent=4)

        self._gat_metadata = meta
        self._metadata = self._metadata | meta

    def list_aggregation_levels(self):
        if 'aggregation_levels' in self._metadata.keys():
            return self._metadata['aggregation_levels']
        else:
            print("aggregation_levels not set, this might be an issue with your gat_metadata generation")


    def set_aggregation_level(self, level: str):
        if level in self._metadata['aggregation_levels']:
            print(f"setting aggregation level to {level}")
            self._gen_area_map = {k:v[level] for k,v in self._metadata['generator_area_maps'].items()}
            self._load_area_map = {k:v[level] for k,v in self._metadata['load_area_maps'].items()}
            # create new gen_id -> area map
            # create new load_id -> area map
        else:
            print(f"aggregation level {level} not found, try a value in list_aggregation_levels()")

    def get_generation(self):

        df = pd.read_parquet(f"{self._solution_data}/generation_actual.pq.gz")
        # keep columns that start with generator and also in tech map
        columns_to_keep = [val for val in df.columns if  val in self._tech_map.keys()]
        return df[columns_to_keep]

    def get_availability(self):

        df = pd.read_parquet(f"{self._solution_data}/generation_availability.pq.gz")

        columns_to_keep = [val for val in df.columns if val in self._tech_map.keys()]

        return df[columns_to_keep]

    def get_load(self):
        df = pd.read_parquet(f"{self._solution_data}/{self._load_file}")
        if self._load_file == 'nodal_load.pq.gz':
            df = df*-1.0
        return df

    def get_unserved(self):
        return NotImplemented

    def get_generation_capacity(self):

        df = pd.read_parquet(os.path.join(self._solution_data, 'installed_capacity.pq.gz')).T
        df['Technology'] = df.index.map(self._tech_map).map(self._tech_simple)
        return df.groupby("Technology").sum().T

    def get_storage_charging(self):

        df = pd.read_parquet(os.path.join(self._solution_data, 'store_actual.pq.gz'))

        return df

    def get_line_flow(self):
        df = pd.read_parquet(f"{self._solution_data}/power_flow_actual.pq.gz")

        hvdc_file = 'power_flow_actual_HVDC.pq.gz'
        if hvdc_file in os.listdir(self._solution_data):
            hvdc_df = pd.read_parquet(os.path.join(self._solution_data, hvdc_file))
            return df.merge(hvdc_df, left_index=True, right_index=True)
        else:
            return df

    def get_production_cost(self):
        return NotImplemented
