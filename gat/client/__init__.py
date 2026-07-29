"""GAT Client — connect to a remote GAT server."""

from __future__ import annotations

from typing import Optional

from gat.client.connection import Connection
from gat.client.remote_scenario import RemoteScenario


class GATClient:
    """Client for interacting with a GAT server.

    Example::

        client = GATClient("http://localhost:8815")
        client.list_scenarios()
        scenario = client.scenario("rts-gmlc", "base-case")
        df = scenario.query("generation", group_by=["technology_simple"])
    """

    def __init__(
        self,
        url: str = "http://localhost:8815",
        token: Optional[str] = None,
    ) -> None:
        self._conn = Connection(url, token=token)

    def health(self) -> dict:
        """Check server health."""
        return self._conn.get_json("/health")

    def list_scenarios(self) -> list[dict]:
        """List all materialized scenarios on the server."""
        resp = self._conn.get_json("/scenarios")
        return resp.get("scenarios", [])

    def scenario(self, project: str, scenario: str) -> RemoteScenario:
        """Get a RemoteScenario handle for querying data."""
        return RemoteScenario(self._conn, project, scenario)

    def push(
        self,
        project: str,
        scenario: str,
        handler: str,
        system_path: Optional[str] = None,
        simulation_paths: Optional[list[str]] = None,
    ) -> dict:
        """Push a scenario for server-side ingestion."""
        body = {
            "project": project,
            "scenario": scenario,
            "handler": handler,
        }
        if system_path:
            body["system_path"] = system_path
        if simulation_paths:
            body["simulation_paths"] = simulation_paths
        return self._conn.post_json("/scenarios/ingest", body)

    def delete_scenario(self, project: str, scenario: str) -> dict:
        """Delete a materialized scenario."""
        return self._conn.delete_json(f"/scenarios/{project}/{scenario}")

    def get_scenario_info(self, project: str, scenario: str) -> dict:
        """Get detailed info about a scenario."""
        return self._conn.get_json(f"/scenarios/{project}/{scenario}")
