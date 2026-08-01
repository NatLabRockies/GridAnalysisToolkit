import os
import re
import warnings
from typing import Any, Dict, List, Optional, Union

import yaml
from loguru import logger
from pydantic import BaseModel

from gat import __version__
from gat.config import config as gc
from gat.quickplots.utils import random_color, standard_color_dict

from .base import DatasetConfig, Technology
from .lookups import FileAreaLookup, GeoAreaLookup, SiennaAreaLookup
from .reeds import ReEDsConfig
from .sienna import SiennaSystemConfig as SiennaConfig


def _tokenize_technology(name: str) -> set:
    return set(t for t in re.split(r"[-_\s]+", name.lower()) if t)


def _fuzzy_match_technology(
    model_technology: str, candidates: List[str]
) -> Optional[str]:
    """Token-overlap match against known display groups.

    Model technology naming is backend- and even model-specific (PLEXOS
    categories in particular are arbitrary, user-defined in the PLEXOS GUI),
    so there's no fixed convention to hardcode against. This scores
    candidates by Jaccard overlap of whitespace/hyphen/underscore-delimited
    tokens rather than whole-string character similarity
    (``difflib.get_close_matches``) -- compound codes like "Solar_PV" or
    "NATURAL_GAS_CC" are one- or two-token matches that get buried in noise
    under whole-string comparison (e.g. "Solar_PV" scores higher against
    "storage" than against "PV" under SequenceMatcher, purely from shared
    letters), but resolve correctly once compared token-by-token.
    """
    model_tokens = _tokenize_technology(model_technology)
    if not model_tokens:
        return None

    best_candidate, best_score = None, 0.0
    for candidate in candidates:
        candidate_tokens = _tokenize_technology(candidate)
        overlap = model_tokens & candidate_tokens
        if not overlap:
            continue
        score = len(overlap) / len(model_tokens | candidate_tokens)
        if score > best_score:
            best_candidate, best_score = candidate, score

    return best_candidate


class TechnologyMapping(BaseModel):
    display_group: str  # Simplified technology name for display (e.g., "Solar", "Wind")
    display_color: Optional[str] = None  # Will use standard color if available
    display_order: Optional[int] = None  # For ordering in stack charts
    curtailable: bool = False  # Whether this tech can be curtailed

    @classmethod
    def new(cls, model_technology: str):
        """Use standard technology mapping to see if model_technology
        maps to a standard technology. If not map to itself and give user warning that random color is assigned.

        If it does map to a standard technology, use standard color
        If not, give random color and give user warning.

        Allow for shorthand colors. e.g user can select something like NLR_PV to use the standard NLR PV color.

        Assign order based on increasing index. Might use display order found in standard color dict. (Might have to be done in a different scope)
        Default to assign 0 (putting unmapped technologies at the bottom.)

        Assign curtailment based on standard curtailable technologies. We normally assign

        Args:
            model_technology: The technology name from the model

        Returns:
            TechnologyMapping: A new instance with appropriate display settings
        """

        # First check if the technology is directly in standard_color_dict
        if model_technology in standard_color_dict:
            display_group = model_technology
            display_color = standard_color_dict[model_technology]
            # Find position in standard_color_dict to use as display_order
            display_order = list(standard_color_dict.keys()).index(model_technology)
            curtailable = model_technology in gc.curtailable_tech
        else:
            # Check if technology matches any keys after normalizing (removing dashes, lowercasing)
            normalized_tech = (
                model_technology.lower()
                .replace("-", "")
                .replace("_", "")
                .replace(" ", "")
            )
            normalized_dict = {
                k.lower().replace("-", "").replace("_", "").replace(" ", ""): k
                for k in standard_color_dict.keys()
            }

            if normalized_tech in normalized_dict:
                standard_tech = normalized_dict[normalized_tech]
                display_group = standard_tech
                display_color = standard_color_dict[standard_tech]
                display_order = list(standard_color_dict.keys()).index(standard_tech)
                curtailable = standard_tech in gc.curtailable_tech
            else:
                # Model technology naming can be arbitrary (e.g. PLEXOS
                # categories are user-defined in the PLEXOS GUI, not a fixed
                # convention), so try a token-overlap fuzzy match against
                # the standard display groups before giving up.
                fuzzy_tech = _fuzzy_match_technology(
                    model_technology, list(standard_color_dict.keys())
                )
                if fuzzy_tech is not None:
                    display_group = fuzzy_tech
                    display_color = standard_color_dict[fuzzy_tech]
                    display_order = list(standard_color_dict.keys()).index(fuzzy_tech)
                    curtailable = fuzzy_tech in gc.curtailable_tech
                    warnings.warn(
                        f"Technology '{model_technology}' not found in standard mappings. "
                        f"Fuzzy-matched to '{fuzzy_tech}' based on shared keywords -- "
                        f"override via config technology_mappings if this is wrong."
                    )
                else:
                    # If not found in standard mappings, use the model technology as is
                    display_group = model_technology
                    display_color = random_color()
                    display_order = 0  # Default to bottom
                    curtailable = model_technology in gc.curtailable_tech
                    warnings.warn(
                        f"Technology '{model_technology}' not found in standard mappings. Assigning random color."
                    )

        return cls(
            display_group=display_group,
            display_color=display_color,
            display_order=display_order,
            curtailable=curtailable,
        )

    def update_color(self):
        """Updates the mapped color if the users manually reassigns the model technology to a standard display_group

        If the display_group matches a standard technology in standard_color_dict,
        updates the color to match that standard technology.
        Also updates the display_order and curtailable flags accordingly.

        Args:
            None
        Returns:
            None
        """

        # Check if the display_group matches a standard technology
        if self.display_group in standard_color_dict:
            # Update color to match the standard technology
            self.display_color = standard_color_dict[self.display_group]
            # Update display order
            self.display_order = list(standard_color_dict.keys()).index(
                self.display_group
            )
            # Update curtailable flag
            self.curtailable = self.display_group in gc.curtailable_tech
        else:
            # Try normalized matching as in the new() method
            normalized_display = (
                self.display_group.lower()
                .replace("-", "")
                .replace("_", "")
                .replace(" ", "")
            )
            normalized_dict = {
                k.lower().replace("-", "").replace("_", "").replace(" ", ""): k
                for k in standard_color_dict.keys()
            }

            if normalized_display in normalized_dict:
                standard_tech = normalized_dict[normalized_display]
                # Update color based on the matched standard technology
                self.display_color = standard_color_dict[standard_tech]
                # Update display order
                self.display_order = list(standard_color_dict.keys()).index(
                    standard_tech
                )
                # Update curtailable flag
                self.curtailable = standard_tech in gc.curtailable_tech
            # If no match is found, keep the existing color (which might be random)


