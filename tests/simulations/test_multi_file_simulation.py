"""Unit tests for BaseSimulation.from_paths and its default fallback,
MultiFileSimulation.

Uses a minimal fake BaseSimulation rather than a real format's parser --
only the default-orchestration mechanism itself is under test here.
"""

import pandas as pd
import pytest

from gat.datasets import DatasetInfo, DatasetKind
from gat.interfaces import BaseSimulation
from gat.simulations.multi_file import MultiFileSimulation


class _FakeSimulation(BaseSimulation):
    """One instance per path; each path maps to a fixed hourly frame."""

    _DATA = {
        "a": pd.date_range("2030-01-01", periods=24, freq="h"),
        "b": pd.date_range("2030-01-03", periods=24, freq="h"),
        "c": pd.date_range("2030-01-05", periods=24, freq="h"),
    }

    def __init__(self, path, scale=1):
        self.path = path
        self.scale = scale

    def list_datasets(self):
        return [
            DatasetInfo(
                name="load",
                description="d",
                kind=DatasetKind.RAW_SIMULATION,
                entity_column="e",
            )
        ]

    def get_dataset(self, name):
        idx = self._DATA[self.path]
        return pd.DataFrame({"v": [self.scale] * len(idx)}, index=idx)

    def get_default_category_maps(self):
        return [f"category-map-from-{self.path}"]

    def get_default_compositions(self):
        return [f"composition-from-{self.path}"]


def test_single_path_returns_bare_instance_not_wrapped():
    result = _FakeSimulation.from_paths("a")
    assert isinstance(result, _FakeSimulation)
    assert not isinstance(result, MultiFileSimulation)


def test_multi_path_returns_multi_file_simulation():
    result = _FakeSimulation.from_paths(["a", "b"])
    assert isinstance(result, MultiFileSimulation)


def test_kwargs_forwarded_to_every_instance():
    result = _FakeSimulation.from_paths(["a", "b"], scale=5)
    combined = result.get_dataset("load")
    assert (combined["v"] == 5).all()


def test_list_datasets_unions_by_name():
    result = _FakeSimulation.from_paths(["a", "b"])
    names = [d.name for d in result.list_datasets()]
    assert names == ["load"]


def test_get_dataset_combines_via_combine_overlapping_frames():
    result = _FakeSimulation.from_paths(["a", "b", "c"])
    combined = result.get_dataset("load")
    assert len(combined) == 72
    assert combined.index.min() == pd.Timestamp("2030-01-01")
    assert combined.index.max() == pd.Timestamp("2030-01-05 23:00:00")
    assert combined.index.is_monotonic_increasing


def test_category_maps_and_compositions_come_from_first_instance():
    result = _FakeSimulation.from_paths(["a", "b"])
    assert result.get_default_category_maps() == ["category-map-from-a"]
    assert result.get_default_compositions() == ["composition-from-a"]


def test_empty_path_list_raises():
    with pytest.raises(ValueError):
        MultiFileSimulation(_FakeSimulation, [])
