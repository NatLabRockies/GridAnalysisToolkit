from __future__ import annotations

import copy
import os
import sys
from typing import Any, Dict, List, Optional

import h5py
import pandas as pd
import polars as pl
from loguru import logger
from pydantic import BaseModel, field_validator

from .base import BaseSimulationParser
from .utils import block_combination_strategy, dedup_slices


class SiennaSimulationDataset(BaseModel):
    """
    Configuration for a single simulation dataset.

    Tracks whether base_power multiplication should be applied and allows
    custom multipliers.
    """

    name: str  # Dataset name (e.g., "ActivePowerVariable__ThermalStandard")
    h5_path: str  # Full H5 path to the dataset
    apply_base_power: bool = False  # Whether to multiply by base_power
    custom_multiplier: Optional[float] = None  # Override base_power with custom value


class SiennaModelConfig(BaseModel):
    name: Optional[str] = None
    root_path: str
    base_power: int
    horizon_count: int
    interval_ms: int
    num_executions: int
    resolution_ms: int
    system_uuid: str
    merge: Optional[block_combination_strategy] = (
        "right"  # default to forecasted data for UC, day-ahead market.
    )


class SiennaSimulationConfig(BaseModel):
    """
    This class holds the attributes for a given set of Simulation attributes
    This class is responsible for generating the timestamps of decision and emulation models
    """

    initial_time: str  # should be a datetime object
    num_steps: int
    step_resolution_ms: int
    decision_models: Optional[Dict[str, SiennaModelConfig]] = None
    emulation_models: Optional[Dict[str, SiennaModelConfig]] = None

    @property
    def simulation_models(self) -> list[str]:
        models = []
        if self.decision_models:
            models.extend(self.decision_models.keys())

        if self.emulation_models:
            models.extend(self.emulation_models.keys())

        return models

    @classmethod
    def from_h5_file(cls, h5_file_path: str) -> "SiennaSimulationConfig":
        """
        Initialize SiennaSimulationConfig from H5 simulation attributes

        Args:
            sim_attrs: Attributes from /simulation path in H5 file
            h5_file_path: Path to H5 file for reading model-specific attributes

        Returns:
            SiennaSimulationConfig instance
        """
        try:
            with h5py.File(h5_file_path, "r") as h5data:
                if "/simulation" not in h5data.keys():
                    raise KeyError

                sim_attrs = h5data.get("/simulation").attrs
                itime = sim_attrs.get("initial_time")
                # Extract core simulation attributes
                config_data = {
                    "initial_time": itime.decode()
                    if isinstance(itime, bytes)
                    else itime,
                    "num_steps": int(sim_attrs["num_steps"]),
                    "step_resolution_ms": int(sim_attrs["step_resolution_ms"]),
                }

                # Read decision models
                decision_models = {}
                emulation_models = {}

                # Load decision models
                if "/simulation/decision_models" in h5data:
                    for model_name in h5data["/simulation/decision_models"].keys():
                        try:
                            model_attrs = dict(
                                h5data[
                                    f"/simulation/decision_models/{model_name}"
                                ].attrs.items()
                            )
                            root_path = f"/simulation/decision_models/{model_name}"
                            model_config = cls._create_model_config(
                                model_attrs, model_name, root_path
                            )
                            if model_config:
                                decision_models[model_name] = model_config
                        except Exception as e:
                            logger.warning(
                                f"Could not load decision model {model_name}: {e}"
                            )

                # Load emulation models
                if "/simulation/emulation_model" in h5data:
                    # Check if this is a single emulation model or multiple models
                    emulation_group = h5data["/simulation/emulation_model"]

                    # Check if emulation_model has attributes (single model)
                    if len(emulation_group.attrs) > 0:
                        try:
                            em_attrs = dict(emulation_group.attrs.items())
                            root_path = "/simulation/emulation_model"
                            # Use "emulation_model" as the default name for single emulation model
                            model_name = em_attrs.get("name", "emulation_model")
                            model_config = cls._create_model_config(
                                em_attrs, model_name, root_path
                            )
                            if model_config:
                                emulation_models[model_name] = model_config
                        except Exception as e:
                            logger.warning(f"Could not load emulation model: {e}")
                    else:
                        # Multiple emulation models - iterate through subgroups
                        for subgroup_name in emulation_group.keys():
                            try:
                                model_path = (
                                    f"/simulation/emulation_model/{subgroup_name}"
                                )
                                if isinstance(h5data[model_path], h5py.Group):
                                    model_attrs = dict(h5data[model_path].attrs.items())
                                    # Use 'name' attribute from subgroup if available, otherwise use subgroup name
                                    model_name = model_attrs.get("name", subgroup_name)
                                    if isinstance(model_name, bytes):
                                        model_name = model_name.decode()
                                    model_config = cls._create_model_config(
                                        model_attrs, model_name, model_path
                                    )
                                    if model_config:
                                        emulation_models[model_name] = model_config
                            except Exception as e:
                                logger.warning(
                                    f"Could not load emulation model {subgroup_name}: {e}"
                                )

            config_data["decision_models"] = (
                decision_models if decision_models else None
            )
            config_data["emulation_models"] = (
                emulation_models if emulation_models else None
            )

            return cls(**config_data)

        except Exception as e:
            logger.error(
                f"Failed to create SiennaSimulationConfig from H5 attributes: {e}"
            )
            raise ValueError(f"Invalid H5 simulation attributes: {e}")

    @staticmethod
    def _create_model_config(
        model_attrs: Dict[str, Any], model_name: str, root_path: str
    ) -> Optional[SiennaModelConfig]:
        """
        Create a SiennaModelConfig from model attributes

        Args:
            model_attrs: Attributes from model path in H5 file
            model_name: Name of the model for logging
            root_path: Root path to the model in the H5 file

        Returns:
            SiennaModelConfig instance or None if creation fails
        """
        try:
            # Handle byte strings
            processed_attrs = {}
            for key, value in model_attrs.items():
                if isinstance(value, bytes):
                    processed_attrs[key] = value.decode()
                else:
                    processed_attrs[key] = value

            # Ensure required fields exist with defaults
            config_data = {
                "root_path": root_path,
                "base_power": int(processed_attrs.get("base_power", 100)),
                "horizon_count": int(processed_attrs.get("horizon_count", 24)),
                "interval_ms": int(processed_attrs.get("interval_ms", 3600000)),
                "num_executions": int(processed_attrs.get("num_executions", 1)),
                "resolution_ms": int(processed_attrs.get("resolution_ms", 300000)),
                "system_uuid": str(processed_attrs.get("system_uuid", "")),
                "name": processed_attrs.get("name", model_name),
            }

            return SiennaModelConfig(**config_data)

        except Exception as e:
            logger.warning(f"Could not create model config for {model_name}: {e}")
            return None

    @field_validator("initial_time")
    @classmethod
    def validate_initial_time(cls, v):
        """Validate that initial_time is a valid datetime string"""
        try:
            pd.to_datetime(v)
            return v
        except Exception:
            raise ValueError(f"Invalid datetime format: {v}")


