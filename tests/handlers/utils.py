import os
import pytest

home = os.path.expanduser('~')
plexos_dir = os.path.normpath(f'{home}/.gat-test-data/plexos')
sienna_dir = os.path.normpath(f'{home}/.gat-test-data/sienna')


def get_scenario_handler(handler_type):
    from gat.scenariohandlers import PlexosScenario, FileScenario
    if handler_type == 'plexos':
        if not os.path.isdir(plexos_dir):
            pytest.skip(f"plexos fixture not available at {plexos_dir}")
        s = PlexosScenario(plexos_dir)

    elif handler_type == 'sienna':
        if not os.path.isfile(os.path.join(sienna_dir, 'metadata.json')):
            pytest.skip(f"sienna fixture not available at {sienna_dir}")
        s = FileScenario(sienna_dir)
        s._load_file ='regional_load.pq.gz'

    s._use_cache = False
    return s

def get_scenario_object_dir(handler_type):
    from gat.scenariohandlers import PlexosScenario, FileScenario
    if handler_type == 'plexos':
        if not os.path.isdir(plexos_dir):
            pytest.skip(f"plexos fixture not available at {plexos_dir}")
        s = PlexosScenario
        dir = plexos_dir
    elif handler_type == 'sienna':
        if not os.path.isfile(os.path.join(sienna_dir, 'metadata.json')):
            pytest.skip(f"sienna fixture not available at {sienna_dir}")
        s = FileScenario
        dir = sienna_dir
    return s, dir
