import logging

import pandas as pd
import numpy as np

from roams.constants import COMMON_EMISSIONS_UNITS, COMMON_PRODUCTION_UNITS
from roams.utils import convert_units, ch4_volume_to_mass

class CoveredProductionDistData:
    """
    This is a class intended to be the go-between standing between the 
    estimated covered productivity of assets covered by the aerial survey, and
    the ROAMS model that will make use of it.
    
    Like other input classes, it will use a fixed set of output units to 
    report relevant quantities to the ROAMS model.

    Args:
        covered_production_dist_file (str): 
            Path to a csv file that contains a list of well-level production 
            values whose distribution is expected to be the same as that for 
            the covered region.

        covered_production_dist_col (str): 
            The name of the column in `covered_production_dist_file` that 
            holds the estimates of emissions from a well in the covered study 
            region.

        covered_production_dist_unit (str): 
            The units of the emissions rate described in 
            `covered_production_dist_col`.
            E.g. "mscf/day".
        
        total_covered_ngprod_mcfd (float, int): 
            An estimate for total production in the surveyed region ("covered 
            production"), in terms of mcf of natural gas per day.
            E.g. 12345.67

        frac_production_ch4 (float):
            The fraction of NG that is CH4.
            E.g. 0.9 

        loglevel (int, optional):
            The level to which information should be logged as this code 
            is called.
            Defaults to logging.INFO

    Raises:
        ValueError:
            When the given `frac_production_ch4` is not a number that's at 
            least 0 and at most 1.
        
        KeyError:
            When the `covered_production_col` isn't in the provided data.
        
        ValueError:
            When the user didn't provide units of covered production.
    """
    def __init__(
        self,
        covered_production_dist_file : str,
        covered_production_dist_col : str,
        covered_production_dist_unit : str,
        frac_production_ch4 : float,
        loglevel = logging.INFO,
    ):
        self.log = logging.getLogger("roams.production.input.CoveredProductionData")
        self.log.setLevel(loglevel)

        self.covered_production_dist_file = covered_production_dist_file

        self.log.info(
            f"Loading simulated emissions of production infrastructure from {covered_production_dist_file}"
        )
        self._raw_covered_prod_dist = pd.read_csv(self.covered_production_dist_file)
        self.log.debug(f"Raw simulated data has shape = {self._raw_covered_prod_dist.shape}")

        if not isinstance(frac_production_ch4,(float,int)) or (not 0<=frac_production_ch4<=1):
            raise ValueError(
                f"{frac_production_ch4 = } should be a value from 0 through 1."
            )
        
        self.frac_production_ch4 = frac_production_ch4
        self.log.info(
            f"Assuming that {(100*frac_production_ch4):.2f}% of produced "
            "natural gas is CH4."
        )
        
        if covered_production_dist_col not in self._raw_covered_prod_dist.columns:
            raise KeyError(
                f"{covered_production_dist_col = } is not in the covered production table. "
                "The only columns available are: "
                f"`{'`, `'.join(self._raw_covered_prod_dist.columns)}`."
            )
        self.covered_production_dist_col = covered_production_dist_col
        
        if covered_production_dist_unit is None:
            raise ValueError(
                f"You have to provide units for {covered_production_dist_unit = } in the "
                "covered production table input."
            )
        self.covered_production_dist_unit = covered_production_dist_unit

    @property
    def ng_production_dist_volumetric(self) -> np.ndarray:
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
            self._raw_covered_prod_dist[self.covered_production_dist_col].values,
            self.covered_production_dist_unit,
            COMMON_PRODUCTION_UNITS
        )
    
    @property
    def ch4_production_dist_volumetric(self) -> np.ndarray:
        """
        Return the estimate of the CH4 production distribution provided in 
        the underlying table, in units of COMMON_PRODUCTION_UNITS, 
        which is a volumetric production rate.

        Returns:
            np.ndarray:
                The estimated volumetric rate of production of CH4 for 
                wells in the covered region, in units of 
                COMMON_PRODUCTION_UNITS. The order of observations will stay 
                the same as in the input data.
        """
        return self.ng_production_dist_volumetric * self.frac_production_ch4

    @property
    def ch4_production_dist_mass(self) -> np.ndarray:
        """
        Return the estimate of the CH4 production distribution provided in 
        the underlying table, in units of COMMON_EMISSIONS_UNITS.

        The mass units are taken from COMMON_EMISSIONS_UNITS.

        Returns:
            np.ndarray:
                The estimated volumetric rate of production of CH4 for 
                wells in the covered region, in units of 
                COMMON_PRODUCTION_UNITS. The order of observations will stay 
                the same as in the input data.
        """
        return ch4_volume_to_mass(
            self.ch4_production_dist_volumetric,
            COMMON_PRODUCTION_UNITS,
            COMMON_EMISSIONS_UNITS
        )