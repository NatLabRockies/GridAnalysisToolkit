"""
Author: Micah Webb
Date: 2025-06-03

Description: This report aims to generate plots that compare two scenarios.
The script aims to be flexible enough to override certain parts of the configuration to make
it as reusable as possible.
"""

from pydantic import BaseModel
from typing import List, Union, Dict, Optional, Any
from gat.models.scenario import ScenarioConfig, load_config
from gat import __version__
from loguru import logger
import argparse
import os
import yaml
import sys
import click
from pathlib import Path
import inspect
import importlib

# Import version
try:
    from gat._version import version as __version__
except ImportError:
    __version__ = "unknown"

import matplotlib

matplotlib.use("Agg")  # set to non-interactive
import matplotlib.pyplot as plt
from gat.logging_config import setup_logging


def discover_available_plots() -> List[str]:
    """Discovers available plot functions in the multi_system module.

    Returns:
        List[str]: Names of available plot functions
    """
    try:
        logger.info("Attempting to discover available plot functions")
        plot_module = importlib.import_module("gat.quickplots.multi_system")

        # Get all functions from the module
        plot_functions = []
        for name, obj in inspect.getmembers(plot_module):
            # Check if it's a function and not a private/special method
            if inspect.isfunction(obj) and not name.startswith("_"):
                try:
                    # Get function signature
                    sig = inspect.signature(obj)
                    params = list(sig.parameters.values())

                    # Debug the function and its first parameter
                    if params:
                        first_param_annotation = getattr(params[0], "annotation", None)
                        first_param_name = getattr(
                            first_param_annotation,
                            "__name__",
                            str(first_param_annotation),
                        )
                        logger.debug(
                            f"Function: {name}, First param: {first_param_name}"
                        )

                        # Add function if it accepts MultiScenario as first parameter
                        if first_param_name == "MultiScenario":
                            plot_functions.append(name)
                            logger.info(f"Added plot function: {name}")
                except Exception as e:
                    logger.warning(f"Error inspecting function {name}: {e}")

        logger.info(
            f"Discovered {len(plot_functions)} plot functions: {plot_functions}"
        )
        return plot_functions
    except ImportError as e:
        logger.warning(f"Could not import gat.quickplots.multi_system module: {e}")
        return []
    except Exception as e:
        logger.warning(f"Error discovering plot functions: {e}")
        return []


class ComparisonReportConfig(BaseModel):
    # TODO enable pptx output by merging code changes from other branch
    output_fmt: Union[str, List[str]] = "pptx"
    output_path: str = "./gat_sys_comparison"
    # GAT version used to create this config
    gat_version: Optional[str] = __version__

    # graphs to plot.
    # Must be in list of multi-plots
    # In the future, support for plugins will allow user-defined multi-scenario plots to be discovered and added here.
    output_plots: List[str] = []
    dpi: int = 200

    plot_kwargs: Dict[str, Any] = {}
    # Scenario level configs will be included in Scenario Object
    # display names, etc will be contained in these objects.
    s1: ScenarioConfig
    s2: ScenarioConfig

    def __init__(self, **data):
        # Set default output_plots if not provided
        if "output_plots" not in data or not data["output_plots"]:
            data["output_plots"] = discover_available_plots()
        super().__init__(**data)

    @classmethod
    def from_config(cls, path):
        """Loads the reporting config from a path."""
        try:
            with open(path, "r") as f:
                config_data = yaml.safe_load(f)
                config = cls(**config_data)

                # Check for version mismatch
                if config.gat_version and config.gat_version != __version__:
                    logger.warning(
                        f"Report config was created with GAT version {config.gat_version}, but current version is {__version__}. This may cause compatibility issues."
                    )

                return config
        except Exception as e:
            logger.error(f"Failed to load configuration from {path}: {e}")
            raise

    def save_config(self, path):
        """Saves the reporting config to a path."""
        try:
            # Update version when saving
            self.gat_version = __version__

            config_dict = self.model_dump()
            with open(path, "w") as f:
                yaml.dump(config_dict, f, sort_keys=False)
            logger.info(f"Configuration saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save configuration to {path}: {e}")
            raise

    def update_gat_colormap(self):
        """Updates the color map based on the combined color and order of the two scenario configurations"""
        # Combine technology mappings from both scenarios
        combined_tech_mappings = {}

        # Add mappings from s1
        for tech, mapping in self.s1.technology_mappings.items():
            combined_tech_mappings[tech] = mapping

        # Add or update mappings from s2
        for tech, mapping in self.s2.technology_mappings.items():
            if tech not in combined_tech_mappings:
                combined_tech_mappings[tech] = mapping

        # Update both scenario configs with the combined mappings
        self.s1.technology_mappings = combined_tech_mappings.copy()
        self.s2.technology_mappings = combined_tech_mappings.copy()


