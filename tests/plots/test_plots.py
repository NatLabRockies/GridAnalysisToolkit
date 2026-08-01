import os
import pytest
from glob import glob
import gat.quickplots as qp
from utils import *


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_plot_bars(handler_type):
    """Should plot in order"""

    # Test that the legend is in correct order

    # Test that we can rename a technology and it works/ maps to other

    # Test that the load columns map to lines

    assert True


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_plot_stacked_area(handler_type):

    # Test that the legend is in correct order

    # Test that we can rename a technology and it works/ maps to other

    # Test that the load columns map to lines

    assert True


@pytest.mark.parametrize("handler_type", ["plexos", "sienna"])
def test_area_facets(handler_type):

    # Test one area vs many
    scenario = get_scenario_handler(handler_type)

    dispatch = scenario.get_area_dispatch()

    areas = dispatch.columns.get_level_values(level="Area")

    dispatch_single = dispatch[[areas[0]]]

    # test single
    qp.facet_area_annual_dispatch(dispatch_single)

    # test multiple
    dispatch_multiple = dispatch[areas[0:5]]

    qp.facet_area_annual_dispatch(dispatch_multiple)

    # TODO
    # There should be no empty ax objects.
    # Number of ax objects should equal number of areas.
    assert True
