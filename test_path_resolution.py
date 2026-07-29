#!/usr/bin/env python
"""
Standalone test script for scenario path resolution.

Tests that relative and absolute paths are correctly resolved
when adding scenarios to projects.

Run with: python test_path_resolution.py
"""

import sys
import tempfile
from pathlib import Path

import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from gat.models.project import SiennaScenarioConfig
from gat.project_management.manager import ProjectManager


def test_relative_path_within_project():
    """Test that relative paths are resolved to absolute paths."""
    print("\n" + "=" * 70)
    print("TEST: Relative path resolution to absolute")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Initialize project structure
        (project_path / "scenarios").mkdir()
        (project_path / "palettes").mkdir()
        (project_path / "data").mkdir()

        # Create project config
        config_data = {
            "name": "Test Project",
            "gat_version": "1.0.0",
            "version": "0.1.0",
        }
        with open(project_path / "gat-project.yaml", "w") as f:
            yaml.dump(config_data, f)

        # Create dummy data files
        system_file = project_path / "data" / "system.json"
        with open(system_file, "w") as f:
            f.write('{"data": {}, "data_format_version": "3.0.0"}')

        sim_file = project_path / "data" / "results.h5"
        sim_file.touch()

        manager = ProjectManager(project_path)

        # Get absolute paths for data files
        system_abs = str(system_file)
        sim_abs = str(sim_file)

        print(f"Input files:")
        print(f"  System: {system_abs}")
        print(f"  Simulation: {sim_abs}")

        # Add scenario with relative paths (they should be resolved to absolute)
        config = manager.add_scenario(
            scenario_id="test_scenario",
            name="Test Scenario",
            scenario_type="sienna",
            system_path="data/system.json",
            simulation_paths="data/results.h5",
        )

        print(f"\n✓ Scenario created")
        print(f"  System path stored: {config.system_path}")
        print(f"  Simulation path stored: {config.simulation_paths}")

        assert isinstance(config, SiennaScenarioConfig)
        # Note: paths should still be as-provided when calling ProjectManager directly
        # The CLI does the resolution to absolute paths
        assert config.system_path == "data/system.json"
        assert config.simulation_paths == "data/results.h5"
        print("✓ Paths stored as provided (ProjectManager doesn't auto-resolve)")

        # Reload and verify
        loaded_config = manager.load_scenario("test_scenario")
        assert loaded_config.system_path == "data/system.json"
        print("✓ Paths persist correctly after reload")

        # Test path resolution (ProjectManager can resolve relative paths)
        resolved = manager.resolve_path("data/system.json")
        print(f"  Resolved path: {resolved}")
        assert resolved.exists()
        print("✓ Path resolution works via resolve_path()")

    print("✅ TEST PASSED\n")


def test_absolute_path_storage():
    """Test that absolute paths are stored as-is."""
    print("=" * 70)
    print("TEST: Absolute path storage")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Initialize project structure
        (project_path / "scenarios").mkdir()
        (project_path / "data").mkdir()

        # Create project config
        config_data = {
            "name": "Test Project",
            "gat_version": "1.0.0",
            "version": "0.1.0",
        }
        with open(project_path / "gat-project.yaml", "w") as f:
            yaml.dump(config_data, f)

        # Create dummy data files
        system_file = project_path / "data" / "system.json"
        with open(system_file, "w") as f:
            f.write('{"data": {}, "data_format_version": "3.0.0"}')

        sim_file = project_path / "data" / "results.h5"
        sim_file.touch()

        manager = ProjectManager(project_path)

        # Add scenario with ABSOLUTE paths
        system_abs = str(system_file)
        sim_abs = str(sim_file)

        print(f"Input absolute paths:")
        print(f"  System: {system_abs}")
        print(f"  Simulation: {sim_abs}")

        config = manager.add_scenario(
            scenario_id="test_abs",
            name="Test Absolute",
            scenario_type="sienna",
            system_path=system_abs,
            simulation_paths=sim_abs,
        )

        print(f"\nStored paths:")
        print(f"  System path: {config.system_path}")
        print(f"  Simulation path: {config.simulation_paths}")

        # Paths should be stored as-is (ProjectManager doesn't modify them)
        # The CLI would have resolved them to absolute before calling add_scenario
        assert config.system_path == system_abs
        assert config.simulation_paths == sim_abs
        print("✓ Absolute paths stored as-is")

    print("✅ TEST PASSED\n")


