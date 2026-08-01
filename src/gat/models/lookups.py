from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Union, Any, TYPE_CHECKING
from pathlib import Path
from abc import ABC, abstractmethod
import pandas as pd

if TYPE_CHECKING:
    import geopandas as gpd
# Lookup types = Area-Area, Node-Area, Node-Geometry, SiennaBusLookup


class BaseRelationLookup(BaseModel, ABC):
    file_path: str
    source_value: str
    target_value: str
    available_values: List[str]
    lookup_type: str  # one of the lookup types above

    class Config:
        arbitrary_types_allowed = True

    def __str__(self) -> str:
        """Custom string representation for better debugging"""
        return (
            f"{self.__class__.__name__}("
            f"file='{self.file_path}', "
            f"source='{self.source_value}', "
            f"target='{self.target_value}', "
            f"type='{self.lookup_type}', "
            f"available_values={self.available_values})"
        )

    @classmethod
    @abstractmethod
    def from_file(cls, file_path: Union[str, Path], source_value: Optional[str] = None):
        """Initializes the lookup class from a file
        must be implemented in a concrete class
        """
        pass

    @abstractmethod
    def map_to_area(self, input_array: List[Any]) -> Dict[Union[str, int], str]:
        """Maps an input array of str or int into a dictionary of input->target"""
        pass

    @property
    def target_value(self) -> str:
        """Get the current target value"""
        return self.target_value

    @target_value.setter
    def target_value(self, val: str) -> None:
        """Set the target value if it's in available values"""
        if val in self._available_values:
            self.target_value = val
        else:
            print(
                f"Error setting target_value={val}, use one of the following {self._available_values}"
            )

    @property
    def source_value(self) -> str:
        """Get the current source value"""
        return self.source_value

    @source_value.setter
    def source_value(self, val: str) -> None:
        """Set the source value"""
        self.source_value = val

    @property
    def available_values(self) -> List[str]:
        """Get available values"""
        return self.available_values

    @property
    def file_path(self) -> str:
        """Get the file path"""
        return self.file_path


