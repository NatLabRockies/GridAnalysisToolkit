"""
Author: Micah Webb
Email: micah.webb@nlr.gov

"""

import numpy as np
import pandas as pd
from typing import Union


def calc_loading(flow_matrix: np.matrix, line_ratings: np.array, dtype=np.float32):
    """
    Input: matrix of raw flow values, vector of line ratings
    Output: Matrix of loading values as a percent of line rating
    """
    result = np.divide(flow_matrix, line_ratings)
    return np.abs(result * 100.0).astype(dtype)


def calc_congestion(matrix: np.matrix, threshold=100.0):
    """
    Input: matrix of loading values
    Ouput: 1s or 0s, np.int8
    """

    return (matrix >= threshold).astype(np.int8)


def calc_ramp_rate(net_load: Union[pd.Series, pd.DataFrame]) -> pd.Series:
    """
    Accepts a series or dataframe with a datetimeindex, with inferrable frequency.

    returns a series in MW/Min
    Averages if frequency is not in minutes
    """

    # must be a series with a datetime index and

    if type(net_load.index) == pd.core.indexes.datetimes.DatetimeIndex:
        dt_freq = pd.infer_freq(net_load.index)
        if dt_freq:
            minutes_in_period = pd.Timedelta(
                net_load.index[1] - net_load.index[0]
            ) / pd.Timedelta(value=1, unit="m")

            ramp_series = (net_load - net_load.shift(1)) / minutes_in_period

            ramp_series.name = "Ramp (MW/Min)"

            return ramp_series
