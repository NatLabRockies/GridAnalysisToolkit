"""
Author: Micah Webb
Email: micah.webb@nlr.gov

Description: Pydantic models and resulting apis that describe a Power System and generate common data representations
like graph, geospatial representations. The System also includes apis for calculating system capacity by generation type.


"""

from pydantic import BaseModel
from typing import List, Optional, Union, Dict, Any


class Region(BaseModel):
    id: Union[str, int]
    name: str


class Node(BaseModel):
    id: Union[str, int]
    # a single area or a lookup of areas e.g. keys=interconnect, MMWG, ISO, etc
    area: Union[Region, Dict[str, Region]]
    latitude: Optional[float]
    longitude: Optional[float]


class Arc(BaseModel):
    id: Union[str, int]
    from_node: Node
    to_node: Node


class TransmissionLine(BaseModel):
    id: Union[str, int]
    name: Union[str, int]
    arc: Optional[Arc]  # Might not have the network representation
    capacity: Optional[float] = None
    type: Optional[str] = None  # AC or DC
    voltage: Optional[float] = None


class Transformer(BaseModel):
    id: Union[str, int]
    name: Union[str, int]
    arc: Optional[Arc] = None
    capacity: Optional[float] = None
    high_voltage: Optional[float] = None
    low_voltage: Optional[float] = None


class Load(BaseModel):
    id: Union[str, int]
    name: Union[str, int]
    flexible: bool = False
    storage: bool = False


class GenerationTechnology(BaseModel):
    name: str
    curtailable: bool = False
    dispatchable: bool = False  # determines the net load calculation


class Generator(BaseModel):
    # The name of the generator
    id: Union[str, int]
    name: Union[str, int]
    technology: GenerationTechnology
    node: Optional[Node]
    capacity: Optional[float]


