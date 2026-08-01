"""CLI commands for GAT Plot — direct standard plot generation.

Provides `gat plot` for generating standard plots.
Supports both direct invocation (`gat plot monthly-dispatch`) and
an interactive selector (`gat plot`).
"""

import click
from loguru import logger

# Maps CLI-friendly names to (plot_function_name, description, handler_kwargs)
STANDARD_PLOTS = {
    "monthly-dispatch": {
        "description": "Monthly system generation dispatch (stacked bar)",
        "function": "plot_monthly_system_dispatch",
    },
    "total-dispatch": {
        "description": "Total system generation mix (donut chart)",
        "function": "plot_total_system_dispatch",
    },
    "timeseries-dispatch": {
        "description": "System dispatch over time (stacked area)",
        "function": "plot_system_dispatch_timeseries",
    },
    "area-dispatch-monthly": {
        "description": "Monthly dispatch by area/region (stacked bars)",
        "function": "plot_monthly_area_dispatch",
    },
    "area-dispatch-total": {
        "description": "Total dispatch by area (stacked bar)",
        "function": "plot_total_area_dispatch",
    },
    "demand-windows": {
        "description": "Peak and minimum demand windows (stacked area)",
        "function": "plot_minmax_system_demand_windows",
    },
    "curtailment-monthly": {
        "description": "Monthly VRE curtailment (stacked bar)",
        "function": "plot_monthly_system_curtailment",
    },
    "curtailment-total": {
        "description": "Total VRE curtailment (donut chart)",
        "function": "plot_total_system_curtailment",
    },
    "area-demand-windows": {
        "description": "Peak and minimum demand windows by area",
        "function": "plot_minmax_area_demand_windows",
    },
    "mean-hourly-area": {
        "description": "Mean hourly dispatch profile by area",
        "function": "plot_mean_hourly_area",
    },
    "net-load-min-area": {
        "description": "Net load minimum window by area",
        "function": "plot_net_load_min_area",
    },
}


def _run_plot(scenario, plot_name: str, backend: str = None):
    """Execute a standard plot by CLI name."""
    from gat.quickplots.generation_plots import (
        plot_mean_hourly_area,
        plot_minmax_area_demand_windows,
        plot_minmax_system_demand_windows,
        plot_monthly_area_dispatch,
        plot_monthly_system_curtailment,
        plot_monthly_system_dispatch,
        plot_net_load_min_area,
        plot_total_area_dispatch,
        plot_total_system_curtailment,
        plot_total_system_dispatch,
    )

    plot_map = {
        "monthly-dispatch": plot_monthly_system_dispatch,
        "total-dispatch": plot_total_system_dispatch,
        "area-dispatch-monthly": plot_monthly_area_dispatch,
        "area-dispatch-total": plot_total_area_dispatch,
        "demand-windows": plot_minmax_system_demand_windows,
        "curtailment-monthly": plot_monthly_system_curtailment,
        "curtailment-total": plot_total_system_curtailment,
        "area-demand-windows": plot_minmax_area_demand_windows,
        "mean-hourly-area": plot_mean_hourly_area,
        "net-load-min-area": plot_net_load_min_area,
    }

    fn = plot_map.get(plot_name)
    if fn is None:
        # Handle timeseries-dispatch separately (not a registered @plot_function)
        if plot_name == "timeseries-dispatch":
            from gat.quickplots.core import plot_stacked_component_area

            dispatch = scenario.get_system_dispatch(include_charging=False)
            plot_stacked_component_area(
                dispatch,
                include_total_load=False,
                include_native_load=False,
                include_net_load=False,
                backend=backend,
            )
            return

        raise click.ClickException(f"Unknown plot: {plot_name}")

    kwargs = {}
    if backend:
        kwargs["backend"] = backend
    fn(scenario, **kwargs)


def _interactive_select():
    """Simple interactive plot selector using arrow keys or numbered list."""
    names = list(STANDARD_PLOTS.keys())

    click.echo("\n  Available plots:\n")
    for i, name in enumerate(names, 1):
        desc = STANDARD_PLOTS[name]["description"]
        click.echo(f"  {i:>2}. {name:<25} {desc}")
    click.echo()

    while True:
        choice = click.prompt(
            "  Select a plot (number or name)", default="", show_default=False
        )
        if not choice:
            return None

        # Try as number
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(names):
                return names[idx]
        except ValueError:
            pass

        # Try as name (partial match)
        matches = [n for n in names if choice.lower() in n.lower()]
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            click.echo(f"  Ambiguous: {', '.join(matches)}")
        else:
            click.echo(f"  Unknown plot: {choice}")


@click.command("plot")
@click.argument("name", required=False, default=None)
@click.option(
    "--list", "-l", "list_plots", is_flag=True, help="List available standard plots"
)
@click.option("--project", "-p", default=None, help="Project ID")
@click.option("--scenario", "-s", default=None, help="Scenario ID")
@click.option("--backend", "-b", default=None, help="Plot backend: static, interactive")
@click.option(
    "--server", "server_url", default=None, help="GAT server URL for remote data"
)
def plot_cmd(name, list_plots, project, scenario, backend, server_url):
    """Generate standard plots directly.

    \b
    Run with no arguments for an interactive plot selector, or specify
    a plot name to generate it directly.

    \b
    Examples:
        gat plot                          # interactive selector
        gat plot --list                   # list available plots
        gat plot monthly-dispatch         # generate monthly dispatch chart
        gat plot total-dispatch -b interactive  # plotly backend
    """
    if list_plots:
        click.echo("\n  Available standard plots:\n")
        for cli_name, info in STANDARD_PLOTS.items():
            click.echo(f"    {cli_name:<25} {info['description']}")
        click.echo(
            f"\n  Usage: gat plot <name> [-b backend] [-p project] [-s scenario]\n"
        )
        return

    if name is None:
        name = _interactive_select()
        if name is None:
            return

    if name not in STANDARD_PLOTS:
        # Fuzzy match
        matches = [n for n in STANDARD_PLOTS if name.lower() in n.lower()]
        if len(matches) == 1:
            name = matches[0]
        else:
            raise click.ClickException(
                f"Unknown plot '{name}'. Run `gat plot --list` to see available plots."
            )

    from gat.loader import load

    scenario_obj, _palette, _manager = load(
        project=project,
        scenario=scenario,
        verbose=False,
        server_url=server_url,
    )

    click.echo(f"\n  Generating: {STANDARD_PLOTS[name]['description']}...\n")
    _run_plot(scenario_obj, name, backend=backend)
