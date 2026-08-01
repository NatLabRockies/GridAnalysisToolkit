"""
Core plotting primitives for GAT.

Each function handles data preparation (column ordering, pos/neg splitting,
color resolution, annotation geometry) and then delegates rendering to the
active plotting backend.  Pass ``backend=`` to override the session default.
"""

import math

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union

import gat.quickplots as qp
from .utils import order_columns_colors, random_color, get_colormap
from ..config import config
from ..models.palette import Palette

# Lazy import — avoid pulling matplotlib at module level so that
# backend-only users don't need it on the import path.
_mpl_Line2D = None


def _get_Line2D():
    global _mpl_Line2D
    if _mpl_Line2D is None:
        from matplotlib.lines import Line2D
        _mpl_Line2D = Line2D
    return _mpl_Line2D


def _get_backend(backend):
    """Resolve a backend name (or None) to a PlotBackend instance."""
    from .backends import get_backend
    return get_backend(backend)


def _resolve_columns_colors(
    columns, palette: Optional[Palette] = None,
) -> tuple:
    """Resolve column ordering and colors from a palette or the global colormap.

    Args:
        columns: DataFrame columns (Index or list).
        palette: Optional Palette for ordering and color resolution.

    Returns:
        (columns_ordered, colors) — both lists of the same length.
    """
    if palette is not None:
        color_map = palette.get_color_map()
        ordered_names = palette.get_ordered_display_names()
        # Keep only columns present in the DataFrame, in palette order
        cols = [c for c in ordered_names if c in columns]
        # Append any columns not covered by the palette
        cols += [c for c in columns if c not in set(cols)]
        colors = [color_map.get(c, random_color()) for c in cols]
        return cols, colors
    return order_columns_colors(columns)


# ------------------------------------------------------------------ #
# Helper — kept for backward compat with dispatch/transmission code
# ------------------------------------------------------------------ #

def create_load_handles(components: List) -> List:
    """Create legend handles for load overlay lines."""
    Line2D = _get_Line2D()
    load_elements = []

    if qp.config.net_load_alias in components:
        load_elements.append(
            Line2D([0], [0], color='black',
                   label=qp.config.net_load_alias, linestyle='.'))

    if qp.config.native_load_alias in components:
        load_elements.append(
            Line2D([0], [0], color='black',
                   label=qp.config.native_load_alias, linestyle='-'))

    if qp.config.total_load_alias in components:
        load_elements.append(
            Line2D([0], [0], color='black',
                   label=qp.config.total_load_alias, linestyle='--'))

    return load_elements


# ------------------------------------------------------------------ #
# Core primitive 1 — Stacked Area
# ------------------------------------------------------------------ #

def plot_stacked_component_area(
        df: pd.DataFrame,
        include_total_load=True,
        include_native_load=True,
        include_net_load=True,
        palette: Optional[Palette] = None,
        backend=None,
        **kwargs):
    """Plot components as a stacked area chart.

    Data preparation (column ordering, pos/neg split, load line extraction)
    is done here; rendering is delegated to the active backend.

    Args:
        df: Wide DataFrame with technology columns + optional load columns.
        include_total_load: Overlay total load line if present.
        include_native_load: Overlay native load line if present.
        include_net_load: Overlay net load line if present.
        palette: Optional :class:`Palette` for colors and column ordering.
        backend: Backend name (``"static"``, ``"interactive"``, etc.)
            or ``None`` for the session default.
        **kwargs: Forwarded to the backend (e.g. ``ax=``, ``linewidth=``).
    """
    be = _get_backend(backend)

    # --- data prep (shared across all backends) ---
    sub_cols_ordered, sub_colors = _resolve_columns_colors(df.columns, palette)
    legend = kwargs.pop("legend", True)

    df_pos = df[sub_cols_ordered].map(lambda x: x if x >= 0 else 0)
    df_neg = df[sub_cols_ordered].map(lambda x: x if x < 0 else 0)

    # Build load overlay lines
    load_lines: Dict[str, dict] = {}
    if include_native_load and config.native_load_alias in df.columns.values:
        load_lines[config.native_load_alias] = {
            "data": df[[config.native_load_alias]],
            "color": "Black",
            "style": "-",
        }
    if include_total_load and config.total_load_alias in df.columns.values:
        load_lines[config.total_load_alias] = {
            "data": df[[config.total_load_alias]],
            "color": "Black",
            "style": "--",
        }
    if include_net_load and config.net_load_alias in df.columns.values:
        load_lines[config.net_load_alias] = {
            "data": df[[config.net_load_alias]],
            "color": "grey",
            "style": ":",
            "linewidth": 1,
        }

    # --- render ---
    return be.stacked_area(
        df_pos, df_neg, sub_colors, sub_cols_ordered,
        load_lines=load_lines, legend=legend, **kwargs,
    )


# ------------------------------------------------------------------ #
# Core primitive 2 — Stacked Bar
# ------------------------------------------------------------------ #

