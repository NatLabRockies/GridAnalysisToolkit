"""Regression tests for gat's default logging setup (issue #22, part 3):
a plain `import gat` should be quiet by default (no DEBUG-level spam from
e.g. plot-function registration) without ever clobbering a sink the caller
already configured. Run each case in a subprocess -- the behavior under
test only happens on a package's *first* import in a fresh interpreter,
and this test suite has already imported gat long before this file runs.
"""

import subprocess
import sys


def _run(code: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout + result.stderr


def test_plain_import_suppresses_debug_level_noise():
    output = _run("import gat\n" "import gat.quickplots.dispatch\n")
    assert "DEBUG" not in output


def test_plain_import_still_shows_warning_level():
    output = _run(
        "import gat\n"
        "from loguru import logger\n"
        "logger.warning('should be visible')\n"
    )
    assert "should be visible" in output


def test_preexisting_sink_survives_gat_import():
    output = _run(
        "from loguru import logger\n"
        "logger.remove()\n"
        "logger.add(lambda msg: print('CUSTOM:' + msg, end=''), level='INFO')\n"
        "import gat\n"
        "logger.info('should reach the custom sink')\n"
    )
    assert "CUSTOM:" in output
    assert "should reach the custom sink" in output