class FileAreaLookup(BaseRelationLookup):
    """
    Maps the BaseScenario default Area to another Area using a flat file
    """

    lookup_type: str = "Area-Area"

    @classmethod
    def from_file(cls, file_path: Union[str, Path], source_value: str):
        """
        Reads a csv, parquet, xlsx or other flat file. User must define what
        the source value is that aligns with the default value defined in the model
        """
        import pandas as pd

        # Convert to string path
        file_path = str(file_path)

        # Read file based on extension
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".parquet"):
            df = pd.read_parquet(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
        else:
            raise ValueError(f"Unsupported file format: {file_path}")

        # Extract available values (assuming they're in columns)
        available_values = df.columns.tolist()

        # Create instance
        return cls(
            file_path=file_path,
            source_value=source_value,
            target_value=available_values[0] if available_values else "",
            available_values=available_values,
            lookup_type="Area-Area",
        )

    def map_to_area(self, input_array: List[Any]) -> Dict[Union[str, int], str]:
        """Maps input values to target areas using the file data"""
        import pandas as pd

        # Read the mapping file
        if self._file_path.endswith(".csv"):
            df = pd.read_csv(self.file_path)
        elif self._file_path.endswith(".parquet"):
            df = pd.read_parquet(self.file_path)
        elif self._file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(self.file_path)

        # Create mapping dictionary
        result = {}
        for item in input_array:
            # Find the item in the source column and get its target value
            if item in df[self._source_value].values:
                result[item] = df.loc[
                    df[self._source_value] == item, self._target_value
                ].iloc[0]
            else:
                result[item] = None

        return result


class SiennaAreaLookup(BaseRelationLookup):
    """Specialized lookup for Sienna areas"""

    source_value: str = "SYSTEM_DEFAULT"  # This should never change
    target_value: str = "SYSTEM_DEFAULT"
    available_values: List[str] = ["SYSTEM_DEFAULT"]
    lookup_type: str = "SiennaBusLookup"

    @classmethod
    def from_file(cls, file_path: Union[str, Path], source_value: Optional[str] = None):
        """
        Uses the ACBus component to define what the possible mapping values are.
        """
        # The source_value parameter is ignored as we always use SYSTEM_DEFAULT

        # In a real implementation, you would load Sienna-specific data here
        # For now, we'll just create an instance with defaults

        return cls(
            file_path=str(file_path),
            source_value="SYSTEM_DEFAULT",
            target_value="SYSTEM_DEFAULT",
            available_values=["SYSTEM_DEFAULT"],
            lookup_type="SiennaBusLookup",
        )

    def map_to_area(self, input_array: List[Any]) -> Dict[Union[str, int], str]:
        """Maps Sienna bus IDs to areas"""
        # Implementation specific to Sienna bus mapping
        # For now return a simple mapping
        return {item: self.target_value for item in input_array}


class GeoAreaLookup(BaseRelationLookup):
    """Geospatial lookup for mapping between geometries and areas"""

    lookup_type: str = "Node-Geometry"

    @classmethod
    def from_file(
        cls, file_path: Union[str, Path], source_value: Optional[str] = "geometry"
    ):
        """
        Reads the geospatial file and sets available values and default target.
        """
        import fiona

        # Convert to string path
        file_path = str(file_path)

        try:
            # Get available layers
            available_values = fiona.listlayers(file_path)

            # Create instance with all required fields
            return cls(
                file_path=file_path,  # This needs to be set
                source_value=source_value or "geometry",
                target_value=available_values[0] if available_values else "",
                available_values=available_values,
                lookup_type="Node-Geometry",
            )
        except Exception as e:
            print(f"Error loading GeoPackage: {e}")
            # Return a default instance if there's an error
            return cls(
                file_path=file_path,
                source_value=source_value or "geometry",
                target_value="",
                available_values=[],
                lookup_type="Node-Geometry",
            )

    def map_to_area(self, input_arr: List[Any]) -> Dict[Union[str, int], str]:
        """
        Takes a node dataframe and performs spatial join with the target layer.

        Input array should be a list of tuples: [(node_id, geometry), ...]

        Returns:
            Dictionary of nodes mapping to new strings: {node_id: layer_value}
        """
        import geopandas as gpd
        from shapely.geometry import Point

        # Create GeoDataFrame from input array
        nodes_df = gpd.GeoDataFrame(
            data=[item[0] for item in input_arr],  # node IDs
            geometry=[item[1] for item in input_arr],  # geometries
            columns=["node_id"],
        )

        # Read the target layer
        target_layer = gpd.read_file(self.file_path, layer=self.target_value)

        # Perform spatial join
        joined = gpd.sjoin(nodes_df, target_layer, how="left", predicate="within")

        # Create result dictionary
        # Assuming the target layer has an 'id' column; adjust as needed
        result = {}
        for i, row in joined.iterrows():
            if pd.notna(row.get("index_right")):
                # Get the corresponding value from the target layer
                target_idx = row["index_right"]
                target_row = target_layer.iloc[target_idx]
                result[row["node_id"]] = target_row.get("id", str(target_idx))
            else:
                result[row["node_id"]] = None

        return result

    def attach_spatial_attributes(
        self,
        source_gdf: "gpd.GeoDataFrame",
        layer_name: str = None,
        attribute_column: str = None,
        join_type: str = "left",
        predicate: str = "within",
    ) -> "gpd.GeoDataFrame":
        """
        Performs a spatial join between a source GeoDataFrame and a target layer from a geospatial file.
        Then attaches specified attributes from the target layer to the source GeoDataFrame.

        Parameters:
        -----------
        source_gdf : gpd.GeoDataFrame
            The source GeoDataFrame containing point geometries to be joined
        geospatial_file : str
            Path to the geospatial file (GeoPackage, Shapefile, etc.)
        layer_name : str, optional
            Name of the layer in the geospatial file. Required for multi-layer files like GeoPackage
        attribute_column : str, default='name'
            The column from the target layer to attach to the source GeoDataFrame
        join_type : str, default='left'
            Type of join: 'left', 'right', or 'inner'
        predicate : str, default='within'
            Spatial predicate for the join: 'within', 'contains', 'intersects', etc.

        Returns:
        --------
        gpd.GeoDataFrame
            Original source GeoDataFrame with attached attributes from target layer
        """
        import geopandas as gpd

        target_gdf = self.get_layer_gdf(layer_name)

        if attribute_column is None:
            attribute_column = target_gdf.columns[0]

        # Ensure CRS compatibility
        if (
            source_gdf.crs != target_gdf.crs
            and source_gdf.crs is not None
            and target_gdf.crs is not None
        ):
            target_gdf = target_gdf.to_crs(source_gdf.crs)

        # Perform spatial join
        joined_gdf = gpd.sjoin(
            source_gdf,
            target_gdf[[attribute_column, "geometry"]],
            how=join_type,
            predicate=predicate,
        )

        # Rename the joined column for clarity
        if f"{attribute_column}_right" in joined_gdf.columns:
            joined_gdf = joined_gdf.rename(
                columns={f"{attribute_column}_right": f"area_{attribute_column}"}
            )

        # Drop the index_right column from the spatial join
        if "index_right" in joined_gdf.columns:
            joined_gdf = joined_gdf.drop(columns=["index_right"])

        return joined_gdf.rename(columns={attribute_column: "Area"})

    def get_layer_gdf(self, layer_name: str = None) -> "gpd.GeoDataFrame":

        import geopandas as gpd

        # Read the target layer
        if layer_name:
            target_gdf = gpd.read_file(self.file_path, layer=layer_name)
        else:
            target_gdf = gpd.read_file(self.file_path, layer=self.target_value)

        return target_gdf
