import os
import warnings
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel

from .base import AggregateDataset, DatasetConfig, RawDataset


class SiennaRelation(BaseModel):
    """Defines how to look up component relationships in the system JSON."""

    component_type: str  # The component type to look up in the system json
    component_index_column: Optional[str] = "name"  # The column to use as the index/key
    component_value_column: Optional[str] = "bus"  # The column to use as the value


class SiennaSystemConfig(BaseModel):
    """Configuration for Sienna system-specific settings."""

    data_format_version: str
    load_components: Optional[List[SiennaRelation]] = None
    generation_components: Optional[List[str]] = None
    line_rate_relation: Optional[SiennaRelation] = None
    # The column in ACBus to use as the area lookup value. Can be found in ext.
    area_column: Optional[str] = None

    def save_to_yaml(
        self, filepath: str, dataset_config: Optional[DatasetConfig] = None
    ) -> None:
        """
        Save the configuration to a YAML file.

        Args:
            filepath: Path where the YAML file will be saved
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)

        # Convert model to dict
        config_dict = self.model_dump()

        # Add dataset_config if provided
        if dataset_config:
            config_dict["dataset_config"] = dataset_config.model_dump()

        # Write to YAML file
        with open(filepath, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False)

    @classmethod
    def load_from_yaml(cls, filepath: str) -> "SiennaSystemConfig":
        """
        Load configuration from a YAML file.

        Args:
            filepath: Path to the YAML file

        Returns:
            A new SiennaConfig instance with the loaded configuration
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Config file not found: {filepath}")

        with open(filepath, "r") as file:
            config_dict = yaml.safe_load(file)

        return cls(**config_dict)


def initialize_sienna_dataset_config(
    data_format_version: str = "4.0.0",
) -> DatasetConfig:
    """
    Initialize default dataset configuration for Sienna simulations.

    Args:
        data_format_version: Sienna data format version (default: "4.0.0")

    Returns:
        DatasetConfig with default aggregate datasets for Sienna
    """
    from typing import cast

    from .base import DatasetDefinition

    # Note: scale_factor defaults to 1.0, parser will apply base_power scaling
    # Set scale_factor to base_power value when retrieved, or keep as 1.0 for no scaling
    aggregates: Dict[str, DatasetDefinition] = cast(
        Dict[str, DatasetDefinition],
        {
            "generation": AggregateDataset(
                patterns=["ActivePowerVariable*", "ActivePowerOutVariable*"],
                scale_factor=1.0,  # Will be set to base_power by parser
            ),
            "charging": AggregateDataset(
                patterns=["ActivePowerInVariable*"],
                scale_factor=1.0,
            ),
            "availability": AggregateDataset(
                patterns=["ActivePowerTimeSeriesParameter__RenewableDispatch"],
                scale_factor=1.0,
            ),
            "load": AggregateDataset(
                patterns=[
                    "ActivePowerTimeSeriesParameter__StandardLoad",
                    "ActivePowerTimeSeriesParameter__PowerLoad",
                ],
                scale_factor=1.0,
            ),
            "flow": AggregateDataset(
                patterns=["FlowActivePowerVariable__Line"],
                scale_factor=1.0,
            ),
            "dc_flow": AggregateDataset(
                patterns=["FlowActivePowerVariable__TwoTerminalHVDCLine"],
                scale_factor=1.0,
            ),
            "power_balance": AggregateDataset(
                patterns=["SystemBalanceSlackUp__System"],
                scale_factor=1.0,
            ),
            "cost": AggregateDataset(
                patterns=["ProductionCostExpression*"],
                scale_factor=1.0,  # Cost typically doesn't scale
            ),
            "interchange": AggregateDataset(
                patterns=["FlowActivePowerVariable__AreaInterchange"],
                scale_factor=1.0,
            ),
        },
    )

    return DatasetConfig(aggregates=aggregates)


def initialize_sienna_system_config(data_format_version: str) -> SiennaSystemConfig:
    """
    Initialize system configuration for Sienna.

    Args:
        data_format_version: Sienna data format version

    Returns:
        SiennaSystemConfig with version-specific settings
    """
    system_config = SiennaSystemConfig(
        data_format_version=data_format_version,
        generation_components=[
            "EnergyReservoirStorage",
            "HydroDispatch",
            "HydroEnergyReservoir",
            "HydroPumpedStorage",
            "RenewableDispatch",
            "RenewableNonDispatch",
            "ThermalStandard",
            "ThermalMultiStart",
        ],
        line_rate_relation=None,
    )

    if data_format_version == "4.0.0":
        system_config.load_components = [
            SiennaRelation(
                component_type="PowerLoad",
            ),
            SiennaRelation(
                component_type="StandardLoad",
            ),
            SiennaRelation(
                component_type="ACBus",
                component_index_column="number",
                component_value_column="UUID",
            ),
        ]

        system_config.line_rate_relation = SiennaRelation(
            component_type="Line",
            component_index_column="name",
            component_value_column="rating",
        )

    elif data_format_version == "3.0.0":
        system_config.load_components = [
            SiennaRelation(
                component_type="PowerLoad",
            ),
            SiennaRelation(
                component_type="ACBus",
                component_index_column="number",
                component_value_column="UUID",
            ),
        ]
        if system_config.generation_components:
            system_config.generation_components.append("GenericBattery")
        system_config.line_rate_relation = SiennaRelation(
            component_type="Line",
            component_index_column="name",
            component_value_column="rate",
        )

    else:
        warnings.warn(
            f"Unsupported data format version: {data_format_version}. "
            "Please update the configuration manually",
            UserWarning,
        )

    return system_config
