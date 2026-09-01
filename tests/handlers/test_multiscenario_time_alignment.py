"""Regression tests for MultiScenario._concat_gat_df's misaligned-time-range
warning (issue #22) -- pd.concat(axis=1) silently unions differing scenario
indexes, introducing NaN rows for whichever scenario doesn't cover a given
timestamp. These tests use lightweight fake scenario objects rather than
real fixtures, since only the alignment logic itself is under test.
"""

import warnings

import pandas as pd
import pytest

from gat.scenariohandlers.multi import MultiScenario


class _FakeScenario:
    def __init__(self, df: pd.DataFrame):
        self._df = df

    def get_load(self):
        return self._df

    def get_generation_capacity(self):
        return self._df


def _hourly_frame(start: str, periods: int) -> pd.DataFrame:
    idx = pd.date_range(start, periods=periods, freq="h")
    return pd.DataFrame({"Load": range(periods)}, index=idx)


class TestMultiScenarioTimeAlignment:
    def test_warns_when_scenario_date_ranges_dont_overlap(self):
        ms = MultiScenario(
            {
                "A": _FakeScenario(_hourly_frame("2030-01-01", 24)),
                "B": _FakeScenario(_hourly_frame("2030-01-02", 24)),
            }
        )
        with pytest.warns(UserWarning, match="misaligned time ranges"):
            result = ms._concat_gat_df("get_load")
        assert len(result) == 48

    def test_no_warning_when_scenarios_share_the_same_index(self):
        ms = MultiScenario(
            {
                "A": _FakeScenario(_hourly_frame("2030-01-01", 24)),
                "B": _FakeScenario(_hourly_frame("2030-01-01", 24)),
            }
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            result = ms._concat_gat_df("get_load")
        assert len(result) == 24

    def test_no_alignment_check_for_generation_capacity(self):
        # get_generation_capacity isn't a timeseries -- indexed by Area, not
        # Timestamp -- so differing indexes there are expected, not a bug.
        ms = MultiScenario(
            {
                "A": _FakeScenario(pd.DataFrame({"Coal": [1]}, index=["Area1"])),
                "B": _FakeScenario(
                    pd.DataFrame({"Coal": [1, 2]}, index=["Area1", "Area2"])
                ),
            }
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ms._concat_gat_df("get_generation_capacity")
