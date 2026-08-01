# gat/palette_generator.py
"""
Palette generator for GAT.

Automatically generates palette configurations from system files using
the BaseSystem abstraction. Creates sensible defaults for display categories,
colors, classifications, and stack order.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from loguru import logger

from gat.datahelpers.base_system import BaseSystem, GeneratorCategory
from gat.models.palette import (
    CategoryMapping,
    DisplayCategory,
    LoadClassification,
    Palette,
    VREClassification,
)


class PaletteGenerator:
    """
    Generates palettes from system files.

    Uses BaseSystem implementations to extract generator categories
    and create default palette configurations with appropriate colors,
    classifications, and ordering.

    Example usage:
        from gat.datahelpers.sienna_system import SiennaSystem

        system = SiennaSystem("path/to/system.json")
        generator = PaletteGenerator(system)
        palette = generator.generate(
            name="My Palette",
            description="Auto-generated from system file"
        )
    """

    # Default color palette - categorized by type
    # Colors are from a colorblind-friendly palette
    COLORS = {
        # Renewables (greens/blues)
        "solar": "#FFD700",  # Gold
        "wind": "#87CEEB",  # Sky blue
        "hydro": "#4682B4",  # Steel blue
        "geothermal": "#8B4513",  # Saddle brown
        # Fossil fuels (reds/oranges/browns)
        "coal": "#2F4F4F",  # Dark slate gray
        "gas": "#FF6B6B",  # Light red
        "oil": "#8B0000",  # Dark red
        "nuclear": "#9370DB",  # Medium purple
        # Storage (grays/purples)
        "battery": "#9932CC",  # Dark orchid
        "storage": "#BA55D3",  # Medium orchid
        "pumped_hydro": "#8A2BE2",  # Blue violet
        # Other
        "biomass": "#228B22",  # Forest green
        "waste": "#A0522D",  # Sienna
        "other": "#808080",  # Gray
        "unknown": "#C0C0C0",  # Silver
    }

    # Technology keyword mappings for color selection
    TECH_KEYWORDS = {
        "solar": ["solar", "pv", "photovoltaic", "csp"],
        "wind": ["wind", "wt"],
        "hydro": ["hydro", "water"],
        "geothermal": ["geothermal", "geo"],
        "coal": ["coal"],
        "gas": ["gas", "ng", "naturalgas", "ccgt", "ct", "cc"],
        "oil": ["oil", "petroleum", "diesel"],
        "nuclear": ["nuclear", "nuc"],
        "battery": ["battery", "bess"],
        "storage": ["storage"],
        "pumped_hydro": ["pumped", "psh"],
        "biomass": ["biomass", "bio"],
        "waste": ["waste", "wte"],
    }

    def __init__(self, system: BaseSystem):
        """
        Initialize palette generator.

        Args:
            system: BaseSystem implementation for the target system file
        """
        self.system = system
        self._used_colors = set()

    def _match_color(self, category_name: str) -> str:
        """
        Match a category name to an appropriate color.

        Args:
            category_name: Generator category name

        Returns:
            Hex color code
        """
        name_lower = category_name.lower()

        # Try to match keywords
        for color_key, keywords in self.TECH_KEYWORDS.items():
            for keyword in keywords:
                if keyword in name_lower:
                    color = self.COLORS[color_key]
                    if color not in self._used_colors:
                        self._used_colors.add(color)
                        return color

        # Fallback to default colors
        default_colors = [
            "#1f77b4",  # Blue
            "#ff7f0e",  # Orange
            "#2ca02c",  # Green
            "#d62728",  # Red
            "#9467bd",  # Purple
            "#8c564b",  # Brown
            "#e377c2",  # Pink
            "#7f7f7f",  # Gray
            "#bcbd22",  # Olive
            "#17becf",  # Cyan
        ]

        for color in default_colors:
            if color not in self._used_colors:
                self._used_colors.add(color)
                return color

        # Last resort - return gray
        return self.COLORS["unknown"]

    def _simplify_category_name(self, category: GeneratorCategory) -> str:
        """
        Create a simplified display category name.

        Groups similar technologies together to avoid cluttering
        the legend with too many categories.

        Args:
            category: GeneratorCategory instance

        Returns:
            Simplified category name
        """
        name = category.name

        # Solar variations -> Solar
        if any(k in name.lower() for k in ["solar", "pv", "photovoltaic"]):
            if "csp" in name.lower():
                return "CSP"
            return "Solar"

        # Wind variations -> Wind
        if "wind" in name.lower():
            if "offshore" in name.lower():
                return "Wind Offshore"
            return "Wind"

        # Gas variations -> Natural Gas
        if any(k in name.lower() for k in ["gas", "ng", "naturalgas"]):
            if "ccgt" in name.lower() or "cc" in name.lower():
                return "Natural Gas CC"
            if "ct" in name.lower():
                return "Natural Gas CT"
            return "Natural Gas"

        # Hydro variations -> Hydro
        if "hydro" in name.lower():
            if "pumped" in name.lower():
                return "Pumped Hydro"
            if "reservoir" in name.lower():
                return "Hydro Reservoir"
            return "Hydro"

        # Storage variations -> Battery Storage
        if any(k in name.lower() for k in ["battery", "bess"]):
            return "Battery Storage"

        if "storage" in name.lower() and "hydro" not in name.lower():
            return "Energy Storage"

        # Coal variations -> Coal
        if "coal" in name.lower():
            return "Coal"

        # Nuclear variations -> Nuclear
        if "nuclear" in name.lower() or "nuc" in name.lower():
            return "Nuclear"

        # Biomass variations -> Biomass
        if "biomass" in name.lower() or "bio" in name.lower():
            return "Biomass"

        # Otherwise return cleaned name
        return name.replace("_", " ")

    def _create_display_categories(
        self, generator_categories: List[GeneratorCategory]
    ) -> Tuple[List[DisplayCategory], List[CategoryMapping]]:
        """
        Create display categories and mappings from generator categories.

        Args:
            generator_categories: List of GeneratorCategory from system

        Returns:
            Tuple of (display_categories, category_mappings)
        """
        # Group by simplified names
        category_groups: Dict[str, List[GeneratorCategory]] = {}
        for cat in generator_categories:
            display_name = self._simplify_category_name(cat)
            if display_name not in category_groups:
                category_groups[display_name] = []
            category_groups[display_name].append(cat)

        # Create display categories
        display_categories = []
        category_mappings = []

        for display_name, cats in category_groups.items():
            # Get color based on first category
            color = self._match_color(cats[0].name)

            display_cat = DisplayCategory(
                name=display_name,
                color=color,
                label=display_name,
            )
            display_categories.append(display_cat)

            # Create mappings for all simulation categories
            for cat in cats:
                mapping = CategoryMapping(
                    simulation_category=cat.name, display_category=display_name
                )
                category_mappings.append(mapping)

        return display_categories, category_mappings

    def _create_stack_order(
        self,
        display_categories: List[DisplayCategory],
        generator_categories: List[GeneratorCategory],
    ) -> List[str]:
        """
        Create a sensible stack order for display categories.

        Orders categories from bottom to top in a typical dispatch stack:
        1. Nuclear (baseload)
        2. Coal
        3. Hydro
        4. Natural Gas
        5. Biomass/Other
        6. Wind
        7. Solar
        8. Storage (on top)

        Args:
            display_categories: List of DisplayCategory
            generator_categories: Original generator categories

        Returns:
            Ordered list of display category names
        """
        # Priority order (lower = bottom of stack)
        priority_order = {
            "nuclear": 1,
            "coal": 2,
            "hydro": 3,
            "gas": 4,
            "biomass": 5,
            "other": 6,
            "wind": 7,
            "solar": 8,
            "battery": 9,
            "storage": 9,
        }

        def get_priority(display_name: str) -> int:
            """Get priority for a display category."""
            name_lower = display_name.lower()
            for key, priority in priority_order.items():
                if key in name_lower:
                    return priority
            return 99  # Unknown categories at top

        # Sort by priority
        sorted_cats = sorted(display_categories, key=lambda c: get_priority(c.name))

        return [cat.name for cat in sorted_cats]

    def _create_vre_classification(
        self, generator_categories: List[GeneratorCategory]
    ) -> VREClassification:
        """
        Create VRE classification from generator categories.

        Args:
            generator_categories: List of GeneratorCategory

        Returns:
            VREClassification instance
        """
        vre_technologies = [cat.name for cat in generator_categories if cat.is_vre]
        curtailable_technologies = [
            cat.name for cat in generator_categories if cat.is_curtailable
        ]

        return VREClassification(
            vre_technologies=vre_technologies,
            curtailable_technologies=curtailable_technologies,
        )

    def _create_load_classification(
        self, generator_categories: List[GeneratorCategory]
    ) -> LoadClassification:
        """
        Create load classification from generator categories.

        Identifies storage charging and flexible load categories.

        Args:
            generator_categories: List of GeneratorCategory

        Returns:
            LoadClassification instance
        """
        storage_charging = []

        for cat in generator_categories:
            if cat.is_storage:
                # Storage categories can charge
                storage_charging.append(cat.name)

        return LoadClassification(
            storage_charging_categories=storage_charging, flexible_load_categories=[]
        )

    def generate(
        self,
        name: str,
        simulation_type: str = "sienna",
        description: Optional[str] = None,
        version: str = "1.0.0",
    ) -> Palette:
        """
        Generate a palette from the system file.

        Args:
            name: Palette name
            simulation_type: Type of simulation (sienna, reeds, plexos)
            description: Optional description
            version: Palette version

        Returns:
            Generated Palette instance

        Raises:
            ValueError: If system has no generators
        """
        logger.info(f"Generating palette '{name}' from system file")

        # Get system info
        system_info = self.system.get_system_info()
        if system_info.num_generators == 0:
            raise ValueError("System has no generators - cannot generate palette")

        # Get generator categories
        generator_categories = self.system.list_generator_categories()
        if not generator_categories:
            raise ValueError("No generator categories found in system")

        logger.debug(f"Found {len(generator_categories)} generator categories")

        # Create display categories and mappings
        display_categories, category_mappings = self._create_display_categories(
            generator_categories
        )
        logger.debug(f"Created {len(display_categories)} display categories")

        # Create stack order
        stack_order = self._create_stack_order(display_categories, generator_categories)

        # Create classifications
        vre_classification = self._create_vre_classification(generator_categories)
        load_classification = self._create_load_classification(generator_categories)

        # Build description if not provided
        if not description:
            description = (
                f"Auto-generated palette from {simulation_type} system file. "
                f"Contains {len(display_categories)} display categories covering "
                f"{system_info.num_generators} generators."
            )

        # Create palette
        palette = Palette(
            name=name,
            description=description,
            simulation_type=simulation_type,
            version=version,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            display_categories=display_categories,
            category_mappings=category_mappings,
            stack_order=stack_order,
            vre_classification=vre_classification,
            load_classification=load_classification,
            show_legend=True,
            legend_location="best",
        )

        # Validate
        warnings = palette.validate_stack_order()
        if warnings:
            for warning in warnings:
                logger.warning(f"Palette validation: {warning}")

        logger.info(f"Generated palette with {len(display_categories)} categories")

        return palette

    def print_summary(self, palette: Palette) -> None:
        """
        Print a summary of the generated palette.

        Args:
            palette: Palette to summarize
        """
        print(f"\nPalette: {palette.name}")
        print(f"Description: {palette.description}")
        print(f"Simulation Type: {palette.simulation_type}")
        print(f"\nDisplay Categories ({len(palette.display_categories)}):")
        print("-" * 60)

        for cat in palette.display_categories:
            # Count how many simulation categories map to this
            mappings = [
                m for m in palette.category_mappings if m.display_category == cat.name
            ]
            print(f"  {cat.name:30s} {cat.color:10s} ({len(mappings)} sim categories)")

        if palette.vre_classification:
            print(
                f"\nVRE Technologies ({len(palette.vre_classification.vre_technologies)}):"
            )
            for tech in palette.vre_classification.vre_technologies:
                print(f"  - {tech}")

        if (
            palette.load_classification
            and palette.load_classification.storage_charging_categories
        ):
            print(
                f"\nStorage Charging Categories ({len(palette.load_classification.storage_charging_categories)}):"
            )
            for cat in palette.load_classification.storage_charging_categories:
                print(f"  - {cat}")

        print(f"\nStack Order (bottom to top):")
        for i, cat_name in enumerate(palette.stack_order, 1):
            print(f"  {i}. {cat_name}")
