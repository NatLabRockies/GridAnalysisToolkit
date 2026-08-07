"""Regression test for SimulationAggregator's additive parser_kwargs
constructor param -- future-proofs the aggregator for a parser class whose
constructor needs more than a bare path (e.g. a PLEXOS-shaped
force_convert kwarg), without changing behavior for existing callers that
never pass it.
"""

from gat.simulations.base import BaseSimulationParser
from gat.simulations.generic_aggregator import SimulationAggregator


class _FakeParser(BaseSimulationParser):
    def __init__(self, file_path, tag="default"):
        super().__init__()
        self.file_path = file_path
        self.tag = tag

    @property
    def simulation_models(self):
        return ["UC"]

    def list_raw_datasets(self):
        return {"load": "load"}

    def get_raw_dataset(self, key):
        return None


def _touch(tmp_path, name):
    p = tmp_path / name
    p.write_text("")
    return p


def test_parser_kwargs_forwarded_sequential(tmp_path):
    files = [_touch(tmp_path, "a.h5"), _touch(tmp_path, "b.h5")]
    agg = SimulationAggregator(
        file_paths=files,
        parser_class=_FakeParser,
        parallel=False,
        parser_kwargs={"tag": "custom"},
    )
    assert all(p.tag == "custom" for p in agg.parsers)


def test_parser_kwargs_default_empty_dict(tmp_path):
    files = [_touch(tmp_path, "a.h5")]
    agg = SimulationAggregator(
        file_paths=files, parser_class=_FakeParser, parallel=False
    )
    assert agg.parser_kwargs == {}
    assert agg.parsers[0].tag == "default"
