class gatConfig(object):
    """
    A configuration class used across scenario objects and quickplots.
    Updating the fields of this object impacts how dataframe columns are named,
    how missing load columns are calculated, and how load is named in the plots.

    The configuration also include **self.curtailable_tech**. Adding or removing items
    from this list will determined which generation types are used in the curtailment calculation.
    One should use names in the simplified technology mapping and not the internal generation type defined
    in the power system model.


    :self.native_load_alias: The load excluding any storage charging. Defaults to 'Native Demand'

    :self.total_load_alias: Defaults to 'Total Demand'

    :self.net_load_alias: The total demand minus variable renewable technology (curtailable tech). Defaults to 'Net Demand'

    :self.unserved_energy_alias: Defaults to 'Unserved Energy'

    :self.storage_load_alias: Defaults to 'Storage Demand'

    :self.curtailable_tech: Simplified technology names used in the curtailment calculation. Defaults to ['Land-based Wind','Offshore Wind', 'PV','dPV', 'VRE']

    :self.default_font: The default font used in the plots. Defaults to 'Arial'

    """

    def __init__(self) -> None:

        self.native_load_alias = "Native Demand"

        # Name of column to represent total load including charging.
        self.total_load_alias = "Total Demand"

        # Name to use for the generated Net Load = Total Load - VRE
        self.net_load_alias = "Net Demand"

        # Unserved Energy
        self.unserved_energy_alias = "Unserved Energy"

        self.storage_load_alias = "Storage Demand"

        # list of Variable renewable energies.
        # should be able to update
        self.curtailable_tech = ["Land-based Wind", "Offshore Wind", "PV", "dPV", "VRE"]

        # Plotting properties
        self.default_font = "Arial"

    @property
    def load_columns(self):
        return [self.native_load_alias, self.total_load_alias, self.net_load_alias]


config = gatConfig()