def plot_stacked_component_bar(
        df: pd.DataFrame,
        horizontal=False,
        palette: Optional[Palette] = None,
        backend=None,
        **kwargs):
    """Plot components as a stacked bar chart.

    Args:
        df: Wide DataFrame with technology columns.
        horizontal: If True, render horizontal bars.
        palette: Optional :class:`Palette` for colors and column ordering.
        backend: Backend name or None for session default.
        **kwargs: Forwarded to the backend.
    """
    be = _get_backend(backend)

    # --- data prep ---
    # Filter zero-sum technologies
    df = df.fillna(0)
    df = df.loc[:, df.sum() != 0]

    sub_cols_ordered, sub_colors = _resolve_columns_colors(df.columns, palette)
    legend = kwargs.pop("legend", True)

    df_pos = df[sub_cols_ordered].map(lambda x: x if x >= 0 else 0)
    df_neg = df[sub_cols_ordered].map(lambda x: x if x < 0 else 0)

    # --- render ---
    return be.stacked_bar(
        df_pos, df_neg, sub_colors, sub_cols_ordered,
        horizontal=horizontal, legend=legend, **kwargs,
    )


# ------------------------------------------------------------------ #
# Core primitive 3 — Donut
# ------------------------------------------------------------------ #

def plot_component_donut(
        data: pd.Series,
        threshold: float = 3,
        unit='',
        percent_tot_labels: Optional[List] = None,
        percent_tot_text: Optional[str] = None,
        startangle: Optional[float] = None,
        horizontal_length: float = 0.5,
        radial_length: float = 1.3,
        palette: Optional[Palette] = None,
        backend=None,
        **kwargs):
    """Plot a donut chart of component shares.

    Data preparation (small-category merging, annotation geometry, color
    resolution) is done here; rendering is delegated to the backend.

    Args:
        data: Series with category values.
        threshold: Percentage below which categories are merged into "Smol".
        unit: Unit string for annotation labels.
        percent_tot_labels: Categories to sum for a secondary total.
        percent_tot_text: Label for the secondary total in the center.
        startangle: Starting angle in degrees. Auto-calculated if None.
        horizontal_length: Horizontal offset for annotation lines.
        radial_length: Radial offset for annotation lines.
        backend: Backend name or None for session default.
        **kwargs: Forwarded to the backend (e.g. ``ax=``).
    """
    be = _get_backend(backend)

    # --- data prep ---
    series = data.sort_values()
    total = series.sum()

    sub_total = 0
    if percent_tot_labels is not None:
        sub_total = series.loc[percent_tot_labels].sum()

    percentages = (series / total) * 100

    # Merge small categories into "Smol"
    small_categories = percentages[percentages < threshold]
    large_categories = percentages[percentages >= threshold]

    if not small_categories.empty:
        other_sum = small_categories.sum()
        plot_series = pd.concat([
            large_categories, pd.Series([other_sum], index=['Smol']),
        ])
    else:
        plot_series = large_categories

    # Calculate optimal startangle
    if startangle is None:
        startangle = 90
        if 'Smol' in plot_series.index:
            smol_idx = plot_series.index.get_loc('Smol')
            angle_before_smol = 360 * (
                plot_series.iloc[:smol_idx].sum() / plot_series.sum()
            )
            startangle = (360 - angle_before_smol) % 360

    # Resolve colors — palette takes precedence over global colormap
    if palette is not None:
        pal_colors = palette.get_color_map()
        colors = []
        for label in plot_series.index.values:
            if label in pal_colors:
                colors.append(pal_colors[label])
            elif label == 'Smol':
                colors.append("#d6d4d4")
            else:
                colors.append(random_color())
    else:
        gat_colormap = get_colormap()
        colors = []
        for label in plot_series.index.values:
            if label in gat_colormap:
                colors.append(gat_colormap[label])
            elif label == 'Smol':
                colors.append("#d6d4d4")
            else:
                colors.append(random_color())

    # Build annotation metadata (geometry computed from wedge angles)
    # We compute the annotations upfront so backends don't need trig.
    cumulative = plot_series.cumsum()
    total_pct = plot_series.sum()
    annotations = []
    running = 0.0
    for i, category in enumerate(plot_series.index):
        pct = plot_series.iloc[i]
        theta1 = startangle + 360 * (running / total_pct)
        theta2 = startangle + 360 * ((running + pct) / total_pct)
        angle = (theta1 + theta2) / 2
        rad = math.radians(angle)
        running += pct

        x_start = math.cos(rad)
        y_start = math.sin(rad)
        x_mid = radial_length * math.cos(rad)
        y_mid = radial_length * math.sin(rad)
        x_end = x_mid + (horizontal_length if x_mid >= 0 else -horizontal_length)
        y_end = y_mid

        value = (
            series[category] if category != 'Smol'
            else series[small_categories.index].sum()
        )

        if category == 'Smol' and not small_categories.empty:
            other_details = [
                f'{idx}: {series[idx]:.1f}{unit} ({val:.1f}%)'
                for idx, val in small_categories.items()
            ]
            text = '\n'.join(other_details)
            va = 'top'
        else:
            text = f'{category}: {value:.1f}{unit} ({pct:.1f}%)'
            va = 'center'

        annotations.append({
            "text": text,
            "xy": (x_start, y_start),
            "xytext": (x_end, y_end),
            "ha": 'left' if x_mid >= 0 else 'right',
            "va": va,
        })

    # Build center text
    center_text = f'{total:.1f} {unit}'
    if percent_tot_text is not None:
        center_text = f'{total:.1f} {unit}\n{percent_tot_text}: {sub_total:.1f}'

    # --- render ---
    return be.donut(
        plot_series, colors, annotations, center_text,
        startangle=startangle, **kwargs,
    )


# ------------------------------------------------------------------ #
# Placeholder primitives
# ------------------------------------------------------------------ #

def plot_series_heatmap(series: pd.Series):
    pass


def plot_series_sorted(series: pd.Series):
    pass
