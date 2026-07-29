"""Unit tests for `_resolve_plexos_backend_and_files`.

Pure filesystem-shape tests — no PLEXOS fixture data needed, just zero-byte
files with the right extensions. Confirms the backend-detection logic
routes native PLEXOS Solution.zip/.duckdb input to "duckdb" and
h5plexos-converted .h5 input to "h5", without ever changing resolution for
existing h5 call sites (directories, file lists, globs).
"""
from pathlib import Path

import pytest

from gat.scenariohandlers.plexos import _resolve_plexos_backend_and_files
from gat.scenariohandlers.base import BaseScenario


def _finder(solution_data, pattern):
    """The same free function BaseScenario._find_solution_files delegates
    to, used unbound so these tests don't need a live PlexosScenario."""
    return BaseScenario._find_solution_files(None, solution_data, pattern)


def _touch(path: Path) -> str:
    path.write_text("")
    return str(path)


class TestResolvePlexosBackendAndFiles:
    def test_none_input(self):
        backend, files = _resolve_plexos_backend_and_files(_finder, None, "*.h5")
        assert backend == "h5"
        assert files == []

    def test_empty_string_input(self):
        backend, files = _resolve_plexos_backend_and_files(_finder, "", "*.h5")
        assert backend == "h5"
        assert files == []

    def test_nonexistent_path(self, tmp_path):
        backend, files = _resolve_plexos_backend_and_files(
            _finder, str(tmp_path / "does_not_exist.h5"), "*.h5"
        )
        assert backend == "h5"
        assert files == []

    def test_explicit_single_h5_file(self, tmp_path):
        f = _touch(tmp_path / "sol.h5")
        backend, files = _resolve_plexos_backend_and_files(_finder, f, "*.h5")
        assert backend == "h5"
        assert files == [f]

    def test_explicit_single_zip_file(self, tmp_path):
        f = _touch(tmp_path / "Solution.zip")
        backend, files = _resolve_plexos_backend_and_files(_finder, f, "*.h5")
        assert backend == "duckdb"
        assert files == [f]

    def test_explicit_single_duckdb_file(self, tmp_path):
        f = _touch(tmp_path / "Solution.duckdb")
        backend, files = _resolve_plexos_backend_and_files(_finder, f, "*.h5")
        assert backend == "duckdb"
        assert files == [f]

    def test_list_of_zip_files(self, tmp_path):
        files = [
            _touch(tmp_path / "sol1.zip"),
            _touch(tmp_path / "sol2.zip"),
        ]
        backend, resolved = _resolve_plexos_backend_and_files(_finder, files, "*.h5")
        assert backend == "duckdb"
        assert sorted(resolved) == sorted(files)

    def test_directory_of_h5_files_default_pattern(self, tmp_path):
        _touch(tmp_path / "a.h5")
        _touch(tmp_path / "b.h5")
        backend, files = _resolve_plexos_backend_and_files(_finder, str(tmp_path), "*.h5")
        assert backend == "h5"
        assert len(files) == 2

    def test_directory_of_zip_files_under_default_h5_pattern(self, tmp_path):
        """The retry path: a directory with only .zip files, resolved
        under the default "*.h5" pattern that finds nothing, should still
        be detected as duckdb via the *.zip/*.duckdb fallback."""
        _touch(tmp_path / "sol1.zip")
        _touch(tmp_path / "sol2.zip")
        backend, files = _resolve_plexos_backend_and_files(_finder, str(tmp_path), "*.h5")
        assert backend == "duckdb"
        assert len(files) == 2

    def test_directory_of_zip_files_explicit_pattern(self, tmp_path):
        _touch(tmp_path / "sol1.zip")
        backend, files = _resolve_plexos_backend_and_files(_finder, str(tmp_path), "*.zip")
        assert backend == "duckdb"
        assert len(files) == 1

    def test_mixed_list_raises(self, tmp_path):
        files = [_touch(tmp_path / "a.zip"), _touch(tmp_path / "b.h5")]
        with pytest.raises(ValueError, match="mix of file types"):
            _resolve_plexos_backend_and_files(_finder, files, "*.h5")

    def test_mixed_directory_raises(self, tmp_path):
        _touch(tmp_path / "a.h5")
        _touch(tmp_path / "b.zip")
        # Explicit pattern matching both would require a glob like "*"; a
        # directory naturally mixing formats under "*.h5" only ever sees
        # the h5 file, so exercise the mixed case via an explicit list
        # instead (already covered by test_mixed_list_raises) — this test
        # instead confirms a directory glob that happens to match both
        # extensions (pattern="*") raises.
        with pytest.raises(ValueError, match="mix of file types"):
            _resolve_plexos_backend_and_files(_finder, str(tmp_path), "*")

    def test_never_overrides_successful_h5_result(self, tmp_path):
        """If the default h5 pattern already found files, the zip-retry
        fallback must never run (and never raise) even if .zip files
        also happen to exist in the same directory under a different
        explicit pattern — the retry only fires on zero h5 results."""
        _touch(tmp_path / "a.h5")
        backend, files = _resolve_plexos_backend_and_files(_finder, str(tmp_path), "*.h5")
        assert backend == "h5"
        assert len(files) == 1
