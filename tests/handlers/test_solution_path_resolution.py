"""Regression tests for `~`-expansion in solution-file path resolution.

`os.path.isdir`/`isfile`/`glob` never expand `~` — only shells do, and
only when unquoted. A path typed directly into a Python string (a REPL,
a script, a config value) keeps its literal `~`, which silently resolved
to zero files and left the scenario in a broken partially-initialized
state (self.parser stays None) that failed much later with a confusing,
unrelated AttributeError instead of a clear error at construction time.

Tests below use monkeypatch to redirect HOME into a pytest tmp_path
rather than touching the real user home directory.
"""

from pathlib import Path

import pytest

from gat.scenariohandlers.base import BaseScenario
from gat.scenariohandlers.plexos import PlexosScenario
from gat.scenariohandlers.reeds import ReEDsScenario
from gat.scenariohandlers.sienna import SiennaScenario


def _touch(path: Path) -> str:
    path.write_text("")
    return str(path)


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect '~' expansion to an isolated tmp_path for this test."""
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


class TestBaseScenarioTildeExpansion:
    """BaseScenario._find_solution_files — the default implementation
    shared by PlexosScenario (via a thin super() passthrough) and any
    other handler that doesn't override it."""

    def test_tilde_single_file(self, fake_home):
        f = _touch(fake_home / "sol.h5")
        resolved = BaseScenario._find_solution_files(None, "~/sol.h5", "*.h5")
        assert resolved == [f]

    def test_tilde_nested_file(self, fake_home):
        d = fake_home / "data" / "plexos"
        d.mkdir(parents=True)
        f = _touch(d / "Solution.zip")
        resolved = BaseScenario._find_solution_files(
            None, "~/data/plexos/Solution.zip", "*.h5"
        )
        assert resolved == [f]

    def test_tilde_directory(self, fake_home):
        d = fake_home / "data"
        d.mkdir()
        _touch(d / "a.h5")
        _touch(d / "b.h5")
        resolved = BaseScenario._find_solution_files(None, "~/data", "*.h5")
        assert len(resolved) == 2

    def test_tilde_in_list(self, fake_home):
        f1 = _touch(fake_home / "a.h5")
        f2 = _touch(fake_home / "b.h5")
        resolved = BaseScenario._find_solution_files(
            None, ["~/a.h5", "~/b.h5"], "*.h5"
        )
        assert sorted(resolved) == sorted([f1, f2])


class TestSiennaScenarioTildeExpansion:
    """SiennaScenario re-implements _find_solution_files rather than
    delegating to BaseScenario, so it needs its own coverage."""

    def test_tilde_single_file(self, fake_home):
        f = _touch(fake_home / "simulation_store.h5")
        inst = SiennaScenario.__new__(SiennaScenario)
        resolved = inst._find_solution_files("~/simulation_store.h5", "*.h5")
        assert resolved == [f]


class TestReEDsScenarioTildeExpansion:
    def test_tilde_directory(self, fake_home):
        d = fake_home / "reeds_run"
        d.mkdir()
        inst = ReEDsScenario.__new__(ReEDsScenario)
        resolved = inst._find_solution_files("~/reeds_run", "*")
        assert resolved == str(d)


class TestPlexosScenarioClearErrorOnUnresolvedPath:
    """PlexosScenario previously proceeded silently with self.parser=None
    when nothing resolved, deferring to a confusing AttributeError deep
    inside generator_technology_map. It should now fail immediately and
    clearly, naming the input that didn't resolve."""

    def test_nonexistent_tilde_path_raises_clearly(self, fake_home):
        with pytest.raises(FileNotFoundError, match="does_not_exist.zip"):
            PlexosScenario("~/does_not_exist.zip")

    def test_nonexistent_absolute_path_raises_clearly(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            PlexosScenario(str(tmp_path / "does_not_exist.h5"))

    def test_none_input_does_not_raise_the_new_error(self):
        # No input at all is a legitimate no-op construction path (data
        # attached later) — the new check must not fire for it. This
        # scenario is still broken for an unrelated, separately-filed
        # reason (issue #24: generator_technology_map dereferences a None
        # parser unconditionally), so this only asserts our new check
        # isn't what raises.
        try:
            PlexosScenario()
        except FileNotFoundError:
            pytest.fail("FileNotFoundError should not fire for no input")
        except AttributeError:
            pass  # pre-existing, unrelated — see issue #24

    def test_tilde_zip_resolves_to_duckdb_backend(self, fake_home):
        f = _touch(fake_home / "Solution.zip")
        # Resolution succeeds; construction then proceeds into the duckdb
        # backend, which needs the optional plexos2duckdb dependency and
        # a real solution file to actually parse — neither is available
        # here, so just confirm we got past file resolution into that
        # backend rather than raising FileNotFoundError.
        try:
            PlexosScenario(f"~/{Path(f).name}")
        except FileNotFoundError:
            pytest.fail("a real file should resolve, not raise")
        except Exception:
            pass  # backend-specific failure on a zero-byte fake zip, expected
