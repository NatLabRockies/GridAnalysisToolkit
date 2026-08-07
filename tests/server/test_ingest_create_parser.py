"""Regression tests for gat.server.ingest._create_parser's Sienna and
PLEXOS branches.

Sienna: previously did `simulation_paths[0]`, silently dropping every
file after the first for a multi-file (partitioned) scenario. PLEXOS:
previously imported `gat.simulations.plexos`, a module that doesn't
exist -- the branch has always raised ImportError, so no PLEXOS
simulation could ever be constructed via the server ingest path.

Uses mocks throughout -- no real Sienna/PLEXOS files needed, since only
_create_parser's own routing logic is under test here.
"""

from unittest.mock import MagicMock, patch

from gat.server.ingest import _create_parser


@patch("gat.simulations.sienna_v1.SiennaSimulation.from_paths")
@patch("gat.systems.sienna.SiennaSystem")
def test_sienna_multi_file_forwards_every_path(mock_system_cls, mock_from_paths):
    mock_from_paths.return_value = MagicMock()
    paths = ["week1.h5", "week2.h5", "week3.h5"]

    _create_parser("sienna", system_path="system.json", simulation_paths=paths)

    mock_from_paths.assert_called_once_with(paths, simulation=None)


@patch("gat.simulations.sienna_v1.SiennaSimulation.from_paths")
@patch("gat.systems.sienna.SiennaSystem")
def test_sienna_single_file_still_works(mock_system_cls, mock_from_paths):
    mock_from_paths.return_value = MagicMock()

    _create_parser("sienna", system_path="system.json", simulation_paths=["only.h5"])

    mock_from_paths.assert_called_once_with(["only.h5"], simulation=None)


@patch("gat.simulations.sienna_v1.SiennaSimulation.from_paths")
@patch("gat.systems.sienna.SiennaSystem")
def test_sienna_model_forwarded_when_not_default(mock_system_cls, mock_from_paths):
    mock_from_paths.return_value = MagicMock()

    _create_parser(
        "sienna",
        system_path="system.json",
        simulation_paths=["a.h5"],
        model="UC",
    )

    mock_from_paths.assert_called_once_with(["a.h5"], simulation="UC")


@patch("gat.simulations.plexos_duckdb.PlexosDuckDBSimulation.from_paths")
@patch("gat.systems.plexos_duckdb.PlexosDuckDBSystem")
def test_plexos_no_longer_raises_import_error(mock_system_cls, mock_from_paths):
    mock_from_paths.return_value = MagicMock()
    paths = ["a.zip", "b.zip"]

    system, simulation = _create_parser(
        "plexos", system_path=None, simulation_paths=paths
    )

    mock_system_cls.assert_called_once_with(paths)
    mock_from_paths.assert_called_once_with(paths)
