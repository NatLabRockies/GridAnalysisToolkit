"""
Functions for parsing PLEXOS h5 files
to produce generation, availability, load and line flow datasets.

Called in scenario handler concrete classes to generate "raw" dataframes.

@author: Micah Webb
"""

import pandas as pd
import numpy as np
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from glob import iglob
import h5py
from loguru import logger

def decode_value(input):
    t = type(input)
    if t == bytes or t ==np.bytes_:
        return input.decode()
    else:
        return input

def reduce_plexos_input(plexos_data):

    if type(plexos_data) ==str:
        paths = get_plexos_paths(plexos_data)
    elif type(plexos_data) == list:
        paths = plexos_data

    return paths

def combine_frames_skip_prev(frames: pd.DataFrame) -> pd.DataFrame:

    """
    Combine multiple time-indexed dataframes, dropping rows from later
    frames whose timestamps are already present in earlier frames.

    **Semantic context** (relevant if/when this gets unified with the v1
    path):

    - This function implements the **across-file** convention used by
      Plexos: when aggregating multiple solution h5 files, the *earlier*
      file wins at the overlap. The later file's overlapping head is
      dropped on the assumption that those timestamps were already
      solved in the earlier file.
    - Sienna's **within-file** UC/RAUC block dedup follows the same
      "earlier wins" convention. The two paths agree in direction but
      have separate implementations:
      `gat.simulations.utils.dedup_slices` +
      `gat.simulations.generic_aggregator.SimulationAggregator._combine_frames`
      handle within-file blocks (and across-file Sienna aggregation),
      using a `merge_strategy="left"`/`"right"` argument whose names
      describe *which side gets truncated*, not which side wins.

    Steps:
      1. Order dataframes by max(TimeStamp).
      2. For each non-first frame, drop rows whose index is `<=` the
         previous frame's max.
      3. Concatenate (in input list order — see the unit-test note;
         caller is responsible for chronological input).
    """
    frame_dict = {}
    end_dates = []

    for df in frames:

        last_idx = df.index.max()
        end_dates.append(last_idx)
        frame_dict[last_idx] = df

    # Sort the end dates
    end_dates.sort()
    if len(frame_dict) == 1:
        agg_df = frames[0]
    else:
    # Filter each frame to exclude overlapping timestamps
        for i in range(1, len(end_dates)):

            prev_date = end_dates[i-1]
            curr_end = end_dates[i]

            curr_df = frame_dict[curr_end]
            new_df = curr_df[curr_df.index > prev_date]
            frame_dict[curr_end] = new_df

        final_frames = [df for end_date, df in frame_dict.items()]

        agg_df = pd.concat(final_frames)

    return agg_df


def read_h5_data(file_path, key):

    with h5py.File(file_path,'r') as h5data:

        return h5data[key][()]

def extract_h5_group(file_path: str, schedule: str, freq:str, group:str, datasets=None, dtype='float32'):

    """
        Extracts and h5 group of datasets from a single h5 file
        Expects and h5 file that was generated from an xml Plexos Solution
    """

    with h5py.File(file_path, 'r') as h5data:

        # headers are in either metadata/object or metadata/relations
        relations = [key for key in  h5data[f'/metadata/relations'].keys()]

        sub = 'objects'
        if group in relations:
            sub = 'relations'

        headers = h5data[f'/metadata/{sub}/{group}'][()]

        # split relation name, otherwise group name + "category"
        if group in relations:
            header_names = group.split('_')
        else:
            header_names = [group, 'category']

        # get the timestamps
        timestamps = h5data[f'/metadata/times/{freq}'][()]
        timestamps = pd.to_datetime([val.decode() for val in timestamps])

        # check if datasets are available
        if datasets:
            datasets = [key for key in h5data[f'/data/{schedule}/{freq}/{group}'].keys() if key in datasets]
        else:
            datasets = [key for key in h5data[f'/data/{schedule}/{freq}/{group}'].keys()]

        group_data = [] #

        for d in datasets:

            attributes = h5data[f'/data/{schedule}/{freq}/{group}/{d}'].attrs

            units = decode_value(attributes['units'])
            period_offset = attributes['period_offset']

            new_headers = pd.MultiIndex.from_tuples([(f'{d} ({units})', decode_value(r[0]), decode_value(r[1])) for r in headers], names=['dataset']+header_names)

            data = h5data[f'/data/{schedule}/{freq}/{group}/{d}'][()]
            timewindow = timestamps[period_offset:period_offset+data.shape[1]]

            tshape = timewindow.shape
            sdata = data.squeeze()
            sshape = sdata.shape
            # for yearly data, reshape into a dataframe of one value
            if sdata.ndim == 0:
                sdata = [[sdata]]

            if tshape == sshape:
                index = timewindow
                columns = new_headers

                df = pd.DataFrame(sdata, columns=columns, index=index, dtype=dtype)
                df = df.T

            else:
                index = new_headers
                columns = timewindow
                df = pd.DataFrame(sdata, columns=columns, index=index, dtype=dtype)

            group_data.append(df)

            df.columns.name = 'DateTime'


    all_df = pd.concat(group_data)

    return all_df



