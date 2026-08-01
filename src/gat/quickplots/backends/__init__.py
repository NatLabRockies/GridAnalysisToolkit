"""Plotting backend registry for GAT.

Manages pluggable rendering backends (matplotlib, plotly, etc.).
Each backend implements the PlotBackend protocol defined in protocol.py.

Usage::

    from gat.quickplots.backends import get_backend, set_default_backend

    # Get a specific backend
    be = get_backend("static")       # matplotlib
    be = get_backend("interactive")  # plotly (if installed)

    # Get the default backend (initially "static")
    be = get_backend()

    # Change the default for the session
    set_default_backend("interactive")

    # Register a custom backend
    from gat.quickplots.backends import register_backend
    register_backend("custom", MyCustomBackend())
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from .protocol import PlotBackend

_backends: dict[str, PlotBackend] = {}
_default_backend: str = "static"


def register_backend(name: str, backend: PlotBackend) -> None:
    """Register a plotting backend under the given name.

    Args:
        name: Backend identifier (e.g. "static", "interactive").
        backend: An object implementing the PlotBackend protocol.
    """
    _backends[name] = backend
    logger.debug("Registered plotting backend: '{}'", name)


def get_backend(name: Optional[str] = None) -> PlotBackend:
    """Get a plotting backend by name, or the default if name is None.

    Args:
        name: Backend name. If None, uses the current default.

    Returns:
        The PlotBackend instance.

    Raises:
        ValueError: If the requested backend is not registered.
    """
    name = name or _default_backend
    if name not in _backends:
        available = list(_backends.keys())
        raise ValueError(
            f"Unknown plotting backend '{name}'. " f"Available: {available}"
        )
    return _backends[name]


def set_default_backend(name: str) -> None:
    """Set the default plotting backend for the session.

    Args:
        name: Backend name (must already be registered).

    Raises:
        ValueError: If the backend is not registered.
    """
    global _default_backend
    if name not in _backends:
        available = list(_backends.keys())
        raise ValueError(
            f"Unknown plotting backend '{name}'. " f"Available: {available}"
        )
    _default_backend = name
    logger.info("Default plotting backend set to '{}'", name)


def list_backends() -> list[str]:
    """Return names of all registered backends."""
    return list(_backends.keys())


# ---------------------------------------------------------------------------
# Auto-register built-in backends
# ---------------------------------------------------------------------------

# matplotlib is always available (it's a core dependency)
from .matplotlib_backend import MatplotlibBackend  # noqa: E402

register_backend("static", MatplotlibBackend())

# plotly is optional — register if installed
try:
    from .plotly_backend import PlotlyBackend  # noqa: E402

    register_backend("interactive", PlotlyBackend())
except ImportError:
    pass
