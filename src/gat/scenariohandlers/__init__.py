from ._deprecation import LEGACY_HANDLER_DEPRECATION_MSG  # noqa: F401


def __getattr__(name):
    """Lazy import — each scenario handler (and its own format-specific
    dependencies: h5py, geopandas, polars, duckdb...) only loads on
    first access, so e.g. ``from gat.scenariohandlers import
    PlexosScenario`` never touches Sienna's or ReEDS's dependencies."""
    if name == "SiennaScenario":
        from .sienna import SiennaScenario

        return SiennaScenario
    elif name == "PlexosScenario":
        from .plexos import PlexosScenario

        return PlexosScenario
    elif name == "ReEDsScenario":
        from .reeds import ReEDsScenario

        return ReEDsScenario
    elif name == "MultiScenario":
        from .multi import MultiScenario

        return MultiScenario
    elif name == "BaseScenario":
        from .base import BaseScenario

        return BaseScenario
    elif name == "FileScenario":
        from .file_scenario import FileScenario

        return FileScenario
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "LEGACY_HANDLER_DEPRECATION_MSG",
    "SiennaScenario",
    "PlexosScenario",
    "ReEDsScenario",
    "MultiScenario",
    "BaseScenario",
    "FileScenario",
]