def run(config: ComparisonReportConfig):
    """
    Generate comparison plots based on the provided configuration.

    Args:
        config: ComparisonReportConfig object containing scenario configurations
    """
    import importlib
    from gat.scenariohandlers import MultiScenario
    from gat.utils import scenario_from_config

    setup_logging(config.output_path)
    logger.info("Creating MultiScenario object")

    try:
        # Create scenario objects using the utility function
        s1 = scenario_from_config(config.s1)
        s2 = scenario_from_config(config.s2)

        if config.s1.display_name is None:
            config.s1.display_name = "System1"
        if config.s2.display_name is None:
            config.s2.display_name = "System2"

        # Create multi-scenario object
        multi_scenario = MultiScenario(
            {config.s1.display_name: s1, config.s2.display_name: s2}
        )

        # Create output directory if needed

        os.makedirs(config.output_path, exist_ok=True)

        # Check if output_plots is empty and try to populate it
        if not config.output_plots:
            logger.warning(
                "No plot functions specified or discovered. Attempting to rediscover."
            )
            config.output_plots = discover_available_plots()
            if not config.output_plots:
                logger.error(
                    "No plot functions available. Check that gat.quickplots.multi_system module is accessible."
                )
                return

        # Log which plots will be generated
        logger.info(f"Generating the following plots: {config.output_plots}")

        # In the compare_scenarios function where you call plot functions
        for plot_name in config.output_plots:
            try:
                plot_module = importlib.import_module("gat.quickplots.multi_system")

                if hasattr(plot_module, plot_name):
                    plot_func = getattr(plot_module, plot_name)

                    # Check if it's a generator function

                    result = plot_func(multi_scenario, **config.plot_kwargs)

                    if inspect.isgenerator(result):
                        # Handle generator function

                        for name, ax, _df in result:

                            # Process each yielded figure

                            output_file = os.path.join(
                                config.output_path, f"{plot_name}_{name}.png"
                            )
                            plt.savefig(
                                output_file, dpi=config.dpi, bbox_inches="tight"
                            )
                    else:
                        # Handle regular function

                        name, ax, _df = result

                        output_file = os.path.join(
                            config.output_path, f"{plot_name}_{name}.png"
                        )
                        plt.savefig(output_file, dpi=config.dpi, bbox_inches="tight")
            except Exception as e:
                logger.error(f"Error generating plot {plot_name}: {e}")

        # After all plots are made, if pptx is enabled, run dir_to_pptx script
        # TODO we will implement this later.
        if config.output_fmt == "pptx" or (
            isinstance(config.output_fmt, list) and "pptx" in config.output_fmt
        ):
            try:
                from gat.reports.figs_to_pptx import create_ppt_from_pngs

                pptx_path = f"{config.output_path}/system_comparison.pptx"
                if not pptx_path.endswith(".pptx"):
                    pptx_path += ".pptx"
                create_ppt_from_pngs(config.output_path, pptx_path)
                logger.info(f"Generated PowerPoint presentation: {pptx_path}")
            except ImportError:
                logger.error(
                    "PPTX output requested but pptx_helper module not available"
                )
            except Exception as e:
                logger.error(f"Error generating PPTX: {e}")

    except Exception as e:
        logger.error(f"Error comparing scenarios: {e}")
        raise


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate comparison reports for two scenarios."
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Run command parser
    run_parser = subparsers.add_parser("run", help="Run the comparison report")

    # Init command parser
    init_parser = subparsers.add_parser(
        "init", help="Initialize a report configuration file"
    )

    # Common arguments for both subparsers
    for p in [run_parser, init_parser]:
        p.add_argument("--report-config", help="Path to a report configuration file")
        p.add_argument("--s1-config", help="Path to scenario 1 configuration file")
        p.add_argument("--s2-config", help="Path to scenario 2 configuration file")
        p.add_argument("--s1-path", help="Path to scenario 1 system data")
        p.add_argument("--s2-path", help="Path to scenario 2 system data")
        p.add_argument("--s1-name", help="The display name for the first scenario")
        p.add_argument("--s2-name", help="The display name for the second scenario")

        p.add_argument("--area-filter", help="The areas to use in the underlying plots")
        p.add_argument(
            "--output-fmt",
            choices=["dir", "pptx", "both"],
            help="Output format (dir=directory of images, pptx=PowerPoint)",
        )
        p.add_argument("--output-path", help="Path for output files")
        p.add_argument("--save-config", help="Save the configuration to specified path")

    return parser.parse_args()


