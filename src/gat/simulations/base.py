"""
Base simulation parser interface for GAT.

This module defines the abstract interface that all simulation parsers must implement.
Plugin developers should inherit from BaseSimulationParser to support their simulation format.

Key Concepts:
-------------
- **Single File Interface**: Each parser instance handles ONE simulation file
- **Dataset Discovery**: Parsers must provide methods to list and retrieve datasets
- **Model Selection**: Some simulations have multiple models (e.g., decision vs emulation)
- **Automatic Aggregation**: GAT automatically combines multiple files using SimulationAggregator
- **Aggregate Datasets**: Support for combining multiple raw datasets into logical groups

Plugin Developer Workflow:
--------------------------
1. Create a class that inherits from BaseSimulationParser
2. Implement the required abstract methods for reading a single simulation file
3. GAT handles everything else (parallel loading, combining files, deduplication)

Example:
--------
    class MySimulationParser(BaseSimulationParser):
        def __init__(self, file_path: str):
            super().__init__()
            self.file_path = file_path
            # Initialize file handle, read metadata, etc.

        def list_datasets(self) -> dict[str, str]:
            # Return {friendly_name: internal_path}
            return {"generator_dispatch": "/results/generators/power"}

        def get_dataset(self, key: str) -> pd.DataFrame:
            # Read and return dataset as DataFrame with datetime index
            return pd.read_csv(...)  # or read from HDF5, database, etc.
"""

import fnmatch
import warnings
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import pandas as pd

from gat.models.base import AggregateDataset, DatasetConfig, RawDataset