class ScenarioConfig(BaseModel):
    # The type of scenario, should be Plexos, Sienna or ReEDS
    model_type: str
    display_name: Optional[str] = None
    # GAT version used to create this config
    gat_version: Optional[str] = __version__
    # optional paths to scenario data. If not set, loader will require paths to scenarios to be given.
    # Don't set this if you plan to use it for multiple scenarios.
    # Or override?
    simulation_paths: Optional[Union[str, List[str]]] = None
    # optional paths to system data. This should be one system. Sienna Json file or Plexos XML file (future).
    system_path: Optional[str] = None

    # determines which areas to treat as the system
    included_areas: Optional[List[str]] = None
    excluded_areas: Optional[List[str]] = None

    # System-specific configurations (e.g., Sienna version-specific settings)
    system_config: Optional[Union[SiennaConfig, ReEDsConfig, Dict[str, Any]]] = None

    # Dataset configurations - defines available datasets (raw and aggregate)
    dataset_config: Optional[DatasetConfig] = None

    # Maps from native names to display groups
    technology_mappings: Dict[str, TechnologyMapping] = {}

    # Whether the scenario's load timeseries is "total demand" (i.e. already
    # includes storage charging) vs. "native demand" (just the load, charging
    # added separately). Defaults to False — most PCM tools record native
    # load. Settable post-construction via the ``load_includes_charging``
    # property on the scenario handler.
    load_includes_charging: bool = False

    # name of the lookup and the lookup config.
    # used to determine available aggregation levels in the Scenario Object.
    area_lookups: Optional[
        Dict[str, Union[GeoAreaLookup, FileAreaLookup, SiennaAreaLookup]]
    ] = {}

    # Additional display settings
    load_display_settings: Optional[Dict[str, Any]] = None

    # relationships
    # relations: List[RelationSource]

    def save(self, output_path: Optional[str] = None):
        # Update version when saving
        self.gat_version = __version__

        save_path = f"{self.display_name}.yaml"
        if output_path is not None:
            save_path = output_path

        model_dict = self.model_dump()
        with open(save_path, "w") as f:
            yaml.dump(model_dict, f, sort_keys=False)

    def init_technologies(self, initial_map: Dict[str, str]):
        from gat.config import config as gc
        from gat.quickplots.utils import random_color, standard_color_dict

        technologies = {}
        for name, alias in initial_map.items():
            curtailable = False
            if alias in gc.curtailable_tech:
                curtailable = True

            tech = TechnologyMapping(
                display_group=alias,
                display_color=random_color(),
                curtailable=curtailable,
            )
            technologies[name] = tech

        # Assigns the order to the standard order.
        order = 0
        for name, color in standard_color_dict.items():
            for tech in technologies.values():
                if tech.display_group == name:
                    tech.display_order = order
                    tech.display_color = color
                    order += 1

        self.technology_mappings = technologies

    def get_technology_cmap(self) -> Dict[str, str]:
        """
        Get a dictionary mapping technology display groups to colors, ordered by display_order.

        Returns:
            Dict[str, str]: Dictionary with display_group as key and display_color as value,
                           ordered by display_order.
        """
        # Sort technologies by display_order
        sorted_techs = sorted(
            self.technology_mappings.values(),
            key=lambda tech: (
                tech.display_order if tech.display_order is not None else float("inf")
            ),
        )

        # Create a dictionary with display_group as key and display_color as value
        # If multiple technologies map to the same display_group, the last one wins
        cmap = {}
        for tech in sorted_techs:
            if tech.display_group and tech.display_color:
                cmap[tech.display_group] = tech.display_color

        return cmap

    def add_area_lookup(self, file_path, lookup_name=None):
        """
        Add a lookup object to the scenario config based on file type.

        Args:
            file_path (str): Path to the lookup file
            lookup_name (str, optional): Custom name for the lookup. If None,
                                         uses the filename without extension.

        Returns:
            str: The name of the added lookup

        Raises:
            ValueError: If file type is not supported
        """
        import os
        from pathlib import Path

        # Initialize area_lookups if it doesn't exist
        if not hasattr(self, "area_lookups") or self.area_lookups is None:
            self.area_lookups = {}

        # Get file extension and determine lookup type
        file_path = str(file_path)  # Convert Path to string if needed
        file_ext = os.path.splitext(file_path)[1].lower()

        # Create name from filename if not provided
        if lookup_name is None:
            lookup_name = os.path.basename(file_path).split(".")[0]

        # Create appropriate lookup based on file extension
        # TODO add support for shapefiles and geojson
        if file_ext in [".gpkg"]:
            # Geospatial file
            from .lookups import GeoAreaLookup

            lookup = GeoAreaLookup.from_file(file_path)
        elif file_ext in [".csv", ".parquet", ".xlsx", ".xls"]:
            # Tabular data file
            from .lookups import FileAreaLookup

            # Assuming the first column is the source value
            source_column = None  # Will be determined from file in from_file method
            lookup = FileAreaLookup.from_file(file_path, source_column)
        # TODO, Sienna ARea Lookups don't need an extension.
        elif file_ext in [".json", ".sienna"]:
            # Sienna specific file
            from .lookups import SiennaAreaLookup

            lookup = SiennaAreaLookup.from_file(file_path)
        else:
            raise ValueError(
                f"Unsupported file type: {file_ext}. Supported types are: "
                "geospatial (.gpkg, .shp, .geojson), "
                "tabular (.csv, .parquet, .xlsx, .xls), "
                "and Sienna (.json, .sienna)"
            )

        # Add to lookups dictionary
        self.area_lookups[lookup_name] = lookup

        return lookup_name


def load_config(input: Union[str, ScenarioConfig]) -> ScenarioConfig:
    if type(input) == str:
        if os.path.isfile(input):
            with open(input, "r") as f:
                try:
                    model = yaml.safe_load(f)
                    config = ScenarioConfig(**model)

                    # Check for version mismatch
                    if config.gat_version and config.gat_version != __version__:
                        logger.warning(
                            f"Config file was created with GAT version {config.gat_version}, but current version is {__version__}. This may cause compatibility issues."
                        )

                    return config
                except Exception as e:
                    logger.error("Failed to load Scenario Config")
                    logger.error(str(e))
    elif type(input) == ScenarioConfig:
        return input
    else:
        raise TypeError
