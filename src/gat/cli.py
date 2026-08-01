"""
GAT Command Line Entry Point

Author: Micah Webb
Date: 2025-06-03

Description: This file serves as the entry point to the Grid Analysis Toolkit command line interface.

The CLI is designed to be lightweight - heavy imports are deferred until commands are actually used.
"""

import click

# ============================================================
# Lazy loading utilities
# ============================================================


class LazyGroup(click.Group):
    """
    A Click group that lazily loads subcommands.
    This avoids importing heavy modules until they're actually needed.
    """

    def __init__(self, *args, lazy_subcommands=None, **kwargs):
        super().__init__(*args, **kwargs)
        # lazy_subcommands is a dict of {name: import_path}
        self._lazy_subcommands = lazy_subcommands or {}

    def list_commands(self, ctx):
        base = super().list_commands(ctx)
        lazy = list(self._lazy_subcommands.keys())
        return sorted(base + lazy)

    def get_command(self, ctx, cmd_name):
        if cmd_name in self._lazy_subcommands:
            return self._load_lazy_command(cmd_name)
        return super().get_command(ctx, cmd_name)

    def _load_lazy_command(self, cmd_name):
        import_path = self._lazy_subcommands[cmd_name]
        module_path, attr_name = import_path.rsplit(".", 1)

        try:
            import importlib

            module = importlib.import_module(module_path)
            return getattr(module, attr_name)
        except (ImportError, AttributeError) as e:
            click.echo(f"Warning: Could not load command '{cmd_name}': {e}", err=True)
            return None


# ============================================================
# Main CLI Group
# ============================================================


@click.group()
@click.version_option(package_name="gat")
@click.option("--verbose", "-v", is_flag=True, help="Show info-level logs")
@click.option("--debug", is_flag=True, help="Show debug-level logs")
@click.pass_context
def cli(ctx, verbose, debug):
    """Grid Analysis Toolkit (GAT) CLI.

    A toolkit for wrangling data for Bulk Grid Dispatch and Transmission Analysis.
    """
    ctx.ensure_object(dict)

    # Quiet logging by default for CLI; --verbose or --debug to restore
    from gat.logging_config import setup_cli_logging

    level = "DEBUG" if debug else "INFO" if verbose else "ERROR"
    setup_cli_logging(level)


# ============================================================
# Init Command Group (lazy loaded)
# ============================================================


@cli.group("init", cls=LazyGroup)
def init():
    """Initialize a Scenario, Report or Extraction configuration file.

    Types of configurations:

    REPORTS:

    - system_comparison (Compares the capacity of two systems)
    - scenario_single (Standard System + Simulation plots)

    SCENARIO:

    - sienna
    - plexos
    - reeds
    """
    pass


@init.command("report")
@click.option("--type", "report_type", help="Type of report to initialize")
def init_report(report_type):
    """Initialize a report configuration."""
    # Lazy import
    from gat.logging_config import setup_logging

    setup_logging()

    click.echo(f"Initializing report configuration (type={report_type})")
    # TODO: Implement report initialization


# ============================================================
# Run Command Group (lazy loaded)
# ============================================================


@cli.group("run", cls=LazyGroup)
def run():
    """Run reports to generate visualizations and analysis.

    Available reports are dynamically discovered from the reports package.
    """
    pass


@run.command("report")
@click.argument("config_path", type=click.Path(exists=True))
@click.option("--output", "-o", help="Output directory")
def run_report(config_path, output):
    """Run a report from a configuration file."""
    # Lazy import - only load heavy modules when command is executed
    from gat.logging_config import setup_logging

    setup_logging(output_dir=output)

    click.echo(f"Running report from {config_path}")
    # TODO: Implement report running


# ============================================================
# Register lightweight commands directly
# ============================================================

# Import and register project/source commands (these are lightweight)
from gat.cli_projects import config_cmd, projects, sources
from gat.cli_projects_v1 import project
from gat.cli_plot import plot_cmd
from gat.cli_server import server, push_cmd, scenarios_cmd, query_cmd

cli.add_command(projects)
cli.add_command(sources)
cli.add_command(config_cmd, name="config")
cli.add_command(project)  # v1.0 project management commands
cli.add_command(plot_cmd, name="plot")
cli.add_command(server)
cli.add_command(push_cmd, name="push")
cli.add_command(scenarios_cmd, name="scenarios")
cli.add_command(query_cmd, name="query")


# ============================================================
# Lazy report command registration
# ============================================================


def _register_report_commands_lazy():
    """
    Register report commands lazily.
    Only called when init or run subcommands need the report plugins.
    """
    import importlib
    import pkgutil

    from loguru import logger

    try:
        from gat import reports

        for _, name, _ in pkgutil.iter_modules(reports.__path__):
            try:
                module_name = f"gat.reports.{name}"
                module = importlib.import_module(module_name)

                # Register init commands
                if hasattr(module, "register_commands") and callable(
                    module.register_commands
                ):
                    logger.debug(f"Registering commands from {module_name}")
                    module.register_commands(init)

                # Register run commands
                if hasattr(module, "register_run_commands") and callable(
                    module.register_run_commands
                ):
                    logger.debug(f"Registering run commands from {module_name}")
                    module.register_run_commands(run)

            except ImportError as e:
                logger.debug(f"Skipping report module {name}: {e}")
            except Exception as e:
                logger.warning(f"Failed to register commands from {name}: {e}")
    except ImportError:
        # reports module not available
        pass


# Create a flag to track if report commands have been registered
_reports_registered = False


def _ensure_reports_registered():
    """Ensure report commands are registered (called lazily)."""
    global _reports_registered
    if not _reports_registered:
        _register_report_commands_lazy()
        _reports_registered = True


# Override the init and run group invoke to lazily load report commands
_original_init_invoke = init.invoke
_original_run_invoke = run.invoke


def _init_invoke_with_lazy_load(ctx):
    _ensure_reports_registered()
    return _original_init_invoke(ctx)


def _run_invoke_with_lazy_load(ctx):
    _ensure_reports_registered()
    return _original_run_invoke(ctx)


init.invoke = _init_invoke_with_lazy_load
run.invoke = _run_invoke_with_lazy_load


if __name__ == "__main__":
    cli()
