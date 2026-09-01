"""Default multi-file BaseSimulation implementation.

This is what BaseSimulation.from_paths() falls back to when a format
doesn't override it: one inner-class instance per path, datasets combined
with gat.simulations.utils.combine_overlapping_frames. It's the "parse
each file into a Python object, then let GAT combine them" case -- the
common one, free for any BaseSimulation subclass whose constructor takes
a single file path.

Formats that combine through a different mechanism (e.g. PlexosDuckDBSimulation,
which ATTACHes multiple files at the SQL layer) override from_paths
directly instead of going through this class.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Type

import pandas as pd

from ..interfaces import BaseSimulation
from .utils import combine_overlapping_frames

if TYPE_CHECKING:
    from ..categories import CategoryMap
    from ..datasets import DatasetComposition, DatasetInfo


class MultiFileSimulation(BaseSimulation):
    """Combines N single-file BaseSimulation instances into one.

    Args:
        inner_cls: A BaseSimulation subclass whose constructor accepts a
            single path (plus optional kwargs).
        paths: The partition files to combine.
        merge_strategy: Passed to combine_overlapping_frames for every
            dataset -- "earlier_wins"/"later_wins" (or the legacy
            "right"/"left" spellings). Default "earlier_wins".
        **inner_kwargs: Forwarded to inner_cls(path, **inner_kwargs) for
            every instance.
    """

    def __init__(
        self,
        inner_cls: Type[BaseSimulation],
        paths: list[str | Path],
        merge_strategy: str = "earlier_wins",
        **inner_kwargs,
    ):
        if len(paths) < 1:
            raise ValueError("MultiFileSimulation requires at least one path")
        self._instances = [inner_cls(p, **inner_kwargs) for p in paths]
        self._merge_strategy = merge_strategy

    def list_datasets(self) -> list["DatasetInfo"]:
        """Union of every instance's datasets by name -- metadata comes
        from whichever instance first reported a given name."""
        by_name: dict[str, "DatasetInfo"] = {}
        for instance in self._instances:
            for info in instance.list_datasets():
                by_name.setdefault(info.name, info)
        return list(by_name.values())

    def get_dataset(self, name: str) -> pd.DataFrame:
        frames = [instance.get_dataset(name) for instance in self._instances]
        return combine_overlapping_frames(frames, merge_strategy=self._merge_strategy)

    def get_default_category_maps(self) -> list["CategoryMap"]:
        return self._instances[0].get_default_category_maps()

    def get_default_compositions(self) -> list["DatasetComposition"]:
        return self._instances[0].get_default_compositions()
