"""
Standard system report.

This report generates standard visualizations for a single system scenario.
"""

from loguru import logger
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Union
import click
import yaml
import os
import matplotlib.pyplot as plt

from gat.models.scenario import ScenarioConfig, load_config
from gat import __version__, scenario_from_config
from gat.registry.utils import generate_plot_config
from gat.logging_config import setup_logging


class SystemReportConfig(BaseModel):
    """Configuration for standard system report."""

    model_type: str
    report_type: Optional[str] = (
        None  # 'generation', 'system', 'transmission', 'cost', 'emissions'
    )
    output_fmt: Union[str, List[str]] = "pptx"
    output_path: str = "./gat_scenario_report"
    output_plots: List[Dict[str, Any]] = Field(default_factory=list)
    dpi: int = 200
    plot_kwargs: Dict[str, Any] = {}
    save_data: bool = True
    scenario: ScenarioConfig
    # GAT version used to create this config
    gat_version: Optional[str] = __version__

    def __init__(self, **data):
        # Initialize first to ensure model_type is available
        super().__init__(**data)
        # Set default output_plots if not provided or empty
        if not data.get("output_plots"):
            logger.debug(
                f"No output_plots provided, discovering plots for model type: {self.model_type} and report type: {self.report_type}"
            )
            self.output_plots = discover_available_plots(
                self.model_type, self.report_type
            )
            logger.debug(f"Discovered {len(self.output_plots)} plot configurations")

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

            # Check if we need to discover plots
            if not self.output_plots:
                logger.info("Discovering plots before saving config")
                self.output_plots = discover_available_plots(
                    self.model_type, self.report_type
                )

            # Create a serializable dict
            config_dict = self.model_dump()

            # Make sure plot configurations are properly serialized
            for plot_config in config_dict["output_plots"]:
                # Ensure all values are serializable
                for key, value in list(plot_config.items()):
                    if callable(value) or value.__class__.__module__ != "builtins":
                        plot_config[key] = str(value)

            with open(path, "w") as f:
                yaml.dump(config_dict, f, sort_keys=False)

            logger.info(
                f"Configuration saved to {path} with {len(self.output_plots)} plot configurations"
            )
        except Exception as e:
            logger.error(f"Failed to save configuration to {path}: {e}")
            raise


def discover_available_plots(model_type=None, plot_type=None) -> List[Dict[str, Any]]:
    """Discovers available plot functions for BaseScenario objects and returns their configurations.

    Args:
        model_type: The type of model ('sienna', 'plexos', etc.)
        plot_type: The type of plot to filter by ('generation', 'system', 'transmission', 'cost', 'emissions')

    Returns:
        List[Dict[str, Any]]: List of plot configuration objects
    """
    try:
        from gat.registry import get_plot_names, get_plot_function, discover_all_plots

        discover_all_plots()

        logger.debug(
            f"Discovering plots for model type: {model_type}, plot type: {plot_type}"
        )

        # Get all plot functions that work with BaseScenario
        generic_plot_names = get_plot_names("BaseScenario", plot_type)
        logger.debug(
            f"Found {len(generic_plot_names)} generic plot names: {generic_plot_names}"
        )
        generic_plot_configs = []

        # Get model-specific plot functions if a model type is specified
        model_plot_names = []
        if model_type == "sienna":
            model_plot_names = get_plot_names("SiennaScenario", plot_type)
        elif model_type == "plexos":
            model_plot_names = get_plot_names("PlexosScenario", plot_type)

        logger.debug(
            f"Found {len(model_plot_names)} model-specific plot names: {model_plot_names}"
        )
        model_plot_configs = []

        # Generate config for each generic plot
        for plot_name in generic_plot_names:
            plot_func = get_plot_function(plot_name)
            if plot_func:
                config = generate_plot_config(plot_func)
                config["source"] = "generic"
                generic_plot_configs.append(config)

        # Generate config for each model-specific plot
        for plot_name in model_plot_names:
            plot_func = get_plot_function(plot_name)
            if plot_func:
                config = generate_plot_config(plot_func)
                config["source"] = model_type
                model_plot_configs.append(config)

        # Combine model-specific and generic plot configurations
        plot_configs = model_plot_configs + generic_plot_configs

        logger.info(f"Discovered {len(plot_configs)} plot configurations")
        return plot_configs

    except ImportError as e:
        logger.warning(f"Could not import plugin management system: {e}")
        return []


