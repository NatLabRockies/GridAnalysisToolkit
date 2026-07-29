# Sienna

Sienna stores system level data in a JSON file and timeseries data in h5 files that can be in various locations.

Timeseries data is often stored with the headers in a separate location than the data. Timestamps are built by viewing attributes of either UC or emulation_model.

**H5 dataset example:**

dataset -> "ActivePowerTimeSeriesParameter__StandardLoad"

headers -> "ActivePowerTimeSeriesParameter__StandardLoad__columns"


**SiennaSimulationParser**: Parses singular h5 files. Lists available datasets and returns formatted timeseries dataframes based on desired dataset key or h5 path.

For multi-file aggregation, use the generic `SimulationAggregator` parameterized with `parser_class=SiennaSimulationParser` (parallel loading enabled by default). The previous `SiennaSimulationAggregator` was removed in Phase 10.

**SiennaSystemParser**: Parses the Sienna System JSON file. Lists available datasets by component and returns formatted dataframes based on component type desired.


```{eval-rst}
.. automodule:: gat.datahelpers.sienna
    :members:

```