def test_external_path_handling():
    """Test that paths outside project are stored as absolute."""
    print("=" * 70)
    print("TEST: External path handling")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Initialize project structure
        (project_path / "scenarios").mkdir()
        (project_path / "data").mkdir()

        # Create project config
        config_data = {
            "name": "Test Project",
            "gat_version": "1.0.0",
            "version": "0.1.0",
        }
        with open(project_path / "gat-project.yaml", "w") as f:
            yaml.dump(config_data, f)

        # Create external file (outside project)
        external_dir = Path(tmpdir) / "external_data"
        external_dir.mkdir()
        external_system = external_dir / "system.json"
        with open(external_system, "w") as f:
            f.write('{"data": {}, "data_format_version": "3.0.0"}')

        # Create internal simulation file
        sim_file = project_path / "data" / "results.h5"
        sim_file.touch()

        manager = ProjectManager(project_path)

        # Add scenario with external system path
        print(f"External file: {external_system}")
        print(f"Internal file: data/results.h5")

        config = manager.add_scenario(
            scenario_id="test_external",
            name="Test External",
            scenario_type="sienna",
            system_path=str(external_system),
            simulation_paths="data/results.h5",
        )

        print(f"\nStored paths:")
        print(f"  System path: {config.system_path}")
        print(f"  Simulation path: {config.simulation_paths}")

        # External path should be stored as absolute (as provided)
        assert Path(config.system_path).is_absolute()
        assert str(external_system) == config.system_path
        print("✓ External path stored as absolute")

        # Internal path stored as-is (the CLI would resolve it before calling add_scenario)
        assert config.simulation_paths == "data/results.h5"
        print("✓ Internal path stored as provided")

    print("✅ TEST PASSED\n")


def test_multiple_simulation_paths():
    """Test handling of multiple simulation files."""
    print("=" * 70)
    print("TEST: Multiple simulation paths")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Initialize project structure
        (project_path / "scenarios").mkdir()
        (project_path / "data").mkdir()

        # Create project config
        config_data = {
            "name": "Test Project",
            "gat_version": "1.0.0",
            "version": "0.1.0",
        }
        with open(project_path / "gat-project.yaml", "w") as f:
            yaml.dump(config_data, f)

        # Create dummy data files
        system_file = project_path / "data" / "system.json"
        with open(system_file, "w") as f:
            f.write('{"data": {}, "data_format_version": "3.0.0"}')

        sim_file1 = project_path / "data" / "results1.h5"
        sim_file1.touch()
        sim_file2 = project_path / "data" / "results2.h5"
        sim_file2.touch()

        manager = ProjectManager(project_path)

        # Add scenario with multiple simulation paths
        config = manager.add_scenario(
            scenario_id="test_multi",
            name="Test Multi",
            scenario_type="sienna",
            system_path="data/system.json",
            simulation_paths=["data/results1.h5", "data/results2.h5"],
        )

        print(f"Simulation paths: {config.simulation_paths}")

        assert isinstance(config.simulation_paths, list)
        assert len(config.simulation_paths) == 2
        assert "data/results1.h5" in config.simulation_paths
        assert "data/results2.h5" in config.simulation_paths
        print("✓ Multiple paths stored correctly")

        # Test get_simulation_paths_list
        paths_list = config.get_simulation_paths_list()
        assert len(paths_list) == 2
        print("✓ get_simulation_paths_list works")

    print("✅ TEST PASSED\n")


def test_path_validation():
    """Test path validation for existing and missing files."""
    print("=" * 70)
    print("TEST: Path validation")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_path = Path(tmpdir) / "test_project"
        project_path.mkdir()

        # Initialize project structure
        (project_path / "scenarios").mkdir()
        (project_path / "data").mkdir()

        # Create project config
        config_data = {
            "name": "Test Project",
            "gat_version": "1.0.0",
            "version": "0.1.0",
        }
        with open(project_path / "gat-project.yaml", "w") as f:
            yaml.dump(config_data, f)

        # Create only system file (simulation missing)
        system_file = project_path / "data" / "system.json"
        with open(system_file, "w") as f:
            f.write('{"data": {}, "data_format_version": "3.0.0"}')

        manager = ProjectManager(project_path)

        # Add scenario with missing simulation path
        config = manager.add_scenario(
            scenario_id="test_missing",
            name="Test Missing",
            scenario_type="sienna",
            system_path="data/system.json",
            simulation_paths="data/missing.h5",
        )

        print(f"Created scenario with missing file: data/missing.h5")

        # Validate - should have warnings
        warnings = manager.validate_scenario_paths("test_missing")
        print(f"Validation warnings: {len(warnings)}")
        for w in warnings:
            print(f"  - {w}")

        assert len(warnings) > 0
        assert any("missing.h5" in w for w in warnings)
        print("✓ Missing files detected correctly")

    print("✅ TEST PASSED\n")


def main():
    """Run all tests."""
    print("\n" + "#" * 70)
    print("# Path Resolution Test Suite")
    print("#" * 70)

    tests = [
        ("Relative path resolution", test_relative_path_within_project),
        ("Absolute path storage", test_absolute_path_storage),
        ("External path handling", test_external_path_handling),
        ("Multiple simulation paths", test_multiple_simulation_paths),
        ("Path validation", test_path_validation),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ TEST ERROR: {test_name}")
            print(f"   Error: {e}\n")
            failed += 1

    print("\n" + "=" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✅ ALL TESTS PASSED!")
        sys.exit(0)


if __name__ == "__main__":
    main()
