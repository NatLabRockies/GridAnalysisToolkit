# gat/datahelpers/base_system.py
"""
Base system abstraction for GAT.

Defines the abstract interface for reading system files from different
simulation platforms (Sienna, ReEDS, Plexos, etc.). This abstraction
enables palette auto-generation and consistent system data access across
different simulation types.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd
from pydantic import BaseModel


class SystemInfo(BaseModel):
    """Basic information about a power system."""

    name: Optional[str] = None
    description: Optional[str] = None
    base_power: Optional[float] = None  # MVA base
    data_format_version: Optional[str] = None
    num_generators: Optional[int] = None
    num_buses: Optional[int] = None
    num_loads: Optional[int] = None


class GeneratorCategory(BaseModel):
    """
    Information about a generator category/type.

    Used for palette generation - each category typically maps to
    a display category in the palette.
    """

    name: str  # The category name (e.g., "Solar_PV", "Gas_CT")
    display_name: Optional[str] = None  # Human-readable name
    fuel_type: Optional[str] = None  # Fuel type if applicable
    prime_mover: Optional[str] = None  # Prime mover type if applicable
    technology: Optional[str] = None  # Technology classification
    count: int = 0  # Number of generators in this category
    total_capacity: Optional[float] = None  # Total capacity in MW
    is_vre: bool = False  # Variable Renewable Energy flag
    is_storage: bool = False  # Storage flag
    is_curtailable: bool = False  # Can be curtailed


class LoadCategory(BaseModel):
    """Information about a load category/type."""

    name: str
    display_name: Optional[str] = None
    is_flexible: bool = False  # Flexible/dispatchable load
    is_storage_charging: bool = False  # Storage charging load
    count: int = 0
    total_demand: Optional[float] = None  # Total demand in MW


class BaseSystem(ABC):
    """
    Abstract base class for system file parsers.

    Defines the interface for reading system data from different
    simulation platforms. Implementations should focus on extracting
    metadata and categories for palette generation, not detailed
    time-series data.

    Example usage:
        system = SiennaSystem("path/to/system.json")
        categories = system.list_generator_categories()
        info = system.get_system_info()
    """

    def __init__(self, system_path: str):
        """
        Initialize the system parser.

        Args:
            system_path: Path to the system file

        Raises:
            FileNotFoundError: If system file doesn't exist
            ValueError: If system file is invalid
        """
        self.system_path = Path(system_path)
        if not self.system_path.exists():
            raise FileNotFoundError(f"System file not found: {system_path}")

    @abstractmethod
    def get_system_info(self) -> SystemInfo:
        """
        Get basic system information.

        Returns:
            SystemInfo with system metadata
        """
        pass

    @abstractmethod
    def list_generator_categories(self) -> List[GeneratorCategory]:
        """
        List all generator categories in the system.

        Returns:
            List of GeneratorCategory instances with metadata

        Note:
            This should identify unique categories based on the simulation
            platform's conventions. For Sienna, this might be based on
            generator type + fuel type. For ReEDS, it might be technology
            classes.
        """
        pass

    @abstractmethod
    def list_load_categories(self) -> List[LoadCategory]:
        """
        List all load categories in the system.

        Returns:
            List of LoadCategory instances

        Note:
            Some systems may not have explicit load categories.
            Return empty list if not applicable.
        """
        pass

    @abstractmethod
    def get_generator_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """
        Get detailed generator data.

        Args:
            category: Optional category filter. If None, return all generators.

        Returns:
            DataFrame with generator metadata including:
            - name: Generator name
            - category: Generator category
            - capacity: Installed capacity (MW)
            - fuel_type: Fuel type
            - technology: Technology type
            - bus: Bus/node connection
            - Any other platform-specific fields

        Note:
            Column names should be standardized across implementations
            where possible.
        """
        pass

    @abstractmethod
    def get_load_data(self, category: Optional[str] = None) -> pd.DataFrame:
        """
        Get detailed load data.

        Args:
            category: Optional category filter

        Returns:
            DataFrame with load metadata
        """
        pass

    def list_datasets(self) -> Dict[str, str]:
        """
        List all available datasets in the system file.

        Returns:
            Dictionary mapping friendly names to internal dataset paths/keys
            Format: {friendly_name: dataset_type}

        Note:
            Default implementation provides common datasets based on the
            abstract methods. Override to provide platform-specific datasets
            or additional data types.

        Example:
            {
                "generators": "generator_data",
                "loads": "load_data",
                "generator_categories": "generator_categories",
                "load_categories": "load_categories"
            }
        """
        datasets = {
            "generators": "generator_data",
            "loads": "load_data",
            "generator_categories": "generator_categories",
            "load_categories": "load_categories",
            "system_info": "system_info",
        }
        return datasets

    def get_dataset(self, key: str, **kwargs) -> pd.DataFrame:
        """
        Retrieve a dataset from the system file.

        Args:
            key: Dataset key (from list_datasets()) or dataset type
            **kwargs: Additional arguments passed to underlying methods
                     (e.g., category filter)

        Returns:
            pandas DataFrame with requested system data

        Raises:
            KeyError: If the key doesn't exist
            ValueError: If the dataset cannot be retrieved

        Example:
            # Get all generators
            df = system.get_dataset("generators")

            # Get generators for a specific category
            df = system.get_dataset("generators", category="Solar_PV")

        Note:
            This provides a unified interface for accessing system data,
            similar to the simulation parser interface.
        """
        # Map dataset keys to methods
        dataset_methods = {
            "generators": self.get_generator_data,
            "generator_data": self.get_generator_data,
            "loads": self.get_load_data,
            "load_data": self.get_load_data,
            "generator_categories": self._get_generator_categories_as_df,
            "load_categories": self._get_load_categories_as_df,
            "system_info": self._get_system_info_as_df,
        }

        if key not in dataset_methods:
            available = ", ".join(self.list_datasets().keys())
            raise KeyError(
                f"Dataset '{key}' not found. Available datasets: {available}"
            )

        method = dataset_methods[key]

        # Call the method - handle different signatures
        try:
            if key in ["generator_data", "generators", "load_data", "loads"]:
                # These methods accept optional keyword arguments
                return method(**kwargs)
            else:
                # These methods don't accept arguments
                return method()
        except Exception as e:
            raise ValueError(f"Failed to retrieve dataset '{key}': {e}")

    def get_datasets(self, *keys: str, **kwargs) -> Dict[str, pd.DataFrame]:
        """
        Retrieve multiple datasets at once.

        Args:
            *keys: One or more dataset keys
            **kwargs: Additional arguments passed to get_dataset

        Returns:
            Dictionary mapping keys to DataFrames
        """
        results = {}
        for key in keys:
            results[key] = self.get_dataset(key, **kwargs)
        return results

    def _get_generator_categories_as_df(self) -> pd.DataFrame:
        """Convert generator categories to DataFrame."""
        categories = self.list_generator_categories()
        if not categories:
            return pd.DataFrame()
        return pd.DataFrame([cat.dict() for cat in categories])

    def _get_load_categories_as_df(self) -> pd.DataFrame:
        """Convert load categories to DataFrame."""
        categories = self.list_load_categories()
        if not categories:
            return pd.DataFrame()
        return pd.DataFrame([cat.dict() for cat in categories])

    def _get_system_info_as_df(self) -> pd.DataFrame:
        """Convert system info to DataFrame."""
        info = self.get_system_info()
        return pd.DataFrame([info.dict()])

    def list_component_types(self) -> Set[str]:
        """
        List all component types in the system.

        Returns:
            Set of component type names

        Note:
            This is a convenience method that may not be needed for all
            implementations. Default returns empty set.
        """
        return set()

    def get_vre_categories(self) -> List[str]:
        """
        Get list of VRE (Variable Renewable Energy) category names.

        Returns:
            List of category names classified as VRE

        Note:
            Default implementation checks GeneratorCategory.is_vre flag.
            Override if platform has specific VRE identification logic.
        """
        categories = self.list_generator_categories()
        return [cat.name for cat in categories if cat.is_vre]

    def get_storage_categories(self) -> List[str]:
        """
        Get list of storage category names.

        Returns:
            List of category names classified as storage
        """
        categories = self.list_generator_categories()
        return [cat.name for cat in categories if cat.is_storage]

    def get_curtailable_categories(self) -> List[str]:
        """
        Get list of curtailable category names.

        Returns:
            List of category names that can be curtailed
        """
        categories = self.list_generator_categories()
        return [cat.name for cat in categories if cat.is_curtailable]

    def validate(self) -> List[str]:
        """
        Validate the system file and return any warnings.

        Returns:
            List of warning messages (empty if no issues)

        Note:
            Override to implement platform-specific validation.
        """
        warnings = []

        try:
            info = self.get_system_info()
            if info.num_generators == 0:
                warnings.append("System has no generators")
        except Exception as e:
            warnings.append(f"Failed to read system info: {e}")

        try:
            categories = self.list_generator_categories()
            if not categories:
                warnings.append("No generator categories found")
        except Exception as e:
            warnings.append(f"Failed to list generator categories: {e}")

        return warnings

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}('{self.system_path}')"
