"""Dataset metadata and composition definitions for GAT v1.0.0.

Provides the core data classes that describe datasets throughout the system:
- DatasetKind: whether a dataset is raw (parsed from files) or composed (union of raw datasets)
- DatasetInfo: metadata about a dataset returned by list_datasets()
- DatasetComposition: defines how raw datasets combine into a composed dataset
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class DatasetKind(Enum):
    """Distinguishes raw datasets from composed datasets."""

    RAW_SYSTEM = "raw_system"
    RAW_SIMULATION = "raw_simulation"
    COMPOSED = "composed"


@dataclass
class DatasetInfo:
    """Metadata about a dataset returned by list_datasets().

    Both raw and composed datasets appear in the same list.
    The `kind` field indicates whether a dataset was parsed directly
    from source files or is a transposed union of other datasets.
    """

    name: str
    description: str
    kind: DatasetKind
    entity_column: str
    columns: list[str] | None = None
    source_datasets: list[str] | None = None
    row_count: int | None = None


@dataclass
class DatasetComposition:
    """Defines a composed dataset as a transposed union of raw datasets.

    The composed table is materialized during ingestion:
    - Raw sim tables are timestamp-rows × entity-columns
    - The composed table is entity-rows × timestamp-columns
    - No aggregation — just stacking rows from multiple raw datasets

    Example:
        DatasetComposition(
            name="generation",
            description="All generation output",
            source_datasets=[
                "ActivePowerVariable__ThermalStandard",
                "ActivePowerVariable__RenewableDispatch",
            ],
            entity_column="entity_id",
        )
    """

    name: str
    description: str
    source_datasets: list[str]
    entity_column: str = "entity_id"
