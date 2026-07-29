"""
Generic simulation aggregator for combining multiple simulation files.

This module provides a generic aggregator that can combine multiple simulation files
of any type, as long as they implement the BaseSimulationParser interface.

Key Features:
-------------
- Works with any parser type (Sienna, ReEDS, PLEXOS, custom formats)
- Parallel file loading using multiprocessing
- Automatic deduplication of overlapping time periods
- Consistent interface matching single parser
- Avoids Python GIL for true parallel performance

Architecture:
-------------
The aggregator acts as a transparent wrapper around multiple parsers:
- User creates aggregator with file paths and parser class
- Aggregator instantiates parsers (potentially in parallel)
- All operations (list_datasets, get_dataset) are delegated to parsers
- Results are automatically combined and deduplicated

Example:
--------
    # Single file (no aggregation needed)
    parser = SiennaSimulationParser("simulation_1.h5")

    # Multiple files (automatic aggregation)
    aggregator = SimulationAggregator(
        file_paths=["sim_1.h5", "sim_2.h5", "sim_3.h5"],
        parser_class=SiennaSimulationParser
    )

    # Same interface for both!
    datasets = aggregator.list_datasets()
    data = aggregator.get_dataset("generator_dispatch")
"""

import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Type, Union

import pandas as pd
from loguru import logger

from .base import BaseSimulationParser
from .utils import combine_overlapping_frames


