# tests/test_scenario_paths.py
"""
Tests for scenario path resolution.

Tests that relative and absolute paths are correctly resolved
when adding scenarios to projects.
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from gat.models.project import SiennaScenarioConfig
from gat.project_management.manager import ProjectManager


@pytest.fixture
def temp_project():
    """Create a temporary project for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Initialize project structure
        (project_path / "scenarios").mkdir()
        (project_path / "palettes").mkdir()
        (project_path / "pipelines").mkdir()
        (project_path / "data").mkdir()

        # Create project config
        config_data = {
            "name": "Test Project",
            "gat_version": "1.0.0",
            "version": "0.1.0",
        }
        with open(project_path / "gat-project.yaml", "w") as f:
            yaml.dump(config_data, f)

        yield project_path


@pytest.fixture
def sample_data_files(temp_project):
    """Create sample data files for testing."""
    data_dir = temp_project / "data"

    # Create dummy system file
    system_file = data_dir / "system.json"
    with open(system_file, "w") as f:
        f.write('{"data": {}, "data_format_version": "3.0.0"}')

    # Create dummy simulation file
    sim_file = data_dir / "results.h5"
    sim_file.touch()

    return {"system": system_file, "simulation": sim_file}


class TestPathResolution:
    """Tests for path resolution in scenario configuration."""

    def test_relative_path_within_project(self, temp_project, sample_data_files):
        """Test that relative paths within project are stored correctly."""
        manager = ProjectManager(temp_project)

        # Add scenario with paths relative to project root
        config = manager.add_scenario(
            scenario_id="test_scenario",
            name="Test Scenario",
            scenario_type="sienna",
            system_path="data/system.json",
            simulation_paths="data/results.h5",
        )

        assert isinstance(config, SiennaScenarioConfig)
        assert config.system_path == "data/system.json"
        assert config.simulation_paths == "data/results.h5"

        # Verify file was saved
        scenario_file = temp_project / "scenarios" / "test_scenario.yaml"
        assert scenario_file.exists()

        # Reload and verify
        loaded_config = manager.load_scenario("test_scenario")
        assert loaded_config.system_path == "data/system.json"
        assert loaded_config.simulation_paths == "data/results.h5"

    def test_absolute_path_resolution(self, temp_project, sample_data_files):
        """Test that absolute paths are handled correctly."""
        manager = ProjectManager(temp_project)

        # Add scenario with absolute paths
        system_abs = str(sample_data_files["system"])
        sim_abs = str(sample_data_files["simulation"])

        config = manager.add_scenario(
            scenario_id="test_abs",
            name="Test Absolute",
            scenario_type="sienna",
            system_path=system_abs,
            simulation_paths=sim_abs,
        )

        # Since paths are within project, they should be stored as relative
        assert config.system_path == "data/system.json"
        assert config.simulation_paths == "data/results.h5"

    def test_multiple_simulation_paths(self, temp_project, sample_data_files):
        """Test handling of multiple simulation files."""
        manager = ProjectManager(temp_project)
        data_dir = temp_project / "data"

        # Create additional simulation files
        sim_file2 = data_dir / "results2.h5"
        sim_file2.touch()

        config = manager.add_scenario(
            scenario_id="test_multi",
            name="Test Multi",
            scenario_type="sienna",
            system_path="data/system.json",
            simulation_paths=["data/results.h5", "data/results2.h5"],
        )

        assert isinstance(config.simulation_paths, list)
        assert len(config.simulation_paths) == 2
        assert "data/results.h5" in config.simulation_paths
        assert "data/results2.h5" in config.simulation_paths

    def test_path_validation(self, temp_project, sample_data_files):
        """Test path validation for existing and missing files."""
        manager = ProjectManager(temp_project)

        # Add scenario with valid paths
        manager.add_scenario(
            scenario_id="test_valid",
            name="Test Valid",
            scenario_type="sienna",
            system_path="data/system.json",
            simulation_paths="data/results.h5",
        )

        # Validate - should have no warnings
        warnings = manager.validate_scenario_paths("test_valid")
        assert len(warnings) == 0

        # Add scenario with invalid path
        manager.add_scenario(
            scenario_id="test_invalid",
            name="Test Invalid",
            scenario_type="sienna",
            system_path="data/nonexistent.json",
            simulation_paths="data/results.h5",
        )

        # Validate - should have warnings
        warnings = manager.validate_scenario_paths("test_invalid")
        assert len(warnings) > 0
        assert any("nonexistent.json" in w for w in warnings)

    def test_path_resolution_with_resolve_path(self, temp_project, sample_data_files):
        """Test ProjectManager.resolve_path method."""
        manager = ProjectManager(temp_project)

        # Test relative path resolution
        rel_path = "data/system.json"
        resolved = manager.resolve_path(rel_path)
        assert resolved == temp_project / "data" / "system.json"
        assert resolved.exists()

        # Test that resolved path is absolute
        assert resolved.is_absolute()

    def test_get_simulation_paths_list(self, temp_project):
        """Test SiennaScenarioConfig.get_simulation_paths_list method."""
        # Test with single path (string)
        config1 = SiennaScenarioConfig(
            name="Test", system_path="system.json", simulation_paths="sim.h5"
        )
        paths1 = config1.get_simulation_paths_list()
        assert isinstance(paths1, list)
        assert len(paths1) == 1
        assert paths1[0] == "sim.h5"

        # Test with multiple paths (list)
        config2 = SiennaScenarioConfig(
            name="Test",
            system_path="system.json",
            simulation_paths=["sim1.h5", "sim2.h5"],
        )
        paths2 = config2.get_simulation_paths_list()
        assert isinstance(paths2, list)
        assert len(paths2) == 2
        assert "sim1.h5" in paths2
        assert "sim2.h5" in paths2


