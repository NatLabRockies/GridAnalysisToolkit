"""
This file is for the base Scenario class and should not be directly imported.

This class is used by model specific implementations which gain the common functions once they implement the core abstract methods.



Handle a multitude of mappings

* mapping nodes to geographically defined areas
* overriding generators technologies to custom defined ones. (Not to be confused with display groups)
* Adding area -> area mappings. (e.g. county->state). These should be clean mappings without participation factors.
* Handle multiple technology mapping levels from specific to general. (e.g. generator-> Gas-CC/Gas-CT or generator-> Gas/Thermal, gen->Solar/wind vs gen->renewable)


Base class should be appendable in a way that multiple node->area mappings can be applied either through geopandas, shapefile, flat file etc.

Base class provides a list of

"""