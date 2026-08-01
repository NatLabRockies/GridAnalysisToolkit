from .utils import *
import pandas as pd
import numpy as np
import pytest
from gat.scenariohandlers.compute import *
import time


@pytest.mark.parametrize("handler_type", ["sienna", "plexos"])
def test_loading_calc(handler_type):
    try:

        scenario = get_scenario_handler(handler_type)

        flow = scenario.get_flow()
        line_rating = scenario._line_rating_map

        # get a sample of 100 lines
        flow_sample = flow.T.sample(100).T  # get a sample of 100 lines
        sample_columns = flow_sample.columns

        # calc loading for each transmission line == column
        loading_data_simple = {
            col: 100.0 * abs(flow_sample[col] / line_rating[col])
            for col in flow_sample.columns
        }
        loading_simple = pd.DataFrame(loading_data_simple).astype(np.float32)

        loading_numpy = scenario.get_line_loading()[sample_columns]

        # verify arrays are equal for each value/position.
        print(loading_simple.head())

        assert np.allclose(
            loading_simple.values,
            loading_numpy.values,
            rtol=1e-5,
            atol=1e-8,
            equal_nan=True,
        )

        # assert np.array_equal(loading_simple.values, loading_numpy, equal_nan=True)

    except Exception as e:
        print(e)
        assert False


@pytest.mark.parametrize("handler_type", ["sienna"])
def test_congestion(handler_type):

    scenario = get_scenario_handler(handler_type)
    loading = scenario.get_line_loading()

    s1 = time.perf_counter()
    print(loading.values[0])
    congestion = calc_congestion(loading.values, threshold=90)
    e1 = time.perf_counter()
