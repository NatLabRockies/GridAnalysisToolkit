from gat.scenariohandlers.base import BaseScenario
from gat.models.scenario import ScenarioConfig
from typing import Optional, Union, List, Type
import logging
import importlib

def scenario_from_config(config: ScenarioConfig,
                         system_path: Optional[str] = None,
                         simulation_paths: Optional[Union[str, List[str]]] = None,
                         display_name: Optional[str] = None) -> BaseScenario:
    """
    Creates a Scenario Object from a ScenarioConfig.

    Args:
        config: ScenarioConfig object containing model type and other settings
        system_path: Optional path to system data, overrides config value if provided
        simulation_paths: Optional path(s) to simulation data, overrides config value if provided
        display_name: Optional display name, overrides config value if provided

    Returns:
        BaseScenario: A concrete implementation of BaseScenario based on model_type

    Raises:
        ValueError: If model_type is unsupported or scenario class cannot be loaded
        ImportError: If required modules cannot be imported
    """
    model_type = config.model_type.lower()

    try:
        # Determine the appropriate scenario class based on model_type
        scenario_class = None

        if model_type == "sienna":
            from gat.scenariohandlers import SiennaScenario
            scenario_class = SiennaScenario
        elif model_type == "plexos":
            from gat.scenariohandlers import PlexosScenario
            scenario_class = PlexosScenario
        elif model_type == "reeds":
            from gat.scenariohandlers import ReEDsScenario
            scenario_class = ReEDsScenario
        else:
            # Try dynamic import as a fallback
            try:
                module_name = f"gat.scenariohandlers.{model_type}"
                class_name = f"{model_type.capitalize()}Scenario"
                module = importlib.import_module(module_name)
                scenario_class = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                raise ValueError(f"Unsupported model type: {model_type}. Error: {str(e)}")

        # Create the scenario object using the appropriate class
        scenario = scenario_class.from_config(
            config_path=config,
            system_path=system_path,
            simulation_paths=simulation_paths,
            display_name=display_name
        )

        return scenario

    except ImportError as e:
        logging.error(f"Failed to import scenario handler for {model_type}: {e}")
        raise
    except Exception as e:
        logging.error(f"Error creating scenario from config: {e}")
        raise