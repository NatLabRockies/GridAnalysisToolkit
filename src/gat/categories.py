"""Category maps for GAT v1.0.0.

Category maps define how entity IDs map to category labels for GROUP BY
operations. They are stored in DuckDB as simple two-column tables
(entity_id, category) and joined to composed datasets during queries.

Sources can be:
- Direct dict mapping
- External file (CSV/Excel)
- Spatial geometry (shapefile/GeoJSON) with spatial join via a system table
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CategoryMap:
    """Maps entity_id values to category labels.

    Exactly one of `mapping`, `mapping_file`, or `geometry_file` should be set.

    Examples:
        # Direct mapping
        CategoryMap(
            name="technology_simple",
            description="Simplified technology groups",
            entity_column="entity_id",
            category_column="technology",
            mapping={"gen_101": "Gas", "gen_102": "Gas", "solar_01": "Solar"},
        )

        # From CSV file
        CategoryMap(
            name="iso_region",
            description="ISO region assignment",
            entity_column="entity_id",
            category_column="region",
            mapping_file="/path/to/gen_iso_map.csv",
        )

        # Spatial join
        CategoryMap(
            name="state",
            description="US state from bus coordinates",
            entity_column="entity_id",
            category_column="state",
            geometry_file="/path/to/us-states.shp",
            geometry_key="STATE_NAME",
            join_via="Bus",  # system dataset with lat/lon
        )
    """

    name: str
    description: str
    entity_column: str = "entity_id"
    category_column: str = "category"

    # Source — exactly one of these should be set:
    mapping: dict[str, str] | None = None
    mapping_file: str | None = None
    geometry_file: str | None = None
    geometry_key: str | None = None
    join_via: str | None = None

    # Which datasets this map applies to (None = auto-discover)
    applies_to: list[str] | None = None


class CategoryMapRegistry:
    """Manages registered category maps for a scenario.

    Category maps can be added by:
    - Extension developers (default maps from system data)
    - Users (external files, spatial data)
    """

    def __init__(self) -> None:
        self._maps: dict[str, CategoryMap] = {}

    def register(self, cat_map: CategoryMap) -> None:
        """Register a category map."""
        self._maps[cat_map.name] = cat_map

    def get(self, name: str) -> CategoryMap:
        """Get a category map by name."""
        if name not in self._maps:
            raise KeyError(
                f"Category map '{name}' not found. "
                f"Available: {list(self._maps.keys())}"
            )
        return self._maps[name]

    def list_maps(self) -> list[str]:
        """Return names of all registered category maps."""
        return list(self._maps.keys())

    def list_for_dataset(self, dataset_name: str) -> list[str]:
        """Return names of category maps applicable to a dataset.

        A map applies if:
        - applies_to is None (applies to all), or
        - dataset_name is in applies_to
        """
        return [
            name
            for name, cm in self._maps.items()
            if cm.applies_to is None or dataset_name in cm.applies_to
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._maps

    def __len__(self) -> int:
        return len(self._maps)
