import os

from unittest import TestCase

import pandas as pd
import numpy as np

from roams.conf import TEST_DIR
from roams.midstream_ghgi.input import GHGIDataInput
from roams.utils import ch4_volume_to_mass

STATE_GHGI_FILENAME = os.path.join(TEST_DIR,"_state_ghgi.csv")
STATE_PROD_FILENAME = os.path.join(TEST_DIR,"_state_prod.csv")
NATNL_PROD_FILENAME = os.path.join(TEST_DIR,"_natl_prod.csv")
NATNL_NGPROD_GHGI_FILENAME = os.path.join(TEST_DIR,"_natl_ngprodch4.csv")
NATNL_NGPROD_UNCERT_GHGI_FILENAME = os.path.join(TEST_DIR,"_natl_nguncertch4.csv")
NATNL_PETPROD_GHGI_FILENAME = os.path.join(TEST_DIR,"_natl_petprodch4.csv")

STATE_GHGI = pd.DataFrame({"GHGI Gas":["Methane","Carbon Dioxide"],"1900":[.30,.10],"1901":[.31,.11]})
STATE_PROD = pd.DataFrame({"GHGI State":["State1","State2"],"1900":[2*1e6,5*1e6],"1901":[2*1e6,5*1e6]})
NATNL_PROD = pd.DataFrame({"Oil":[2*1e9,5*1e9],"Gas":[2*1e9,5*1e9],"production month":["August 1, 1900","August 1, 1901"]})
NATNL_NGPROD_GHGI = pd.DataFrame(
    [
        # Omitting rows that may otherwise be included, but aren't called 
        # out by the code specifically
        ["","Gathering and Boosting","80","80"],
        ["","Transmission and Storage","200","200"],
        ["","Processing","80","80"],
        ["","Total","10,000","10,000"],
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
        ["","Total","10,000","10,000"],
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
                {"c1":1.5}, # Too large
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
                {"c1":-.1}, # Too small
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
                {"c1":.5}, # Fine
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
                {"c1":.5}, # Fine
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
            {"c1":0.0}, # 0% of NG is CH4
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
            {"c1":1.}, # 100% of NG is CH4
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
            {"c1":.5}, # 50% of NG is CH4
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
            {"c1":1.}, # 100% of NG is CH4
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
            {"c1":1.}, # 100% of NG is CH4
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
            {"c1":1.}, # 100% of NG is CH4
            1,  # 100% of midstream loss is aerially measurable
        )
        np.testing.assert_array_equal(
            0.*hundredpct_submdl_frac,
            g.submdl_midstream_ch4_loss_rate
        )

    def test_correct_values(self):
        """
        Assert that the test inputs should result in specific state and 
        national midstream loss estimates.
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
            {"c1":1.}, # 100% of NG is CH4
            0., # 0% of midstream loss is aerially measurable
        )
        # The value in 1900 for this state is 3.0 MMT CO2eq
        # [3.0 MMT CO2eq] x [1 MMT CH4 / 25 MMT CO2eq] x [1e3 kt / 1 MMT] = 12 kt CH4
        state_ch4em = (.30/25) * 1e3 # 1.2 kt/yr

        # Denominator = state production of CH4 (assuming 100% of NG is CH4)
        state_ch4prod = ch4_volume_to_mass((2e6)*1.,"mcf/yr","kt/yr")

        calculated_state_loss = state_ch4em/state_ch4prod

        state_loss = g.compute_state_lossrate()

        # Overall state loss rate should be equal to [state CH4 emitted]/[state CH4 produced]
        self.assertAlmostEqual(
            calculated_state_loss,
            state_loss,
            10
        )
        
        natnl_midstream_em_frac = g.compute_natnl_midstream_em_frac()

        self.assertEqual(
            # 360 = total midstream components, 20k = total CH4 emissions of gas + oil
            # (in the dummy test data)
            (360/20_000),
            natnl_midstream_em_frac["mid"]
        )
        self.assertEqual(
            (360/20_000)*.9,
            natnl_midstream_em_frac["low"]
        )
        self.assertEqual(
            (360/20_000)*1.1,
            natnl_midstream_em_frac["high"]
        )

        # 2e9 MCF of NG (assumed to be 100% CH4) translated into kt/yr of CH4
        natnl_ch4prod = ch4_volume_to_mass((2e9)*1,"mcf/yr","kt/yr")
        
        # national midstream emissions from component processes
        natnl_ch4em = 360 # kt/yr
        
        natnl_midstream_lossrate = g.compute_natnl_midstream_loss()

        # Total national midstream loss should be [US midstream CH4 emitted]/[US CH4 produced]
        self.assertEqual(
            natnl_ch4em/natnl_ch4prod,
            natnl_midstream_lossrate.loc["mid"]
        )
        self.assertEqual(
            natnl_ch4em/natnl_ch4prod*.9,
            natnl_midstream_lossrate.loc["low"]
        )
        self.assertEqual(
            natnl_ch4em/natnl_ch4prod*1.1,
            natnl_midstream_lossrate.loc["high"]
        )

        # The lesser of national and state midstream loss should be the 
        # state midstream loss in this case, which is the 
        #   (state loss rate)*(national midstream emissions fraction)
        # (this is what is returned as the property that ROAMSModel depends 
        # on)
        self.assertEqual(
            state_loss*natnl_midstream_em_frac.loc["mid"],
            g.total_midstream_ch4_loss_rate.loc["mid"]
        )
        self.assertEqual(
            state_loss*natnl_midstream_em_frac.loc["low"],
            g.total_midstream_ch4_loss_rate.loc["low"]
        )
        self.assertEqual(
            state_loss*natnl_midstream_em_frac.loc["low"],
            g.total_midstream_ch4_loss_rate.loc["low"]
        )

if __name__=="__main__":
    import unittest
    unittest.main()
