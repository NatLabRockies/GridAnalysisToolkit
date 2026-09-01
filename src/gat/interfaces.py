"""Abstract interfaces for GAT v1.0.0 extension developers.

Extension developers implement BaseSystem and BaseSimulation to support
a new power system modeling tool. These interfaces are generic — they
expose arbitrary named datasets via list_datasets() / get_dataset()
rather than hardcoding data types like "generation" or "load".

Composed datasets (like "generation" = union of multiple raw datasets)
are defined via DatasetComposition and also appear in list_datasets().
Category maps (technology groupings, regional mappings, etc.) enable
flexible GROUP BY operations in DuckDB.

Users interact with the higher-level Scenario class, which composes
a BaseSystem + BaseSimulation together.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from .categories import CategoryMap
from .datasets import DatasetComposition, DatasetInfo


class BaseSystem(ABC):
    """Parses a power system definition into named datasets.

    Each dataset is a flat DataFrame: entity_id | property_1 | property_2 | ...
    Numeric columns should use float32 to reduce memory consumption.

    Extension developers must implement list_datasets() and get_dataset().
    They may optionally provide default category maps and compositions.

    Example datasets a Sienna implementation might expose:
        - ThermalStandard: name, bus, area, prime_mover, fuel, capacity_mw
        - RenewableDispatch: name, bus, area, prime_mover, capacity_mw
        - Bus: name, area, latitude, longitude
        - Line: name, from_bus, to_bus, rating_mw
        - generators (composed): union of all generator component types
    """

    @abstractmethod
    def list_datasets(self) -> list[DatasetInfo]:
        """Return metadata about all available system datasets.

        Should include both raw datasets (parsed from source files) and
        developer-defined compositions (unions of raw datasets).
        """

    @abstractmethod
    def get_dataset(self, name: str) -> pd.DataFrame:
        """Return the named dataset as a flat DataFrame.

        For composed datasets, returns the concatenation of source datasets
        with no aggregation.
        """

    def get_default_category_maps(self) -> list[CategoryMap]:
        """Return developer-provided category maps derived from system data.

        Examples: generator→area (from bus→area relationship),
        generator→fuel (from system component data).
        """
        return []

    def get_default_compositions(self) -> list[DatasetComposition]:
        """Return developer-provided dataset compositions.

        Example: "generators" = union of ThermalStandard, RenewableDispatch, etc.
        """
        return []

    def get_branch_ratings(self) -> dict[str, float]:
        """Return a mapping of branch entity names to their MW ratings.

        Used by line_loading() to compute loading as a percentage of rating.
        The mapping should include all branch/line/interchange entity types
        that appear in flow simulation datasets.

        Returns:
            Dict mapping entity name to rating in MW.
        """
        return {}

    def get_bus_coordinates(self) -> pd.DataFrame:
        """Return bus name, UUID, latitude, longitude as a DataFrame.

        Used during ingestion to store geographic coordinates in DuckDB
        alongside the system data. Returns empty DataFrame if coordinates
        are not available.
        """
        return pd.DataFrame(columns=["name", "UUID", "latitude", "longitude"])


class BaseSimulation(ABC):
    """Parses simulation results into named timeseries datasets.

    Raw format: rows = timestamps (DatetimeIndex), columns = entity names,
    values = float32. This is the natural output of most parsers.

    Composed datasets are materialized during ingestion as transposed tables
    (entity_id rows × timestamp columns) for efficient GROUP BY.

    Extension developers must implement list_datasets() and get_dataset().
    They may optionally provide default category maps and compositions.

    Example datasets a Sienna implementation might expose:
        - ActivePowerVariable__ThermalStandard: timeseries per generator
        - ActivePowerVariable__RenewableDispatch: timeseries per generator
        - ActivePowerTimeSeriesParameter__StandardLoad: timeseries per load
        - FlowActivePowerVariable__Line: timeseries per line
        - generation (composed): union of all generation datasets
        - load (composed): union of all load datasets
    """

    @abstractmethod
    def list_datasets(self) -> list[DatasetInfo]:
        """Return metadata about all available simulation datasets.

        Should include both raw datasets (parsed from simulation files) and
        developer-defined compositions (unions of raw datasets).
        """

    @abstractmethod
    def get_dataset(self, name: str) -> pd.DataFrame:
        """Return the named dataset as a DataFrame.

        Raw datasets: rows=timestamps (DatetimeIndex), columns=entity names,
        values=float32.

        Composed datasets: same format — concatenates columns from source
        datasets (no aggregation).
        """

    def get_default_category_maps(self) -> list[CategoryMap]:
        """Return developer-provided category maps."""
        return []

    def get_default_compositions(self) -> list[DatasetComposition]:
        """Return developer-provided dataset compositions.

        Example: "generation" = union of ActivePowerVariable__ThermalStandard,
        ActivePowerVariable__RenewableDispatch, etc.
        """
        return []

    @classmethod
    def from_paths(
        cls, paths: str | Path | list[str | Path], **kwargs
    ) -> "BaseSimulation":
        """Construct from one or more partition files (e.g. weekly/monthly
        chunks of one logical simulation, submitted in parallel) treated
        as a single combined simulation.

        Default: instantiate ``cls(path, **kwargs)`` once per path and
        combine their datasets via
        ``gat.simulations.multi_file.MultiFileSimulation`` — free for any
        subclass whose constructor takes a single file path, which covers
        most extensions, without them needing to implement multi-file
        support themselves.

        Override this when your format combines through a different
        mechanism than "N single-file objects + pandas concat" — e.g. SQL
        ATTACH across converted files (see
        ``PlexosDuckDBSimulation.from_paths``).
        """
        path_list = [paths] if isinstance(paths, (str, Path)) else list(paths)

        if len(path_list) == 1:
            return cls(path_list[0], **kwargs)

        from .simulations.multi_file import MultiFileSimulation

        return MultiFileSimulation(cls, path_list, **kwargs)
