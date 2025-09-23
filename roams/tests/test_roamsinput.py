import os
import json
import logging
from copy import deepcopy

from unittest import TestCase

import numpy as np

from roams.conf import TEST_DIR
FAKE_INPUT_FILE = os.path.join(TEST_DIR,"_fake_input.json")

from roams.input import ROAMSConfig

from roams.tests.test_aerialinput import SOURCE_FILE, PLUME_FILE
from roams.tests.test_siminput import SIM_FILE
from roams.tests.test_coveredprodinput import COVERED_PROD_FILE
from roams.tests.test_ghgiinput import STATE_GHGI_FILENAME, STATE_PROD_FILENAME, NATNL_PROD_FILENAME, NATNL_NGPROD_GHGI_FILENAME, NATNL_NGPROD_UNCERT_GHGI_FILENAME, NATNL_PETPROD_GHGI_FILENAME

TEST_CONFIG = {
    "sim_em_file" : SIM_FILE,
    "sim_em_col" : "emissions",
    "sim_em_unit" : "kgh",
    "sim_prod_col" : "production",
    "sim_prod_unit" : "mscf/hr",
    "plume_file" : PLUME_FILE,
    "source_file" : SOURCE_FILE,
    "source_id_name" : "source_id",
    "asset_col" : "asset_type",
    "asset_groups": {"production":["prod"],"midstream":["midstream"]},
    "coverage_count" : "coverage_count",
    "aerial_em_col" : None,
    "aerial_em_unit" : None,
    "wind_norm_col" : "wind_norm_em",
    "wind_norm_unit" : "kgh:mps",
    "wind_speed_col" : "windspeed",
    "wind_speed_unit" : "mps",
    "cutoff_col" : "cutoff",
    "covered_productivity_dist_file" : COVERED_PROD_FILE,
    "covered_productivity_dist_col" : "estimated productivity (vol/time)",
    "covered_productivity_dist_unit" : "mscf/day",
    "total_covered_ngprod_mcfd" : 100_000,
    "total_covered_oilprod_bbld" : 10_000,
    "num_wells_to_simulate" : 1000,
    "well_visit_count" : 1_000_000_000,
    "wells_per_site" : 3.14159,
    "state_ghgi_file" : STATE_GHGI_FILENAME,
    "ghgi_co2eq_unit" : "MMT/yr",
    "production_state_est_file" : STATE_PROD_FILENAME,
    "production_natnl_est_file" : NATNL_PROD_FILENAME,
    "production_est_unit" : "mscf/yr",
    "ghgi_ch4emissions_ngprod_file" : NATNL_NGPROD_GHGI_FILENAME,
    "ghgi_ch4emissions_ngprod_uncertainty_file" : NATNL_NGPROD_UNCERT_GHGI_FILENAME,
    "ghgi_ch4emissions_petprod_file" : NATNL_PETPROD_GHGI_FILENAME,
    "ghgi_ch4emissions_unit" : "kt/yr",
    "year" : 1,
    "state" : "State1",
    "frac_aerial_midstream_emissions": 0.25,
    "gas_composition" : {"C1":.5,"C2":.3,"C3":.1},
    "stratify_sim_sample" : True,
    "n_mc_samples" : 100,
    "prod_transition_point" : None,
    "partial_detection_correction" : True,
    "simualte_error": True,
    "noise_fn": {"name":"normal","loc":1.0,"scale":1.0},
    "PoD_fn" : "bin",
    "correction_fn" : {"name":"power","constant":4.08,"power":0.77},
    "midstream_transition_point" : 1000,
    "foldername" : None,
    "save_mean_dist" : True,
    "loglevel" : logging.INFO,
}

log = logging.getLogger("roams.tests.test_roamsinput.ROAMSInputTests")

