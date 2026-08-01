import fnmatch
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class Technology(BaseModel):
    # whether the technology is considered curtailable
    # autofill attempted
    curtailable: bool = False

    # The simplified technology name that determines grouped aggregation and
    # display name in resulting data and plots.
    # Autofill attempted.
    display_group: str = "Other"

    # The display color. Autofill attempted.
    display_color: str

    # The order of the display for dispatch stacks. Autofill attempted.
    # If duplicate display orders? Sort by Alphabetical?
    display_order: int = -1


class RelationSource(BaseModel):
    # the type of relationship
    # node->area
    # generator->area
    # load->area
    # generator->node
    # load->node
    relation_type: str
    file_type: str  # Json or csv
    location: str  # path to source


class Node(BaseModel):
    type: str  # BUs? Do we need type?
    id: str  # UUID
    display_name: str  # Name
    latitude: Optional[float]
    longitude: Optional[float]


class RawDataset(BaseModel):
    """
    Configuration for a single raw dataset from the simulation.

    Attributes:
        h5_path: Path to the dataset in the H5 file (e.g., "/simulation/decision_models/UC/variables/ActivePowerVariable__Gen1")
        scale_factor: Scaling factor to apply. Set to base_power value for power datasets, or custom value (default: 1.0)
    """

    h5_path: str
    scale_factor: float = 1.0


class AggregateDataset(BaseModel):
    """
    Configuration for an aggregate dataset composed of multiple raw datasets.

    Attributes:
        patterns: List of glob patterns to match raw datasets (e.g., ["ActivePowerVariable__*"])
        scale_factor: Scaling factor to apply. Set to base_power value for power datasets, or custom value (default: 1.0)
        combination_method: How to combine datasets - 'concat' (default) or 'sum'
    """

    patterns: List[str]
    scale_factor: float = 1.0
    combination_method: str = "concat"  # 'concat' or 'sum'

    @field_validator("patterns")
    @classmethod
    def validate_patterns(cls, v):
        """Ensure patterns list is not empty."""
        if not v:
            raise ValueError("Patterns list cannot be empty")
        return v

    @field_validator("combination_method")
    @classmethod
    def validate_combination_method(cls, v):
        """Ensure combination_method is valid."""
        if v not in ["concat", "sum"]:
            raise ValueError("combination_method must be 'concat' or 'sum'")
        return v


# Union type for dataset definitions
DatasetDefinition = Union[RawDataset, AggregateDataset]


class DatasetConfig(BaseModel):
    """
    Configuration for named datasets in a scenario.

    This provides a unified interface where each named dataset can be either:
    - A RawDataset: Direct reference to a single dataset in the simulation
    - An AggregateDataset: Combination of multiple datasets via patterns

    The parser's get_dataset() and list_datasets() methods use this configuration
    to provide a curated view of the simulation data.

    Example:
        aggregates = {
            "generation": AggregateDataset(patterns=["ActivePowerVariable__*"]),
            "flow": AggregateDataset(patterns=["FlowActivePowerVariable__Line"]),
            "specific_gen": RawDataset(h5_path="/path/to/dataset")
        }
    """

    # Dictionary mapping friendly names to dataset definitions
    aggregates: Dict[str, DatasetDefinition] = Field(default_factory=dict)

    def get_dataset_config(self, name: str) -> Optional[DatasetDefinition]:
        """
        Get dataset configuration by name.

        Args:
            name: Name of the dataset

        Returns:
            DatasetDefinition (RawDataset or AggregateDataset) if found, None otherwise
        """
        return self.aggregates.get(name)

    def add_dataset(
        self, name: str, definition: DatasetDefinition, overwrite: bool = False
    ):
        """
        Add a dataset configuration.

        Args:
            name: Name for the dataset
            definition: RawDataset or AggregateDataset configuration
            overwrite: Whether to overwrite if name already exists

        Raises:
            ValueError: If name exists and overwrite is False
        """
        if name in self.aggregates and not overwrite:
            raise ValueError(
                f"Dataset '{name}' already exists. Set overwrite=True to replace."
            )
        self.aggregates[name] = definition

    def remove_dataset(self, name: str):
        """Remove a dataset configuration."""
        self.aggregates.pop(name, None)

    def list_dataset_names(self) -> List[str]:
        """List all configured dataset names."""
        return list(self.aggregates.keys())

    def validate_datasets(
        self, available_raw_datasets: List[str]
    ) -> Dict[str, List[str]]:
        """
        Validate dataset configurations against available raw datasets.

        Args:
            available_raw_datasets: List of available raw dataset names from simulation

        Returns:
            Dictionary mapping dataset names to their matched raw datasets
            (For RawDataset, returns single-item list; for AggregateDataset, returns all matches)

        Raises:
            ValueError: If any dataset configuration is invalid
        """
        results = {}
        errors = []

        for name, definition in self.aggregates.items():
            if isinstance(definition, RawDataset):
                # For raw datasets, verify the h5_path exists
                # Note: h5_path validation happens at parser level
                results[name] = [definition.h5_path]

            elif isinstance(definition, AggregateDataset):
                # For aggregate datasets, match patterns
                matches = set()
                for pattern in definition.patterns:
                    has_match = False
                    for dataset in available_raw_datasets:
                        if fnmatch.fnmatch(dataset, pattern):
                            has_match = True
                            matches.add(dataset)

                    if not has_match:
                        errors.append(
                            f"Dataset '{name}': pattern '{pattern}' matched no raw datasets"
                        )

                if not matches:
                    errors.append(f"Dataset '{name}' has no matching raw datasets")
                else:
                    results[name] = sorted(list(matches))

        if errors:
            raise ValueError(
                "Dataset validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        return results
