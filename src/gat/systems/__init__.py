"""GAT system implementations.

Lazily imported on first access, matching gat.scenariohandlers and
gat.simulations — constructing a PlexosSystem never touches Sienna's
dependencies, and vice versa.
"""


def __getattr__(name):
    if name == "PlexosSystem":
        from .plexos import PlexosSystem

        return PlexosSystem
    elif name == "PlexosDuckDBSystem":
        from .plexos_duckdb import PlexosDuckDBSystem

        return PlexosDuckDBSystem
    elif name == "SiennaSystem":
        from .sienna import SiennaSystem

        return SiennaSystem
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["PlexosSystem", "PlexosDuckDBSystem", "SiennaSystem"]