def run(config: SystemReportConfig):
    """
    Generate standard system report based on the provided configuration.

    Args:
        config: SystemReportConfig object containing scenario configuration
    """
    setup_logging(config.output_path)
    from gat.registry import get_plot_function, discover_all_plots
    from gat.registry.utils import execute_plot

    logger.info("Creating Scenario object")

    try:
        # Discover all plots
        discover_all_plots()

        # Create scenario object using the utility function
        scenario = scenario_from_config(config.scenario)

        # Create output directory if needed
        os.makedirs(config.output_path, exist_ok=True)

        # Check if output_plots is empty and try to populate it
        if not config.output_plots:
            logger.warning(
                "No plot configurations specified or discovered. Attempting to rediscover."
            )
            config.output_plots = discover_available_plots(
                config.model_type, config.report_type
            )
            if not config.output_plots:
                logger.error(
                    "No plot functions available. Check that plot plugins are properly registered."
                )
                return

        # Log which plots will be generated
        plot_names = [plot_config["name"] for plot_config in config.output_plots]
        logger.info(f"Generating the following plots: {plot_names}")

        # Execute each plot function
        for plot_config in config.output_plots:
            try:
                plot_name = plot_config["name"]

                # Get the plot function from the plugin system
                plot_func = get_plot_function(plot_name)

                if not plot_func:
                    logger.warning(
                        f"Plot function {plot_name} not found in plugin registry"
                    )
                    continue

                # Merge plot-specific options from the configuration with global plot_kwargs
                plot_options = config.plot_kwargs.copy()
                if "options" in plot_config and plot_config["options"]:
                    # Only include enabled options
                    for option_name, option_value in plot_config["options"].items():
                        if option_value is not None:
                            plot_options[option_name] = option_value

                logger.info(f"Generating plot: {plot_name}")

                # Execute the plot function

                result = execute_plot(
                    plot_func,
                    scenario,
                    plot_kwargs=plot_options,
                    output_path=config.output_path,
                    dpi=config.dpi,
                    save_data=config.save_data,
                )

                # Close the figure to prevent overlap issues
                if result is not None:
                    if len(result) == 3:
                        _, ax, _ = result
                    else:
                        _, ax = result
                    plt.close(ax.figure)

            except Exception as e:
                logger.error(
                    f"An unexpected error occurred while processing {plot_config.get('name', 'unknown plot')}: {e}"
                )
                continue

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
        logger.error(f"Failed to run system report: {e}")
        raise