class System(BaseModel):
    id: Union[str, int]
    name: Union[str, int]

    generators: Dict[Union[int, str], Generator]
    loads: Dict[Union[int, str], Load]
    transmission: Optional[Dict[Union[int, str], TransmissionLine]] = None
    transformers: Optional[Dict[Union[int, str], Transformer]] = None

    nodes: Optional[Dict[Union[int, str], Node]] = None
    arcs: Optional[Dict[Union[int, str], Arc]] = None

    regions: Optional[Dict[str, Region]] = None

    # Put geo first so autocompletion works with .geo*
    def geo_generators(self):
        """Build a GeoDataFrame of generators positioned at their nodes.

        Returns None if no nodes carry coordinates (callers can then
        fall back to an externally-provided sidecar; see the
        `bus_geometry` upload flow). Skips generators whose `node` is
        unset or whose node lacks coords.
        """
        try:
            import geopandas as gpd
            import pandas as pd
            from shapely.geometry import Point
        except ImportError:  # geopandas/shapely are optional at runtime
            return None

        if not self.nodes:
            return None
        node_coords = {
            nid: (n.latitude, n.longitude)
            for nid, n in self.nodes.items()
            if n.latitude is not None and n.longitude is not None
        }
        if not node_coords:
            return None

        rows = []
        for gid, gen in (self.generators or {}).items():
            if gen.node is None:
                continue
            coords = node_coords.get(gen.node.id)
            if not coords:
                continue
            lat, lon = coords
            rows.append(
                {
                    "id": gid,
                    "name": gen.name,
                    "technology": gen.technology.name if gen.technology else None,
                    "capacity": gen.capacity,
                    "node_id": gen.node.id,
                    "geometry": Point(lon, lat),
                }
            )
        if not rows:
            return None
        return gpd.GeoDataFrame(
            pd.DataFrame.from_records(rows), geometry="geometry", crs="EPSG:4326"
        )

    def geo_lines(self):
        """Build a GeoDataFrame of transmission lines as LineString features.

        Each line uses its arc's `from_node` and `to_node` coordinates.
        Returns None if no arcs have positioned endpoints.
        """
        try:
            import geopandas as gpd
            import pandas as pd
            from shapely.geometry import LineString
        except ImportError:
            return None

        if not self.nodes:
            return None
        node_coords = {
            nid: (n.latitude, n.longitude)
            for nid, n in self.nodes.items()
            if n.latitude is not None and n.longitude is not None
        }
        if not node_coords or not self.transmission:
            return None

        rows = []
        for lid, line in self.transmission.items():
            if not line.arc:
                continue
            a = node_coords.get(line.arc.from_node.id)
            b = node_coords.get(line.arc.to_node.id)
            if not a or not b:
                continue
            rows.append(
                {
                    "id": lid,
                    "name": line.name,
                    "type": line.type,
                    "voltage": line.voltage,
                    "capacity": line.capacity,
                    "geometry": LineString([(a[1], a[0]), (b[1], b[0])]),
                }
            )
        if not rows:
            return None
        return gpd.GeoDataFrame(
            pd.DataFrame.from_records(rows), geometry="geometry", crs="EPSG:4326"
        )

    def geo_transformers(self):
        """Point GeoDataFrame for transformers, positioned at their arc midpoints.

        Per the original docstring: even though transformers span an arc,
        endpoints are typically co-located in a substation. Emits a
        warning if any transformer's arc endpoints are >100 m apart.
        """
        try:
            import geopandas as gpd
            import pandas as pd
            from shapely.geometry import Point
        except ImportError:
            return None

        if not self.nodes or not self.transformers:
            return None
        node_coords = {
            nid: (n.latitude, n.longitude)
            for nid, n in self.nodes.items()
            if n.latitude is not None and n.longitude is not None
        }
        if not node_coords:
            return None

        import math
        import warnings

        def _haversine_m(a, b):
            lat1, lon1 = math.radians(a[0]), math.radians(a[1])
            lat2, lon2 = math.radians(b[0]), math.radians(b[1])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            h = (
                math.sin(dlat / 2) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
            )
            return 2 * 6_371_000 * math.asin(math.sqrt(h))

        rows = []
        for tid, xfmr in self.transformers.items():
            if not xfmr.arc:
                continue
            a = node_coords.get(xfmr.arc.from_node.id)
            b = node_coords.get(xfmr.arc.to_node.id)
            if not a or not b:
                continue
            if _haversine_m(a, b) > 100:
                warnings.warn(
                    f"Transformer {tid!r} arc endpoints are >100 m apart; "
                    f"using midpoint may misrepresent location.",
                    RuntimeWarning,
                )
            mid_lat = (a[0] + b[0]) / 2
            mid_lon = (a[1] + b[1]) / 2
            rows.append(
                {
                    "id": tid,
                    "name": xfmr.name,
                    "capacity": xfmr.capacity,
                    "high_voltage": xfmr.high_voltage,
                    "low_voltage": xfmr.low_voltage,
                    "geometry": Point(mid_lon, mid_lat),
                }
            )
        if not rows:
            return None
        return gpd.GeoDataFrame(
            pd.DataFrame.from_records(rows), geometry="geometry", crs="EPSG:4326"
        )

    def network(self):
        """Returns the networkx representation of the system"""
        return NotImplemented

    def generation_capacity(self) -> Dict[str, float]:
        """
        Gets the aggregates system capacity by GenerationTechnology and Area as a dataframe, series or dictionary.
        """
        pass

    def transformer_capacity(self) -> Dict[str, float]:
        """
        Gets the aggregate transformer capacity by High/Low Voltage and Area
        """
        pass

    def transmission_capacity(self) -> Dict[str, float]:
        """
        Gets the transmission capacity be Voltage, and Area or Area->Area

        In the case of Area->Area, the naming is ordered alphabetically.
        """
        pass

    def transmission_intraregional(self) -> List[TransmissionLine]:
        """
        Gets the subset transmission lines that lie soley within an area or region.
        """
        pass

    def transmission_interregional(self) -> List[TransmissionLine]:
        """
        Gets the subset of transmission lines that connect two regions
        """
        pass
