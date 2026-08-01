from .utils import *
import pandas as pd
import pytest
from glob import glob


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_scenario_dir_input(handler_type):
    try:
        handler, dir = get_scenario_object_dir(handler_type)

        scenario = handler(dir)
        assert True
    except Exception as e:
        print(e)
        assert False


# TODO sienna file input not implemented
@pytest.mark.parametrize("handler_type", ["plexos"])
def test_scenario_file_list_input(handler_type):
    try:
        handler, dir = get_scenario_object_dir(handler_type)
        files = glob(f"{dir}/*.h5")

        scenario = handler(files)

        assert True
    except Exception as e:
        print(e)
        assert False


# begin basic data loading tests
@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_get_generators_tech(handler_type):
    try:
        scenario = get_scenario_handler(handler_type)

        gen_tech = scenario.get_generators_tech()
        assert True
    except Exception as e:
        print(e)
        assert False


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_get_line_flows(handler_type):
    try:
        scenario = get_scenario_handler(handler_type)

        flow = scenario.get_flow()
        assert True
    except Exception as e:
        print(e)
        assert False


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_get_gen_curt(handler_type):
    try:
        scenario = get_scenario_handler(handler_type)

        gen_curt = scenario.get_gen_and_curtailment()
        assert True
    except Exception as e:
        print(e)
        assert False


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
# @pytest.mark.parametrize("include_load", [True, False])
# @pytest.mark.parametrize("include_use", [True, False])
def test_get_area_load(handler_type):
    try:
        scenario = get_scenario_handler(handler_type)

        load = scenario.get_area_load()
        assert True
    except Exception as e:
        print(e)
        assert False


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_get_area_unserved(handler_type):
    scenario = get_scenario_handler(handler_type)

    result = scenario.get_area_unserved()
    assert result is NotImplemented or isinstance(result, pd.DataFrame)


# Begin more end-to-end tests
@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
@pytest.mark.parametrize("include_load", [True, False])
@pytest.mark.parametrize("include_use", [True, False])
def test_get_area_dispatch(handler_type, include_load, include_use):
    scenario = get_scenario_handler(handler_type)

    dispatch = scenario.get_area_dispatch(
        include_load=include_load, include_use=include_use
    )
    assert isinstance(dispatch, pd.DataFrame)
    assert not dispatch.empty


# TODO
@pytest.mark.parametrize("handler_type", ["plexos"])
def test_get_production_cost(handler_type):
    try:

        # scenario = get_scenario_handler(handler_type)

        # cost = scenario.get_raw_production_cost_annual('zone')
        assert True
    except Exception as e:
        print(e)
        assert False


def test_shape_mismatch():
    """Regression check for a Plexos solution whose area-load shapes
    disagreed across datasets.

    Point GAT_PLEXOS_SHAPE_FIXTURE at a local Plexos solution directory to
    run this; it skips otherwise. Previously this was parametrized on a
    hardcoded developer path, which meant it never ran for anyone else.
    """
    scenario_path = os.environ.get("GAT_PLEXOS_SHAPE_FIXTURE")
    if not scenario_path or not os.path.isdir(scenario_path):
        pytest.skip("set GAT_PLEXOS_SHAPE_FIXTURE to a Plexos solution directory")
    from gat.scenariohandlers import PlexosScenario

    ps = PlexosScenario(scenario_path)

    ps.get_area_load()

    # ps.get_area_dispatch(include_load=False, include_use=False)

    assert True
