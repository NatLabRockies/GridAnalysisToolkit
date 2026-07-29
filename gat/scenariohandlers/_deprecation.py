"""Shared deprecation helper for legacy scenario handler classes."""
import warnings

LEGACY_HANDLER_DEPRECATION_MSG = (
    "{cls} is deprecated and will be migrated to a duckdb-backed implementation "
    "in a future release. New code should use `gat.load(...)` to obtain a "
    "scenario object via the supported v1 entry point."
)


def warn_legacy_handler(instance):
    """Emit a DeprecationWarning pointing at the user's call site (stacklevel=3:
    user → handler.__init__ → this helper)."""
    warnings.warn(
        LEGACY_HANDLER_DEPRECATION_MSG.format(cls=type(instance).__name__),
        DeprecationWarning,
        stacklevel=3,
    )
