"""
Functions for parsing PLEXOS h5 files
to produce generation, availability, load and line flow datasets.

Called in scenario handler concrete classes to generate "raw" dataframes.

@author: Micah Webb
"""

import pandas as pd
import os
from glob import iglob
import h5py
from .parsers import *


class PlexosParser:

    def __init__(self, solution_dir=None, solution_files=None) -> None:

        self._solution_dir = solution_dir
        self._files = solution_files

        if self._files == None:
            if os.path.isdir(self._solution_dir):

                self._files = iglob(self._solution_dir)
        else:
            # check that everything is a file

            for file in self._files:
                if os.path.isfile(file) == False:
                    print(f"path does not exist {file}")

        pass

    def list_keys(self, h5path: str):
        template_file = self._files[0]
        with h5py.File(template_file) as h5data:
            return [key for key in h5data[h5path].keys()]

    def list_groups(self, schedule="ST", freq="interval"):
        h5path = f"/data/{schedule}/{freq}"
        return self.list_keys(h5path)

    def list_datasets(self, schedule, freq, group):
        h5path = f"/data/{schedule}/{freq}/{group}"

        return self.list_keys(h5path)

    def get_metadata(self, h5_path, reverse=False):

        map = parse_h5_map(self._files[0], h5_path, reverse=reverse)
        return map

    def list_metadata(self, group):
        raise NotImplementedError()

    def get_h5dataset(self, schedule, freq, group, dataset, template=False):
        """
        aggregates a specific h5 dataset across multiple h5 files
        """

        if template:
            result = extract_h5_data(self._files[0], schedule, freq, group, dataset)
        else:
            result = agg_plexos_parallel(
                self._files, schedule, freq, group, datasets=[dataset]
            )

        result = result.droplevel(level="dataset")
        result.columns = [decode_value(col) for col in result.columns]
        return result

    def get_h5group(self, schedule, freq, group, datasets=[], plexos_format=True):
        """
        Combines datasets from a group for all h5 files into a single dataframe. Each column represents
        an h5 dataset with the units appended in ().

        Expects The following
        Plexos Schedule (ST, MT, LT)
        Frequency - interval or day
        Group - The h5 group of the data you want to extract

        """

        result = agg_plexos_parallel(self._files, schedule, freq, group, datasets)
        if plexos_format:
            df_new = result.unstack(level="dataset").stack(level="DateTime")
            return df_new
        else:
            return result


class SiennaSimulationParser:

    def __init__(self, solution_dir=None, solution_files=None) -> None:

        self._solution_dir = solution_dir
        self._files = solution_files

        if self._files == None:
            if os.path.isdir(self._solution_dir):

                self._files = iglob(self._solution_dir)
        else:
            # check that everything is a file

            for file in self._files:
                if os.path.isfile(file) == False:
                    print(f"path does not exist {file}")

        pass

    def get_values(self):

        read_h5_data()