class BaseSimulationParser(ABC):
    """
    Abstract base class for simulation file parsers.

    Each parser instance should handle ONE simulation file. GAT will automatically
    handle combining multiple files using the SimulationAggregator class.

    Required Methods:
    -----------------
    - list_datasets(): Return available datasets with their keys
    - get_dataset(key): Return a specific dataset as a pandas DataFrame
    - simulation_models: Property listing available simulation models (if applicable)

    Optional Features:
    ------------------
    - Model selection for simulations with multiple model types
    - Custom metadata extraction
    - File validation

    Attributes:
    -----------
    _selected_model : Optional[Any]
        Currently selected simulation model (if applicable)
    """

    def __init__(self):
        """
        Initialize the parser.

        Subclasses should:
        1. Call super().__init__()
        2. Store the file path
        3. Open/validate the file
        4. Extract metadata (models, timestamps, etc.)
        """
        self._selected_model: Optional[Any] = None
        self._dataset_config: Optional[DatasetConfig] = None
        self._raw_datasets_cache: Optional[Dict[str, str]] = None

    @property
    def dataset_config(self) -> Optional[DatasetConfig]:
        """
        Get the dataset configuration for this parser.

        Returns:
            DatasetConfig instance if set, None otherwise
        """
        return self._dataset_config

    @dataset_config.setter
    def dataset_config(self, config: DatasetConfig):
        """
        Set the dataset configuration and validate it.

        Args:
            config: DatasetConfig instance with aggregate dataset definitions

        Raises:
            ValueError: If datasets don't match any raw datasets
        """
        if config.aggregates:
            # Validate dataset configs against available raw datasets
            available = list(self.list_raw_datasets().keys())
            config.validate_datasets(available)
        self._dataset_config = config
        # Clear cache when config changes
        self._raw_datasets_cache = None

    @property
    def selected_model(self) -> Optional[Any]:
        """
        Get the currently selected simulation model.

        Returns:
            Currently selected model object or None

        Note:
            Some simulation formats have multiple model types (e.g., Sienna has
            decision models and emulation models). If your format only has one
            model type, this can return None or a default model.
        """
        return self._selected_model

    @selected_model.setter
    def selected_model(self, model_name: Optional[str]):
        """
        Set the selected simulation model with validation.

        Args:
            model_name: Name of the model to select, or None for default

        Raises:
            ValueError: If model_name is not valid

        Note:
            Override this setter to implement model selection logic specific
            to your simulation format.
        """
        self._selected_model = model_name

    @property
    @abstractmethod
    def simulation_models(self) -> List[str]:
        """
        List available simulation models in this file.

        Returns:
            List of model names available in the simulation file

        Note:
            If your simulation format only has one model type, return a list
            with a single default name like ["default"] or ["main"].

        Example:
            For Sienna: ["ED", "UC", "emulation_model"]
            For simple formats: ["default"]
        """
        pass

    @abstractmethod
    def list_raw_datasets(self) -> Dict[str, str]:
        """
        List all raw datasets available in the simulation file.

        This method discovers the actual datasets in the simulation file
        (e.g., from H5 structure) without any filtering or configuration.

        Returns:
            Dictionary mapping dataset names to internal dataset paths/keys
            Format: {dataset_name: internal_path}

        Raises:
            ValueError: If no model is selected (for formats with multiple models)
            FileNotFoundError: If the file cannot be read

        Example:
            {
                "ActivePowerVariable__ThermalStandard": "/simulation/decision_models/UC/variables/ActivePowerVariable__ThermalStandard",
                "ActivePowerVariable__RenewableDispatch": "/simulation/decision_models/UC/variables/ActivePowerVariable__RenewableDispatch",
                "FlowActivePowerVariable__Line": "/simulation/decision_models/UC/variables/FlowActivePowerVariable__Line"
            }

        Note:
            - This is the raw view of simulation data
            - Subclasses must implement this to expose their file format
            - Keys should match the actual dataset identifiers in the file
        """
        pass

    def list_datasets(self) -> Dict[str, str]:
        """
        List all configured datasets.

        If dataset_config is set, returns the configured dataset names.
        Otherwise, falls back to listing raw datasets.

        Returns:
            Dictionary mapping dataset names to descriptions/types
            Format: {dataset_name: description}

        Example:
            {
                "generation": "AggregateDataset (2 patterns)",
                "flow": "AggregateDataset (1 pattern)",
                "specific_gen": "RawDataset"
            }
        """
        if self._dataset_config and self._dataset_config.aggregates:
            # Return configured datasets with type information
            result = {}
            for name, definition in self._dataset_config.aggregates.items():
                if isinstance(definition, RawDataset):
                    result[name] = "RawDataset"
                elif isinstance(definition, AggregateDataset):
                    result[name] = (
                        f"AggregateDataset ({len(definition.patterns)} patterns)"
                    )
                else:
                    result[name] = "Unknown"
            return result
        else:
            # Fall back to raw datasets
            return self.list_raw_datasets()

    @abstractmethod
    def get_raw_dataset(self, key: str) -> Optional[pd.DataFrame]:
        """
        Retrieve a raw dataset from the simulation file.

        This method retrieves data directly from the simulation file
        without any configuration-based transformations.

        Args:
            key: Raw dataset key or internal path

        Returns:
            pandas DataFrame with:
            - DateTime index representing simulation timestamps
            - Columns for each component (generators, loads, etc.)
            - Numeric values in native units (before scaling)
            Returns None if dataset cannot be retrieved.

        Raises:
            KeyError: If the key doesn't exist
            ValueError: If no model is selected (for multi-model formats)
            FileNotFoundError: If the file cannot be read

        Example:
            df = parser.get_raw_dataset("ActivePowerVariable__ThermalStandard")
            # Returns DataFrame with raw data from simulation

        Note:
            - Index MUST be DatetimeIndex for proper aggregation
            - Values are in native simulation units (often per-unit)
            - This is the base method that subclasses must implement
        """
        pass

    def get_dataset(
        self, key: str, base_power: Optional[float] = None
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve a dataset using the configured dataset definitions.

        If dataset_config is set and key is in dataset_configs, retrieves according
        to the configuration (RawDataset or AggregateDataset).
        Otherwise, falls back to get_raw_dataset().

        Args:
            key: Dataset name from dataset_configs or raw dataset key
            base_power: Optional base_power for scaling. If None, uses parser's default.

        Returns:
            pandas DataFrame with:
            - DateTime index representing simulation timestamps
            - Columns for each component (generators, loads, etc.)
            - Numeric values scaled according to configuration
            Returns None if dataset cannot be retrieved.

        Example:
            # With dataset_config set:
            df = parser.get_dataset("generation")  # Uses AggregateDataset config

            # Without dataset_config:
            df = parser.get_dataset("ActivePowerVariable__Gen1")  # Falls back to raw

        Note:
            - This is the main user-facing method for dataset retrieval
            - Automatically applies scaling based on configuration
            - Supports both configured and raw dataset access
        """
        # Check if we have a configured dataset with this name
        if self._dataset_config and key in self._dataset_config.aggregates:
            definition = self._dataset_config.aggregates[key]

            if isinstance(definition, RawDataset):
                # Retrieve single raw dataset
                df = self.get_raw_dataset(definition.h5_path)
                if df is not None:
                    # Apply scaling
                    scale_factor = definition.scale_factor
                    # If scale_factor is 1.0, apply base_power scaling
                    if scale_factor == 1.0:
                        bp = (
                            base_power
                            if base_power is not None
                            else self._get_base_power()
                        )
                        if bp is not None:
                            scale_factor = bp

                    if scale_factor != 1.0:
                        df = df * scale_factor
                return df

            elif isinstance(definition, AggregateDataset):
                # Retrieve and combine multiple datasets
                return self._get_aggregate_dataset_from_config(definition, base_power)

        # Fall back to raw dataset retrieval
        return self.get_raw_dataset(key)

    def _get_base_power(self) -> Optional[float]:
        """
        Get the base_power value for scaling.

        Subclasses should override this to provide format-specific base_power.
        Default implementation returns None.

        Returns:
            Base power value or None
        """
        return None

    def _get_aggregate_dataset_from_config(
        self, definition: AggregateDataset, base_power: Optional[float] = None
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve an aggregate dataset according to its configuration.

        Args:
            definition: AggregateDataset configuration
            base_power: Optional base_power for scaling

        Returns:
            Combined DataFrame or None
        """
        matched_datasets = self.match_datasets_by_patterns(definition.patterns)

        if not matched_datasets:
            warnings.warn(
                f"No datasets matched patterns {definition.patterns}",
                UserWarning,
            )
            return None

        frames = []
        for dataset_name in matched_datasets:
            df = self.get_raw_dataset(dataset_name)
            if df is not None:
                frames.append(df)

        if not frames:
            warnings.warn(
                f"No data retrieved for patterns {definition.patterns}",
                UserWarning,
            )
            return None

        # Combine according to method
        if definition.combination_method == "sum":
            # Sum across all datasets
            combined_df = pd.concat(frames, axis=1).sum(axis=1).to_frame(name="total")
        else:  # concat
            # Concatenate horizontally (default)
            combined_df = pd.concat(frames, axis=1)

        # Apply scaling
        scale_factor = definition.scale_factor
        # If scale_factor is 1.0, apply base_power scaling
        if scale_factor == 1.0:
            bp = base_power if base_power is not None else self._get_base_power()
            if bp is not None:
                scale_factor = bp

        if scale_factor != 1.0:
            combined_df = combined_df * scale_factor

        return combined_df

    def get_datasets(self, *keys: str) -> Dict[str, Optional[pd.DataFrame]]:
        """
        Retrieve multiple datasets at once.

        Args:
            *keys: One or more dataset keys

        Returns:
            Dictionary mapping keys to DataFrames (or None for failed retrievals)

        Note:
            Default implementation calls get_dataset() for each key.
            Override for more efficient batch loading if your format supports it.
        """
        results = {}
        for key in keys:
            results[key] = self.get_dataset(key)
        return results

    def match_datasets_by_patterns(
        self, patterns: List[str], available_datasets: Optional[List[str]] = None
    ) -> List[str]:
        """
        Match dataset names using glob patterns.

        Args:
            patterns: List of glob patterns (e.g., ["ActivePowerVariable__*"])
            available_datasets: Optional list of dataset names to match against.
                              If None, uses self.list_raw_datasets().keys()

        Returns:
            List of matched dataset names (sorted, deduplicated)

        Example:
            >>> parser.match_datasets_by_patterns(["ActivePowerVariable__*"])
            ['ActivePowerVariable__Generator1', 'ActivePowerVariable__Generator2']
        """
        if available_datasets is None:
            available_datasets = list(self.list_raw_datasets().keys())

        matches = set()
        unmatched_patterns = []

        for pattern in patterns:
            has_match = False
            for dataset in available_datasets:
                if fnmatch.fnmatch(dataset, pattern):
                    has_match = True
                    matches.add(dataset)

            if not has_match:
                unmatched_patterns.append(pattern)

        # Warn about unmatched patterns
        if unmatched_patterns:
            warnings.warn(
                f"The following patterns matched no datasets: {unmatched_patterns}. "
                f"Consider updating the configuration.",
                UserWarning,
            )

        return sorted(list(matches))

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get simulation metadata.

        Returns:
            Dictionary of metadata about the simulation

        Note:
            Optional method. Override to provide useful metadata like:
            - Simulation start/end times
            - Resolution (hourly, 5-minute, etc.)
            - Software version
            - Solver information
            - Base power value
            - Any format-specific metadata

        Example:
            {
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2024-12-31T23:00:00",
                "resolution": "1H",
                "software": "MySimTool v2.1",
                "solver": "HiGHS",
                "base_power": 100.0
            }
        """
        return {}

    def validate(self) -> List[str]:
        """
        Validate the simulation file and return warnings.

        Returns:
            List of warning messages (empty if no issues)

        Note:
            Optional method. Override to implement validation checks like:
            - File format version compatibility
            - Required datasets exist
            - Data integrity checks
            - Timestamp consistency
        """
        return []

    def close(self):
        """
        Close file handles and cleanup resources.

        Note:
            Optional method. Override if your parser maintains open file handles
            or other resources that need explicit cleanup.
        """
        pass

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def __repr__(self) -> str:
        """String representation."""
        file_path = getattr(self, "file_path", "unknown")
        return f"{self.__class__.__name__}('{file_path}')"
