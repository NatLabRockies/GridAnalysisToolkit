"""
SimulationFile -> Pydantic model for opening, listing and reading available datasets (Abstract, users must implement concrete versions). Would be good to abstract for databases and apis.

SimulationDataset -> a singular dataset with units and scaling factor.

Simulation -> Multiple SimulationFile object (concrete implementation handled by gat. plugin backend system supported.
handles parallelism. Merges data into a duckdb database as a cache.
)


"""

from pathlib import Path

from pydantic import BaseModel


class SimulationFile(BaseModel):
    path: Path


class SimulationDataset(BaseModel):
    h5_path: str
    scale: int | float = 1
    unit: str  # TODO this should be a properly supported enum.


class SimulationDatasetGroup(BaseModel):
    name: str
    datasets: list[SimulationDataset]


class Simulation(BaseModel):
    files: Path
    datasets: dict[str, list[SimulationDataset | SimulationDatasetGroup]] | None

    # this should be an abstract method that developers are required to define
    @classmethod
    def from_files(cls) -> "Simulation":
        return

    # abstract
    def get(self, key, start, end):
        return

    # abstract
    def list(self):
        """lists the available"""

        return
