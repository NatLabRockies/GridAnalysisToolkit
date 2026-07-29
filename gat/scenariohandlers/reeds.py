"""
ReEDS Scenario Object  for interfacing with ReEDsScenario across various ReEDS specific CSV files.

Warning: This class is not fully implemented.

@author: Micah Webb
"""

from .base import columns_to_simple, plexos_map_simple, BaseScenario
import warnings
import os
import pandas as pd
from typing import Union, List

class ReEDsScenario(BaseScenario):
    _expected_model_type = 'reeds'

    def _find_solution_files(self, solution_data: Union[str, List[str]], pattern: str = "*") -> List[str]:
        """
        ReEDS-specific implementation that just stores the directory path.

        Parameters:
        -----------
        solution_data : str or list of str
            Path to solution data directory
        pattern : str, optional
            Not used for ReEDS

        Returns:
        --------
        List[str]
            The directory path as a single-item list
        """
        if isinstance(solution_data, str):
            if os.path.isdir(solution_data):
                # If it's the outputs directory or contains one, normalize it
                if os.path.basename(solution_data) == 'outputs':
                    return os.path.normpath(solution_data)
                elif os.path.exists(os.path.join(solution_data, 'outputs')):
                    return os.path.normpath(solution_data)
                else:
                    return os.path.normpath(solution_data)
        elif isinstance(solution_data, list):
            # If it's a list, return the first directory
            for item in solution_data:
                if os.path.isdir(item):
                    return os.path.normpath(item)

        # Return empty list if no valid directory found
        return []

    def __init__(self, simulation_files=None, solve_year=None, config=None, pattern=None,
                 # Deprecated alias — use simulation_files instead
                 solution_data=None,
                 # Alias used by gat.loader for v1 ReedsScenarioConfig.path
                 path=None) -> None:

        """
        Initialize a ReEDsScenario object with configuration and solution data.

        Parameters:
        -----------
        simulation_files : str or list of str
            Path to solution data directory
        solve_year : int, optional
            The year to solve for
        config : ScenarioConfig, optional
            Configuration object for the scenario
        pattern : str, optional
            Not used for ReEDS
        solution_data : str or list of str, optional
            Deprecated. Use ``simulation_files`` instead.
        """
        from ._deprecation import warn_legacy_handler
        warn_legacy_handler(self)
        from .base import _resolve_simulation_files

        # `path` is the v1 alias for `simulation_files`.
        if path is not None and simulation_files is None:
            simulation_files = path
        simulation_files = _resolve_simulation_files(simulation_files, solution_data)

        warnings.warn("The ReEds class is not fully implemented, use with caution.")

        # Create a default config if none provided
        if config is None:

            from gat.models.scenario import ScenarioConfig
            from gat.models.reeds import ReEDsConfig
            config = ScenarioConfig(model_type=self._expected_model_type)
            config.system_path = simulation_files
            config.system_config = ReEDsConfig(solve_year=solve_year)
            self._solution_data = config.system_path
        else:
            self._solution_data = config.system_path

       # Generate mappings
        self._tech_map = self.generator_technology_map
        self._tech_simple = plexos_map_simple


        # Set up technology mappings
        if len(config.technology_mappings) > 0:
            print("updating tech simple")
            self._tech_simple = {model_name: config.display_group for model_name, config in config.technology_mappings.items()}
        elif self._tech_map:
            print("initializing config technologies")
            config.init_technologies(plexos_map_simple)

        # Call parent initialization to find directory and set up config
        super().__init__(
            simulation_files=simulation_files,
            config=config,
            tech_map=self._tech_map

        )


        # If solution data ends with /outputs, it needs to be reset up one level
        if self._solution_data and os.path.basename(self._solution_data) == 'outputs':
            self._solution_data = os.path.dirname(self._solution_data)

        # Set up year information
        self._weather_year = 2012  # TODO determine if this is still needed.
        self._all_solve_years = self.list_solve_years() if self._solution_data else []
        self._solve_year_value = None
        self.solve_year = self.config.system_config.solve_year


        # Get area mappings from data
        if self._solution_data:
            gen_curt = self.get_gen_and_curtailment()
            ent_map = {col: col for col in gen_curt.columns.get_level_values(level='Area').unique()}
            self._area_map = ent_map
        else:
            self._area_map = {}


    def _find_solution_files(self, solution_data: Union[str, List[str]], pattern: str = "*") -> List[str]:
        """
        ReEDS-specific implementation that just stores the directory path.

        Parameters:
        -----------
        solution_data : str or list of str
            Path to solution data directory
        pattern : str, optional
            Not used for ReEDS

        Returns:
        --------
        List[str]
            The directory path as a single-item list
        """
        if isinstance(solution_data, str):
            if os.path.isdir(solution_data):
                # If it's the outputs directory or contains one, normalize it
                if os.path.basename(solution_data) == 'outputs':
                    return os.path.normpath(solution_data)
                elif os.path.exists(os.path.join(solution_data, 'outputs')):
                    return os.path.normpath(solution_data)
                else:
                    return os.path.normpath(solution_data)
        elif isinstance(solution_data, list):
            # If it's a list, return the first directory
            for item in solution_data:
                if os.path.isdir(item):
                    return os.path.normpath(item)

        # Return empty list if no valid directory found
        return []
    @property
    def solve_year(self):
        return self._solve_year_value

    @solve_year.setter
    def solve_year(self, solve_year: int):

        if solve_year not in self._all_solve_years:
            warnings.warn(f"""{solve_year} not available,
                          defaulting to {self._all_solve_years[0]},
                          to change use one of the following {self._all_solve_years}""")
            self._solve_year_value = self._all_solve_years[0]
        else:
            self._solve_year_value = solve_year

    def list_solve_years(self):
        df = pd.read_csv(f'{self._solution_data}/outputs/gen_ivrt.csv')
        return df['t'].unique().tolist()

    @property
    def generator_technology_map(self):
        df = pd.read_csv(f'{self._solution_data}/outputs/gen_ivrt.csv')
        generator_names = df['i'].unique()

        # only take the technology name up to the first '_'
        return {g:g.split('_')[0] for g in generator_names}

    def get_generation(self):
        return NotImplemented

    def get_availability(self):
        return NotImplemented

    def set_area_map(self, area_map: str ) -> None:
        self._area_map = area_map.lower()

    def get_production_cost(self):
        return NotImplemented

    def get_storage_charging(self):
        return NotImplemented

    def get_generation_capacity(self)->pd.DataFrame:
        """
        **ReEDS input file cap_ivrt.csv**

        :returns: dataframe of generator capacities by technology and area
        """

        df = pd.read_csv(f'{self._solution_data}/outputs/cap_ivrt.csv')

        df = df.pivot_table(index=['t','r'], columns='i', values='Value', aggfunc='sum', fill_value=0.0).loc[self.solve_year]

        new_columns = columns_to_simple(df.columns, self._tech_simple)

        df.columns = pd.MultiIndex.from_tuples(new_columns)

        df3 = df.T.groupby(level=0).sum().T
        df3.columns.name = 'Technology'
        df3.index.name = 'Area'
        if self._area_map:
            df3.index = [self._area_map[ix] for ix in df3.index]
            df3.index.name='Area'
            return df3.groupby(level='Area').sum()
        else:
            return df3

    def get_line_flow():
        return NotImplemented
    def get_unserved():
        return NotImplemented

    def get_load(self)->pd.DataFrame:
        """
        **ReEDS Dataset: outputs/load_cat.csv**

        :load types: end_use, h2_prod, dist_loss, trans_loss

        :returns: Load by type and area.
        """

        file_path = os.path.join(self._solution_data,'outputs/load_cat.csv')
        df = pd.read_csv(file_path)
        df = df[df.loadtype.isin({'end_use','h2_prod','dist_loss','trans_loss'})]
        df['Timestamp'] = pd.to_datetime(df['t'].apply(lambda x: f'01-01-{x}'))

        df = df.set_index('t').loc[self.solve_year]
        ldf = df.pivot_table(index='Timestamp', columns=['r','loadtype'], values='Value', fill_value=0.0)
        ldf.columns.names=['Area', 'Technology']
        return ldf



    def get_area_dispatch(self)->pd.DataFrame:

        """
        :returns: Timeseries dataframe of generation, load and curtailment by technology and area.
        """
        dispatch = self.get_gen_and_curtailment()


        dispatch.columns = pd.MultiIndex.from_tuples([
            (
                self._area_map[col[0]],
                col[1]
            ) for col in dispatch.columns
        ], names=['Area', 'Technology'])

        return dispatch.T.groupby(level=[0,1]).sum().T

    def get_ivrt(self, file_name, analysis_year)->pd.DataFrame:

        """
        Parser like function to read various ivrt files.

        :param file_name: _ivrt.csv

        :param analysis_year: The year for the future generation capacity

        :returns: timeseries dataframe dataset formatted for the input analysis year.
        """

        df = pd.read_csv(f'{self._solution_data}/outputs/{file_name}')
        df = df[df.t == analysis_year]
        df['reeds_year'] = pd.to_datetime(df['t'].apply(lambda x: f'01-01-{x}'))

        if 'allh' in df.columns:
            df['delta'] = df['allh'].apply(lambda x: pd.Timedelta(days = int(x.split('h')[0].split('d')[1]) , hours=int(x.split('h')[1]) ))
            df['Timestamp'] = df['reeds_year'] + df['delta']
        else:
            df['Timestamp'] = df['reeds_year']

        return df

    def get_generators_tech(self, file='gen_ivrt.csv')->pd.DataFrame:

        """
        **ReEDS Dataset: gen_ivrt.csv**

        :returns: timeseries dataframe of generation by technology.
        """

        df = self.get_ivrt(file, self.solve_year)
        df['Technology'] = [col[0] for col in columns_to_simple(df['i'], self._tech_simple)]
        df['Area'] = df['r']

        return df.pivot_table(index='Timestamp', columns=['Area','Technology'], values='Value', aggfunc='sum', fill_value=0.0)

    def get_availability_tech(self)->pd.DataFrame:

        df = self.get_ivrt('cap_avail.csv', self.solve_year)
        df['Technology'] = [col[0] for col in columns_to_simple(df['i'], self._tech_simple)]
        df['Area'] = df['r']

        return df

    def get_regional_curtailment(self, file='curt_ann.csv')->pd.DataFrame:
        """
        **ReEDS Dataset: curt_ann.csv**

        :returns: Timeseries Dataframe of regional curtailment.
        """

        df = self.get_ivrt(file, self.solve_year)
        df['Area'] = df['r']

        return df.pivot_table(index='Timestamp', columns=['Area'], values='Value', aggfunc='sum', fill_value=0.0)

    def get_gen_and_curtailment(self)->pd.DataFrame:
        """
        Aggregates and combines generation and curtailment from get_generators_tech() and get_regional_curtailment()

        :returns: Timeseries dataframe of Generation by Technology and Area and Total Curtailment by Area.

        """

        gen_tech = self.get_generators_tech()

        reg_curt = self.get_regional_curtailment()

        reg_curt.columns = pd.MultiIndex.from_tuples([(col, 'Curtailment') for col in reg_curt.columns], names=['Area', 'Technology'])

        return pd.merge(gen_tech, reg_curt, left_index=True, right_index=True)


    def get_area_load(self)->pd.DataFrame:

        """
        :returns: Timeseries dataframe of load aggregated by area/region.

        """

        df = self.get_load()

        df.columns = pd.MultiIndex.from_tuples([
            (self._area_map[col[0]], col[1]) for col in df.columns
        ], names=['Area', 'Technology'])

        return df

    def get_installed_capacity(self)->pd.DataFrame:
        """
        **ReEDS dataset: cap_ivrt.csv**

        :returns: Dataframe of installed generation capacity by technology and Area/region.

        """

        df = pd.read_csv(f'{self._solution_data}/outputs/cap_ivrt.csv')

        df = df.pivot_table(index=['t','r'], columns='i', values='Value', aggfunc='sum', fill_value=0.0).loc[self.solve_year]

        new_columns = columns_to_simple(df.columns, self._tech_simple)

        df.columns = pd.MultiIndex.from_tuples(new_columns)

        df3 = df.T.groupby(level=0).sum().T
        df3.columns.name = 'Technology'
        df3.index.name = 'Area'
        if self._area_map:
            df3.index = [self._area_map[ix] for ix in df3.index]
            return df3.groupby(level=0).sum()
        else:
            return df3


    def get_line_flow(self):
        return NotImplemented

