"""Matplotlib rendering backend for GAT.

Implements the PlotBackend protocol using matplotlib. This is the default
backend and reproduces the existing rendering behavior from core.py.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


class MatplotlibBackend:
    """Matplotlib implementation of the PlotBackend protocol."""

    name: str = "static"

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
        ax = kwargs.pop("ax", None) or plt.axes()
        linewidth = kwargs.pop("linewidth", 0)

        ax = df_pos[columns_ordered].plot.area(
            stacked=True, color=colors, linewidth=linewidth, ax=ax,
            legend=legend, **kwargs,
        )

        # Overlay load lines
        for line_name, line_info in (load_lines or {}).items():
            line_info["data"].plot.line(
                color=line_info.get("color", "black"),
                ax=ax,
                linestyle=line_info.get("style", "-"),
                linewidth=line_info.get("linewidth", 1),
                label=line_name,
                legend=legend,
            )

        # Capture legend before negative area duplicates entries
        if legend:
            handles, labels = ax.get_legend_handles_labels()

        # Negative area
        df_neg[columns_ordered].plot.area(
            stacked=True, color=colors, linewidth=linewidth, ax=ax,
            legend=False, **kwargs,
        )

        # Auto y-limits
        max_stack = df_pos.sum(axis=1).max()
        min_stack = df_neg.sum(axis=1).min()
        max_y = max(max_stack, df_pos.max().max())
        min_y = min(min_stack, df_neg.min().min())
        min_pad = min_y * 0.10 if min_y != 0 else 0
        ax.set_ylim(min_y - min_pad, max_y + max_y * 0.10)

        if legend:
            ax.legend(handles[::-1], labels[::-1], bbox_to_anchor=(1.05, 0.95))

        ax.spines[["right", "top"]].set_visible(False)
        return ax

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
        ax = kwargs.pop("ax", None) or plt.axes()
        linewidth = kwargs.pop("linewidth", 0)
        kind = "barh" if horizontal else "bar"

        ax = df_pos[columns_ordered].plot(
            kind=kind, stacked=True, color=colors,
            linewidth=linewidth, ax=ax, legend=legend, **kwargs,
        )

        if legend:
            handles, labels = ax.get_legend_handles_labels()

        df_neg[columns_ordered].plot(
            kind=kind, stacked=True, color=colors,
            linewidth=linewidth, ax=ax, legend=False, **kwargs,
        )

        max_stack = df_pos.sum(axis=1).max()
        min_stack = df_neg.sum(axis=1).min()
        max_y = max(max_stack, df_pos.max().max())
        min_y = min(min_stack, df_neg.min().min())
        min_pad = min_y * 0.10 if min_y != 0 else 0

        if horizontal:
            ax.set_xlim(min_y - min_pad, max_y + max_y * 0.10)
        else:
            ax.set_ylim(min_y - min_pad, max_y + max_y * 0.10)

        if legend:
            ax.legend(handles[::-1], labels[::-1], bbox_to_anchor=(1.05, 0.95))

        ax.spines[["right", "top"]].set_visible(False)
        return ax

    def donut(
        self,
        plot_series: pd.Series,
        colors: List[str],
        annotations: List[dict],
        center_text: str,
        **kwargs: Any,
    ) -> Any:
        ax = kwargs.pop("ax", None) or plt.gca()
        startangle = kwargs.pop("startangle", 90)

        wedges, _texts = ax.pie(
            plot_series, labels=None, colors=colors,
            startangle=startangle, wedgeprops=dict(width=0.45),
        )

        for ann in annotations:
            ax.annotate(
                ann["text"],
                xy=ann["xy"],
                xytext=ann["xytext"],
                textcoords="data",
                ha=ann.get("ha", "center"),
                va=ann.get("va", "center"),
                arrowprops=dict(
                    arrowstyle="-",
                    connectionstyle="angle,angleA=0,angleB=90,rad=0",
                    color="gray", lw=0.8,
                ),
            )

        ax.text(
            0, 0, center_text,
            ha="center", va="center",
            fontsize=18, fontweight="bold",
        )
        ax.axis("equal")
        return ax

    def line(
        self,
        df: pd.DataFrame,
        colors: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Any:
        ax = kwargs.pop("ax", None) or plt.gca()
        if colors and len(colors) == len(df.columns):
            kwargs["color"] = colors
        df.plot.line(ax=ax, **kwargs)
        return ax

    def boxplot(
        self,
        df: pd.DataFrame,
        **kwargs: Any,
    ) -> Any:
        ax = kwargs.pop("ax", None) or plt.gca()
        df.plot.box(
            ax=ax,
            boxprops=dict(color="darkgreen", linestyle="-", linewidth=1.5, alpha=0.5),
            medianprops=dict(color="black", linestyle="-", linewidth=2.5),
            whiskerprops=dict(linestyle="-", linewidth=1.5),
            capprops=dict(linestyle="-", linewidth=1.5),
            patch_artist=True,
            showfliers=False,
            grid=False,
            rot=0,
            **kwargs,
        )
        return ax

    # ------------------------------------------------------------------ #
    # Figure/subplot creation
    # ------------------------------------------------------------------ #

    def create_subplots(
        self,
        nrows: int,
        ncols: int,
        **kwargs: Any,
    ) -> Tuple[Any, Any]:
        fig, axs = plt.subplots(nrows, ncols, **kwargs)
        return fig, axs

    # ------------------------------------------------------------------ #
    # Formatting helpers
    # ------------------------------------------------------------------ #

    def set_title(self, chart: Any, title: str) -> None:
        chart.set_title(title)

    def set_ylabel(self, chart: Any, label: str) -> None:
        chart.set_ylabel(label)

    def set_xlabel(self, chart: Any, label: str) -> None:
        chart.set_xlabel(label)

    def set_xlim(self, chart: Any, xmin: Any, xmax: Any) -> None:
        chart.set_xlim(xmin, xmax)

    def set_ylim(self, chart: Any, ymin: Any, ymax: Any) -> None:
        chart.set_ylim(ymin, ymax)

    def add_annotation(
        self,
        chart: Any,
        text: str,
        xy: Tuple[Any, Any],
        xytext: Tuple[Any, Any],
        **kwargs: Any,
    ) -> None:
        arrowprops = kwargs.pop(
            "arrowprops",
            dict(facecolor="black", shrink=0.05, width=1),
        )
        chart.annotate(text, xy=xy, xytext=xytext, arrowprops=arrowprops, **kwargs)

    def remove_legend(self, chart: Any) -> None:
        legend = chart.get_legend()
        if legend is not None:
            legend.remove()