def main():
    """Main entry point for the script."""
    args = parse_args()

    if args.command is None:
        logger.error("No command specified. Use 'run' or 'init'.")
        sys.exit(1)

    try:
        # Initialize config
        report_config = None

        # If report config is provided, load it
        if args.report_config and os.path.exists(args.report_config):
            logger.info(f"Loading report configuration from {args.report_config}")
            report_config = ComparisonReportConfig.from_config(args.report_config)

        # If no report config is provided, we need s1_config and s2_config at minimum
        elif args.s1_config and args.s2_config:
            logger.info("Building configuration from individual scenario configs")
            s1_config = load_config(args.s1_config)
            s2_config = load_config(args.s2_config)

            # Override paths if provided
            if args.s1_path:
                s1_config.simulation_paths = args.s1_path
            if args.s2_path:
                s2_config.simulation_paths = args.s2_path

            report_config = ComparisonReportConfig(s1=s1_config, s2=s2_config)
        else:
            logger.error(
                "Either --report-config or both --s1-config and --s2-config must be provided"
            )
            sys.exit(
                1
            )  # Override config values with command line arguments if provided

        # override display names if argument provided.
        if args.s1_name:
            report_config.s1.display_name = args.s1_name

        if args.s2_name:
            report_config.s2.display_name = args.s2_name

        if args.output_fmt:
            if args.output_fmt == "both":
                report_config.output_fmt = ["dir", "pptx"]
            else:
                report_config.output_fmt = args.output_fmt

        if args.output_path:
            report_config.output_path = args.output_path
            # If output path ends with .pptx, set format to pptx
            if args.output_path.endswith(".pptx"):
                report_config.output_fmt = "pptx"

        # Handle area_filter if provided
        if args.area_filter:
            # Initialize plot_kwargs if it doesn't exist
            if report_config.plot_kwargs is None:
                report_config.plot_kwargs = {}

            # Split comma-separated areas and store as a list
            areas = [area.strip() for area in args.area_filter.split(",")]
            report_config.plot_kwargs["area_filter"] = areas
            logger.info(f"Setting area filter to: {areas}")

        # Update the colormap based on the combined scenario configurations
        report_config.update_gat_colormap()

        # If init command or save_config is specified, save the configuration
        if args.command == "init" or args.save_config:
            save_path = (
                args.save_config
                if args.save_config
                else "comparison_report_config.yaml"
            )
            logger.info(f"Saving configuration to {save_path}")
            report_config.save_config(save_path)

            if args.command == "init":
                logger.info(
                    "Configuration initialized. Use 'run' command to generate the report."
                )
                return

        # Run the comparison if command is 'run'
        if args.command == "run":
            logger.info("Running comparison report")
            run(report_config)
            logger.info("Comparison report completed")

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def main_with_args(args):
    """Main entry point for the script when called with pre-parsed arguments."""
    # Setup logging

    if args.command is None:
        logger.error("No command specified. Use 'run' or 'init'.")
        sys.exit(1)

    try:
        # Initialize config
        report_config = None

        # If report config is provided, load it
        if args.report_config and os.path.exists(args.report_config):
            logger.info(f"Loading report configuration from {args.report_config}")
            report_config = ComparisonReportConfig.from_config(args.report_config)

        # If no report config is provided, we need s1_config and s2_config at minimum
        elif args.s1_config and args.s2_config:
            logger.info("Building configuration from individual scenario configs")
            s1_config = load_config(args.s1_config)
            s2_config = load_config(args.s2_config)

            # Override paths if provided
            if args.s1_path:
                s1_config.simulation_paths = args.s1_path
            if args.s2_path:
                s2_config.simulation_paths = args.s2_path

            report_config = ComparisonReportConfig(s1=s1_config, s2=s2_config)
        else:
            logger.error(
                "Either --report-config or both --s1-config and --s2-config must be provided"
            )
            sys.exit(
                1
            )  # Override config values with command line arguments if provided

        # override display names if argument provided.
        if args.s1_name:
            report_config.s1.display_name = args.s1_name

        if args.s2_name:
            report_config.s2.display_name = args.s2_name

        if args.output_fmt:
            if args.output_fmt == "both":
                report_config.output_fmt = ["dir", "pptx"]
            else:
                report_config.output_fmt = args.output_fmt

        if args.output_path:
            report_config.output_path = args.output_path
            # If output path ends with .pptx, set format to pptx
            if args.output_path.endswith(".pptx"):
                report_config.output_fmt = "pptx"

        # Handle area_filter if provided
        if args.area_filter:
            # Initialize plot_kwargs if it doesn't exist
            if report_config.plot_kwargs is None:
                report_config.plot_kwargs = {}

            # Split comma-separated areas and store as a list
            areas = [area.strip() for area in args.area_filter.split(",")]
            report_config.plot_kwargs["area_filter"] = areas
            logger.info(f"Setting area filter to: {areas}")

        # Update the colormap based on the combined scenario configurations
        report_config.update_gat_colormap()

        # If init command or save_config is specified, save the configuration
        if args.command == "init" or args.save_config:
            save_path = (
                args.save_config
                if args.save_config
                else "comparison_report_config.yaml"
            )
            logger.info(f"Saving configuration to {save_path}")
            report_config.save_config(save_path)

            if args.command == "init":
                logger.info(
                    "Configuration initialized. Use 'run' command to generate the report."
                )
                return

        # Run the comparison if command is 'run'
        if args.command == "run":
            logger.info("Running comparison report")
            run(report_config)
            logger.info("Comparison report completed")

    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def register_commands(init_group):
    """Register system comparison init commands with the init CLI group.

    Args:
        init_group: The click group for 'init' to attach commands to
    """

    @init_group.command("multi")
    @click.option(
        "--report-config", type=click.Path(), help="Path to a report configuration file"
    )
    @click.option(
        "--s1-config",
        type=click.Path(exists=True),
        help="Path to scenario 1 configuration file",
    )
    @click.option(
        "--s2-config",
        type=click.Path(exists=True),
        help="Path to scenario 2 configuration file",
    )
    @click.option(
        "--s1-path", type=click.Path(exists=True), help="Path to scenario 1 system data"
    )
    @click.option(
        "--s2-path", type=click.Path(exists=True), help="Path to scenario 2 system data"
    )
    @click.option("--s1-name", help="The display name for the first scenario")
    @click.option("--s2-name", help="The display name for the second scenario")
    @click.option(
        "--area-filter",
        help="The areas to use in the underlying plots (comma-separated)",
    )
    @click.option(
        "--output-fmt", type=click.Choice(["dir", "pptx", "both"]), help="Output format"
    )
    @click.option("--output-path", type=click.Path(), help="Path for output files")
    @click.option(
        "--save-config",
        type=click.Path(),
        help="Save the configuration to specified path",
    )
    def system_comparison_init(
        report_config,
        s1_config,
        s2_config,
        s1_path,
        s2_path,
        s1_name,
        s2_name,
        area_filter,
        output_fmt,
        output_path,
        save_config,
    ):
        """Initialize a system comparison report configuration.

        This command generates a configuration file for comparing two power system scenarios.
        The configuration can be used later with the 'gat run system_comparison' command.

        The system comparison report generates visualizations comparing key metrics between two
        different power system scenarios, such as generation mix, emissions, costs, etc.

        Examples:
            gat init system_comparison --s1-config=s1.yaml --s2-config=s2.yaml
            gat init system_comparison --report-config=existing_config.yaml --save-config=new_config.yaml
        """
        # Create an args object with the command set to "init"
        args = type(
            "Args",
            (),
            {
                "command": "init",
                "report_config": report_config,
                "s1_config": s1_config,
                "s2_config": s2_config,
                "s1_path": s1_path,
                "s2_path": s2_path,
                "s1_name": s1_name,
                "s2_name": s2_name,
                "area_filter": area_filter,
                "output_fmt": output_fmt,
                "output_path": output_path,
                "save_config": save_config or "comparison_report_config.yaml",
            },
        )

        try:
            main_with_args(args)
            click.echo(
                f"System comparison configuration initialized and saved to {args.save_config}"
            )
        except Exception as e:
            click.echo(f"Error initializing system comparison: {e}", err=True)


