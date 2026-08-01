from gat.scenariohandlers import SiennaScenario, PlexosScenario
from gat.models.scenario import ScenarioConfig, load_config
from typing import Union


def load_scenario(
    config: Union[str, ScenarioConfig],
) -> Union[PlexosScenario, SiennaScenario]:
    """Loads a scenario based on a config object"""

    config = load_config(config)

    if type(config) == ScenarioConfig:

        if config.type == "Plexos":
            scen = PlexosScenario(
                config.scenario_paths,
            )
        elif config.type == "Sienna":
            scen = SiennaScenario(
                config.scenario_paths, config.system_path, config=config
            )

        return scen
    else:
        raise ValueError