class TestPathEdgeCases:
    """Tests for edge cases in path handling."""

    def test_path_outside_project(self, temp_project):
        """Test handling paths outside project directory."""
        manager = ProjectManager(temp_project)

        # Create file outside project
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            external_file = Path(f.name)
            f.write(b'{"data": {}}')

        try:
            # Add scenario with external path
            config = manager.add_scenario(
                scenario_id="test_external",
                name="Test External",
                scenario_type="sienna",
                system_path=str(external_file),
                simulation_paths="data/results.h5",
            )

            # Path outside project should be stored as absolute
            assert Path(config.system_path).is_absolute()
            assert str(external_file) == config.system_path

        finally:
            external_file.unlink()

    def test_path_with_dots(self, temp_project, sample_data_files):
        """Test paths with .. components."""
        manager = ProjectManager(temp_project)

        # Create subdirectory
        subdir = temp_project / "data" / "subdir"
        subdir.mkdir()

        # Add scenario with .. in path
        config = manager.add_scenario(
            scenario_id="test_dots",
            name="Test Dots",
            scenario_type="sienna",
            system_path="data/subdir/../system.json",
            simulation_paths="data/results.h5",
        )

        # Path should be normalized
        assert ".." not in config.system_path
        assert config.system_path == "data/system.json"

    def test_symlink_resolution(self, temp_project, sample_data_files):
        """Test handling of symlinks."""
        manager = ProjectManager(temp_project)

        # Create symlink to data directory
        link_dir = temp_project / "link_data"
        data_dir = temp_project / "data"

        try:
            link_dir.symlink_to(data_dir)

            # Add scenario using symlink path
            config = manager.add_scenario(
                scenario_id="test_symlink",
                name="Test Symlink",
                scenario_type="sienna",
                system_path="link_data/system.json",
                simulation_paths="link_data/results.h5",
            )

            # Paths should be resolved to real paths
            # (might be link_data or data depending on resolve behavior)
            assert "system.json" in config.system_path
            assert "results.h5" in config.simulation_paths

        except OSError:
            # Symlinks might not be supported on all systems
            pytest.skip("Symlinks not supported on this system")


class TestReEDSAndPlexosPaths:
    """Tests for ReEDS and Plexos path handling."""

    def test_reeds_path_resolution(self, temp_project):
        """Test path resolution for ReEDS scenarios."""
        manager = ProjectManager(temp_project)

        # Create ReEDS output directory
        reeds_dir = temp_project / "data" / "reeds_output"
        reeds_dir.mkdir(parents=True)

        config = manager.add_scenario(
            scenario_id="test_reeds",
            name="Test ReEDS",
            scenario_type="reeds",
            path="data/reeds_output",
            solve_year=2035,
        )

        assert config.path == "data/reeds_output"
        assert config.solve_year == 2035

    def test_plexos_path_resolution(self, temp_project):
        """Test path resolution for Plexos scenarios."""
        manager = ProjectManager(temp_project)

        # Create Plexos solution file
        solution_file = temp_project / "data" / "solution.zip"
        solution_file.touch()

        config = manager.add_scenario(
            scenario_id="test_plexos",
            name="Test Plexos",
            scenario_type="plexos",
            solution_path="data/solution.zip",
        )

        assert config.solution_path == "data/solution.zip"
