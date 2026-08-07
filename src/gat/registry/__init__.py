"""
Plugin management system for GAT.

This module provides tools for registering, discovering, and managing plotting functions
that can be used with the GAT reporting system.
"""

import importlib
import inspect
from loguru import logger
import pkgutil
import sys
from functools import wraps
from typing import Dict, List, Callable, Set, Optional, Any, Union, Type
from pathlib import Path

# Dictionary to store registered plot functions
# Structure: {function_name: {"function": function_obj, "signature": signature_obj, "type": scenario_type}}
_registered_plots: Dict[str, Dict[str, Any]] = {}

# Track which plugin modules have been loaded
_loaded_modules: Set[str] = set()


def plot_function(
    scenario_type: Optional[str] = "BaseScenario", plot_type: Optional[str] = "system"
):
    """
    Decorator to register a function as a plot function for GAT.

    Args:
        scenario_type: The type of scenario this plot works with (e.g., "BaseScenario", "SiennaScenario")
                      Defaults to "BaseScenario" which means it works with any scenario.

        plot_type: The type of plot. o

    Returns:
        The decorated function

    Example:
        ::

            @plot_function("MultiScenario", "system")
            def plot_generation_capacities(multi_scenario, **kwargs):
                ...
    """

    def decorator(func: Callable) -> Callable:
        # Get function signature
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        # Verify function signature has at least one parameter (the scenario)
        if not params:
            logger.warning(
                f"Plot function {func.__name__} has no parameters. It should accept a scenario object."
            )
            return func

        # Register the function
        _registered_plots[func.__name__] = {
            "function": func,
            "signature": sig,
            "model_type": scenario_type,
            "plot_type": plot_type,
            "module": func.__module__,
        }

        # Log the registration
        logger.debug(f"Registered plot function: {func.__name__} for {scenario_type}")

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def discover_internal_plots() -> None:
    """Discover and register internal plotting functions."""
    logger.info("Discovering internal plot functions")

    # Discover built-in plotting modules
    from gat import quickplots

    # Load all modules in the quickplots package
    for _, name, _ in pkgutil.iter_modules(
        quickplots.__path__, f"{quickplots.__name__}."
    ):
        if name not in _loaded_modules:
            try:
                logger.debug(f"Loading internal plotting module: {name}")
                importlib.import_module(name)
                _loaded_modules.add(name)
            except Exception as e:
                logger.warning(f"Failed to load internal plotting module {name}: {e}")


def discover_external_plots() -> None:
    """Discover and register external plotting functions from entry points."""
    logger.info("Discovering external plot functions")

    try:
        # Find all entry points with the 'gat_ext' group
        for entry_point in importlib.metadata.entry_points().select(group="gat_ext"):
            if entry_point.name not in _loaded_modules:
                try:
                    logger.debug(f"Loading external plugin: {entry_point.name}")
                    plugin_module = entry_point.load()
                    _loaded_modules.add(entry_point.name)
                except Exception as e:
                    logger.warning(
                        f"Failed to load external plugin {entry_point.name}: {e}"
                    )
    except Exception as e:
        logger.warning(f"Error discovering external plugins: {e}")


def discover_all_plots() -> None:
    """Discover and register all available plotting functions."""
    discover_internal_plots()
    discover_external_plots()


def get_plots(
    scenario_type: Optional[str] = None, plot_type: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Get registered plot functions, optionally filtered by scenario type and plot type.

    Args:
        scenario_type: If provided, only return plots for this scenario type
        plot_type: If provided, only return plots for this plot type

    Returns:
        Dictionary of plot functions and their metadata
    """
    # Make sure plots have been discovered
    if not _registered_plots:
        discover_all_plots()

    # If no type filter, return all plots
    if scenario_type is None and plot_type is None:
        return _registered_plots

    filtered_plots = {}
    for name, info in _registered_plots.items():
        # Include if:
        # 1. No scenario_type filter OR it matches the scenario_type OR it's a base scenario
        # 2. AND (No plot_type filter OR it matches the plot_type)
        scenario_match = (
            scenario_type is None
            or info["model_type"] == scenario_type
            or info["model_type"] == "BaseScenario"
        )
        plot_match = plot_type is None or info["plot_type"] == plot_type

        if scenario_match and plot_match:
            filtered_plots[name] = info

    return filtered_plots


def get_plot_names(
    scenario_type: Optional[str] = None, plot_type: Optional[str] = None
) -> List[str]:
    """
    Get names of registered plot functions, optionally filtered by scenario type and plot type.

    Args:
        scenario_type: If provided, only return plot names for this scenario type
        plot_type: If provided, only return plot names for this plot type

    Returns:
        List of plot function names
    """
    plots = get_plots(scenario_type, plot_type)
    return list(plots.keys())


def get_plot_function(name: str) -> Optional[Callable]:
    """
    Get a registered plot function by name.

    Args:
        name: Name of the plot function

    Returns:
        The plot function or None if not found
    """
    plots = get_plots()
    if name in plots:
        return plots[name]["function"]
    return None
