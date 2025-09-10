import logging

import pandas as pd
import numpy as np

from roams.constants import COMMON_EMISSIONS_UNITS, COMMON_PRODUCTION_UNITS
from roams.utils import convert_units

class SimulatedProductionAssetData:
    """
    This is a class intended to be the go-between standing between the 
    simulated estimates of emissions and production in a given basin, and 
    the ROAMS model that will do something with it. 
    
    Like other input classes, it will use a fixed set of output units to 
    report relevant quantities to the ROAMS model.

    A column of estimated production is required if the simulated data is 
    intended to be stratified.

    Args:
        simulated_results (str): 
            Path to a csv file that contains simulated emissions, and perhaps 
            production, of a given region of interest.

        emissions_col (str): 
            The name of the column in `simulated_results` that holds the 
            estimates of emissions from a well in the covered study region.

        emissions_units (str): 
            The units of the emissions rate described in `emissions_col`.
            E.g. "kgh".

        production_col (str, optional): 
            The name of the column in `simulated_results` that holds the 
            estimates of production from a well in the covered study region.
            If not specified, the code will later break if this ends up 
            being required for stratification or any other analysis.
            Defaults to None.
        
        production_units (str, optional): 
            The units of production described in `production_col`.
            E.g. "mscf/day".
            Defaults to None.

        loglevel (int, optional):
            The level to which information should be logged as this code 
            is called.
            Defaults to logging.INFO
    """
    def __init__(
        self,
        simulated_results : str,
        emissions_col : str,
        emissions_units : str,
        production_col = None,
        production_units = None,
        loglevel = logging.INFO,
    ):
        self.log = logging.getLogger("roams.simulated.input.SimulatedProductionData")
        self.log.setLevel(loglevel)

        self.simulated_results = simulated_results

        self.log.info(
            f"Loading simulated emissions of production infrastructure from {simulated_results}"
        )
        self._raw_sim_data = pd.read_csv(self.simulated_results)
        self.log.debug(f"Raw simulated data has shape = {self._raw_sim_data.shape}")
        
        if emissions_col not in self._raw_sim_data.columns:
            raise KeyError(
                f"{emissions_col = } is not in the simulated results table. "
                "The only columns available are: "
                f"`{'`, `'.join(self._raw_sim_data.columns)}`."
            )
        self.emissions_col = emissions_col
        
        if emissions_units is None:
            raise ValueError(
                f"You have to provide units for {emissions_col = } in the "
                "simulated results table."
            )
        self.emissions_units = emissions_units
        
        if production_col not in self._raw_sim_data.columns and production_col is not None:
            raise KeyError(
                f"{production_col = } is not in the simulated results "
                "table. The only columns available are: "
                f"`{'`, `'.join(self._raw_sim_data.columns)}`."
            )
        
        # It's possible to set the production_col as None here, the implicit 
        # assumption being that the `simulated_production` property will 
        # never be queried.
        self.production_col = production_col

        # Only raise an error with production units if production_col is not None
        if production_units is None and production_col is not None:
            raise ValueError(
                f"You have to provide units for {production_col = } in the "
                "simulated results table if you're providing it."
            )
        
        self.production_units = production_units

    @property
    def simulated_emissions(self) -> np.ndarray:
        """
        Return all simulated emissions in the table, in the common units 
        of emissions used around the codebase.

        Returns:
            np.ndarray:
                The simulated emissions estimates provided in the inputs, 
                converted to COMMON_EMISSIONS_UNITS if possible. The order 
                of observations will stay the same as in the input data.
        """
        return convert_units(
            self._raw_sim_data[self.emissions_col].values,
            self.emissions_units,
            COMMON_EMISSIONS_UNITS
        )
    
    @property
    def simulated_production(self) -> np.ndarray:
        """
        Return all simulated production in the table, in the common units of 
        production used around the codebase.

        Returns:
            np.ndarray:
                The simulated production rate for each simulated well in 
                the input table, converted to common units of production. The 
                order of observations will stay the same as in the input data.

        Raises:
            KeyError:
                When self.production_col is None (meaning it was never 
                provided in the first place).
        """
        if self.production_col is None:
            raise KeyError(
                f"The argument `production_col` was not given to this class, "
                "which it would need to provide production data from the "
                "input table."
            )

        return convert_units(
            self._raw_sim_data[self.production_col].values,
            self.production_units,
            COMMON_PRODUCTION_UNITS
        )