class SimulationAggregator:
    """
    Generic aggregator for combining multiple simulation files.

    Provides a unified interface for working with multiple simulation files
    as if they were a single simulation. Handles parallel loading, model
    selection across files, and automatic deduplication of overlapping data.

    Attributes:
    -----------
    file_paths : List[Path]
        Paths to all simulation files
    parser_class : Type[BaseSimulationParser]
        Parser class to use for each file
    parsers : List[BaseSimulationParser]
        Instantiated parser objects for each file
    parallel : bool
        Whether to use parallel loading
    """

    def __init__(
        self,
        file_paths: Union[str, Path, Sequence[Union[str, Path]]],
        parser_class: Type[BaseSimulationParser],
        parallel: bool = True,
        max_workers: Optional[int] = None,
    ):
        """
        Initialize the simulation aggregator.

        Args:
            file_paths: Single path or list of paths to simulation files
            parser_class: Parser class to instantiate (must inherit from BaseSimulationParser)
            parallel: Whether to load files in parallel (default: True)
            max_workers: Maximum number of parallel workers (default: CPU count)

        Raises:
            ValueError: If no valid files provided or parser_class is invalid
            FileNotFoundError: If any file doesn't exist
        """
        # Normalize file paths to list
        if not isinstance(file_paths, list):
            file_paths = [file_paths]

        self.file_paths = [Path(fp) for fp in file_paths]
        self.parser_class = parser_class
        self.parallel = parallel
        self.max_workers = max_workers or mp.cpu_count()

        # Validate inputs
        if not self.file_paths:
            raise ValueError("No file paths provided")

        if not issubclass(parser_class, BaseSimulationParser):
            raise ValueError(
                f"parser_class must inherit from BaseSimulationParser, "
                f"got {parser_class}"
            )

        # Check all files exist
        for fp in self.file_paths:
            if not fp.exists():
                raise FileNotFoundError(f"Simulation file not found: {fp}")

        logger.info(
            f"Creating aggregator for {len(self.file_paths)} files "
            f"using {parser_class.__name__}"
        )

        # Initialize parsers
        self.parsers: List[BaseSimulationParser] = []
        self._selected_model: Optional[str] = None

        self._initialize_parsers()
        self._validate_parsers()
        self._set_default_model()

    def _initialize_parsers(self):
        """Initialize parser instances for each file."""
        if self.parallel and len(self.file_paths) > 1:
            logger.debug(f"Loading {len(self.file_paths)} files in parallel")
            self.parsers = self._initialize_parsers_parallel()
        else:
            logger.debug(f"Loading {len(self.file_paths)} files sequentially")
            self.parsers = self._initialize_parsers_sequential()

        logger.info(f"Successfully initialized {len(self.parsers)} parsers")

    def _initialize_parsers_sequential(self) -> List[BaseSimulationParser]:
        """Initialize parsers sequentially."""
        parsers = []
        for i, file_path in enumerate(self.file_paths):
            try:
                logger.debug(
                    f"Loading file {i + 1}/{len(self.file_paths)}: {file_path.name}"
                )
                parser = self.parser_class(str(file_path))  # type: ignore
                parsers.append(parser)
            except Exception as e:
                logger.error(f"Failed to load {file_path}: {e}")
                raise
        return parsers

    def _initialize_parsers_parallel(self) -> List[BaseSimulationParser]:
        """
        Initialize parsers in parallel using ProcessPoolExecutor.

        Note: This avoids the Python GIL by using separate processes.
        The parser class must be pickleable for this to work.
        """
        parsers: List[Optional[BaseSimulationParser]] = [None] * len(self.file_paths)

        try:
            # Use ProcessPoolExecutor to avoid GIL
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all parsing tasks
                future_to_idx = {
                    executor.submit(self._load_single_file, str(fp)): i
                    for i, fp in enumerate(self.file_paths)
                }

                # Collect results as they complete
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        parser = future.result()
                        parsers[idx] = parser
                        logger.debug(
                            f"Completed loading file {idx + 1}/{len(self.file_paths)}"
                        )
                    except Exception as e:
                        logger.error(f"Failed to load file {idx}: {e}")
                        raise

        except Exception as e:
            logger.warning(f"Parallel loading failed: {e}. Falling back to sequential.")
            return self._initialize_parsers_sequential()

        # Filter out None values (shouldn't happen, but type safety)
        return [p for p in parsers if p is not None]

    def _load_single_file(self, file_path: str) -> BaseSimulationParser:
        """
        Load a single file (used for parallel loading).

        Args:
            file_path: Path to simulation file

        Returns:
            Initialized parser instance
        """
        return self.parser_class(file_path)  # type: ignore

    def _validate_parsers(self):
        """Validate that all parsers have compatible simulation models."""
        if not self.parsers:
            raise ValueError("No valid parsers created")

        # Check that all parsers have the same available simulation models
        reference_models = set(self.parsers[0].simulation_models)

        for i, parser in enumerate(self.parsers[1:], 1):
            parser_models = set(parser.simulation_models)
            if parser_models != reference_models:
                logger.warning(
                    f"Parser {i} has different simulation models: "
                    f"{parser_models} vs {reference_models}"
                )

    def _set_default_model(self):
        """Set the default selected model based on the first parser."""
        if self.parsers and self.parsers[0].selected_model:
            # Get model name - handle both string and object types
            if hasattr(self.parsers[0].selected_model, "name"):
                model_name = self.parsers[0].selected_model.name
            else:
                model_name = str(self.parsers[0].selected_model)

            self.selected_model = model_name

    @property
    def simulation_models(self) -> List[str]:
        """
        Get simulation models available across all parsers.

        Returns:
            List of model names available in all files
        """
        if not self.parsers:
            return []

        # Get intersection of all available models
        model_sets = [set(parser.simulation_models) for parser in self.parsers]
        common_models = model_sets[0]
        for model_set in model_sets[1:]:
            common_models = common_models.intersection(model_set)

        return sorted(list(common_models))

    @property
    def selected_model(self) -> Optional[str]:
        """
        Get the currently selected simulation model name.

        Returns:
            Selected model name or None
        """
        return self._selected_model

    @selected_model.setter
    def selected_model(self, model_name: Optional[str]):
        """
        Set the selected simulation model for all parsers.

        Args:
            model_name: Name of model to select, or None to clear

        Raises:
            ValueError: If model_name is not available in all parsers
        """
        if model_name is None:
            self._selected_model = None
            for parser in self.parsers:
                parser.selected_model = None
            return

        available_models = self.simulation_models
        if model_name not in available_models:
            raise ValueError(
                f"Model '{model_name}' not found in all files. "
                f"Available models: {', '.join(available_models)}"
            )

        # Set the model for all parsers
        for parser in self.parsers:
            parser.selected_model = model_name

        self._selected_model = model_name
        logger.debug(
            f"Set selected model to '{model_name}' for all {len(self.parsers)} parsers"
        )

    def list_datasets(self) -> Dict[str, str]:
        """
        Get deduplicated datasets available across all parsers.

        Returns:
            Dictionary of dataset names and their internal paths

        Raises:
            ValueError: If no model is selected (for multi-model formats)
        """
        all_datasets = {}

        for i, parser in enumerate(self.parsers):
            try:
                parser_datasets = parser.list_datasets()
                logger.debug(f"Parser {i}: Found {len(parser_datasets)} datasets")

                # Merge datasets (dataset names should be consistent across files)
                for dataset_name, dataset_path in parser_datasets.items():
                    if dataset_name not in all_datasets:
                        all_datasets[dataset_name] = dataset_path
                    elif all_datasets[dataset_name] != dataset_path:
                        logger.warning(
                            f"Dataset '{dataset_name}' has different paths across files: "
                            f"'{all_datasets[dataset_name]}' vs '{dataset_path}'"
                        )

            except Exception as e:
                logger.warning(f"Failed to get datasets from parser {i}: {e}")

        logger.debug(f"Total unique datasets across all files: {len(all_datasets)}")
        return all_datasets

    def get_dataset(
        self,
        key: str,
        merge_strategy: str = "left",
    ) -> pd.DataFrame:
        """
        Get dataset combined across all simulation files.

        Args:
            key: Dataset name or internal path
            merge_strategy: How to handle overlapping time periods:
                - "left": Keep earlier timestamps, remove overlap with future blocks
                - "right": Keep later timestamps, remove overlap with previous blocks

        Returns:
            Combined DataFrame with deduplicated timestamps

        Raises:
            KeyError: If dataset key doesn't exist
            ValueError: If no model is selected or no data retrieved
        """
        logger.debug(f"Getting dataset '{key}' from {len(self.parsers)} files")

        frames = []
        for i, parser in enumerate(self.parsers):
            try:
                df = parser.get_dataset(key)
                if df is not None and not df.empty:
                    frames.append(df)
                    logger.debug(f"Parser {i}: Retrieved data with shape {df.shape}")
                else:
                    logger.warning(f"Parser {i}: No data returned for key '{key}'")
            except Exception as e:
                logger.error(f"Failed to get dataset from parser {i}: {e}")
                raise

        if not frames:
            raise ValueError(f"No data retrieved for key '{key}' from any parser")

        # Combine frames - this handles overlapping timestamps
        logger.debug(
            f"Combining {len(frames)} DataFrames using '{merge_strategy}' strategy"
        )
        return self._combine_frames(frames, merge_strategy=merge_strategy)

    def get_datasets(
        self, *keys: str, merge_strategy: str = "left"
    ) -> Dict[str, pd.DataFrame]:
        """
        Get multiple datasets at once.

        Args:
            *keys: One or more dataset keys
            merge_strategy: Merge strategy for overlapping time periods

        Returns:
            Dictionary mapping keys to combined DataFrames
        """
        results = {}
        for key in keys:
            results[key] = self.get_dataset(key, merge_strategy=merge_strategy)
        return results

    def _combine_frames(
        self,
        frames: List[pd.DataFrame],
        merge_strategy: str = "left",
    ) -> pd.DataFrame:
        """
        Combine DataFrames handling overlapping timestamps.

        Thin wrapper over ``gat.simulations.utils.combine_overlapping_frames``
        — the shared "earlier/later wins" primitive used by every GAT
        backend that combines multiple files/blocks (this aggregator,
        ``gat.datahelpers.plexos_duckdb.PlexosDuckDBSource.pivot_wide``).
        See that function's docstring for the full semantic explanation
        and the ``merge_strategy`` direction ("left" truncates the
        earlier block so the later one wins; "right" truncates the later
        block so the earlier one wins — "right" matches the legacy
        ``gat.datahelpers.parsers.combine_frames_skip_prev`` Plexos path).

        Args:
            frames: List of pandas DataFrames to combine
            merge_strategy: "left" or "right" — see semantic note above

        Returns:
            Combined DataFrame with deduplicated timestamps
        """
        combined = combine_overlapping_frames(frames, merge_strategy=merge_strategy)
        logger.debug(f"Combined result shape: {combined.shape}")
        return combined  # type: ignore[return-value]

    def get_metadata(self) -> Dict[str, Any]:
        """
        Get metadata from the first simulation file.

        Returns:
            Dictionary of metadata
        """
        if not self.parsers:
            return {}

        return self.parsers[0].get_metadata()

    def validate(self) -> List[str]:
        """
        Validate all simulation files and return warnings.

        Returns:
            List of warning messages from all parsers
        """
        all_warnings = []

        for i, parser in enumerate(self.parsers):
            try:
                warnings = parser.validate()
                if warnings:
                    all_warnings.extend([f"File {i}: {w}" for w in warnings])
            except Exception as e:
                all_warnings.append(f"File {i}: Validation failed - {e}")

        return all_warnings

    def close(self):
        """Close all parser file handles."""
        for parser in self.parsers:
            try:
                parser.close()
            except Exception as e:
                logger.warning(f"Failed to close parser: {e}")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"SimulationAggregator("
            f"{len(self.file_paths)} files, "
            f"parser={self.parser_class.__name__})"
        )
