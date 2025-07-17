import logging

import pandas as pd
import numpy as np

from roams.constants import COMMON_EMISSIONS_UNITS, COMMON_PRODUCTION_UNITS, ALVAREZ_ET_AL_CH4_FRAC
from roams.utils import convert_units, ch4_volume_to_mass

class CoveredProductionData:
    """
    This is a class intended to be the go-between standing between the 
    estimated covered productivity of assets covered by the aerial survey, and
    the ROAMS model that will make use of it.
    
    Like other input classes, it will use a fixed set of output units to 
    report relevant quantities to the ROAMS model.

    Args:
        covered_production_file (str): 
            Path to a csv file that contains simulated emissions, and perhaps 
            production, of a given region of interest.

        covered_production_col (str): 
            The name of the column in `covered_production_file` that holds the 
            estimates of emissions from a well in the covered study region.

        covered_production_unit (str): 
            The units of the emissions rate described in `covered_production_col`.
            E.g. "mscf/day".

        frac_production_ch4 (float, optional):
            The fraction of NG that is CH4.
            Defaults to ALVAREZ_ET_AL_CH4_FRAC.

        loglevel (int, optional):
            The level to which information should be logged as this code 
            is called.
            Defaults to logging.INFO
    """
    def __init__(
        self,
        covered_production_file : str,
        covered_production_col : str,
        covered_production_unit : str,
        frac_production_ch4 : float = ALVAREZ_ET_AL_CH4_FRAC,
        loglevel = logging.INFO,
    ):
        self.log = logging.getLogger("roams.production.input.CoveredProductionData")
        self.log.setLevel(loglevel)

        self.covered_production_file = covered_production_file

        self.log.info(
            f"Loading simulated emissions of production infrastructure from {covered_production_file}"
        )
        self._raw_covered_prod = pd.read_csv(self.covered_production_file)
        self.log.debug(f"Raw simulated data has shape = {self._raw_covered_prod.shape}")

        self.frac_production_ch4 = frac_production_ch4
        self.log.info(
            f"Assuming that {(100*frac_production_ch4):.2f}% of produced "
            "natural gas is CH4."
        )
        
        if covered_production_col not in self._raw_covered_prod.columns:
            raise KeyError(
                f"{covered_production_col = } is not in the covered production table. "
                "The only columns available are: "
                f"`{'`, `'.join(self._raw_covered_prod.columns)}`."
            )
        self.covered_production_col = covered_production_col
        
        if covered_production_unit is None:
            raise ValueError(
                f"You have to provide units for {covered_production_unit = } in the "
                "covered production table input."
            )
        self.covered_production_unit = covered_production_unit

    @property
    def ng_production_volumetric(self) -> np.ndarray:
        """
        Return covered well NG production provided in the underlying table, 
        in units of COMMON_PRODUCTION_UNITS, which is a volumetric production 
        rate.

        Returns:
            np.ndarray:
                The estimated volumetric rate of production of NG for wells 
                in the covered region, in units of COMMON_PRODUCTION_UNITS. 
                The order of observations will stay the same as in the input 
                data.
        """
        return convert_units(
            self._raw_covered_prod[self.covered_production_col].values,
            self.covered_production_unit,
            COMMON_PRODUCTION_UNITS
        )
    
    @property
    def ch4_production_volumetric(self) -> np.ndarray:
        """
        Return covered well CH4 production provided in the underlying table, 
        in units of COMMON_PRODUCTION_UNITS, which is a volumetric production 
        rate.

        Returns:
            np.ndarray:
                The estimated volumetric rate of production of CH4 for 
                wells in the covered region, in units of 
                COMMON_PRODUCTION_UNITS. The order of observations will stay 
                the same as in the input data.
        """
        return self.ng_production_volumetric * self.frac_production_ch4

    @property
    def ch4_production_mass(self) -> np.ndarray:
        """
        Return covered well CH4 production provided in the underlying table, 
        in units of COMMON_EMISSIONS_UNITS

        The mass units are taken from COMMON_EMISSIONS_UNITS.

        Returns:
            np.ndarray:
                The estimated volumetric rate of production of CH4 for 
                wells in the covered region, in units of 
                COMMON_PRODUCTION_UNITS. The order of observations will stay 
                the same as in the input data.
        """
        return ch4_volume_to_mass(
            self.ch4_production_volumetric,
            self.covered_production_unit,
            COMMON_EMISSIONS_UNITS
        )