def register_run_commands(run_group):
    """Register system comparison run commands with the run CLI group.

    Args:
        run_group: The click group for 'run' to attach commands to
    """

    @run_group.command("multi")
    @click.option(
        "--report-config",
        type=click.Path(exists=True),
        help="Path to a report configuration file",
    )
    @click.option(
        "--s1-config",
        type=click.Path(exists=True),
        help="Path to scenario 1 configuration file",
    )
    @click.option(
        "--s2-config",
        type=click.Path(exists=True),
        help="Path to scenario 2 configuration file",
    )
    @click.option(
        "--s1-path", type=click.Path(exists=True), help="Path to scenario 1 system data"
    )
    @click.option(
        "--s2-path", type=click.Path(exists=True), help="Path to scenario 2 system data"
    )
    @click.option("--s1-name", help="The display name for the first scenario")
    @click.option("--s2-name", help="The display name for the second scenario")
    @click.option(
        "--area-filter",
        help="The areas to use in the underlying plots (comma-separated)",
    )
    @click.option(
        "--output-fmt", type=click.Choice(["dir", "pptx", "both"]), help="Output format"
    )
    @click.option("--output-path", type=click.Path(), help="Path for output files")
    def system_comparison_run(
        report_config,
        s1_config,
        s2_config,
        s1_path,
        s2_path,
        s1_name,
        s2_name,
        area_filter,
        output_fmt,
        output_path,
    ):
        """Run a system/scenario comparison report.

        This command runs a system comparison report using either an existing configuration
        file or command line parameters. It generates visualizations comparing key metrics
        between two different power system scenarios, such as generation mix, emissions,
        costs, etc.

        Examples:
            gat run system_comparison --report-config=my_config.yaml
            gat run system_comparison --s1-config=s1.yaml --s2-config=s2.yaml --output-fmt=pptx
        """
        # Create an args object with the command set to "run"
        args = type(
            "Args",
            (),
            {
                "command": "run",
                "report_config": report_config,
                "s1_config": s1_config,
                "s2_config": s2_config,
                "s1_path": s1_path,
                "s2_path": s2_path,
                "s1_name": s1_name,
                "s2_name": s2_name,
                "area_filter": area_filter,
                "output_fmt": output_fmt,
                "output_path": output_path,
                "save_config": None,  # No need to save config when running
            },
        )

        try:
            main_with_args(args)
            click.echo("System comparison report completed successfully")
        except Exception as e:
            click.echo(f"Error running system comparison: {e}", err=True)


if __name__ == "__main__":
    main()
