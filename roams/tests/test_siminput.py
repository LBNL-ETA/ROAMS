import os

from unittest import TestCase

import pandas as pd
import numpy as np

from roams.simulated.input import SimulatedProductionAssetData
from roams.constants import COMMON_EMISSIONS_UNITS, COMMON_PRODUCTION_UNITS
from roams.conf import TEST_DIR

SIM_FILE = os.path.join(TEST_DIR,"_test_sim_data.csv")

# Create a dummy plume table (one plume per source)
DUMMY_SIM_DATA = pd.DataFrame(
    {
        "emissions":[1,2,3,4,5],
        "production":[20,30,40,50,60],
    }
)

# Write dummy source data
DUMMY_SIM_DATA.to_csv(SIM_FILE,index=False)

class AerialSurveyDataTests(TestCase):

    def test_common_unit_no_change(self):
        """
        Assert that when the input units are the same as the common units, 
        the values coming out of the attribute entrypoints are identical to 
        those in the raw data.
        """        
        sim_results = SimulatedProductionAssetData(
            SIM_FILE,
            emissions_col="emissions",
            emissions_units=COMMON_EMISSIONS_UNITS,
            production_col="production",
            production_units=COMMON_PRODUCTION_UNITS,
        )
        np.testing.assert_equal(
            sim_results.simulated_emissions,
            DUMMY_SIM_DATA["emissions"].values
        )
        np.testing.assert_equal(
            sim_results.simulated_production,
            DUMMY_SIM_DATA["production"].values
        )
    
    def test_mscf_per_h(self):
        """
        Assert that when the production values are in mscf/hr instead of the 
        default mscf/d, production coming out of the entry point are 24x.
        """        
        sim_results = SimulatedProductionAssetData(
            SIM_FILE,
            emissions_col="emissions",
            emissions_units=COMMON_EMISSIONS_UNITS,
            production_col="production",
            production_units="mscf/h",
        )
        # In this case emissions should be unchanged
        np.testing.assert_equal(
            sim_results.simulated_emissions,
            DUMMY_SIM_DATA["emissions"].values
        )

        # ... but production should be turned into mscf/d
        # by 24 mscf/d = 1 mscf/h
        np.testing.assert_equal(
            sim_results.simulated_production,
            DUMMY_SIM_DATA["production"].values*24
        )
    
    def test_missing_col_errors(self):
        """
        Assert that mis-specification of the emissions column produces a 
        KeyError, as well as mis-specification of the production column.
        """
        with self.assertRaises(KeyError):
            sim_results = SimulatedProductionAssetData(
                SIM_FILE,
                emissions_col="THIS COLUMN DOESNT EXIST",
                emissions_units=COMMON_EMISSIONS_UNITS,
                production_col="production",
                production_units=COMMON_PRODUCTION_UNITS,
            )

        with self.assertRaises(KeyError):
            sim_results = SimulatedProductionAssetData(
                SIM_FILE,
                emissions_col="emissions",
                emissions_units=COMMON_EMISSIONS_UNITS,
                production_col="THIS COLUMN DOESNT EXIST",
                production_units=COMMON_PRODUCTION_UNITS,
            )

    def test_consistent_input_errors(self):
        """
        Assert that inconsistent inputs produce ValueErrors.
        """
        with self.assertRaises(ValueError):
            # When emissions column is given, unit has to be given
            # (this should raise an error)
            sim_results = SimulatedProductionAssetData(
                SIM_FILE,
                emissions_col="emissions",
                emissions_units=None,
                production_col="production",
                production_units=COMMON_PRODUCTION_UNITS,
            )
        
        with self.assertRaises(ValueError):
            # When production column is given and exists in the data, 
            # the unit has to be specified
            sim_results = SimulatedProductionAssetData(
                SIM_FILE,
                emissions_col="emissions",
                emissions_units=COMMON_EMISSIONS_UNITS,
                production_col="production",
                production_units=None,
            )

if __name__=="__main__":
    import unittest
    unittest.main()