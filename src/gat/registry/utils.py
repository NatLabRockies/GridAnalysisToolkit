"""
Utilities for working with GAT plugins and plot functions.
"""

import os
import inspect
import matplotlib.pyplot as plt
from typing import Dict, Any, Callable, Optional, Tuple, Generator, Union, List
from loguru import logger


def execute_plot(
    plot_func: Callable,
    scenario: Any,
    plot_kwargs: Dict[str, Any] = None,
    output_path: Optional[str] = None,
    dpi: int = 200,
    save_data: bool = False
) -> Optional[Tuple[str, Any, Optional[Any]]]:
    """
    Execute a plot function with error handling.

    Args:
        plot_func: The plotting function to execute
        scenario: The scenario object to pass to the plot function
        plot_kwargs: Additional keyword arguments to pass to the plot function
        output_path: If provided, save the plot to this path
        dpi: DPI for saved images
        save_data: Whether to save the plot data to a CSV file

    Returns:
        If the plot function is a generator, None (plots are saved individually)
        Otherwise, a tuple of (name, matplotlib_axis, dataframe) where dataframe may be None
    """
    if plot_kwargs is None:
        plot_kwargs = {}

    try:
        # Check if it's a generator function
        if inspect.isgeneratorfunction(plot_func):
            # Handle generator function
            for result in plot_func(scenario, **plot_kwargs):
                # Unpack the result - might be (name, ax) or (name, ax, df)
                if len(result) == 3:
                    name, ax, df = result
                else:
                    name, ax = result
                    df = None

                if output_path:
                    # Process each yielded figure
                    output_file = os.path.join(output_path, f"{name}.png")
                    output_dir = os.path.dirname(output_file)

                    os.makedirs(output_dir, exist_ok=True)
                    plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
                    plt.close(ax.figure)

                    # Save dataframe if available and requested
                    if save_data and df is not None:
                        data_file = os.path.join(output_path, f"{name}.csv")
                        df.to_csv(data_file)
                        logger.info(f"Saved plot data to {data_file}")


            return None
        else:
            # Handle regular function
            result = plot_func(scenario, **plot_kwargs)

            # Unpack the result - might be (name, ax) or (name, ax, df)
            if len(result) == 3:
                name, ax, df = result
            else:
                name, ax = result
                df = None

            if output_path:
                output_file = os.path.join(output_path, f"{name}.png")
                output_dir = os.path.dirname(output_file)
                os.makedirs(output_dir, exist_ok=True)
                plt.savefig(output_file, dpi=dpi, bbox_inches='tight')
                plt.close(ax.figure)

                # Save dataframe if available and requested
                if save_data and df is not None:
                    data_file = os.path.join(output_path, f"{name}.csv")
                    df.to_csv(data_file)
                    logger.info(f"Saved plot data to {data_file}")

            return (name, ax, df) if df is not None else (name, ax, None)
    except Exception as e:
        plt.close()
        logger.error(f"Error executing plot function {plot_func.__name__}: {e}")
        return None


def get_plot_options(plot_func: Callable) -> Dict[str, Any]:
    """
    Get the configurable options for a plot function.

    Args:
        plot_func: The plot function to analyze

    Returns:
        Dictionary of parameter names and their default values (if any)
    """
    options = {}
    sig = inspect.signature(plot_func)

    # Skip the first parameter (scenario)
    for name, param in list(sig.parameters.items())[1:]:
        # Skip **kwargs
        if param.kind == param.VAR_KEYWORD:
            continue

        # Get default value if available
        if param.default != param.empty:
            options[name] = param.default
        else:
            options[name] = None

    return options


def generate_plot_config(plot_func: Callable) -> Dict[str, Any]:
    """
    Generate a configuration dictionary for a plot function.

    Args:
        plot_func: The plot function to analyze

    Returns:
        Configuration dictionary with metadata about the plot
    """
    sig = inspect.signature(plot_func)
    options = get_plot_options(plot_func)

    # Get the first parameter type (scenario type)
    first_param = next(iter(sig.parameters.values()), None)
    scenario_type = "Unknown"
    if first_param and first_param.annotation != inspect.Parameter.empty:
        scenario_type = first_param.annotation.__name__ if hasattr(first_param.annotation, '__name__') else str(first_param.annotation)

    # Get docstring
    docstring = inspect.getdoc(plot_func) or "No description available"

    # Create config
    config = {
        "name": plot_func.__name__,
        "description": docstring.split("\n")[0] if docstring else "No description",
        "scenario_type": scenario_type,
        "options": options,
        "enabled": True if not options else False,  # Disable by default if it requires options
        "module": plot_func.__module__
    }

    return config