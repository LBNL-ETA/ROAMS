import os

from unittest import TestCase

import pandas as pd
import numpy as np

from roams.conf import TEST_DIR
from roams.midstream_ghgi.input import GHGIDataInput

STATE_GHGI_FILENAME = os.path.join(TEST_DIR,"_state_ghgi.csv")
STATE_PROD_FILENAME = os.path.join(TEST_DIR,"_state_prod.csv")
NATNL_PROD_FILENAME = os.path.join(TEST_DIR,"_natl_prod.csv")
NATNL_NGPROD_GHGI_FILENAME = os.path.join(TEST_DIR,"_natl_ngprodch4.csv")
NATNL_NGPROD_UNCERT_GHGI_FILENAME = os.path.join(TEST_DIR,"_natl_nguncertch4.csv")
NATNL_PETPROD_GHGI_FILENAME = os.path.join(TEST_DIR,"_natl_petprodch4.csv")

STATE_GHGI = pd.DataFrame({"GHGI Gas":["Methane","Carbon Dioxide"],"1900":[300,100],"1901":[301,101]})
STATE_PROD = pd.DataFrame({"GHGI State":["State1","State2"],"1900":[20,50],"1901":[20,50]})
NATNL_PROD = pd.DataFrame({"Oil":[20,50],"Gas":[20,50],"Enverus production month":["August 1, 1900","August 1, 1901"]})
NATNL_NGPROD_GHGI = pd.DataFrame(
    [
        ["","Gathering and Boosting","800","800"],
        ["","Transmission and Storage","2,000","2,000"],
        ["","Processing","800","800"],
        ["","Total","3,600","3,600"],
    ],
    columns = pd.MultiIndex.from_tuples([("","",""),("","","Stage"),("","","1900"),("","","1901")])
)
NATNL_NGPROD_UNCERT_GHGI = pd.DataFrame( # 8 columns skip 4 rows
    [
        ["","Natural Gas","CH4","0.0","0.0","0.0","-10%","10%"],
        ["","Natural Gas","CO2","0.0","0.0","0.0","-10%","10%"],
        ["","Natural Gas","N2O","0.0","0.0","0.0","-10%","10%"],
    ],
    columns = pd.MultiIndex.from_tuples(
        [
            ("",)*6,("",)*6,("",)*6,("",)*6, # 4 rows to skip
            ("",)*4 + ("Lower","Boundb"),
            ("",)*4 + ("Upper","Boundb"),
            ("",)*4 + ("Lower","Boundb"),
            ("",)*4 + ("Upper","Boundb"),
        ]
    )
)
NATNL_PETPROD_GHGI = pd.DataFrame(
    [
        ["","Total","3,600","3,600"],
    ],
    columns = pd.MultiIndex.from_tuples([("","",""),("","","Activity"),("","","1900"),("","","1901")])
)

STATE_GHGI.to_csv(STATE_GHGI_FILENAME,index=False)
STATE_PROD.to_csv(STATE_PROD_FILENAME,index=False)
NATNL_PROD.to_csv(NATNL_PROD_FILENAME,index=False)
NATNL_NGPROD_GHGI.to_csv(NATNL_NGPROD_GHGI_FILENAME,index=False)
NATNL_NGPROD_UNCERT_GHGI.to_csv(NATNL_NGPROD_UNCERT_GHGI_FILENAME,index=False)
NATNL_PETPROD_GHGI.to_csv(NATNL_PETPROD_GHGI_FILENAME,index=False)

