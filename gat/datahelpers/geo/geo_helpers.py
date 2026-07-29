import geopandas as gpd
from shapely.geometry import Point, LineString


# ── Column-name detection ──
# Common case-/whitespace-insensitive aliases for the columns we care about
# in user-supplied geo files. `_normalize_col_name` applies the matching
# rule so detection is consistent everywhere.

_LAT_NAMES = {"lat", "latitude", "y", "lat_y", "point_y", "geo_lat", "facility_lat"}
_LON_NAMES = {"lon", "lng", "long", "longitude", "x", "lat_x", "point_x", "geo_lon", "geo_lng", "facility_lon", "facility_lng"}
_BUS_ID_NAMES = {"bus_id", "bus_number", "bus", "node_id", "node", "id", "name"}


def _normalize_col_name(col: str) -> str:
    """Case-/whitespace-insensitive column normalizer used by detection."""
    return col.lower().strip().replace(" ", "_")


def detect_latlon_columns(columns):
    """Auto-detect latitude/longitude columns from a list of names.

    Matching is case-insensitive and ignores leading/trailing whitespace,
    so "Latitude", "LATITUDE", " lat ", "Lat Y" all match. Returns
    `(lat_col, lon_col)` using the original name as it appears in the
    file, or `(None, None)` if not found.
    """
    lat_col = lon_col = None
    for col in columns:
        n = _normalize_col_name(col)
        if n in _LAT_NAMES and lat_col is None:
            lat_col = col
        elif n in _LON_NAMES and lon_col is None:
            lon_col = col
    return lat_col, lon_col


def detect_bus_id_column(columns):
    """Auto-detect a bus-ID column. Returns the original name, or None."""
    for col in columns:
        if _normalize_col_name(col) in _BUS_ID_NAMES:
            return col
    return None

def convert_to_geonode(df, lat_col='Latitude', lon_col='Longitude', default_crs='EPSG:4326') -> gpd.GeoDataFrame:

    "Takes a dataframe with lat/lon values and returns a GeoDataFrame version of it"

    df['geometry'] = df.apply(lambda row: Point(row[lon_col], row[lat_col]), axis=1)

    gdf = gpd.GeoDataFrame(df, geometry=df['geometry'])
    gdf = gdf.set_crs(default_crs)
    gdf.drop(columns=[lat_col, lon_col],inplace=True)

    return gdf


def convert_to_geoline(df, from_lat='from_lat', from_lon='from_lon', to_lat='to_lat', to_lon='to_lon', default_crs='EPSG:4326')->gpd.GeoDataFrame:

    df['geometry'] = df.apply(lambda row: LineString([
        [row[from_lon] , row[from_lat]], # From Point
        [row[to_lon], row[to_lat] ] # To Point
        ]
        ),
        axis=1)
    gdf = gpd.GeoDataFrame(df, geometry=df['geometry'])
    gdf = gdf.set_crs(default_crs)
    gdf.drop(columns=[from_lat, to_lat, from_lon, to_lon], inplace=True)
    return gdf

def map_to_area(point_gdf: gpd.GeoDataFrame, area_gdf: gpd.GeoDataFrame):
    """
    Intention: Take a Point geodataframe and map to a MultiPolygon Frame

    """
    return NotImplemented
