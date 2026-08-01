"""
EGRET - Scenario Object for interfacing with EGRET JSON system and simulation data.

@author: Micah Webb
"""

from .base import egret_map_simple, load_map, BaseScenario
import glob
import json
import pandas as pd


class EGRETScenario(BaseScenario):
    """
    Class for interfacing with EGRET JSON data.

    Parameters:
    ------------
    solution_data: path to solution data.

    Returns:
    ------------
    EGRETScenario

    """

    def __init__(
        self,
        simulation_files=None,
        gen_area_map=None,
        load_area_map=None,
        line_rating_map=None,
        # Deprecated alias — use simulation_files instead
        solution_data=None,
    ) -> None:
        from .base import _resolve_simulation_files

        simulation_files = _resolve_simulation_files(simulation_files, solution_data)

        super().__init__(
            simulation_files,
            tech_map=None,
            gen_area_map=gen_area_map,
            load_area_map=load_area_map,
            line_rating_map=line_rating_map,
        )

        self._solution_data = simulation_files
        self._tech_map = self.get_gen_tech_map()
        self._tech_simple = load_map(egret_map_simple)

    def list_simulation_files(self):
        """
        Returns list of simulation files to parse.
        May need Regex if directory has multiple types of json files.
        """

        return [file for file in glob(f"{self._solution_data}/*.json")]

    def load_egret_file(self, file_path):
        return json.loads(open(file_path, "r").read())

    def get_raw_generators(self):
        """Loops through the json files and aggregates to a generator dataframe"""
        files = self.list_simulation_files()

        frames = []
        for filepath in files:

            egret_obj = json.loads(open(filepath, "r").read())

            df = self.get_generator_dataframe(egret_obj)

            # TODO JSON files might overlap timewindows
            frames.append(df)

        return pd.concat(frames)

    # TODO add availability, load and flow data functions
    def get_raw_availability(self):
        return NotImplemented

    def get_regional_load(self):
        return NotImplemented

    def get_line_flow_data(self):
        return NotImplemented

    def get_raw_production_cost_annual(self):
        return NotImplemented

    def get_generator_dataframe(self, egret_obj):
        """Extracts the generator data from a parsed json file."""
        generators = egret_obj["elements"]["generator"].keys()

        data = {
            gen: egret_obj["elements"]["generator"][gen]["pg"]["values"]
            for gen in generators
        }
        timestamps = egret_obj["system"]["time_keys"]

        df = pd.DataFrame(data, index=pd.to_datetime(timestamps))

        return df

    def get_gen_area_map(self):
        """Loads the generator bus map based on first json file"""
        file_path = self.list_simulation_files()[0]
        egret_obj = self.load_egret_file(file_path)

        # TODO might be beneficial to pass in the area key if you
        # want something besides generator to bus mappings.
        return self.get_generator_map(egret_obj, "bus")

    def get_gen_tech_map(self):
        """Loads the generator egret tech map based on first json file"""
        file_path = self.list_simulation_files()[0]
        egret_obj = self.load_egret_file(file_path)
        return self.get_generator_map(egret_obj, "fuel")

    def get_generator_map(self, egret_obj, gen_key):
        """Creates a Generator - area/Technology map based on loaded json obj."""
        generators = egret_obj["elements"]["generator"]
        return {gen: value[gen_key] for gen, value in generators.items()}