class GHGIDataInputTests(TestCase):

    def test_assert_ValueError(self):
        """
        Assert that fractional CH4 content or midstream emissions will 
        produce ValueErrors when making the class.
        """
        with self.assertRaises(ValueError):
            g = GHGIDataInput(
                STATE_GHGI_FILENAME,
                STATE_PROD_FILENAME,
                NATNL_PROD_FILENAME,
                NATNL_NGPROD_GHGI_FILENAME,
                NATNL_NGPROD_UNCERT_GHGI_FILENAME,
                NATNL_PETPROD_GHGI_FILENAME,
                1900,
                "State1",
                1.5, # Too large
                .5, # Fine
            )
        
        with self.assertRaises(ValueError):
            g = GHGIDataInput(
                STATE_GHGI_FILENAME,
                STATE_PROD_FILENAME,
                NATNL_PROD_FILENAME,
                NATNL_NGPROD_GHGI_FILENAME,
                NATNL_NGPROD_UNCERT_GHGI_FILENAME,
                NATNL_PETPROD_GHGI_FILENAME,
                1900,
                "State1",
                -.1, # Too small
                .5, # Fine
            )
        
        with self.assertRaises(ValueError):
            g = GHGIDataInput(
                STATE_GHGI_FILENAME,
                STATE_PROD_FILENAME,
                NATNL_PROD_FILENAME,
                NATNL_NGPROD_GHGI_FILENAME,
                NATNL_NGPROD_UNCERT_GHGI_FILENAME,
                NATNL_PETPROD_GHGI_FILENAME,
                1900,
                "State1",
                .5, # Fine
                1.5, # Too large
            )
        
        with self.assertRaises(ValueError):
            g = GHGIDataInput(
                STATE_GHGI_FILENAME,
                STATE_PROD_FILENAME,
                NATNL_PROD_FILENAME,
                NATNL_NGPROD_GHGI_FILENAME,
                NATNL_NGPROD_UNCERT_GHGI_FILENAME,
                NATNL_PETPROD_GHGI_FILENAME,
                1900,
                "State1",
                .5, # Fine
                -.1, # Too small
            )

    def test_ch4_frac_behavior(self):
        """
        Assert that production (denominator of fractional loss) scales 
        as expected with changes to the fraction of CH4 in NG.
        """
        g = GHGIDataInput(
            STATE_GHGI_FILENAME,
            STATE_PROD_FILENAME,
            NATNL_PROD_FILENAME,
            NATNL_NGPROD_GHGI_FILENAME,
            NATNL_NGPROD_UNCERT_GHGI_FILENAME,
            NATNL_PETPROD_GHGI_FILENAME,
            1900,
            "State1",
            0.0, # 0% of NG is CH4
            0.,  # 0% of midstream loss is aerial
        )
        # Total and sub-mdl CH4 emissions should be inf if 0% of NG production 
        # is CH4 (the denominator of fractional loss is 0)
        self.assertTrue(
            (g.submdl_midstream_ch4_loss_rate==np.inf).all()
        )
        self.assertTrue(
            (g.total_midstream_ch4_loss_rate==np.inf).all()
        )
        
        # 100% of NG is CH4
        g = GHGIDataInput(
            STATE_GHGI_FILENAME,
            STATE_PROD_FILENAME,
            NATNL_PROD_FILENAME,
            NATNL_NGPROD_GHGI_FILENAME,
            NATNL_NGPROD_UNCERT_GHGI_FILENAME,
            NATNL_PETPROD_GHGI_FILENAME,
            1900,
            "State1",
            1., # 100% of NG is CH4
            0., # 0% of midstream loss is aerially measurable
        )
        hundredpct_ch4_loss_rate = g.total_midstream_ch4_loss_rate
        
        g = GHGIDataInput(
            STATE_GHGI_FILENAME,
            STATE_PROD_FILENAME,
            NATNL_PROD_FILENAME,
            NATNL_NGPROD_GHGI_FILENAME,
            NATNL_NGPROD_UNCERT_GHGI_FILENAME,
            NATNL_PETPROD_GHGI_FILENAME,
            1900,
            "State1",
            .5, # 50% of NG is CH4
            0., # 0% of midstream loss is aerially measurable
        )
        # If 50% of NG is CH4, the loss rate is doubled compared to 100% 
        # saturation (the denominator is halved)
        np.testing.assert_array_equal(
            2*hundredpct_ch4_loss_rate,
            g.total_midstream_ch4_loss_rate
        )
        
    def test_midstream_aerial_frac(self):
        """
        Assert that 
        """        
        g = GHGIDataInput(
            STATE_GHGI_FILENAME,
            STATE_PROD_FILENAME,
            NATNL_PROD_FILENAME,
            NATNL_NGPROD_GHGI_FILENAME,
            NATNL_NGPROD_UNCERT_GHGI_FILENAME,
            NATNL_PETPROD_GHGI_FILENAME,
            1900,
            "State1",
            1., # 100% of NG is CH4
            0.0,# 0% of midstream loss is aerial
        )
        hundredpct_submdl_frac = g.submdl_midstream_ch4_loss_rate
        
        # If 100% of NG is CH4, but 50% of estimated loss rate is aerially 
        # estimable, then the sub-mdl loss rate should be 50% as much as 
        # when the assumption was 0%.
        g = GHGIDataInput(
            STATE_GHGI_FILENAME,
            STATE_PROD_FILENAME,
            NATNL_PROD_FILENAME,
            NATNL_NGPROD_GHGI_FILENAME,
            NATNL_NGPROD_UNCERT_GHGI_FILENAME,
            NATNL_PETPROD_GHGI_FILENAME,
            1900,
            "State1",
            1., # 100% of NG is CH4
            .5, # 50% of midstream loss is aerially measurable
        )
        np.testing.assert_array_equal(
            .5*hundredpct_submdl_frac,
            g.submdl_midstream_ch4_loss_rate
        )
        
        # If 100% of NG is CH4, but 100% of estimated loss rate is aerially 
        # estimable, then the sub-mdl loss rate should be 50% as much as 
        # when the assumption was 0%.
        g = GHGIDataInput(
            STATE_GHGI_FILENAME,
            STATE_PROD_FILENAME,
            NATNL_PROD_FILENAME,
            NATNL_NGPROD_GHGI_FILENAME,
            NATNL_NGPROD_UNCERT_GHGI_FILENAME,
            NATNL_PETPROD_GHGI_FILENAME,
            1900,
            "State1",
            1., # 100% of NG is CH4
            1,  # 100% of midstream loss is aerially measurable
        )
        np.testing.assert_array_equal(
            0.*hundredpct_submdl_frac,
            g.submdl_midstream_ch4_loss_rate
        )

if __name__=="__main__":
    import unittest
    unittest.main()
