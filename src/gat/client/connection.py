"""HTTP connection layer for the GAT client."""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd

try:
    import httpx
    import pyarrow as pa
    import pyarrow.ipc
except ImportError as e:
    raise ImportError(
        "Client dependencies not installed. Run: pip install nlr-gat[client]"
    ) from e


class Connection:
    """Manages HTTP communication with a GAT server."""

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self.base_url = base_url.rstrip("/")
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=300.0,  # 5 min for large queries/ingestion
        )

    def get_json(self, path: str) -> dict:
        """GET request, return JSON."""
        resp = self._client.get(path)
        resp.raise_for_status()
        return resp.json()

    def post_json(self, path: str, body: dict) -> dict:
        """POST request with JSON body, return JSON."""
        resp = self._client.post(path, json=body)
        resp.raise_for_status()
        return resp.json()

    def delete_json(self, path: str) -> dict:
        """DELETE request, return JSON."""
        resp = self._client.delete(path)
        resp.raise_for_status()
        return resp.json()

    def post_arrow(self, path: str, body: dict) -> pd.DataFrame:
        """POST request, deserialize Arrow IPC response to DataFrame."""
        resp = self._client.post(path, json=body)
        resp.raise_for_status()

        reader = pa.ipc.open_stream(resp.content)
        table = reader.read_all()
        return table.to_pandas()

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()
