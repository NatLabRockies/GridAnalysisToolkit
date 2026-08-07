"""Unit tests for SiennaSimulation.from_paths -- specifically that the
across-file merge direction comes from the selected model's own
SiennaModelConfig.merge (via SiennaSimulationParser.merge_strategy)
rather than a hardcoded default, since a UC/decision model and an
emulation model can legitimately want different behavior at a partition
seam.

Uses a mocked SiennaSimulationParser rather than real fixture data --
only the from_paths routing/merge-strategy-selection logic is under test
here; tests/handlers/test_sienna_multifile.py covers the real,
Docker-fixture-based integration path.
"""

from unittest.mock import MagicMock, patch

from gat.simulations.multi_file import MultiFileSimulation
from gat.simulations.sienna_v1 import SiennaSimulation


def _mock_simulation(monkeypatch, merge_strategy):
    """Patch SiennaSimulation's dependencies so construction never touches
    a real file, and the underlying parser reports the given merge
    strategy."""

    def fake_init(self, simulation_path, simulation=None, compositions=None):
        self._parser = MagicMock()
        self._parser.simulation = "Emulator"
        self._parser.merge_strategy = merge_strategy
        self._compositions = {}
        self._raw_datasets = {}
        self._resolved_compositions = {}

    monkeypatch.setattr(SiennaSimulation, "__init__", fake_init)


@patch("gat.simulations.sienna.SiennaSimulationParser")
def test_single_path_bypasses_multi_file_simulation(mock_parser_cls, monkeypatch):
    _mock_simulation(monkeypatch, merge_strategy="right")
    result = SiennaSimulation.from_paths("a.h5")
    assert isinstance(result, SiennaSimulation)
    assert not isinstance(result, MultiFileSimulation)
    mock_parser_cls.assert_not_called()  # no probe needed for a single path


@patch("gat.simulations.sienna.SiennaSimulationParser")
def test_multi_path_uses_probed_merge_strategy(mock_parser_cls, monkeypatch):
    probe = MagicMock()
    probe.merge_strategy = "left"
    mock_parser_cls.return_value = probe

    _mock_simulation(monkeypatch, merge_strategy="left")
    result = SiennaSimulation.from_paths(["a.h5", "b.h5"])

    assert isinstance(result, MultiFileSimulation)
    assert result._merge_strategy == "left"
    mock_parser_cls.assert_called_once_with("a.h5")


@patch("gat.simulations.sienna.SiennaSimulationParser")
def test_multi_path_sets_selected_model_on_probe_when_given(
    mock_parser_cls, monkeypatch
):
    probe = MagicMock()
    probe.merge_strategy = "right"
    mock_parser_cls.return_value = probe

    _mock_simulation(monkeypatch, merge_strategy="right")
    SiennaSimulation.from_paths(["a.h5", "b.h5"], simulation="UC")

    assert probe.selected_model == "UC"


@patch("gat.simulations.sienna.SiennaSimulationParser")
def test_multi_path_falls_back_when_probe_reports_none(mock_parser_cls, monkeypatch):
    probe = MagicMock()
    probe.merge_strategy = None
    mock_parser_cls.return_value = probe

    _mock_simulation(monkeypatch, merge_strategy=None)
    result = SiennaSimulation.from_paths(["a.h5", "b.h5"])

    assert result._merge_strategy == "earlier_wins"
