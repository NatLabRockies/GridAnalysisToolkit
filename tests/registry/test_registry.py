import pytest
from gat.registry import discover_all_plots, get_plot_names


def test_discover_all_plots():
    # Test that plots can be discovered
    discover_all_plots()

    # Get the list of available plots
    available_plots = get_plot_names()

    # Check that we have at least one plot available
    assert len(available_plots) > 0, "No plots were discovered"

    # Check that the returned value is a list of strings
    assert isinstance(available_plots, list), "Available plots should be a list"
    assert all(
        isinstance(plot, str) for plot in available_plots
    ), "All plot names should be strings"

    # Print the available plots for debugging purposes
    print(f"Available plots: {available_plots}")
