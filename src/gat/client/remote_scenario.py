"""RemoteScenario — duck-type compatible with local Scenario for remote queries."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from gat.client.connection import Connection


class RemoteScenario:
    """Scenario-compatible interface that queries a GAT server.

    Mirrors the local Scenario API so that plot code can work
    transparently against local or remote data.
    """

    def __init__(self, conn: Connection, project: str, scenario: str) -> None:
        self._conn = conn
        self.project = project
        self.name = scenario
        self._info: Optional[dict] = None

    def _ensure_info(self) -> dict:
        if self._info is None:
            self._info = self._conn.get_json(f"/scenarios/{self.project}/{self.name}")
        return self._info

    # ------------------------------------------------------------------ #
    # Level 1: Dataset discovery
    # ------------------------------------------------------------------ #

    def list_datasets(self) -> list[str]:
        """List available datasets (table names) on the server."""
        info = self._ensure_info()
        return info.get("datasets", [])

    def list_category_maps(self, dataset: str | None = None) -> list[str]:
        """List available category maps."""
        info = self._ensure_info()
        return info.get("category_maps", [])

    # ------------------------------------------------------------------ #
    # Level 2: Queries
    # ------------------------------------------------------------------ #

    def query(
        self,
        dataset: str,
        group_by: list[str] | None = None,
        palette=None,
    ) -> pd.DataFrame:
        """Query a dataset with optional grouping.

        Args:
            dataset: Dataset name (e.g. "generation").
            group_by: Category map names to GROUP BY.
            palette: Not supported for remote queries (ignored).

        Returns:
            Wide DataFrame from the server.
        """
        if group_by:
            return self._conn.post_arrow(
                "/query/grouped",
                {
                    "project": self.project,
                    "scenario": self.name,
                    "dataset": dataset,
                    "group_by": group_by,
                },
            )

        # Unqualified table name — server auto-prefixes via search_path
        return self.sql(f"SELECT * FROM {dataset}")

    def sql(self, query: str) -> pd.DataFrame:
        """Execute SQL against the server."""
        return self._conn.post_arrow(
            "/query",
            {
                "project": self.project,
                "scenario": self.name,
                "sql": query,
            },
        )

    # ------------------------------------------------------------------ #
    # Level 3: Analytics
    # ------------------------------------------------------------------ #

    def net_load(
        self,
        load_dataset: str = "load",
        generation_dataset: str = "generation",
        vre_categories: list[str] | None = None,
        area_map: str = "native_area",
        tech_map: str | None = None,
    ) -> pd.DataFrame:
        """Compute net load via server-side SQL."""
        if vre_categories is None or tech_map is None:
            return self.query(load_dataset, group_by=[area_map])

        vre_list = ", ".join(f"'{c}'" for c in vre_categories)
        sql = f"""
            WITH load_by_area AS (
                SELECT cm.category AS {area_map}, SUM(COLUMNS(* EXCLUDE (entity_id)))
                FROM {load_dataset} g
                JOIN catmap__{area_map} cm ON g.entity_id = cm.entity_id
                GROUP BY cm.category
            ),
            vre_by_area AS (
                SELECT a.category AS {area_map}, SUM(COLUMNS(* EXCLUDE (entity_id)))
                FROM {generation_dataset} g
                JOIN catmap__{tech_map} t ON g.entity_id = t.entity_id
                JOIN catmap__{area_map} a ON g.entity_id = a.entity_id
                WHERE t.category IN ({vre_list})
                GROUP BY a.category
            )
            SELECT l.*
            FROM load_by_area l
        """
        return self.sql(sql)

    def curtailment(
        self,
        generation_dataset: str = "generation",
        availability_dataset: str = "availability",
        vre_categories: list[str] | None = None,
        tech_map: str | None = None,
    ) -> pd.DataFrame:
        """Compute curtailment via server-side SQL."""
        if vre_categories and tech_map:
            vre_list = ", ".join(f"'{c}'" for c in vre_categories)
            sql = f"""
                SELECT g.entity_id
                FROM {generation_dataset} g
                JOIN {availability_dataset} a ON g.entity_id = a.entity_id
                JOIN catmap__{tech_map} t ON g.entity_id = t.entity_id
                WHERE t.category IN ({vre_list})
                ORDER BY g.entity_id
            """
        else:
            sql = f"""
                SELECT g.entity_id
                FROM {generation_dataset} g
                JOIN {availability_dataset} a ON g.entity_id = a.entity_id
                ORDER BY g.entity_id
            """
        return self.sql(sql)

    def ramp_rate(
        self,
        dataset: str = "generation",
        group_by: list[str] | None = None,
    ) -> pd.DataFrame:
        """Compute ramp rate — fetches data then computes locally."""
        import numpy as np

        if group_by:
            df = self.query(dataset, group_by=group_by)
            group_cols = list(group_by)
        else:
            df = self.query(dataset)
            group_cols = ["entity_id"]

        ts_cols = [c for c in df.columns if c not in group_cols]
        if len(ts_cols) < 2:
            raise ValueError("Need at least 2 timestamps for ramp rate")

        t0 = pd.Timestamp(ts_cols[0])
        t1 = pd.Timestamp(ts_cols[1])
        minutes = (t1 - t0).total_seconds() / 60.0

        values = df[ts_cols].values.astype(np.float64)
        ramp = np.diff(values, axis=1) / minutes
        nan_col = np.full((ramp.shape[0], 1), np.nan)
        ramp = np.hstack([nan_col, ramp])

        result = df[group_cols].copy()
        for i, col in enumerate(ts_cols):
            result[col] = ramp[:, i].astype(np.float32)
        return result

    def line_loading(
        self,
        flow_dataset: str = "line_flow",
        rating_map: dict[str, float] | None = None,
    ) -> pd.DataFrame:
        """Compute line loading — fetches flow data then computes locally."""
        import numpy as np

        flow_df = self.query(flow_dataset)
        entity_ids = flow_df["entity_id"].values
        ts_cols = [c for c in flow_df.columns if c != "entity_id"]
        flow_matrix = flow_df[ts_cols].values

        if rating_map is None:
            raise ValueError(
                "rating_map required for remote line_loading "
                "(server does not have system parser access)"
            )

        ratings = np.array(
            [rating_map.get(eid, np.nan) for eid in entity_ids],
            dtype=np.float32,
        )
        invalid = np.isnan(ratings) | (ratings == 0)

        out = np.full_like(flow_matrix, np.nan, dtype=np.float32)
        loading = np.abs(
            np.divide(
                flow_matrix,
                ratings[:, np.newaxis],
                out=out,
                where=(~invalid)[:, np.newaxis],
            )
            * 100.0
        ).astype(np.float32)

        result = pd.DataFrame({"entity_id": entity_ids})
        for i, col in enumerate(ts_cols):
            result[col] = loading[:, i]
        return result
