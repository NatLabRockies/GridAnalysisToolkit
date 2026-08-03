"""
Simulation parsers and aggregators for GAT.

This module provides the core interfaces and implementations for reading
simulation results from various power system simulation tools.

Base Classes (for plugin developers):
--------------------------------------
- BaseSimulationParser: Abstract interface for single-file parsers
- SimulationAggregator: Generic aggregator for combining multiple files

Concrete Implementations:
-------------------------
- SiennaSimulationParser: Parser for Sienna/PowerSimulations.jl HDF5 files

Plugin Developer Guide:
-----------------------
To support a new simulation format:

1. Create a parser class inheriting from BaseSimulationParser
2. Implement required abstract methods:
   - simulation_models (property)
   - list_datasets()
   - get_dataset(key)
3. GAT automatically handles multi-file aggregation via SimulationAggregator

Example:
--------
    # Single file
    from gat.simulations import SiennaSimulationParser
    parser = SiennaSimulationParser("simulation.h5")
    datasets = parser.list_datasets()
    data = parser.get_dataset("generator_dispatch")

    # Multiple files (automatic aggregation)
    from gat.simulations import SimulationAggregator, SiennaSimulationParser
    aggregator = SimulationAggregator(
        file_paths=["sim1.h5", "sim2.h5", "sim3.h5"],
        parser_class=SiennaSimulationParser
    )
    data = aggregator.get_dataset("generator_dispatch")

Every name below is lazily imported on first access — constructing a
PlexosSimulation, for instance, never touches Sienna's h5py/polars
dependencies, and vice versa.
"""

_SIENNA_NAMES = {
    "SiennaModelConfig",
    "SiennaSimulationConfig",
    "SiennaSimulationParser",
}
_UTILS_NAMES = {"block_combination_strategy", "dedup_slices", "resolve_compositions"}


def __getattr__(name):
    if name == "BaseSimulationParser":
        from .base import BaseSimulationParser

        return BaseSimulationParser
    elif name == "SimulationAggregator":
        from .generic_aggregator import SimulationAggregator

        return SimulationAggregator
    elif name in _SIENNA_NAMES:
        from . import sienna

        return getattr(sienna, name)
    elif name == "PlexosDuckDBSimulation":
        from .plexos_duckdb import PlexosDuckDBSimulation

        return PlexosDuckDBSimulation
    elif name == "PlexosSimulation":
        from .plexos_v1 import PlexosSimulation

        return PlexosSimulation
    elif name in _UTILS_NAMES:
        from . import utils

        return getattr(utils, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # Base classes
    "BaseSimulationParser",
    "SimulationAggregator",
    # Sienna implementations
    "SiennaModelConfig",
    "SiennaSimulationConfig",
    "SiennaSimulationParser",
    # Plexos implementations
    "PlexosSimulation",
    "PlexosDuckDBSimulation",
    # Utilities
    "dedup_slices",
    "block_combination_strategy",
    "resolve_compositions",
]
