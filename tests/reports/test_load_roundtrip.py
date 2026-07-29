"""End-to-end round-trip test for `gat.load`.

The existing `tests/test_loader.py` mocks the scenario constructors, so it
verifies argument-passing but not real loading. This test goes the full
distance: create a temp project on disk, register a project ref under a
mocked `XDG_CONFIG_HOME`, save a scenario YAML pointing at the in-repo
plexos fixture, then call `gat.load(...)` and verify the returned object
is a real, working scenario.

Covers (transitively):
- `gat.loader.load` and `_load_local_scenario`
- `gat.models.user.{get_config_dir, get_projects_dir, save_project_ref}`
- `gat.project_management.manager.{ProjectManager.init_project, add_scenario, save_scenario, load_scenario}`
- `gat.models.project.PlexosScenarioConfig`
- The legacy `PlexosScenario` factory invocation in `gat.loader._load_local_scenario`
"""
import warnings

import pytest


@pytest.fixture
def isolated_user_config(tmp_path, monkeypatch):
    """Redirect ~/.config/gat/ to a temp dir for the duration of the test.

    The user's actual project registry is untouched.
    """
    config_root = tmp_path / "xdg_config"
    config_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_root))
    return config_root / "gat"


def test_gat_load_roundtrip_against_plexos_fixture(
    isolated_user_config,
    tmp_path,
    plexos_fixture_root,
):
    """Initialize a temp project, point a scenario at the plexos fixture,
    register the project ref, and call `gat.load` — verify the returned
    handler is a real `PlexosScenario` that can serve `get_*` calls.

    This catches regressions in the project YAML schema, the loader's
    factory dispatch, and the gluing between `ProjectManager` and the
    handler constructors — none of which the mock-based loader tests
    cover.
    """
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from gat.models.project import PlexosScenarioConfig
    from gat.models.user import UserProjectRef, save_project_ref
    from gat.project_management.manager import ProjectManager
    import gat

    # 1. Initialize a project directory in tmp_path
    project_dir = tmp_path / "test-project"
    pm = ProjectManager(project_dir)
    pm.init_project(name="test-roundtrip-project")

    # 2. Add a Plexos scenario pointing at the in-repo fixture
    scenario_id = "plexos-fixture-test"
    scenario_config = PlexosScenarioConfig(
        name="Plexos Fixture Test",
        solution_path=str(plexos_fixture_root),
    )
    pm.save_scenario(scenario_id, scenario_config)

    # 3. Set this scenario as the project's default so gat.load can pick it up
    config = pm.load_config()
    config.default_scenario = scenario_id
    pm.save_config(config)

    # 4. Register the project ref under the mocked XDG_CONFIG_HOME
    project_ref = UserProjectRef(
        project_id="test-roundtrip",
        name="Test Roundtrip",
        path=str(project_dir),
        is_default=True,
    )
    save_project_ref(project_ref)

    # 5. Call gat.load() — this exercises the real loader path end-to-end
    scenario, palette, project = gat.load(
        project="test-roundtrip",
        scenario=scenario_id,
        verbose=False,
    )

    # 6. Verify what came back is real and functional
    from gat.scenariohandlers import PlexosScenario
    assert isinstance(scenario, PlexosScenario)
    assert scenario.parser is not None
    # Smoke test that one get_* call works against the loaded scenario.
    gen = scenario.get_generation()
    assert gen.shape[0] > 0
    assert gen.shape[1] > 0


def test_gat_load_default_resolves_to_registered_project(
    isolated_user_config,
    tmp_path,
    plexos_fixture_root,
):
    """`gat.load()` with no args should pick up the default project we
    registered. Catches regressions in the default-resolution logic
    (`get_default_project_ref` + the auto-pick branch in `load`)."""
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    from gat.models.project import PlexosScenarioConfig
    from gat.models.user import UserProjectRef, save_project_ref
    from gat.project_management.manager import ProjectManager
    import gat

    project_dir = tmp_path / "default-project"
    pm = ProjectManager(project_dir)
    pm.init_project(name="default-roundtrip")

    pm.save_scenario(
        "default-scenario",
        PlexosScenarioConfig(
            name="Default Plexos",
            solution_path=str(plexos_fixture_root),
        ),
    )
    cfg = pm.load_config()
    cfg.default_scenario = "default-scenario"
    pm.save_config(cfg)

    save_project_ref(UserProjectRef(
        project_id="default-rt",
        name="Default RT",
        path=str(project_dir),
        is_default=True,
    ))

    # Pass no project / no scenario → should resolve via defaults.
    scenario, _palette, _project = gat.load(verbose=False)

    from gat.scenariohandlers import PlexosScenario
    assert isinstance(scenario, PlexosScenario)
