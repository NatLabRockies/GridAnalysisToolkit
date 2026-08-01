"""Generate a PowerPoint deck from local fixtures for visual review.

This is a developer tool, not a pytest test. Run it manually after
substantive changes to plotting / reporting / handler / aggregation code,
then open the .pptx (or browse the PNGs) and eyeball the figures.

Usage (from repo root):
    python tests/visual/generate_fixture_deck.py                    # plexos only (default)
    python tests/visual/generate_fixture_deck.py --model-type sienna
    python tests/visual/generate_fixture_deck.py --all              # both, one after another

    # or via the Makefile:
    make fixture-deck            # plexos
    make fixture-deck-sienna     # sienna
    make fixture-deck-all        # both

Fixture resolution (mirrors tests/conftest.py's search order) — override with
--fixture / --system-path / --simulation-path, or these env vars:

    Plexos: GAT_PLEXOS_FIXTURE, else ~/.gat-test-data/plexos, else example_data/plexos
    Sienna: GAT_SIENNA_SYSTEM_FIXTURE + GAT_SIENNA_SIMULATION_FIXTURE, else a
            (system.json, simulation_store.h5) pair auto-detected under
            ~/.gat-test-data/sienna or example_data/sienna/v4

Output is written to tests/visual/output/<model-type>/ (gitignored).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.path.expanduser("~"))
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "tests" / "visual" / "output"


def _resolve_plexos_fixture(explicit: Optional[Path]) -> Optional[Path]:
    if explicit is not None:
        return explicit
    env = os.environ.get("GAT_PLEXOS_FIXTURE")
    candidates = [Path(env)] if env else []
    candidates += [
        HOME / ".gat-test-data" / "plexos",
        REPO_ROOT / "example_data" / "plexos",
    ]
    for p in candidates:
        if p.is_dir() and any(p.glob("*.h5")):
            return p
    return None


def _resolve_sienna_fixture(
    explicit_system: Optional[Path], explicit_sim: Optional[Path]
) -> Optional[tuple[Path, Path]]:
    if explicit_system is not None and explicit_sim is not None:
        return explicit_system, explicit_sim

    env_system = os.environ.get("GAT_SIENNA_SYSTEM_FIXTURE")
    env_sim = os.environ.get("GAT_SIENNA_SIMULATION_FIXTURE")
    if env_system and env_sim:
        return Path(env_system), Path(env_sim)

    candidates = [
        HOME / ".gat-test-data" / "sienna",
        REPO_ROOT / "example_data" / "sienna" / "v4",
        REPO_ROOT / "example_data" / "sienna" / "v5",
    ]
    for p in candidates:
        if not p.is_dir():
            continue
        json_files = sorted(p.glob("*.json"))
        h5_files = sorted(p.glob("*.h5"))
        if json_files and h5_files:
            return json_files[0], h5_files[0]
    return None


def _run_plexos(fixture: Path, output: Path) -> None:
    from gat.models.scenario import ScenarioConfig
    from gat.reports.scenario_single import SystemReportConfig, run

    scenario_config = ScenarioConfig(
        model_type="plexos",
        display_name="plexos-fixture",
        simulation_paths=str(fixture),
    )
    report_config = SystemReportConfig(
        model_type="plexos",
        scenario=scenario_config,
        output_path=str(output),
        output_fmt="pptx",
    )
    run(report_config)
    print(f"plexos deck written to: {output}")


def _run_sienna(system_path: Path, simulation_path: Path, output: Path) -> None:
    from gat.models.scenario import ScenarioConfig
    from gat.reports.scenario_single import SystemReportConfig, run

    scenario_config = ScenarioConfig(
        model_type="sienna",
        display_name="sienna-fixture",
        system_path=str(system_path),
        simulation_paths=str(simulation_path),
    )
    report_config = SystemReportConfig(
        model_type="sienna",
        scenario=scenario_config,
        output_path=str(output),
        output_fmt="pptx",
    )
    run(report_config)
    print(f"sienna deck written to: {output}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--model-type",
        choices=["plexos", "sienna"],
        default="plexos",
        help="which fixture deck to build (ignored if --all)",
    )
    parser.add_argument(
        "--all", action="store_true", help="build both plexos and sienna decks"
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="plexos fixture directory (directory of .h5 solution files)",
    )
    parser.add_argument(
        "--system-path", type=Path, default=None, help="sienna system file (.json)"
    )
    parser.add_argument(
        "--simulation-path",
        type=Path,
        default=None,
        help="sienna simulation file (.h5)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help=f"output root directory (default: {DEFAULT_OUTPUT_ROOT})",
    )
    args = parser.parse_args(argv)

    model_types = ["plexos", "sienna"] if args.all else [args.model_type]
    exit_code = 0

    for model_type in model_types:
        output_dir = args.output / model_type
        output_dir.mkdir(parents=True, exist_ok=True)

        if model_type == "plexos":
            fixture = _resolve_plexos_fixture(args.fixture)
            if fixture is None:
                print(
                    "plexos fixture not found (set --fixture, GAT_PLEXOS_FIXTURE, "
                    "or populate ~/.gat-test-data/plexos)",
                    file=sys.stderr,
                )
                exit_code = 1
                continue
            _run_plexos(fixture, output_dir)
        else:
            resolved = _resolve_sienna_fixture(args.system_path, args.simulation_path)
            if resolved is None:
                print(
                    "sienna fixture not found (set --system-path/--simulation-path, "
                    "GAT_SIENNA_SYSTEM_FIXTURE/GAT_SIENNA_SIMULATION_FIXTURE, or "
                    "populate ~/.gat-test-data/sienna)",
                    file=sys.stderr,
                )
                exit_code = 1
                continue
            system_path, simulation_path = resolved
            _run_sienna(system_path, simulation_path, output_dir)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
