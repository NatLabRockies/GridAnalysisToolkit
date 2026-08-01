"""
GAT - Grid Analysis Toolkit

A toolkit for wrangling data for Bulk Grid Dispatch and Transmission Analysis.
"""

__author__ = "Micah Webb"
__email__ = "micah.webb@nlr.gov"

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"


# Lazy imports - these are loaded only when accessed
def __getattr__(name):
    """Lazy import mechanism for heavy modules."""
    if name == "load":
        from .loader import load

        return load
    elif name == "load_scenario_only":
        from .loader import load_scenario_only

        return load_scenario_only
    elif name == "load_palette_only":
        from .loader import load_palette_only

        return load_palette_only
    elif name == "load_scenario":
        from .core import load_scenario

        return load_scenario
    elif name == "scenario_from_config":
        from .utils import scenario_from_config

        return scenario_from_config
    elif name == "setup_logging":
        from .logging_config import setup_logging

        return setup_logging
    elif name == "SiennaScenario":
        from .scenariohandlers import SiennaScenario

        return SiennaScenario
    elif name == "PlexosScenario":
        from .scenariohandlers import PlexosScenario

        return PlexosScenario
    elif name == "ReEDsScenario":
        from .scenariohandlers import ReEDsScenario

        return ReEDsScenario
    elif name == "BaseScenario":
        from .scenariohandlers import BaseScenario

        return BaseScenario
    elif name == "MultiScenario":
        from .scenariohandlers import MultiScenario

        return MultiScenario
    elif name == "Scenario":
        from .scenario import Scenario

        return Scenario
    elif name == "GATDatabase":
        from .backends import GATDatabase

        return GATDatabase
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# Define what's available for `from gat import *`
__all__ = [
    "__version__",
    "__author__",
    "__email__",
    "load",
    "load_scenario_only",
    "load_palette_only",
    "load_scenario",
    "scenario_from_config",
    "setup_logging",
    "SiennaScenario",
    "PlexosScenario",
    "ReEDsScenario",
    "BaseScenario",
    "MultiScenario",
    "Scenario",
    "GATDatabase",
]
