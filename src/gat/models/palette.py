# gat/models/palette.py
"""
Palette models for GAT.

Palettes define how simulation data is aggregated and displayed:
- Map simulation categories to display categories
- Define colors, hatches, and visual properties
- Control stacking order in plots
- Override specific generators to custom categories
- Handle VRE (Variable Renewable Energy) and load classifications

Palettes can exist at user level (~/.config/gat/palettes/) or project level
(project/palettes/) and can be shared across teams.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class DisplayCategory(BaseModel):
    """
    Visual properties for a display category.

    A display category is what users see in plots - multiple simulation
    categories can map to the same display category.
    """

    name: str
    color: str  # Hex color code or named color
    hatch: Optional[str] = (
        None  # Matplotlib hatch pattern (e.g., '///', '\\\\\\', 'xx')
    )
    width: Optional[float] = None  # Line width or bar width multiplier
    alpha: Optional[float] = 1.0  # Transparency (0-1)
    label: Optional[str] = None  # Display label (defaults to name if not set)

    def get_label(self) -> str:
        """Get the display label, falling back to name if not set."""
        return self.label if self.label else self.name


class CategoryMapping(BaseModel):
    """
    Maps simulation categories to display categories.

    For example:
    - simulation_category: "Gas_CT", "Gas_CC", "Gas_Steam"
    - display_category: "Natural Gas"
    """

    simulation_category: str
    display_category: str


class GeneratorOverride(BaseModel):
    """
    Override mapping for specific generators.

    This allows specific generators to be assigned to custom categories,
    overriding the default simulation category mapping. Useful for:
    - Grouping generators in a hydro cascade
    - Highlighting specific resources
    - Creating custom aggregations
    """

    generator_name: str
    custom_category: str  # The custom category name
    display_category: str  # Which display category to use


class LoadClassification(BaseModel):
    """
    Classification of load types for net load calculations.

    Defines what counts as:
    - Native load (excluding flexible loads)
    - Total load (including charging)
    - Storage charging load
    """

    storage_charging_categories: List[str] = Field(
        default_factory=list,
        description="Simulation categories that count as storage charging",
    )
    flexible_load_categories: List[str] = Field(
        default_factory=list,
        description="Simulation categories that count as flexible load",
    )


class VREClassification(BaseModel):
    """
    Classification of Variable Renewable Energy (VRE) sources.

    Defines which generation counts as VRE for curtailment calculations
    and net load analysis. Technology is defined at the simulation level,
    not display category level, to handle hybrid resources like PV+Battery
    (where PV is VRE but battery is not).
    """

    vre_technologies: List[str] = Field(
        default_factory=list,
        description="Simulation technologies that count as VRE (e.g., 'Solar_PV', 'Wind')",
    )
    curtailable_technologies: List[str] = Field(
        default_factory=list,
        description="Simulation technologies that can be curtailed",
    )


class Palette(BaseModel):
    """
    A complete palette definition for data aggregation and visualization.

    Palettes control how raw simulation data is aggregated and displayed:
    1. Category mappings: simulation categories → display categories
    2. Display properties: colors, hatches, labels for each display category
    3. Stack order: order of categories in stacked plots
    4. Generator overrides: specific generators → custom categories
    5. Classifications: VRE, curtailment, load types

    Example usage:
        palette = Palette(
            name="Renewable Focus",
            simulation_type="sienna",
            display_categories=[
                DisplayCategory(name="Solar", color="#FFD700"),
                DisplayCategory(name="Wind", color="#87CEEB"),
                DisplayCategory(name="Gas", color="#FF6B6B"),
            ],
            category_mappings=[
                CategoryMapping(simulation_category="Solar_PV", display_category="Solar"),
                CategoryMapping(simulation_category="Wind_Onshore", display_category="Wind"),
                CategoryMapping(simulation_category="Gas_CT", display_category="Gas"),
                CategoryMapping(simulation_category="Gas_CC", display_category="Gas"),
            ],
            stack_order=["Solar", "Wind", "Gas"],
        )
    """

    # Metadata
    name: str
    description: Optional[str] = None
    simulation_type: str  # sienna, plexos, reeds, or "universal"
    version: str = "1.0.0"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    # Link to the analytical layer
    category_map: Optional[str] = None  # CategoryMap name (e.g. "fuel", "prime_mover")
    dimension: str = "technology"  # "technology" | "area" | "custom"

    # Display categories with visual properties
    display_categories: List[DisplayCategory] = Field(
        default_factory=list,
        description="Display categories with their visual properties",
    )

    # Mappings from simulation data to display categories
    category_mappings: List[CategoryMapping] = Field(
        default_factory=list,
        description="Map simulation categories to display categories",
    )

    # Stack order for plots (display category names in order)
    stack_order: List[str] = Field(
        default_factory=list,
        description="Order of display categories in stacked plots (bottom to top)",
    )

    # Generator-specific overrides
    generator_overrides: List[GeneratorOverride] = Field(
        default_factory=list,
        description="Override specific generators to custom categories",
    )

    # Classifications for special handling
    vre_classification: Optional[VREClassification] = None
    load_classification: Optional[LoadClassification] = None

    # Default settings
    default_colormap: Optional[str] = None  # For continuous data
    show_legend: bool = True
    legend_location: str = "best"

    def get_display_category(self, name: str) -> Optional[DisplayCategory]:
        """Get a display category by name."""
        for cat in self.display_categories:
            if cat.name == name:
                return cat
        return None

    def get_mapping_for_simulation_category(
        self, simulation_category: str
    ) -> Optional[str]:
        """
        Get the display category for a simulation category.

        Args:
            simulation_category: The simulation category name

        Returns:
            Display category name, or None if no mapping exists
        """
        for mapping in self.category_mappings:
            if mapping.simulation_category == simulation_category:
                return mapping.display_category
        return None

    def get_override_for_generator(self, generator_name: str) -> Optional[str]:
        """
        Get the custom category for a generator if overridden.

        Args:
            generator_name: The generator name

        Returns:
            Display category name, or None if no override exists
        """
        for override in self.generator_overrides:
            if override.generator_name == generator_name:
                return override.display_category
        return None

    def get_aggregation_map(self) -> Dict[str, str]:
        """Get a mapping of simulation categories to display categories.

        Used to re-aggregate a grouped query result: values from simulation
        categories that map to the same display category are summed.

        Returns:
            Dict mapping simulation category name → display category name.
        """
        return {
            m.simulation_category: m.display_category
            for m in self.category_mappings
        }

    def get_ordered_display_names(self) -> List[str]:
        """Return display category names in stack order.

        Categories in ``stack_order`` come first (in that order), followed by
        any display categories not listed in ``stack_order``.
        """
        ordered = list(self.stack_order)
        all_names = {cat.name for cat in self.display_categories}
        for name in all_names - set(ordered):
            ordered.append(name)
        return ordered

    def get_color_map(self) -> Dict[str, str]:
        """Get a mapping of display category names to colors."""
        return {cat.name: cat.color for cat in self.display_categories}

    def get_hatch_map(self) -> Dict[str, Optional[str]]:
        """Get a mapping of display category names to hatch patterns."""
        return {cat.name: cat.hatch for cat in self.display_categories}

    def is_vre(self, simulation_technology: str) -> bool:
        """Check if a simulation technology is classified as VRE."""
        if not self.vre_classification:
            return False
        return simulation_technology in self.vre_classification.vre_technologies

    def is_curtailable(self, simulation_technology: str) -> bool:
        """Check if a simulation technology is curtailable."""
        if not self.vre_classification:
            return False
        return simulation_technology in self.vre_classification.curtailable_technologies

    def is_storage_charging(self, simulation_category: str) -> bool:
        """Check if a simulation category counts as storage charging."""
        if not self.load_classification:
            return False
        return (
            simulation_category in self.load_classification.storage_charging_categories
        )

    def validate_stack_order(self) -> List[str]:
        """
        Validate that stack_order contains all display categories.

        Returns:
            List of warnings for missing or extra categories
        """
        warnings = []
        display_names = {cat.name for cat in self.display_categories}
        stack_names = set(self.stack_order)

        missing = display_names - stack_names
        if missing:
            warnings.append(
                f"Display categories not in stack_order: {', '.join(missing)}"
            )

        extra = stack_names - display_names
        if extra:
            warnings.append(
                f"stack_order contains undefined categories: {', '.join(extra)}"
            )

        return warnings

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Renewable Focus",
                "description": "Emphasizes renewable energy sources",
                "simulation_type": "sienna",
                "version": "1.0.0",
                "display_categories": [
                    {"name": "Solar", "color": "#FFD700"},
                    {"name": "Wind", "color": "#87CEEB"},
                    {"name": "Gas", "color": "#FF6B6B"},
                ],
                "category_mappings": [
                    {
                        "simulation_category": "Solar_PV",
                        "display_category": "Solar",
                    },
                    {
                        "simulation_category": "Wind_Onshore",
                        "display_category": "Wind",
                    },
                ],
                "stack_order": ["Solar", "Wind", "Gas"],
            }
        }