def register_commands(init_group):
    """Register system standard report init commands with the init CLI group."""

    from gat.registry import _registered_plots, discover_all_plots

    discover_all_plots()

    available_plots = [
        v["plot_type"]
        for k, v in _registered_plots.items()
        if v["model_type"] != "MultiScenario"
    ]

    @init_group.command("single")
    @click.option(
        "--report-config", type=click.Path(), help="Path to a report configuration file"
    )
    @click.option(
        "--model-type",
        type=click.Choice(["sienna", "plexos"]),
        help="The underlying model type",
    )
    @click.option(
        "--report-type",
        type=click.Choice(available_plots),
        help="The type of report to generate",
    )
    @click.option(
        "--scenario-config",
        type=click.Path(exists=True),
        help="Path to scenario configuration file",
    )
    @click.option(
        "--system-path", type=click.Path(exists=True), help="Path to system data"
    )
    @click.option(
        "--simulation-paths", help="Comma-separated list of paths to simulation data"
    )
    @click.option("--display-name", help="The display name for the scenario")
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
    @click.option(
        "--save-data/--no-save-data", default=True, help="Save plot data to CSV files"
    )
    def single(
        report_config,
        model_type,
        report_type,
        scenario_config,
        system_path,
        simulation_paths,
        display_name,
        area_filter,
        output_fmt,
        output_path,
        save_config,
        save_data,
    ):
        """Initialize a new standard system report configuration."""
        if report_config:
            logger.info(f"Loading report configuration from {report_config}")
            config = SystemReportConfig.from_config(report_config)
        else:
            logger.info("Creating new report configuration from command line options")
            if not model_type:
                click.echo(
                    "Error: --model-type is required when creating a new configuration.",
                    err=True,
                )
                return

            if scenario_config:
                scen_config = load_config(scenario_config)
            elif system_path:
                scen_config = ScenarioConfig(
                    model_type=model_type,
                    system_path=system_path,
                    simulation_paths=(
                        simulation_paths.split(",") if simulation_paths else []
                    ),
                    display_name=display_name,
                    area_filter=area_filter.split(",") if area_filter else [],
                )
            else:
                click.echo(
                    "Error: Either --scenario-config or --system-path must be provided.",
                    err=True,
                )
                return

            config = SystemReportConfig(
                model_type=model_type,
                report_type=report_type,
                scenario=scen_config,
                output_fmt=output_fmt,
                output_path=output_path,
                save_data=save_data,
            )

        # Override with any provided command-line arguments
        if output_fmt:
            config.output_fmt = output_fmt
        if output_path:
            config.output_path = output_path
        if save_data is not None:
            config.save_data = save_data

        if save_config:
            logger.info(f"Saving configuration to {save_config}")
            config.save_config(save_config)
        else:
            # Print the configuration if not saving
            click.echo("\n--- Report Configuration ---")
            click.echo(yaml.dump(config.model_dump(), sort_keys=False))
            click.echo("---------------------------")
            click.echo("To save this configuration, use the --save-config option.")


def register_run_commands(run_group):
    """Register system standard report run commands with the run CLI group."""

    @run_group.command("single")
    @click.option(
        "--report-config",
        type=click.Path(exists=True),
        help="Path to a report configuration file",
    )
    @click.option(
        "--scenario-config",
        type=click.Path(exists=True),
        help="Path to scenario configuration file",
    )
    @click.option(
        "--system-path", type=click.Path(exists=True), help="Path to system data"
    )
    @click.option(
        "--simulation-paths", help="Comma-separated list of paths to simulation data"
    )
    @click.option("--display-name", help="The display name for the scenario")
    @click.option(
        "--area-filter",
        help="The areas to use in the underlying plots (comma-separated)",
    )
    @click.option(
        "--output-fmt", type=click.Choice(["dir", "pptx", "both"]), help="Output format"
    )
    @click.option("--output-path", type=click.Path(), help="Path for output files")
    @click.option(
        "--save-data/--no-save-data", default=True, help="Save plot data to CSV files"
    )
    def single(
        report_config,
        scenario_config,
        system_path,
        simulation_paths,
        display_name,
        area_filter,
        output_fmt,
        output_path,
        save_data,
    ):
        """Run the standard system report."""
        if report_config:
            logger.info(f"Loading report configuration from {report_config}")
            config = SystemReportConfig.from_config(report_config)
        elif scenario_config:
            logger.info(
                "Loading scenario configuration and creating default report config"
            )
            scen_config = load_config(scenario_config)
            config = SystemReportConfig(
                model_type=scen_config.model_type, scenario=scen_config
            )
        elif system_path:
            logger.info(
                "Creating new scenario and report configuration from command line options"
            )
            scen_config = ScenarioConfig(
                system_path=system_path,
                simulation_paths=(
                    simulation_paths.split(",") if simulation_paths else []
                ),
                display_name=display_name,
                area_filter=area_filter.split(",") if area_filter else [],
            )
            config = SystemReportConfig(
                model_type=scen_config.model_type, scenario=scen_config
            )
        else:
            click.echo(
                "Error: Must provide --report-config, --scenario-config, or --system-path.",
                err=True,
            )
            return

        # Override config with command-line options
        if output_fmt:
            config.output_fmt = output_fmt
        if output_path:
            config.output_path = output_path
        if save_data is not None:
            config.save_data = save_data

        logger.info("Starting report generation")
        run(config)
        logger.info("Report generation complete")
