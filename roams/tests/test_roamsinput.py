import os
import json
import logging

from unittest import TestCase

from roams.conf import TEST_DIR
FAKE_INPUT_FILE = os.path.join(TEST_DIR,"_fake_input.json")

from roams.input import ROAMSConfig

from roams.tests.test_aerialinput import SOURCE_FILE, PLUME_FILE
from roams.tests.test_siminput import SIM_FILE
from roams.tests.test_coveredprodinput import COVERED_PROD_FILE

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
    "prod_asset_type" : ("prod",),
    "midstream_asset_type" : ("midstream",),
    "coverage_count" : "coverage_count",
    "aerial_em_col" : None,
    "aerial_em_unit" : None,
    "wind_norm_col" : "wind_norm_em",
    "wind_norm_unit" : "kgh:mps",
    "wind_speed_col" : "windspeed",
    "wind_speed_unit" : "mps",
    "cutoff_col" : "cutoff",
    "covered_productivity_file" : COVERED_PROD_FILE,
    "covered_productivity_col" : "estimated productivity (mscf/day)",
    "covered_productivity_unit" : "mscf/day",
    "num_wells_to_simulate" : 1000,
    "well_visit_count" : 1_000_000_000,
    "wells_per_site" : 3.14159,
    "frac_production_ch4" : .5,
    "stratify_sim_sample" : True,
    "n_mc_samples" : 100,
    "prod_transition_point" : None,
    "partial_detection_correction" : True,
    "simulate_error" : True,
    "PoD_fn" : "bin",
    "correction_fn" : "power_correction",
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
        self._saveConfig(TEST_CONFIG)
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
            "prod_asset_type",
            "midstream_asset_type",
            "coverage_count",
            "covered_productivity_file",
            "covered_productivity_col",
            "covered_productivity_unit",
            "num_wells_to_simulate",
            "well_visit_count",
            "wells_per_site",
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
        for key in (
            "sim_em_file",
            "sim_em_col",
            "sim_em_unit",
            "plume_file",
            "source_file",
            "source_id_name",
            "asset_col",
            "prod_asset_type",
            "midstream_asset_type",
            "coverage_count",
            "covered_productivity_file",
            "covered_productivity_col",
            "covered_productivity_unit",
            "num_wells_to_simulate",
            "well_visit_count",
            "wells_per_site",
            "midstream_transition_point",
            ):
            newconfig = TEST_CONFIG.copy()
            newconfig[key] = None
            with self.assertRaises(ValueError):
                c = ROAMSConfig(newconfig)
    
if __name__=="__main__":
    import unittest
    unittest.main()