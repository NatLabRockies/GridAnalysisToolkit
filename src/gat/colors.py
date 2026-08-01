"""Enumerable color namespaces for GAT.

Provides named color constants accessible via attribute access, so users
building custom palettes don't need to look up hex codes.

Usage::

    from gat.colors import standard

    standard.PV          # "#FFC903"
    standard.WIND        # "#00B6EF"
    standard.GAS_CC      # "#52216B"
    standard["PV"]       # "#FFC903" (subscript access)

    # Use in palette definitions
    from gat.models.palette import DisplayCategory
    DisplayCategory(name="Solar", color=standard.PV)

    # Iterate all colors
    for name, hex_color in standard:
        print(f"{name}: {hex_color}")

Multiple color sets can coexist (standard, colorblind, pastel).
Extensions can register additional color sets.
"""

from __future__ import annotations

import re
from typing import Iterator


class ColorSet:
    """A named collection of colors accessible via attribute or subscript access.

    Each color is a plain hex string, so it works anywhere a color string
    is expected (matplotlib, plotly, CSS, etc.).

    Args:
        name: Display name for this color set (e.g. "standard").
        colors: Mapping of UPPER_SNAKE_CASE names to hex color strings.
    """

    def __init__(self, name: str, colors: dict[str, str]) -> None:
        self._name = name
        self._colors = dict(colors)
        for key, hex_val in colors.items():
            object.__setattr__(self, key, hex_val)

    def __repr__(self) -> str:
        return f"ColorSet('{self._name}', {len(self._colors)} colors)"

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._colors.items())

    def __contains__(self, key: str) -> bool:
        return key in self._colors

    def __len__(self) -> int:
        return len(self._colors)

    def __getitem__(self, key: str) -> str:
        return self._colors[key]

    def keys(self) -> list[str]:
        return list(self._colors.keys())

    def values(self) -> list[str]:
        return list(self._colors.values())

    def items(self) -> list[tuple[str, str]]:
        return list(self._colors.items())


def _normalize_key(name: str) -> str:
    """Convert a display name to an UPPER_SNAKE_CASE attribute name.

    Examples:
        "Land-based Wind" → "LAND_BASED_WIND"
        "NG-CC" → "NG_CC"
        "PV" → "PV"
        "Gas-CC-CCS" → "GAS_CC_CCS"
        "o-g-s" → "O_G_S"
    """
    s = name.strip()
    s = re.sub(r"[\s\-]+", "_", s)
    s = s.upper()
    return s


def color_set_from_display_names(name: str, display_dict: dict[str, str]) -> ColorSet:
    """Build a ColorSet from a dict with display-style keys.

    Normalizes keys to UPPER_SNAKE_CASE for attribute access.
    The original display names are preserved as values alongside
    their normalized keys.

    Args:
        name: Name for the color set.
        display_dict: Mapping of display names to hex colors.
            e.g. {"Land-based Wind": "#00B6EF", "PV": "#FFC903"}
    """
    normalized = {}
    for display_name, hex_color in display_dict.items():
        key = _normalize_key(display_name)
        # First occurrence wins (preserves order priority from dict)
        if key not in normalized:
            normalized[key] = hex_color
    return ColorSet(name, normalized)


# ---------------------------------------------------------------------------
# Built-in color sets
# ---------------------------------------------------------------------------

# The "standard" color set — derived from the legacy standard_color_dict
# in gat/quickplots/config.py. Every entry from that dict is included
# with its key normalized to UPPER_SNAKE_CASE.
#
# If two display names normalize to the same key (e.g. "NG-CC" and "Gas-CC"
# both become "GAS_CC"), the first one in dict order wins. Aliases that
# differ are kept as separate entries.

standard = ColorSet(
    "standard",
    {
        # Nuclear
        "NUCLEAR": "#820000",
        # Coal
        "COAL": "#222222",
        "COAL_CCS": "#707685",
        # Gas (aliases grouped)
        "STEAM_TURBINE": "#222223",
        "NG_CC": "#52216B",
        "GAS_CC": "#52216B",
        "NG_CCS": "#9467BD",
        "GAS_CCS": "#9467BD",
        "COMBINED_CYCLE_GAS_TURBINE": "#52216B",
        "NG_CC_CCS": "#5E1688",
        "GAS_CC_CCS": "#5E1688",
        "NG_CT": "#C2A1DB",
        "GAS_CT": "#C2A1DB",
        "NG": "#C2A1DB",
        "GAS": "#C2A1DB",
        "COMBUSTION_TURBINE": "#C2A1DB",
        # Oil
        "DUAL_FUEL": "#000080",
        "OIL_GAS_STEAM": "#3D3376",
        "O_G_S": "#3D3376",
        "OIL": "#3D3376",
        # Renewables (non-VRE)
        "GEOTHERMAL": "#A96235",
        "LANDFILL_GAS": "#5B9844",
        "BIOPOWER": "#5B9844",
        "RE_CT": "#7FC340",
        "RE_CC": "#7FC340",
        "BECCS": "#A8C839",
        # Hydro / Storage
        "PS": "#CC0079",
        "OTHER": "#FF7FBB",
        "HYDRO": "#187F94",
        "OCEAN": "#000080",
        "PUMPED_HYDRO": "#CC0079",
        "BATTERY": "#FF4A88",
        "BESS": "#FF4A88",
        "STORAGE": "#FF4A88",
        # Hydrogen
        "H2_CT": "#A8C839",
        "H2_CC": "#708238",
        # VRE
        "VRE": "#7FC340",
        "RE": "#7FC340",
        "WIND": "#00B6EF",
        "LAND_BASED_WIND": "#00B6EF",
        "ONSHORE_WIND": "#00B6EF",
        "OFFSHORE_WIND": "#106BA7",
        "CSP": "#FC761A",
        "PV": "#FFC903",
        "UPV": "#FFC903",
        "DPV": "#FFAB02",
        "ELECTROLYZER": "#896F2D",
        "PV_BATTERY": "#D1C202",
        "OSW_BATTERY": "#9B014F",
        # Trade
        "NET_IMPORTS": "#2762C4",
        "NET_EXPORTS": "#E43F3F",
        "IMPORTS_FROM_CANADA": "#193A71",
        # System
        "DEMAND": "#000000",
        "CURTAILMENT": "#E1E1E1",
        "UNSERVED_ENERGY": "#FF0000",
    },
)

# Future color sets (placeholders for extension or community contributions):
# colorblind = ColorSet("colorblind", {...})
# pastel = ColorSet("pastel", {...})
