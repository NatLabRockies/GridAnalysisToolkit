from .scenario import TechnologyMapping
from typing import Dict, List


def create_tech_mappings(model_technologies: List[str]) -> Dict[str, TechnologyMapping]:
    """
    Creates standardized technology mappings using the TechnologyMapping.new() method.

    Args:
        model_technologies: Dictionary mapping generator IDs to their technology types

    Returns:
        Dictionary of technology names to TechnologyMapping objects
    """
    from gat.models.scenario import TechnologyMapping

    tech_mappings = {}
    # Create a mapping for each unique technology type
    unique_techs = set(model_technologies)

    for tech in unique_techs:
        # Create a new TechnologyMapping for this technology
        tech_mapping = TechnologyMapping.new(tech)
        tech_mappings[tech] = tech_mapping

    return tech_mappings
