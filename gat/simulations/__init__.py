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
"""

# Base classes for plugin development
from .base import BaseSimulationParser
from .generic_aggregator import SimulationAggregator

# Sienna-specific implementations
from .sienna import (
    SiennaModelConfig,
    SiennaSimulationConfig,
    SiennaSimulationParser,
)

# Plexos-specific implementations
from .plexos_duckdb import PlexosDuckDBSimulation
from .plexos_v1 import PlexosSimulation

# Utilities
from .utils import block_combination_strategy, dedup_slices, resolve_compositions

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
