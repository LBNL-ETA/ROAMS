import os

from unittest import TestCase

import pandas as pd
import numpy as np

from roams.production.input import CoveredProductionData
from roams.conf import TEST_DIR
from roams.utils import CH4_DENSITY_KGM3, CH4_DENSITY_KGCUFT

COVERED_PROD_FILE = os.path.join(TEST_DIR,"_test_coveredprod_data.csv")

# Create a dummy plume table (one plume per source)
DUMMY_COVEREDPROD_DATA = pd.DataFrame(
    {
        "estimated productivity (mscf/day)":[1,2,3,4,5,6,7,8,9,10.],
    }
)

# Write dummy source data
DUMMY_COVEREDPROD_DATA.to_csv(COVERED_PROD_FILE,index=False)

class CoveredProductionDataTests(TestCase):

    def test_common_prod_unit_no_change(self):
        """
        Assert that when the input units are the same as the common production 
        units, the values in the table match the volumetric NG output.
        """        
        coveredProdData = CoveredProductionData(
            COVERED_PROD_FILE,
            "estimated productivity (mscf/day)",
            "mscf/day",
        )
        np.testing.assert_equal(
            coveredProdData.ng_production_volumetric,
            DUMMY_COVEREDPROD_DATA["estimated productivity (mscf/day)"].values
        )
    
    def test_ch4_frac_application(self):
        """
        Assert that the argument `frac_production_ch4` is properly being 
        treated as a volumetric fraction of CH4 in produced NG.
        """        
        # If the volumetric fraction of CH4 is 0 -> should be 0 across the board
        coveredProdData = CoveredProductionData(
            COVERED_PROD_FILE,
            "estimated productivity (mscf/day)",
            "mscf/day",
            frac_production_ch4=0
        )
        np.testing.assert_equal(
            coveredProdData.ch4_production_volumetric,
            DUMMY_COVEREDPROD_DATA["estimated productivity (mscf/day)"].values*0
        )
        
        # If volumetric fraction is 1 -> should be identical to given values.
        coveredProdData = CoveredProductionData(
            COVERED_PROD_FILE,
            "estimated productivity (mscf/day)",
            "mscf/day",
            frac_production_ch4=1.
        )
        np.testing.assert_equal(
            coveredProdData.ch4_production_volumetric,
            DUMMY_COVEREDPROD_DATA["estimated productivity (mscf/day)"].values
        )

    def test_incorrect_ch4frac(self):
        """
        Assert that incorrect values of CH4 fraction (below 0, above 1, not 
        numeric) result in ValueError.
        """
        with self.assertRaises(ValueError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "estimated productivity (mscf/day)",
                "mscf/day",
                frac_production_ch4=1.01,
            )
        
        with self.assertRaises(ValueError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "estimated productivity (mscf/day)",
                "mscf/day",
                frac_production_ch4=-0.01,
            )
        
        with self.assertRaises(ValueError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "estimated productivity (mscf/day)",
                "mscf/day",
                frac_production_ch4=None,
            )
        
        with self.assertRaises(ValueError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "estimated productivity (mscf/day)",
                "mscf/day",
                frac_production_ch4="0.5",
            )
        
        with self.assertRaises(ValueError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "estimated productivity (mscf/day)",
                "mscf/day",
                frac_production_ch4="50%",
            )

    def test_missing_inputs(self):
        """
        Assert that incorrectly specified production column name or unit 
        raises an Error.
        """
        with self.assertRaises(KeyError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "FAKE COLUMN NAME",
                "mscf/day",
            )
        
        with self.assertRaises(ValueError):
            coveredProdData = CoveredProductionData(
                COVERED_PROD_FILE,
                "estimated productivity (mscf/day)",
                None,
            )

    def test_ch4_mass_conversion(self):
        """
        Assert that the CH4 mass conversion is correct
        """
        # If 100% of NG is CH4, assert the mass of CH4 in 
        # covered NG production is essentially [covered production]*[density]
        coveredProdData = CoveredProductionData(
            COVERED_PROD_FILE,
            "estimated productivity (mscf/day)",
            "mscf/day",
            frac_production_ch4=1.,
        )
        np.testing.assert_array_equal(
            # will be returned in COMMON_EMISSIONS_UNITS (kg/h)
            coveredProdData.ch4_production_mass, 

            # mscf/day x [1000 cuft/mscf] x [.0186 kg/cuft] * [1 day / 24h]
            DUMMY_COVEREDPROD_DATA["estimated productivity (mscf/day)"]*1000*CH4_DENSITY_KGCUFT/24
        )
        
        # If 100% of NG is CH4, assert the mass of CH4 in 
        # covered NG production is essentially [covered production]*[density]
        coveredProdData = CoveredProductionData(
            COVERED_PROD_FILE,
            "estimated productivity (mscf/day)",
            "mscf/h",
            frac_production_ch4=1.,
        )
        np.testing.assert_array_equal(
            # will be returned in COMMON_EMISSIONS_UNITS (kg/h)
            coveredProdData.ch4_production_mass, 

            # mscf/h x [1000 cuft/mscf] x [.0186 kg/cuft]
            DUMMY_COVEREDPROD_DATA["estimated productivity (mscf/day)"]*1000*CH4_DENSITY_KGCUFT
        )
        
        # If 100% of NG is CH4, assert the mass of CH4 in 
        # covered NG production is essentially [covered production]*[density]
        coveredProdData = CoveredProductionData(
            COVERED_PROD_FILE,
            "estimated productivity (mscf/day)",
            "m3/h",
            frac_production_ch4=1.,
        )
        np.testing.assert_array_equal(
            # will be returned in COMMON_EMISSIONS_UNITS (kg/h)
            coveredProdData.ch4_production_mass, 

            # m3/h x x [.657 kg/m3]
            DUMMY_COVEREDPROD_DATA["estimated productivity (mscf/day)"]*CH4_DENSITY_KGM3
        )

if __name__=="__main__":
    import unittest
    unittest.main()