def extract_h5_data(file_path: str, schedule: str, freq:str, group:str, dataset:str, dtype='float32'):

    """
        Takes a single h5 file and
        extracts a dataset

        This method acts as a base function that provides the underlying datasets
        without much modification /aggregation
    """

    df = extract_h5_group(file_path, schedule, freq, group, datasets=[dataset], dtype=dtype)
    return df


def get_plexos_paths(plexos_dir: str) ->  list:

    files = iglob(f"{plexos_dir}/*.h5")
    file_paths = [os.path.normpath(file) for file in files]
    return file_paths



def agg_plexos_dataset(plexos_data: [list,str], schedule: str, freq:str, group:str, dataset:str):

    """
        Input: directory of h5 files
        Output: dataframe of combined files
    """

    paths = reduce_plexos_input(plexos_data)

    frames = []
    for path in paths:

        df = extract_h5_data(path, schedule, freq, group, dataset)

        frames.append(df)

    if freq =='year':
        agg_df = pd.concat(frames).drop_duplicates()
    else:
        agg_df = combine_frames_skip_prev(frames)


    return agg_df


def agg_plexos_parallel(plexos_data: [list, str], schedule: str, freq: str, group: str, datasets=None,
                        max_workers: int = None) -> pd.DataFrame:
    """Aggregate a plexos h5 dataset across multiple solution files.

    Reads each file's `extract_h5_group(...)` result in parallel using a
    `ProcessPoolExecutor` (each worker independently opens its own h5
    handle, since h5py file handles aren't picklable). Falls back to
    sequential reading if a parallel worker raises.

    The output order matches the order of files in `plexos_data` —
    important for `combine_frames_skip_prev`'s overlap-deduplication
    logic to operate on contiguous time windows.

    Parameters
    ----------
    plexos_data : list[str] | str
        File paths or a directory glob (passed through `reduce_plexos_input`).
    schedule : str
        Plexos schedule (e.g., "ST", "MT", "LT").
    freq : str
        Sample frequency (e.g., "interval", "day").
    group : str
        H5 group under `/data/{schedule}/{freq}/`.
    datasets : list[str] | None
        Specific datasets to extract; None pulls everything in the group.
    max_workers : int | None
        Worker count. None → `os.cpu_count()` (capped to len(paths)).

    Returns
    -------
    pd.DataFrame
        Timestamp-indexed dataframe (one column per dataset/entity) with
        per-file overlapping windows deduplicated.
    """
    paths = reduce_plexos_input(plexos_data)

    if len(paths) <= 1:
        # Single file (or nothing to aggregate) — skip the executor overhead.
        frames = [extract_h5_group(path, schedule, freq, group, datasets) for path in paths]
    else:
        workers = min(max_workers or os.cpu_count() or 1, len(paths))
        # `frames_by_index` preserves source-file order across asynchronous
        # completions — `combine_frames_skip_prev` relies on the time-ordered
        # sequence of files for its skip-overlap logic.
        frames_by_index = [None] * len(paths)
        try:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                future_to_index = {
                    ex.submit(extract_h5_group, path, schedule, freq, group, datasets): i
                    for i, path in enumerate(paths)
                }
                for fut in as_completed(future_to_index):
                    i = future_to_index[fut]
                    frames_by_index[i] = fut.result()
            frames = frames_by_index
        except Exception as e:
            # Fall back to sequential — usually triggered by pickling errors
            # or h5py-version mismatches between worker processes.
            logger.warning(
                "agg_plexos_parallel: parallel read failed ({}); "
                "falling back to sequential.", e,
            )
            frames = [extract_h5_group(path, schedule, freq, group, datasets) for path in paths]

    # transpose the results once finished
    framesT = [df.T for df in frames]

    # merge time windows accordingly (drops overlap from one end of each block)
    agg_df = combine_frames_skip_prev(framesT)

    # return Transposed data (column for each timestamp)
    return agg_df.T



def parse_h5_map(file_path, metadata_path, reverse=False):

    with h5py.File(file_path) as h5data:

        metadata = h5data[metadata_path][()]
    if reverse:
        return {decode_value(val[1]): decode_value(val[0]) for val in metadata}
    else:
        return {decode_value(val[0]): decode_value(val[1]) for val in metadata}


def get_h5_map(file_path, h5_path, reverse=False):
    return parse_h5_map(file_path, h5_path, reverse)


def get_h5_gen_tech_map(file_path):

    return parse_h5_map(file_path, 'metadata/objects/generators')


def get_h5_gen_zone_map(file_path):

    return parse_h5_map(file_path, 'metadata/relations/zones_generators', reverse=True)



def get_h5_gen_region_map(file_path):

    return parse_h5_map(file_path, 'metadata/relations/regions_generators', reverse=True)

def get_h5_region_region_map(file_path):
    # identity map for regional load
    map = parse_h5_map(file_path, 'metadata/objects/regions')
    new_map = {key:key for key in map.keys()}
    return new_map





def get_h5_region_zone_map(file_path):

    gen_zone_map = get_h5_gen_zone_map(file_path)
    gen_region_map = get_h5_gen_region_map(file_path)

    region_zone_map = {}
    for generator, region in gen_region_map.items():

        zone = gen_zone_map[generator]
        region_zone_map[region] = zone

    return region_zone_map

