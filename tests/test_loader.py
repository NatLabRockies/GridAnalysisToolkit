"""
Tests for gat.loader module.

Tests the load() function and related convenience functions for loading
projects, scenarios, and palettes with smart defaults.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from gat.loader import load, load_palette_only, load_scenario_only


class TestLoad:
    """Tests for the main load() function."""

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.load_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_with_all_defaults(
        self, mock_manager_class, mock_load_ref, mock_get_default
    ):
        """Test loading with all default values."""
        # Setup mocks
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_config.default_scenario = "test-scenario"
        mock_config.default_palette = "test-palette"
        mock_manager.load_config.return_value = mock_config

        mock_manager.list_scenarios.return_value = ["test-scenario"]
        mock_manager.list_palettes.return_value = ["test-palette"]

        mock_scenario_config = Mock()
        mock_scenario_config.type = "sienna"
        mock_scenario_config.default_palette = None
        mock_scenario_config.get_simulation_paths_list.return_value = ["/test/sim.h5"]
        mock_scenario_config.system_path = "/test/system.json"
        mock_scenario_config.metadata_path = None
        mock_manager.load_scenario.return_value = mock_scenario_config

        mock_palette = Mock()
        mock_manager.load_palette.return_value = mock_palette

        # Execute
        with patch("gat.loader.SiennaScenario") as mock_sienna:
            mock_scenario = Mock()
            mock_sienna.return_value = mock_scenario

            scenario, palette, project = load(verbose=False)

            # Verify
            assert scenario == mock_scenario
            assert palette == mock_palette
            assert project == mock_manager

            mock_get_default.assert_called_once()
            mock_manager.load_scenario.assert_called_once_with("test-scenario")
            mock_manager.load_palette.assert_called_once_with("test-palette")

    @patch("gat.loader.load_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_with_explicit_project(self, mock_manager_class, mock_load_ref):
        """Test loading with explicitly specified project."""
        # Setup mocks
        mock_project_ref = Mock()
        mock_project_ref.project_id = "explicit-project"
        mock_project_ref.name = "Explicit Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/explicit/project")
        mock_load_ref.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_config.default_scenario = "scenario1"
        mock_config.default_palette = None
        mock_manager.load_config.return_value = mock_config

        mock_manager.list_scenarios.return_value = ["scenario1", "scenario2"]
        mock_manager.list_palettes.return_value = []

        mock_scenario_config = Mock()
        mock_scenario_config.type = "reeds"
        mock_scenario_config.default_palette = None
        mock_scenario_config.path = "/reeds/path"
        mock_scenario_config.solve_year = 2035
        mock_manager.load_scenario.return_value = mock_scenario_config

        # Execute
        with patch("gat.loader.ReEDsScenario") as mock_reeds:
            mock_scenario = Mock()
            mock_reeds.return_value = mock_scenario

            scenario, palette, project = load(project="explicit-project", verbose=False)

            # Verify
            mock_load_ref.assert_called_once_with("explicit-project")
            assert scenario == mock_scenario
            assert palette is None  # No palettes available
            assert project == mock_manager

    @patch("gat.loader.get_default_project_ref")
    def test_load_no_default_project_raises_error(self, mock_get_default):
        """Test that load() raises error when no default project and none specified."""
        mock_get_default.return_value = None

        with patch("gat.loader.list_project_refs", return_value=[]):
            with pytest.raises(ValueError, match="No projects found"):
                load(verbose=False)

    @patch("gat.loader.get_default_project_ref")
    def test_load_no_default_project_shows_available(self, mock_get_default):
        """Test that error message shows available projects."""
        mock_get_default.return_value = None

        mock_proj1 = Mock()
        mock_proj1.project_id = "proj1"
        mock_proj2 = Mock()
        mock_proj2.project_id = "proj2"

        with patch(
            "gat.loader.list_project_refs", return_value=[mock_proj1, mock_proj2]
        ):
            with pytest.raises(ValueError, match="proj1, proj2"):
                load(verbose=False)

    @patch("gat.loader.load_project_ref")
    def test_load_invalid_project_raises_error(self, mock_load_ref):
        """Test that load() raises error for invalid project."""
        mock_load_ref.return_value = None

        mock_proj = Mock()
        mock_proj.project_id = "valid-project"

        with patch("gat.loader.list_project_refs", return_value=[mock_proj]):
            with pytest.raises(ValueError, match="Project 'invalid' not found"):
                load(project="invalid", verbose=False)

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_no_scenarios_raises_error(self, mock_manager_class, mock_get_default):
        """Test that load() raises error when project has no scenarios."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "empty-project"
        mock_project_ref.name = "Empty Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/empty/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.list_scenarios.return_value = []  # No scenarios

        mock_config = Mock()
        mock_manager.load_config.return_value = mock_config

        with pytest.raises(ValueError, match="has no scenarios"):
            load(verbose=False)

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_scenario_default_palette_precedence(
        self, mock_manager_class, mock_get_default
    ):
        """Test that scenario's default_palette takes precedence over project's."""
        # Setup mocks
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # Project has default palette
        mock_config = Mock()
        mock_config.default_scenario = "scenario1"
        mock_config.default_palette = "project-palette"
        mock_manager.load_config.return_value = mock_config

        mock_manager.list_scenarios.return_value = ["scenario1"]
        mock_manager.list_palettes.return_value = [
            "project-palette",
            "scenario-palette",
        ]

        # Scenario also has default palette - should take precedence
        mock_scenario_config = Mock()
        mock_scenario_config.type = "sienna"
        mock_scenario_config.default_palette = "scenario-palette"
        mock_scenario_config.get_simulation_paths_list.return_value = ["/test/sim.h5"]
        mock_scenario_config.system_path = "/test/system.json"
        mock_scenario_config.metadata_path = None
        mock_manager.load_scenario.return_value = mock_scenario_config

        mock_palette = Mock()
        mock_manager.load_palette.return_value = mock_palette

        # Execute
        with patch("gat.loader.SiennaScenario") as mock_sienna:
            scenario, palette, project = load(verbose=False)

            # Verify scenario palette was used
            mock_manager.load_palette.assert_called_once_with("scenario-palette")

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_uses_first_scenario_when_no_default(
        self, mock_manager_class, mock_get_default
    ):
        """Test that load() uses first available scenario when no default set."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        # No default scenario
        mock_config = Mock()
        mock_config.default_scenario = None
        mock_config.default_palette = None
        mock_manager.load_config.return_value = mock_config

        mock_manager.list_scenarios.return_value = ["first-scenario", "second-scenario"]
        mock_manager.list_palettes.return_value = []

        mock_scenario_config = Mock()
        mock_scenario_config.type = "plexos"
        mock_scenario_config.default_palette = None
        mock_scenario_config.solution_path = "/plexos/solution.xml"
        mock_manager.load_scenario.return_value = mock_scenario_config

        # Execute
        with patch("gat.loader.PlexosScenario") as mock_plexos:
            scenario, palette, project = load(verbose=False)

            # Verify first scenario was loaded
            mock_manager.load_scenario.assert_called_once_with("first-scenario")

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_invalid_scenario_raises_error(
        self, mock_manager_class, mock_get_default
    ):
        """Test that load() raises error for invalid scenario."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_manager.load_config.return_value = mock_config
        mock_manager.list_scenarios.return_value = ["valid-scenario"]

        with pytest.raises(ValueError, match="Scenario 'invalid' not found"):
            load(scenario="invalid", verbose=False)

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_missing_palette_returns_none(
        self, mock_manager_class, mock_get_default
    ):
        """Test that load() returns None for palette if not found."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_config.default_scenario = "scenario1"
        mock_config.default_palette = None
        mock_manager.load_config.return_value = mock_config

        mock_manager.list_scenarios.return_value = ["scenario1"]
        mock_manager.list_palettes.return_value = ["available-palette"]

        mock_scenario_config = Mock()
        mock_scenario_config.type = "sienna"
        mock_scenario_config.default_palette = None
        mock_scenario_config.get_simulation_paths_list.return_value = ["/test/sim.h5"]
        mock_scenario_config.system_path = "/test/system.json"
        mock_scenario_config.metadata_path = None
        mock_manager.load_scenario.return_value = mock_scenario_config

        # Execute with non-existent palette
        with patch("gat.loader.SiennaScenario"):
            scenario, palette, project = load(palette="nonexistent", verbose=False)

            # Verify palette is None
            assert palette is None


class TestLoadScenarioOnly:
    """Tests for load_scenario_only() convenience function."""

    @patch("gat.loader.load")
    def test_load_scenario_only(self, mock_load):
        """Test that load_scenario_only() calls load() and returns only scenario."""
        mock_scenario = Mock()
        mock_palette = Mock()
        mock_project = Mock()
        mock_load.return_value = (mock_scenario, mock_palette, mock_project)

        result = load_scenario_only(
            project="test-project", scenario="test-scenario", verbose=False
        )

        assert result == mock_scenario
        mock_load.assert_called_once_with(
            project="test-project",
            scenario="test-scenario",
            palette=None,
            verbose=False,
        )


class TestLoadPaletteOnly:
    """Tests for load_palette_only() convenience function."""

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_palette_only_with_default(self, mock_manager_class, mock_get_default):
        """Test loading palette with default project."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_config.default_palette = "default-palette"
        mock_manager.load_config.return_value = mock_config

        mock_manager.list_palettes.return_value = ["default-palette", "other-palette"]

        mock_palette = Mock()
        mock_manager.load_palette.return_value = mock_palette

        result = load_palette_only(verbose=False)

        assert result == mock_palette
        mock_manager.load_palette.assert_called_once_with("default-palette")

    @patch("gat.loader.load_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_palette_only_explicit_palette(
        self, mock_manager_class, mock_load_ref
    ):
        """Test loading specific palette."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_load_ref.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_manager.load_config.return_value = mock_config
        mock_manager.list_palettes.return_value = ["palette1", "palette2"]

        mock_palette = Mock()
        mock_manager.load_palette.return_value = mock_palette

        result = load_palette_only(
            project="test-project", palette="palette2", verbose=False
        )

        assert result == mock_palette
        mock_manager.load_palette.assert_called_once_with("palette2")

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_palette_only_no_palettes_raises_error(
        self, mock_manager_class, mock_get_default
    ):
        """Test that load_palette_only() raises error when no palettes exist."""
        mock_project_ref = Mock()
        mock_project_ref.project_id = "test-project"
        mock_project_ref.name = "Test Project"
        mock_project_ref.get_path.return_value = Path("/test/project")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager

        mock_config = Mock()
        mock_manager.load_config.return_value = mock_config
        mock_manager.list_palettes.return_value = []  # No palettes

        with pytest.raises(ValueError, match="has no palettes"):
            load_palette_only(verbose=False)


class TestScenarioTypeHandling:
    """Tests for handling different scenario types."""

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_sienna_scenario(self, mock_manager_class, mock_get_default):
        """Test loading Sienna scenario type."""
        mock_project_ref = Mock()
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_config.return_value = Mock(
            default_scenario="s1", default_palette=None
        )
        mock_manager.list_scenarios.return_value = ["s1"]
        mock_manager.list_palettes.return_value = []

        mock_scenario_config = Mock()
        mock_scenario_config.type = "sienna"
        mock_scenario_config.default_palette = None
        mock_scenario_config.system_path = "/system.json"
        mock_scenario_config.get_simulation_paths_list.return_value = ["/sim.h5"]
        mock_scenario_config.metadata_path = "/metadata.json"
        mock_manager.load_scenario.return_value = mock_scenario_config

        with patch("gat.loader.SiennaScenario") as mock_sienna:
            scenario, _, _ = load(verbose=False)

            mock_sienna.assert_called_once_with(
                simulation_files=["/sim.h5"],
                system_file="/system.json",
                metadata_file="/metadata.json",
            )

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_reeds_scenario(self, mock_manager_class, mock_get_default):
        """Test loading ReEDS scenario type."""
        mock_project_ref = Mock()
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_config.return_value = Mock(
            default_scenario="s1", default_palette=None
        )
        mock_manager.list_scenarios.return_value = ["s1"]
        mock_manager.list_palettes.return_value = []

        mock_scenario_config = Mock()
        mock_scenario_config.type = "reeds"
        mock_scenario_config.default_palette = None
        mock_scenario_config.path = "/reeds/output"
        mock_scenario_config.solve_year = 2035
        mock_manager.load_scenario.return_value = mock_scenario_config

        with patch("gat.loader.ReEDsScenario") as mock_reeds:
            scenario, _, _ = load(verbose=False)

            mock_reeds.assert_called_once_with(path="/reeds/output", solve_year=2035)

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_plexos_scenario(self, mock_manager_class, mock_get_default):
        """Test loading Plexos scenario type."""
        mock_project_ref = Mock()
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_config.return_value = Mock(
            default_scenario="s1", default_palette=None
        )
        mock_manager.list_scenarios.return_value = ["s1"]
        mock_manager.list_palettes.return_value = []

        mock_scenario_config = Mock()
        mock_scenario_config.type = "plexos"
        mock_scenario_config.default_palette = None
        mock_scenario_config.solution_path = "/plexos/solution.xml"
        mock_manager.load_scenario.return_value = mock_scenario_config

        with patch("gat.loader.PlexosScenario") as mock_plexos:
            scenario, _, _ = load(verbose=False)

            mock_plexos.assert_called_once_with(solution_path="/plexos/solution.xml")

    @patch("gat.loader.get_default_project_ref")
    @patch("gat.loader.ProjectManager")
    def test_load_unsupported_scenario_type_raises_error(
        self, mock_manager_class, mock_get_default
    ):
        """Test that unsupported scenario type raises ValueError."""
        mock_project_ref = Mock()
        mock_project_ref.exists.return_value = True
        mock_project_ref.get_path.return_value = Path("/test")
        mock_get_default.return_value = mock_project_ref

        mock_manager = Mock()
        mock_manager_class.return_value = mock_manager
        mock_manager.load_config.return_value = Mock(
            default_scenario="s1", default_palette=None
        )
        mock_manager.list_scenarios.return_value = ["s1"]
        mock_manager.list_palettes.return_value = []

        mock_scenario_config = Mock()
        mock_scenario_config.type = "unknown-type"
        mock_scenario_config.default_palette = None
        mock_manager.load_scenario.return_value = mock_scenario_config

        with pytest.raises(ValueError, match="Unsupported scenario type"):
            load(verbose=False)