class SiennaSimulationParser(BaseSimulationParser):
    """
    Parser for Sienna simulation H5 files.

    Automatically discovers all simulation models within the file:
    - Emulation models: Names from 'name' attribute in /simulation/emulation_model
    - Decision models: Names from subgroup names in /simulation/decision_models

    Usage:
        # Basic usage with default simulation
        parser = SiennaSimulationParser("simulation.h5")
        datasets = parser.list_datasets()  # Uses default simulation
        data = parser.get_dataset("generator_dispatch")

        # Set specific simulation
        parser.simulation = "UC"  # or parser.selected_model = "UC"
        datasets = parser.list_datasets()

        # Query specific simulation without changing default
        datasets = parser.list_datasets(simulation="ED")
        data = parser.get_dataset("generator_dispatch", simulation="ED")

        # List all available simulations
        simulations = parser.simulation_models
    """

    def __init__(self, simulation_store_path):
        super().__init__()

        if os.path.isfile(os.path.normpath(simulation_store_path)):
            logger.info(f"Loading {simulation_store_path}")
        else:
            logger.error(f"{simulation_store_path} not found")
            raise FileNotFoundError

        self.file_path = os.path.normpath(simulation_store_path)

        # Initialize configuration using classmethod
        self.config = SiennaSimulationConfig.from_h5_file(self.file_path)

        # Set default selected model
        self._set_default_model()

    @property
    def simulation_models(self) -> list[str]:
        """List available simulation models"""
        return self.config.simulation_models

    def _set_default_model(self):
        """Set the default selected model to first emulation model if available, otherwise first decision model"""
        available_models = self.config.simulation_models
        if not available_models:
            logger.warning("No simulation models found in configuration")
            return

        # Prefer first emulation model if available
        if self.config.emulation_models:
            first_emulation_model = list(self.config.emulation_models.keys())[0]
            self.selected_model = first_emulation_model
        elif self.config.decision_models:
            # Use first decision model
            first_decision_model = list(self.config.decision_models.keys())[0]
            self.selected_model = first_decision_model

    @property
    def simulation(self) -> str | None:
        """Get the name of the currently selected simulation model"""
        if self._selected_model is None:
            return None
        return self._selected_model.name

    @simulation.setter
    def simulation(self, model_name: Optional[str]):
        """Set the selected simulation model by name (alias for selected_model setter)"""
        self.selected_model = model_name

    @property
    def selected_model(self) -> SiennaModelConfig | None:
        """Get the currently selected simulation model"""
        return self._selected_model

    @selected_model.setter
    def selected_model(self, model_name: Optional[str]):
        """Set the selected simulation model with validation"""
        if model_name is None:
            self._selected_model = None
        elif model_name in self.config.simulation_models:
            # Check if it's an emulation model
            if (
                self.config.emulation_models
                and model_name in self.config.emulation_models
            ):
                self._selected_model = self.config.emulation_models[model_name]
            # Check if it's a decision model
            elif (
                self.config.decision_models
                and model_name in self.config.decision_models
            ):
                self._selected_model = self.config.decision_models[model_name]
            else:
                # This shouldn't happen if simulation_models property is correct
                logger.error(
                    f"Model '{model_name}' found in simulation_models but not in decision_models or emulation_models"
                )
                raise ValueError(
                    f"Internal error: Model '{model_name}' configuration not found"
                )
        else:
            available_models = ", ".join(self.config.simulation_models)
            raise ValueError(
                f"Model '{model_name}' not found. Available models: {available_models}"
            )

    @property
    def merge_strategy(self) -> block_combination_strategy | None:
        """
        Get the merge strategy for the currently selected model.

        See _get_decision_data() docstring for detailed strategy examples.
        """
        if self._selected_model is None:
            raise ValueError(
                "No simulation model selected. Please set the 'selected_model' property first."
            )
        return self._selected_model.merge

    @merge_strategy.setter
    def merge_strategy(self, strategy: block_combination_strategy | None):
        """Set the merge strategy for the currently selected model"""
        if self._selected_model is None:
            raise ValueError(
                "No simulation model selected. Please set the 'selected_model' property first."
            )

        # Validate the strategy
        if strategy is not None and strategy not in ["left", "right"]:
            raise ValueError(
                f"Invalid merge strategy: {strategy}. Must be 'left', 'right', or None"
            )

        # Update the merge strategy in the model configuration
        self._selected_model.merge = strategy
        logger.info(
            f"Updated merge strategy for model '{self._selected_model.name}' to '{strategy}'"
        )

    @property
    def base_power(self) -> Optional[float]:
        """
        Get the base_power value from the currently selected model.

        Returns:
            Base power value in MW, or None if no model is selected
        """
        if self._selected_model is None:
            return None
        return float(self._selected_model.base_power)

    @property
    def timestamps(self) -> pd.DatetimeIndex:
        """The timestamps for the selected model of the simulation file"""
        try:
            simulation_start = self.config.initial_time
            step_resolution_ms = self.config.step_resolution_ms
            num_steps = self.config.num_steps

            # Use the selected model's resolution, or fall back to first emulation model
            if self._selected_model:
                resolution_ms = self._selected_model.resolution_ms
            elif self.config.emulation_models:
                first_emulation_model = list(self.config.emulation_models.values())[0]
                resolution_ms = first_emulation_model.resolution_ms
            else:
                # Fallback to reading from attributes - this shouldn't happen with new structure
                logger.warning(
                    "No selected model or emulation models found, using fallback resolution"
                )
                resolution_ms = 300000  # Default 5-minute resolution

            periods_per_step = step_resolution_ms / resolution_ms
            num_periods = int(periods_per_step * num_steps)

            raw_index = pd.date_range(
                start=simulation_start, freq=f"{resolution_ms}ms", periods=num_periods
            )
            inferred_index = pd.date_range(
                start=simulation_start,
                freq=raw_index.inferred_freq,
                periods=num_periods,
            )
            return inferred_index

        except Exception as e:
            logger.error(f"An exception has occurred while creating timestamps: {e}")
            raise

    def _get_emulation_data(self, key: str) -> pd.DataFrame | None:
        """
        Get dataset for emulation model (2D data structure)

        Args:
            key: H5 path to the dataset

        Returns:
            DataFrame with timestamps as index and components as columns
        """
        try:
            with h5py.File(
                self.file_path, "r", driver="core", backing_store=False
            ) as h5data:
                data = h5data[key][:]
                columns = [c.decode() for c in h5data[key + "__columns"]]

            df = pd.DataFrame(data.T, columns=columns, index=self.timestamps)

            df.index.name = "DATETIME"

            # Apply base_power multiplication if needed
            if self._should_apply_base_power(key):
                multiplier = self._get_multiplier(key)
                df = df * multiplier
                logger.debug(f"Applied multiplier {multiplier} to dataset {key}")

            return df
        except ValueError as e:
            if "Unknown driver" in str(e):
                print("Core driver is not available, using default")
                with h5py.File(self.file_path, "r") as h5data:
                    data = h5data[key][:]
                    columns = [c.decode() for c in h5data[key + "__columns"]]

                df = pd.DataFrame(data.T, columns=columns, index=self.timestamps)

                df.index.name = "DATETIME"

                # Apply base_power multiplication if needed
                if self._should_apply_base_power(key):
                    multiplier = self._get_multiplier(key)
                    df = df * multiplier
                    logger.debug(f"Applied multiplier {multiplier} to dataset {key}")

                return df
            else:
                print(f"An error occured while reading emulation data: {e}")
                return None

    def _get_decision_data(
        self, key: str, merge_strategy: None | block_combination_strategy = None
    ) -> pd.DataFrame | list[pd.DataFrame] | None:
        """
        Get dataset for decision model (3D data structure with blocks)

        Args:
            key: H5 path to the dataset
            merge_strategy: Merge strategy to use (left, right, or None for no deduplication)

        Returns:
            Single DataFrame or list of DataFrames depending on merge strategy

        Merge Strategy Details:
        ----------------------
        When simulation blocks have overlapping timestamps, two strategies can handle the overlap:

        "left" strategy (ignore_previous=True):
        - Prioritizes REALIZED data
        - Removes Timestamps from CURRENT block that overlap with FUTURE blocks
        - Use for: Real-time data, getting the most recent/realized values

        "right" strategy (ignore_previous=False):
        - Prioritizes FORECASTED data
        - Removes timestamps from CURRENT block that overlap with PREVIOUS blocks
        - Use for: Day-ahead forecasts, unit commitment schedules

        Visual Examples:
        ---------------
        Legend: |-----| = kept data, xxxxx = ignored/skipped data

        LEFT strategy ("realized" - remove future overlap):
        Block 1: |-----|xxxxx|
        Block 2:       |-----|xxxxx|
        Block 3:             |-----|-----|  <=== last block keeps all data

        RIGHT strategy ("forecasted" - remove previous overlap):
        Block 1: |-----|-----|  <=== first block keeps all data
        Block 2:       |xxxxx|------|
        Block 3:             |xxxxx|------|

        Real Examples:
        -------------
        RAUC: block 1 => hour 0-11, block 2 => hour 1-12, block 3 => hour 2-13...

        For REALIZED data ("left" strategy):
        - Hour 0 from block 1, hour 1 from block 2, hour 2 from block 3...
        - Gets the most recent prediction for each hour

        For FORECASTED data ("right" strategy):
        - Use all of block 1 (hours 0-11), then non-overlapping parts of later blocks
        - Gets the earliest available forecast for each hour

        UC: block 1 => hour 0-48, block 2 => hour 24-72...
        For day-ahead forecasted data ("right" strategy):
        - Hours 0-47 from block 1, hours 48-72 from block 2, etc.
        """
        try:
            dedup_blocks = True
            ignore_previous = False
            if merge_strategy is None:
                dedup_blocks = False
            else:
                if merge_strategy == "left":
                    ignore_previous = True
                elif merge_strategy == "right":
                    ignore_previous = False
                else:
                    raise ValueError(
                        f"Invalid merge strategy: {merge_strategy}. Must be 'left', 'right', or None"
                    )

            with h5py.File(
                self.file_path, "r", driver="core", backing_store=False
            ) as h5data:
                data = h5data[key]
                columns = [c.decode() for c in h5data[key + "__columns"]]

                model_config = self._selected_model
                initial_time = self.config.initial_time

                logger.debug(f"Processing decision model dataset: {key}")
                logger.debug(f"Selected model: {model_config.name}")
                logger.debug(f"Merge strategy: {merge_strategy}")
                logger.debug(
                    f"Data shape: {data.shape} (blocks, components, timestamps)"
                )

                # Convert initial time to polars datetime
                itime_dt = pl.Series([initial_time]).str.strptime(
                    pl.Datetime, "%Y-%m-%dT%H:%M:%S"
                )[0]

                # Generate datetime ranges for each block
                date_ranges = []
                for i in range(data.shape[0]):
                    start = itime_dt + pl.duration(
                        milliseconds=i * model_config.interval_ms
                    )
                    dr = pl.datetime_range(
                        start=start,
                        end=start
                        + pl.duration(
                            milliseconds=model_config.horizon_count
                            * model_config.resolution_ms
                        ),
                        interval=f"{model_config.resolution_ms}ms",
                        closed="left",
                        eager=True,
                    )
                    date_ranges.append(dr)
                    logger.debug(
                        f"Block {i}: {dr.min()} to {dr.max()} ({len(dr)} timestamps)"
                    )

                if dedup_blocks:
                    logger.debug(
                        f"Deduplicating overlapping blocks using '{merge_strategy}' strategy - combining into single DataFrame"
                    )

                    # Get deduped slices
                    result_slices = dedup_slices(
                        date_ranges, ignore_previous=ignore_previous
                    )

                    logger.debug(
                        "Block slice results (removing overlap with previous blocks):"
                    )
                    total_original_timestamps = sum(len(dr) for dr in date_ranges)
                    total_deduped_timestamps = 0

                    # Create frames for each block
                    frames = []
                    for i in range(data.shape[0]):
                        start_idx, end_idx = result_slices[i]
                        original_length = len(date_ranges[i])
                        deduped_length = end_idx - start_idx + 1
                        total_deduped_timestamps += deduped_length

                        if start_idx > 0:
                            logger.debug(
                                f"Block {i}: Ignoring first {start_idx} timestamps (overlap with previous blocks)"
                            )
                        if end_idx < original_length - 1:
                            skipped_end = original_length - 1 - end_idx
                            logger.debug(
                                f"Block {i}: Ignoring last {skipped_end} timestamps (overlap with future blocks)"
                            )

                        logger.debug(
                            f"Block {i}: Using slice [{start_idx}:{end_idx}] - {deduped_length}/{original_length} timestamps"
                        )

                        date_range_slice = date_ranges[i][start_idx : end_idx + 1]
                        data_slice = data[i][:, start_idx : end_idx + 1]

                        # Convert polars datetime to pandas datetime strings, then to datetime index
                        datetime_strings = [str(dt) for dt in date_range_slice]
                        datetime_index = pd.to_datetime(datetime_strings)

                        df = pd.DataFrame(data_slice, columns=datetime_index)
                        frames.append(df)

                    logger.debug(
                        f"Total timestamps: {total_original_timestamps} original -> {total_deduped_timestamps} after deduplication"
                    )

                    # Combine all frames horizontally
                    combined_df = pd.concat(frames, axis=1)
                    combined_df.index = columns

                    # Transpose to get timestamps as index, components as columns
                    result_df = combined_df.T
                    result_df.index.name = "DATETIME"

                    # Ensure the index is properly sorted
                    result_df = result_df.sort_index()

                    # Apply base_power multiplication if needed
                    if self._should_apply_base_power(key):
                        multiplier = self._get_multiplier(key)
                        result_df = result_df * multiplier
                        logger.debug(
                            f"Applied multiplier {multiplier} to dataset {key}"
                        )

                    logger.debug(f"Final combined DataFrame shape: {result_df.shape}")
                    logger.debug(f"Index type: {type(result_df.index)}")
                    logger.debug(
                        f"Index range: {result_df.index.min()} to {result_df.index.max()}"
                    )
                    return result_df
                else:
                    logger.debug(
                        "Returning list of DataFrames without deduplication - preserving all block data"
                    )

                    # Return list of DataFrames without deduplication
                    frames = []
                    for i in range(data.shape[0]):
                        date_range = date_ranges[i]
                        data_slice = data[i]

                        # Convert polars datetime to pandas datetime index
                        datetime_strings = [str(dt) for dt in date_range]
                        datetime_index = pd.to_datetime(datetime_strings)

                        df = pd.DataFrame(
                            data_slice.T, columns=columns, index=datetime_index
                        )
                        df.index.name = "DATETIME"

                        # Apply base_power multiplication if needed
                        if self._should_apply_base_power(key):
                            multiplier = self._get_multiplier(key)
                            df = df * multiplier
                            logger.debug(
                                f"Applied multiplier {multiplier} to block {i} of dataset {key}"
                            )

                        frames.append(df)

                        logger.debug(
                            f"Block {i} DataFrame: {df.shape} - {date_range.min()} to {date_range.max()}"
                        )

                    logger.debug(
                        f"Returning {len(frames)} separate DataFrames with potential overlapping timestamps"
                    )
                    return frames

        except Exception as e:
            logger.error(f"An exception has occured in _get_decision_data: {e}")
            return None

    def _should_apply_base_power(self, key: str) -> bool:
        """
        Determine if base_power multiplication should be applied to a dataset.

        By default, applies to datasets with "Power" in the name.
        Can be customized via dataset_configs.

        Args:
            key: Dataset key or H5 path

        Returns:
            True if base_power should be applied
        """
        # Extract dataset name from path if needed
        dataset_name = key.split("/")[-1] if "/" in key else key

        # Check if we have explicit configuration
        if hasattr(self, "dataset_configs") and self.dataset_configs:
            for config in self.dataset_configs:
                if config.name == dataset_name or config.h5_path == key:
                    return config.apply_base_power

        # Default: apply to datasets with "Power" in the name
        return "Power" in dataset_name

    def _get_multiplier(self, key: str) -> float:
        """
        Get the multiplier to apply to a dataset.

        Checks for custom multiplier first, then uses base_power.

        Args:
            key: Dataset key or H5 path

        Returns:
            Multiplier value
        """
        # Extract dataset name from path if needed
        dataset_name = key.split("/")[-1] if "/" in key else key

        # Check if we have explicit configuration with custom multiplier
        if hasattr(self, "dataset_configs") and self.dataset_configs:
            for config in self.dataset_configs:
                if config.name == dataset_name or config.h5_path == key:
                    if config.custom_multiplier is not None:
                        return config.custom_multiplier

        # Use base_power from selected model
        if self._selected_model:
            return float(self._selected_model.base_power)

        # Fallback to 100 MW
        logger.warning(f"No model selected, using default base_power=100 for {key}")
        return 100.0

    def discover_datasets(
        self, simulation: Optional[str] = None
    ) -> List[SiennaSimulationDataset]:
        """
        Discover all datasets for a simulation and create configuration objects.

        Automatically flags datasets with "Power" in the name for base_power multiplication.

        Args:
            simulation: Optional simulation name. If None, uses currently selected model.

        Returns:
            List of SiennaSimulationDataset configurations
        """
        datasets_dict = self.list_datasets(simulation=simulation)

        dataset_configs = []
        for name, h5_path in datasets_dict.items():
            # Auto-detect if base_power should be applied
            apply_base_power = "Power" in name

            config = SiennaSimulationDataset(
                name=name, h5_path=h5_path, apply_base_power=apply_base_power
            )
            dataset_configs.append(config)

        logger.info(f"Discovered {len(dataset_configs)} datasets")
        power_datasets = [c for c in dataset_configs if c.apply_base_power]
        logger.info(
            f"  {len(power_datasets)} datasets flagged for base_power multiplication"
        )

        return dataset_configs

    def set_dataset_configs(self, configs: List[SiennaSimulationDataset]):
        """
        Set custom dataset configurations.

        This allows users to override auto-detection and specify exactly which
        datasets should have base_power applied and with what multipliers.

        Args:
            configs: List of SiennaSimulationDataset configurations
        """
        self.dataset_configs = configs
        logger.info(f"Updated dataset configurations: {len(configs)} datasets")

    def _get_base_power(self) -> Optional[float]:
        """
        Override base class to provide Sienna-specific base_power.

        Returns:
            Base power from selected model, or None if no model selected
        """
        return self.base_power

    def get_raw_dataset(
        self, key: str, simulation: Optional[str] = None
    ) -> pd.DataFrame | None:
        """
        Retrieve a raw dataset from the Sienna simulation file.

        This is the Sienna implementation of the abstract get_raw_dataset method.
        Returns data in native per-unit values without scaling.

        :param key: Dataset key or full h5 path (e.g. ActivePowerVariable__ThermalStandard)
        :param simulation: Optional simulation name to query. If None, uses currently selected model.
        """
        # Temporarily switch model if simulation parameter provided
        original_model = self._selected_model
        try:
            if simulation is not None:
                self.selected_model = simulation

            if self._selected_model is None:
                raise ValueError(
                    "No simulation model selected. Please set the 'selected_model' property or pass 'simulation' parameter."
                )

            # Check if key is a friendly name that maps to an h5 path
            raw_datasets = self.list_raw_datasets()
            if key in raw_datasets.keys():
                key = raw_datasets[key]

            # Determine if this is emulation or decision model data based on root path
            root_path = self._selected_model.root_path
            if root_path.startswith("/simulation/emulation_model"):
                return self._get_emulation_data(key)
            elif root_path.startswith("/simulation/decision_models"):
                # Decision model - use model's merge strategy from config
                merge_strategy = self._selected_model.merge
                return self._get_decision_data(key, merge_strategy=merge_strategy)
            else:
                logger.error(f"Unknown model type for root path: {root_path}")
                raise ValueError(f"Unknown model type for selected model")

        except KeyError:
            logger.warning(
                f"{key} dataset not found in h5 file, use one of the following datasets"
            )
            print("----- Available Raw Datasets -----", file=sys.stderr)
            for k in self.list_raw_datasets().keys():
                print(k, file=sys.stderr)
            return None

        except FileNotFoundError:
            raise FileNotFoundError

        except Exception as e:
            print(f"An exception has occurred in get_raw_dataset: {e}")
            return None
        finally:
            # Restore original model if we temporarily switched
            if simulation is not None:
                self._selected_model = original_model

    def list_raw_datasets(self, simulation: Optional[str] = None) -> dict:
        """
        List all raw datasets available in the Sienna simulation file.

        This is the Sienna implementation of the abstract list_raw_datasets method.

        :param simulation: Optional simulation name to query. If None, uses currently selected model.
        :returns:
            A dictionary of the dataset names and corresponding h5 paths.
            Requires a model to be selected first (or passed via simulation parameter).
            Ignores the additional "__columns" datasets
        """
        # Temporarily switch model if simulation parameter provided
        original_model = self._selected_model
        try:
            if simulation is not None:
                self.selected_model = simulation

            if self._selected_model is None:
                raise ValueError(
                    "No simulation model selected. Please set the 'selected_model' property or pass 'simulation' parameter."
                )

            with h5py.File(self.file_path, "r") as h5data:
                # Use the root_path from the selected model
                root_path = self._selected_model.root_path

                datasets = {}
                if root_path in h5data:
                    root_group = h5data[root_path]

                    for category_name in root_group.keys():
                        category_path = f"{root_path}/{category_name}"
                        category_item = h5data[category_path]

                        # Check if category is a group or dataset
                        if isinstance(category_item, h5py.Group):
                            # Category is a group, iterate through its contents
                            for item_name in category_item.keys():
                                if not item_name.endswith("__columns"):
                                    datasets[item_name] = f"{category_path}/{item_name}"
                        elif isinstance(category_item, h5py.Dataset):
                            # Category is a dataset, add it directly if it's not a columns dataset
                            if not category_name.endswith("__columns"):
                                datasets[category_name] = category_path

                return datasets

        except Exception as e:
            print(f"An exception has occurred in list_raw_datasets: {e}")
            return {}
        finally:
            # Restore original model if we temporarily switched
            if simulation is not None:
                self._selected_model = original_model

    def copy(self, selected_model: Optional[str] = None) -> "SiennaSimulationParser":
        """
        Create a copy of this parser with independent configuration.

        Parameters:
        -----------
        selected_model : str, optional
            Model to select in the new parser. If None, uses current selected_model.

        Returns:
        --------
        SiennaSimulationParser
            New parser instance with independent configuration
        """
        # Create new parser instance
        new_parser = SiennaSimulationParser.__new__(SiennaSimulationParser)

        # Copy file path
        new_parser.file_path = self.file_path

        # Deep copy the configuration to ensure independence
        new_parser.config = copy.deepcopy(self.config)

        # Set the selected model
        if selected_model is not None:
            new_parser.selected_model = selected_model
        else:
            # Copy current selection
            current_model_name = (
                self._selected_model.name if self._selected_model else None
            )
            new_parser.selected_model = current_model_name

        return new_parser
