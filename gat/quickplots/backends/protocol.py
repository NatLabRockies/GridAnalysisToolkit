"""PlotBackend protocol — the interface all rendering backends must implement.

Each backend provides implementations of core chart types (stacked area,
stacked bar, donut, line, boxplot) plus formatting helpers (set_title,
set_ylabel, etc.) so that domain-level plotting functions don't need
backend-specific code.

Backend methods return native objects (matplotlib Axes, plotly Figure, etc.).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple

import pandas as pd


class PlotBackend(Protocol):
    """Protocol that all plotting backends must implement."""

    name: str

    # ------------------------------------------------------------------ #
    # Core chart types
    # ------------------------------------------------------------------ #

    def stacked_area(
        self,
        df_pos: pd.DataFrame,
        df_neg: pd.DataFrame,
        colors: List[str],
        columns_ordered: List[str],
        load_lines: Optional[Dict[str, dict]] = None,
        legend: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Render a stacked area chart.

        Args:
            df_pos: DataFrame with positive values only (zeros for negatives).
            df_neg: DataFrame with negative values only (zeros for positives).
            colors: Hex color for each column in columns_ordered.
            columns_ordered: Column names in stack order.
            load_lines: Optional load overlay lines. Keys are line names,
                values are dicts with "data" (DataFrame), "color", "style".
            legend: Whether to show a legend.
            **kwargs: Backend-specific options (e.g. ax= for matplotlib).

        Returns:
            Native chart object (e.g. matplotlib Axes, plotly Figure).
        """
        ...

    def stacked_bar(
        self,
        df_pos: pd.DataFrame,
        df_neg: pd.DataFrame,
        colors: List[str],
        columns_ordered: List[str],
        horizontal: bool = False,
        legend: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Render a stacked bar chart.

        Args:
            df_pos: DataFrame with positive values.
            df_neg: DataFrame with negative values.
            colors: Hex color per column.
            columns_ordered: Column names in stack order.
            horizontal: If True, render horizontal bars.
            legend: Whether to show a legend.

        Returns:
            Native chart object.
        """
        ...

    def donut(
        self,
        plot_series: pd.Series,
        colors: List[str],
        annotations: List[dict],
        center_text: str,
        **kwargs: Any,
    ) -> Any:
        """Render a donut chart.

        Args:
            plot_series: Series with category values (after small-category
                merging into "Smol").
            colors: Hex color per category.
            annotations: List of annotation dicts, each containing:
                - "text": annotation text
                - "xy": (x, y) starting point
                - "xytext": (x, y) text position
                - "ha": horizontal alignment
            center_text: Text to display in the donut center.

        Returns:
            Native chart object.
        """
        ...

    def line(
        self,
        df: pd.DataFrame,
        colors: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Any:
        """Render a line chart.

        Args:
            df: DataFrame with one or more series to plot.
            colors: Optional colors per column.

        Returns:
            Native chart object.
        """
        ...

    def boxplot(
        self,
        df: pd.DataFrame,
        **kwargs: Any,
    ) -> Any:
        """Render a boxplot.

        Args:
            df: DataFrame where each column is a boxplot group.

        Returns:
            Native chart object.
        """
        ...

    # ------------------------------------------------------------------ #
    # Figure/subplot creation
    # ------------------------------------------------------------------ #

    def create_subplots(
        self,
        nrows: int,
        ncols: int,
        **kwargs: Any,
    ) -> Tuple[Any, Any]:
        """Create a figure with a grid of subplots.

        Returns:
            (figure, axes_array) — types depend on backend.
        """
        ...

    # ------------------------------------------------------------------ #
    # Post-render formatting helpers
    # ------------------------------------------------------------------ #

    def set_title(self, chart: Any, title: str) -> None:
        """Set the chart title."""
        ...

    def set_ylabel(self, chart: Any, label: str) -> None:
        """Set the y-axis label."""
        ...

    def set_xlabel(self, chart: Any, label: str) -> None:
        """Set the x-axis label."""
        ...

    def set_xlim(self, chart: Any, xmin: Any, xmax: Any) -> None:
        """Set x-axis limits."""
        ...

    def set_ylim(self, chart: Any, ymin: Any, ymax: Any) -> None:
        """Set y-axis limits."""
        ...

    def add_annotation(
        self,
        chart: Any,
        text: str,
        xy: Tuple[Any, Any],
        xytext: Tuple[Any, Any],
        **kwargs: Any,
    ) -> None:
        """Add a text annotation with optional arrow."""
        ...

    def remove_legend(self, chart: Any) -> None:
        """Remove the legend from the chart."""
        ...
