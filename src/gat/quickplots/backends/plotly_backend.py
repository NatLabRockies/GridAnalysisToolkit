"""Plotly rendering backend for GAT.

Implements the PlotBackend protocol using plotly. Produces interactive
figures suitable for Jupyter notebooks, dashboards, and HTML export.

All chart methods return a ``plotly.graph_objects.Figure``.  The formatting
helpers (``set_title``, ``set_ylabel``, etc.) accept a Figure and mutate it
in-place via ``update_layout`` / ``update_xaxes`` / ``update_yaxes``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Plotly line-dash mapping from matplotlib linestyle conventions
_DASH_MAP = {
    "-": "solid",
    "--": "dash",
    "-.": "dashdot",
    ":": "dot",
    ".": "dot",
}


class PlotlyBackend:
    """Plotly implementation of the PlotBackend protocol."""

    name: str = "interactive"

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
        fig = kwargs.pop("fig", None) or go.Figure()
        row = kwargs.pop("row", None)
        col = kwargs.pop("col", None)
        trace_kwargs = {"row": row, "col": col} if row is not None else {}

        x = df_pos.index

        # Positive stacked area traces (bottom → top)
        for i, name in enumerate(columns_ordered):
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=df_pos[name],
                    name=name,
                    mode="lines",
                    line=dict(width=0, color=colors[i]),
                    fillcolor=colors[i],
                    stackgroup="pos",
                    showlegend=legend,
                ),
                **trace_kwargs,
            )

        # Negative stacked area traces
        has_neg = df_neg.abs().sum().sum() > 0
        if has_neg:
            for i, name in enumerate(columns_ordered):
                fig.add_trace(
                    go.Scatter(
                        x=x,
                        y=df_neg[name],
                        name=name,
                        mode="lines",
                        line=dict(width=0, color=colors[i]),
                        fillcolor=colors[i],
                        stackgroup="neg",
                        showlegend=False,
                    ),
                    **trace_kwargs,
                )

        # Overlay load lines
        for line_name, line_info in (load_lines or {}).items():
            data = line_info["data"]
            color = line_info.get("color", "black")
            style = line_info.get("style", "-")
            lw = line_info.get("linewidth", 1)
            # data may be a DataFrame with one column
            y = data.iloc[:, 0] if hasattr(data, "iloc") else data
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=y,
                    name=line_name,
                    mode="lines",
                    line=dict(
                        color=color,
                        dash=_DASH_MAP.get(style, "solid"),
                        width=lw,
                    ),
                    showlegend=legend,
                ),
                **trace_kwargs,
            )

        fig.update_layout(
            showlegend=legend,
            template="plotly_white",
        )
        return fig

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
        fig = kwargs.pop("fig", None) or go.Figure()
        row = kwargs.pop("row", None)
        col = kwargs.pop("col", None)
        trace_kwargs = {"row": row, "col": col} if row is not None else {}

        x = [str(v) for v in df_pos.index]

        # Positive bars
        for i, name in enumerate(columns_ordered):
            vals = df_pos[name].values
            bar_kwargs = dict(
                name=name,
                marker_color=colors[i],
                showlegend=legend,
            )
            if horizontal:
                bar_kwargs.update(x=vals, y=x, orientation="h")
            else:
                bar_kwargs.update(x=x, y=vals)
            fig.add_trace(go.Bar(**bar_kwargs), **trace_kwargs)

        # Negative bars
        has_neg = df_neg.abs().sum().sum() > 0
        if has_neg:
            for i, name in enumerate(columns_ordered):
                vals = df_neg[name].values
                bar_kwargs = dict(
                    name=name,
                    marker_color=colors[i],
                    showlegend=False,
                )
                if horizontal:
                    bar_kwargs.update(x=vals, y=x, orientation="h")
                else:
                    bar_kwargs.update(x=x, y=vals)
                fig.add_trace(go.Bar(**bar_kwargs), **trace_kwargs)

        fig.update_layout(
            barmode="relative",
            showlegend=legend,
            template="plotly_white",
        )
        return fig

    def donut(
        self,
        plot_series: pd.Series,
        colors: List[str],
        annotations: List[dict],
        center_text: str,
        **kwargs: Any,
    ) -> Any:
        fig = kwargs.pop("fig", None) or go.Figure()

        fig.add_trace(
            go.Pie(
                labels=list(plot_series.index),
                values=list(plot_series.values),
                hole=0.55,
                marker=dict(colors=colors),
                textinfo="label+percent",
                hoverinfo="label+value+percent",
                showlegend=True,
            )
        )

        # Add center annotation
        fig.update_layout(
            annotations=[
                dict(
                    text=center_text.replace("\n", "<br>"),
                    x=0.5,
                    y=0.5,
                    font_size=18,
                    showarrow=False,
                    xref="paper",
                    yref="paper",
                )
            ],
            template="plotly_white",
        )
        return fig

    def line(
        self,
        df: pd.DataFrame,
        colors: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Any:
        fig = kwargs.pop("fig", None) or go.Figure()
        row = kwargs.pop("row", None)
        col = kwargs.pop("col", None)
        trace_kwargs = {"row": row, "col": col} if row is not None else {}

        x = df.index
        for i, column in enumerate(df.columns):
            line_kwargs: dict = {}
            if colors and i < len(colors):
                line_kwargs["color"] = colors[i]
            fig.add_trace(
                go.Scatter(
                    x=x,
                    y=df[column],
                    name=str(column),
                    mode="lines",
                    line=line_kwargs if line_kwargs else None,
                ),
                **trace_kwargs,
            )

        fig.update_layout(template="plotly_white")
        return fig

    def boxplot(
        self,
        df: pd.DataFrame,
        **kwargs: Any,
    ) -> Any:
        fig = kwargs.pop("fig", None) or go.Figure()

        for column in df.columns:
            fig.add_trace(
                go.Box(
                    y=df[column].dropna(),
                    name=str(column),
                    boxmean=False,
                )
            )

        fig.update_layout(
            template="plotly_white",
            showlegend=False,
        )
        return fig

    # ------------------------------------------------------------------ #
    # Figure/subplot creation
    # ------------------------------------------------------------------ #

    def create_subplots(
        self,
        nrows: int,
        ncols: int,
        **kwargs: Any,
    ) -> Tuple[Any, Any]:
        subplot_titles = kwargs.pop("subplot_titles", None)
        fig = make_subplots(
            rows=nrows,
            cols=ncols,
            subplot_titles=subplot_titles,
            **kwargs,
        )
        # Return (fig, list of (row, col) tuples) to parallel matplotlib's
        # (fig, axes_array) pattern.
        cells = [(r, c) for r in range(1, nrows + 1) for c in range(1, ncols + 1)]
        return fig, cells

    # ------------------------------------------------------------------ #
    # Formatting helpers
    # ------------------------------------------------------------------ #

    def set_title(self, chart: Any, title: str) -> None:
        chart.update_layout(title_text=title)

    def set_ylabel(self, chart: Any, label: str) -> None:
        chart.update_yaxes(title_text=label)

    def set_xlabel(self, chart: Any, label: str) -> None:
        chart.update_xaxes(title_text=label)

    def set_xlim(self, chart: Any, xmin: Any, xmax: Any) -> None:
        chart.update_xaxes(range=[xmin, xmax])

    def set_ylim(self, chart: Any, ymin: Any, ymax: Any) -> None:
        chart.update_yaxes(range=[ymin, ymax])

    def add_annotation(
        self,
        chart: Any,
        text: str,
        xy: Tuple[Any, Any],
        xytext: Tuple[Any, Any],
        **kwargs: Any,
    ) -> None:
        chart.add_annotation(
            x=xytext[0],
            y=xytext[1],
            ax=xy[0],
            ay=xy[1],
            text=text,
            showarrow=True,
            arrowhead=2,
        )

    def remove_legend(self, chart: Any) -> None:
        chart.update_layout(showlegend=False)
