"""Format-specific data parsers.

Deliberately empty at package level — every real caller imports the
specific submodule it needs (e.g. ``gat.datahelpers.sienna``,
``gat.datahelpers.h5Parsers``), and each submodule's own dependencies
(h5py, geopandas, ...) should only load when that submodule is actually
imported. A blanket ``from .X import *`` here would import every
submodule — and its dependencies — the moment anything under
``gat.datahelpers`` is touched, regardless of which format the caller
actually wanted.
"""
