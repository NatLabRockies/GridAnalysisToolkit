"""Sienna simulation implementation for GAT v1.0.0.

Wraps the existing SiennaSimulationParser to implement the BaseSimulation
interface, exposing Sienna H5 simulation files as generic named datasets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

from ..categories import CategoryMap
from ..datasets import DatasetComposition, DatasetInfo, DatasetKind
from ..interfaces import BaseSimulation
from .utils import resolve_compositions

# Default compositions mapping composed dataset names to H5 dataset name patterns.
# These are glob patterns matched against raw dataset names.
_DEFAULT_COMPOSITIONS: dict[str, list[str]] = {
    "generation": [
        "ActivePowerVariable__*",
        "ActivePowerOutVariable__*",
    ],
    "load": [
        "ActivePowerTimeSeriesParameter__*Load*",
        "ActivePowerTimeSeriesParameter__*Admittance*",
    ],
    "line_flow": [
        "FlowActivePowerVariable__*",
    ],
    "reserve": [
        "*ReserveVariable__*",
    ],
    "availability": [
        "ActivePowerTimeSeriesParameter__RenewableDispatch",
        "ActivePowerTimeSeriesParameter__RenewableNonDispatch",
    ],
    # Storage charging: power flowing INTO storage devices (batteries,
    # pumped hydro). Used for total demand = native load + charging.
    "charging": [
        "ActivePowerInVariable__EnergyReservoirStorage",
        "ActivePowerInVariable__HydroPumpedStorage",
        "ActivePowerInVariable__GenericBattery",
    ],
}


class SiennaSimulation(BaseSimulation):
    """Sienna simulation implementation wrapping SiennaSimulationParser.

    Exposes H5 datasets as named datasets and provides default composed
    datasets (generation, load, line_flow) based on naming conventions.

    Args:
        simulation_path: Path to the Sienna simulation H5 file.
        simulation: Name of the simulation model to use (e.g., "UC", "ED").
            If None, uses the parser's default (first emulation model).
        compositions: Override the default composition patterns.
            Keys are composed dataset names, values are lists of glob patterns.
    """

    def __init__(
        self,
        simulation_path: str | Path,
        simulation: str | None = None,
        compositions: dict[str, list[str]] | None = None,
    ) -> None:
        from ..simulations.sienna import SiennaSimulationParser

        self._parser = SiennaSimulationParser(str(simulation_path))

        if simulation is not None:
            self._parser.selected_model = simulation

        self._compositions = compositions or _DEFAULT_COMPOSITIONS

        # Cache raw dataset listing
        self._raw_datasets: dict[str, str] | None = None
        # Cache for resolved compositions (name → list of matched raw dataset names)
        self._resolved_compositions: dict[str, list[str]] | None = None

        logger.info(
            "SiennaSimulation loaded: model='{}', {} raw datasets discovered",
            self._parser.simulation,
            len(self._get_raw_datasets()),
        )

    @classmethod
    def from_paths(
        cls,
        paths: str | Path | list[str | Path],
        simulation: str | None = None,
        **kwargs,
    ) -> "BaseSimulation":
        """Override of BaseSimulation.from_paths: the across-file merge
        direction comes from the selected model's own
        ``SiennaModelConfig.merge`` (already exposed as
        ``SiennaSimulationParser.merge_strategy``) rather than
        ``MultiFileSimulation``'s generic default -- a UC/decision model
        and an emulation model can legitimately want different behavior
        at a partition seam, and this reuses the existing per-model
        setting instead of picking one global default.
        """
        path_list = [paths] if isinstance(paths, (str, Path)) else list(paths)

        if len(path_list) == 1:
            return cls(path_list[0], simulation=simulation, **kwargs)

        from .sienna import SiennaSimulationParser

        # Every partition of one logical simulation shares the same
        # model, so the first file's config is representative -- this is
        # a metadata-only read (SiennaSimulationConfig.from_h5_file opens
        # the file in a `with` block), not a full data parse.
        probe = SiennaSimulationParser(str(path_list[0]))
        if simulation is not None:
            probe.selected_model = simulation
        merge_strategy = probe.merge_strategy or "earlier_wins"

        from .multi_file import MultiFileSimulation

        return MultiFileSimulation(
            cls,
            path_list,
            merge_strategy=merge_strategy,
            simulation=simulation,
            **kwargs,
        )

    @property
    def parser(self) -> object:
        """Access the underlying SiennaSimulationParser for advanced use."""
        return self._parser

    @property
    def base_power(self) -> float:
        """Return the simulation's base_power in MW."""
        return self._parser.base_power or 100.0

    def _get_raw_datasets(self) -> dict[str, str]:
        """Get raw datasets dict, with caching."""
        if self._raw_datasets is None:
            self._raw_datasets = self._parser.list_raw_datasets()
        return self._raw_datasets

    def _resolve_compositions(self) -> dict[str, list[str]]:
        """Resolve composition patterns to actual raw dataset names."""
        if self._resolved_compositions is not None:
            return self._resolved_compositions

        raw_names = list(self._get_raw_datasets().keys())
        resolved = resolve_compositions(raw_names, self._compositions)

        for comp_name, patterns in self._compositions.items():
            if comp_name not in resolved:
                logger.debug(
                    "No raw datasets matched patterns for '{}': {}",
                    comp_name,
                    patterns,
                )

        self._resolved_compositions = resolved
        return resolved

    def list_datasets(self) -> list[DatasetInfo]:
        result: list[DatasetInfo] = []

        # Raw simulation datasets
        for ds_name in sorted(self._get_raw_datasets().keys()):
            result.append(
                DatasetInfo(
                    name=ds_name,
                    description=f"Sienna simulation dataset",
                    kind=DatasetKind.RAW_SIMULATION,
                    entity_column="entity_id",
                )
            )

        # Composed datasets
        for comp_name, source_datasets in self._resolve_compositions().items():
            result.append(
                DatasetInfo(
                    name=comp_name,
                    description=f"Composed dataset ({len(source_datasets)} sources)",
                    kind=DatasetKind.COMPOSED,
                    entity_column="entity_id",
                    source_datasets=source_datasets,
                )
            )

        return result

    def get_dataset(self, name: str) -> pd.DataFrame:
        raw_datasets = self._get_raw_datasets()
        compositions = self._resolve_compositions()

        # Check composed datasets first
        if name in compositions:
            frames = []
            for ds_name in compositions[name]:
                df = self._get_raw_df(ds_name)
                if df is not None:
                    frames.append(df)
            if not frames:
                raise KeyError(f"No data available for composed dataset '{name}'")
            return pd.concat(frames, axis=1)

        # Raw dataset
        if name in raw_datasets:
            df = self._get_raw_df(name)
            if df is None:
                raise KeyError(f"Failed to read dataset '{name}'")
            return df

        available = sorted(raw_datasets.keys()) + sorted(compositions.keys())
        raise KeyError(f"Dataset '{name}' not found. Available: {available}")

    def _get_raw_df(self, name: str) -> pd.DataFrame | None:
        """Get a raw dataset as a DataFrame with float32 values."""
        df = self._parser.get_raw_dataset(name)
        if df is None:
            return None

        # Cast float64 to float32
        float_cols = df.select_dtypes(include=[np.float64]).columns
        if len(float_cols) > 0:
            df = df.copy()
            df[float_cols] = df[float_cols].astype(np.float32)

        return df