class ROAMSInputTests(TestCase):

    def _saveConfig(self,json_blob):
        """
        A utility to save a given json blob to a test file in the tests 
        directory.

        Args:
            json_blob (dict):
                A blob of json information that will be written to the 
                location of FAKE_INPUT_FILE.
        """        
        with open(FAKE_INPUT_FILE,"w") as f:
            json.dump(json_blob,f)

    def test_loadsconfigdict(self):
        """
        Assert that the TEST_CONFIG can be loaded as a dictionary.
        """
        c = ROAMSConfig(TEST_CONFIG)
    
    def test_loadsconfigfile(self):
        """
        Assert that the TEST_CONFIG can be loaded normally when given as a file.
        """
        config = TEST_CONFIG
        self._saveConfig(config)
        c = ROAMSConfig(FAKE_INPUT_FILE)

    def test_missing_inputfailure(self):
        """
        Assert that KeyErrors are raised when required inputs are missing.
        """
        for key in (
            "sim_em_file",
            "sim_em_col",
            "sim_em_unit",
            "plume_file",
            "source_file",
            "source_id_name",
            "asset_col",
            "asset_groups",
            "coverage_count",
            "gas_composition",
            "num_wells_to_simulate",
            "well_visit_count",
            "wells_per_site",
            "total_covered_ngprod_mcfd",
            "total_covered_oilprod_bbld",
            "state_ghgi_file",
            "ghgi_co2eq_unit",
            "production_state_est_file",
            "production_natnl_est_file",
            "production_est_unit",
            "ghgi_ch4emissions_ngprod_file",
            "ghgi_ch4emissions_ngprod_uncertainty_file",
            "ghgi_ch4emissions_petprod_file",
            "ghgi_ch4emissions_unit",
            "year",
            "state",
            "frac_aerial_midstream_emissions",
            "midstream_transition_point",
            ):
            newconfig = TEST_CONFIG.copy()
            newconfig.pop(key)
            with self.assertRaises(KeyError):
                c = ROAMSConfig(newconfig)
    
    def test_wrongtype_inputfailure(self):
        """
        Assert that when required inputs are the wrong type, a ValueError 
        is raised.
        """
        with self.assertRaises(TypeError):
            c = ROAMSConfig(None)

        for key in (
            "sim_em_file",
            "sim_em_col",
            "sim_em_unit",
            "plume_file",
            "source_file",
            "source_id_name",
            "asset_col",
            "asset_groups",
            "coverage_count",
            "gas_composition",
            "num_wells_to_simulate",
            "well_visit_count",
            "wells_per_site",
            "total_covered_ngprod_mcfd",
            "total_covered_oilprod_bbld",
            "state_ghgi_file",
            "ghgi_co2eq_unit",
            "production_state_est_file",
            "production_natnl_est_file",
            "production_est_unit",
            "ghgi_ch4emissions_ngprod_file",
            "ghgi_ch4emissions_ngprod_uncertainty_file",
            "ghgi_ch4emissions_petprod_file",
            "ghgi_ch4emissions_unit",
            "year",
            "state",
            "frac_aerial_midstream_emissions",
            "midstream_transition_point",
            ):
            newconfig = TEST_CONFIG.copy()
            newconfig[key] = None
            with self.assertRaises(TypeError):
                c = ROAMSConfig(newconfig)
    
    def test_incorrect_gas_composition(self):
        """
        Assert that when the gas composition is misspecified, the ROAMSConfig 
        complains appropriately.
        """
        newconfig = TEST_CONFIG.copy()
        
        # Negative total weight described -> should be ValueError
        newconfig["gas_composition"] = {"C1":-1.}
        with self.assertRaises(ValueError):
            c = ROAMSConfig(newconfig)

        # 0 total weight described -> should be ValueError
        newconfig["gas_composition"] = {"C1":0.}
        with self.assertRaises(ValueError):
            c = ROAMSConfig(newconfig)
        
        # .79 total weight described -> should be ValueError
        newconfig["gas_composition"] = {"C1":.79}
        with self.assertRaises(ValueError):
            c = ROAMSConfig(newconfig)
        
        
        # 1.01 total weight described -> should be ValueError
        newconfig["gas_composition"] = {"C1":1.01}
        with self.assertRaises(ValueError):
            c = ROAMSConfig(newconfig)
        
        # c1 is None -> should be ValueError
        newconfig["gas_composition"] = {"C1":None,"C2":.9}
        with self.assertRaises(ValueError):
            c = ROAMSConfig(newconfig)
    
    def test_bad_asset_types(self):
        """
        Assert that when the aerial asset types are incorrectly specified, 
        the appropriate errors will be raised.
        """
        # Remove "midstream" from the asset groups
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["asset_groups"].pop("midstream")
        with self.assertRaises(KeyError):
            c = ROAMSConfig(newconfig)
        
        # Remove "midstream" from the asset groups
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["asset_groups"].pop("production")
        with self.assertRaises(KeyError):
            c = ROAMSConfig(newconfig)
        
        # There's an overlapping asset type
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["asset_groups"] = {"production":["prod"],"midstream":["midstream","prod"]}
        with self.assertRaises(ValueError):
            c = ROAMSConfig(newconfig)
    
    def test_incorrect_noisefn(self):
        """
        Assert that when the noise function to apply to sampled aerial plumes 
        isn't properly specified, you get correct errors.
        """
        # The prior specification of a string is no longer valid, yields TypeError
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["noise_fn"] = "normal"
        with self.assertRaises(TypeError):
            c = ROAMSConfig(newconfig)
        
        # A method name that doesn't exist in numpy.random is an AttributeError
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["noise_fn"] = {"name":"fake"}
        with self.assertRaises(AttributeError):
            c = ROAMSConfig(newconfig)
        
        # When no "name" is in the dictionary, there's a KeyError
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["noise_fn"] = {"loc":1.0,"scale":1.0}
        with self.assertRaises(KeyError):
            c = ROAMSConfig(newconfig)
    
    def test_incorrect_correctionfn(self):
        """
        Assert that when the mean correction function to apply to sampled aerial 
        plumes isn't properly specified, you get correct errors.
        """
        # The prior specification of a string is no longer valid, yields TypeError
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["correction_fn"] = "power_correction"
        with self.assertRaises(TypeError):
            c = ROAMSConfig(newconfig)
        
        # A method name that doesn't exist in roams.aerial.assumptions is an AttributeError
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["correction_fn"] = {"name":"fake"}
        with self.assertRaises(AttributeError):
            c = ROAMSConfig(newconfig)
        
        # When no "name" is in the dictionary, there's a KeyError
        newconfig = deepcopy(TEST_CONFIG)
        newconfig["correction_fn"] = {"constant":1.0,"power":1.0}
        with self.assertRaises(KeyError):
            c = ROAMSConfig(newconfig)
        
    def test_noisefn(self):
        """
        Assert that specification of normal noise occurs as intended.
        """
        # Specify 
        config = deepcopy(TEST_CONFIG)
        config["noise_fn"] = {"name":"normal","loc":1.0,"scale":1.0}
        c = ROAMSConfig(config)
        
        # Set a fixed seed
        np.random.seed(1)
        results = c.noise_fn(np.ones(10))

        np.testing.assert_array_almost_equal(
            results,
            np.array([2.62434536,  0.38824359,  0.47182825, -0.07296862,  1.86540763, -1.3015387 ,  2.74481176,  0.2387931 ,  1.3190391 ,  0.75062962]),
            8
        )

    def test_power_correction_fn(self):
        """
        Assert that power correction function parameters are being handled 
        correctly.
        """
        config = deepcopy(TEST_CONFIG)
        config["correction_fn"] = {"name":"power","constant":2,"power":2} # 2 * (emissions ** 2)
        c = ROAMSConfig(config)

        x = np.arange(100)
        result = c.correction_fn(x)
        np.testing.assert_array_equal(result,2*(x**2))
    
    def test_linear_correction_fn(self):
        """
        Assert that linear correction function parameters are being handled 
        correctly.
        """
        config = deepcopy(TEST_CONFIG)
        config["correction_fn"] = {"name":"linear","slope":2,"intercept":1} # 2*emissions + 1
        c = ROAMSConfig(config)

        x = np.arange(100)
        result = c.correction_fn(x)
        np.testing.assert_array_equal(result,2*x + 1)
    
if __name__=="__main__":
    import unittest
    unittest.main()