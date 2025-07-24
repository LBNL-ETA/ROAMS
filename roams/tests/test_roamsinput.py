import os
import json
import logging

from unittest import TestCase

from roams.conf import TEST_DIR
FAKE_INPUT_FILE = os.path.join(TEST_DIR,"_fake_input.json")

from roams.input import ROAMSConfig

TEST_CONFIG = {
    "prod_sim" : {
        "em_file" : "path/to/simulated/production.csv",
        "em_col" : "sim_emissions",
        "em_unit" : "kgh",
        "prod_col" : "sim_prod",
        "prod_unit" : "mscf/hr",
    },
    "aerial" : {
        "plume_file" : "path/to/plume_file.csv",
        "source_file" : "path/to/source_file.csv",
        "source_id_name" : "source_id",
        "asset_col" : "asset_type",
        "prod_asset_type" : ("prod"),
        "midstream_asset_type" : ("midstream"),
        "coverage_count" : "coverage_count",
        "em_col" : None,
        "em_unit" : None,
        "wind_norm_col" : "wind_norm_em",
        "wind_norm_unit" : "kgh:mps",
        "wind_speed_col" : "windspeed",
        "wind_speed_unit" : "mps",
        "cutoff_col" : "cutoff",
    },
    "coveredRegion" : {
        "productivity_file" : "path/to/covered/production.csv",
        "productivity_col" : "production",
        "productivity_unit" : "mscf/d",
        "num_wells" : 1000,
        "well_visit_count" : 1_000_000_000,
        "wells_per_site" : 3.14159,
        "frac_production_ch4" : .5,
    },
    "algorithm" : {
        "stratify_sim_sample" : True,
        "n_mc_samples" : 100,
        "prod_transition_point" : None,
        "partial_detection_correction" : True,
        "simulate_error" : True,
        "PoD_fn" : "bin",
        "correction_fn" : "power_correction",
        "midstream_transition_point" : 1000,
    },
    "output" : {
        "foldername" : None,
        "save_mean_dist" : True,
        "loglevel" : logging.INFO,
    },
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
        for key in ("em_file","em_col","em_unit"):
            newconfig = TEST_CONFIG.copy()
            newconfig["prod_sim"].pop(key)
            with self.assertRaises(KeyError):
                c = ROAMSConfig(newconfig)

        for key in ("plume_file","source_file","source_id_name","asset_col","prod_asset_type","midstream_asset_type","coverage_count"):
            newconfig = TEST_CONFIG.copy()
            newconfig["aerial"].pop(key)
            with self.assertRaises(KeyError):
                c = ROAMSConfig(newconfig)

        for key in ("productivity_file","productivity_col","productivity_unit","num_wells","well_visit_count","wells_per_site"):
            newconfig = TEST_CONFIG.copy()
            newconfig["coveredRegion"].pop(key)
            with self.assertRaises(KeyError):
                c = ROAMSConfig(newconfig)
        
        for key in ("midstream_transition_point",):
            newconfig = TEST_CONFIG.copy()
            newconfig["algorithm"].pop(key)
            with self.assertRaises(KeyError):
                c = ROAMSConfig(newconfig)
    
    def test_wrongtype_inputfailure(self):
        """
        Assert that when required inputs are the wrong type, a ValueError 
        is raised.
        """
        for key in ("em_file","em_col","em_unit"):
            newconfig = TEST_CONFIG.copy()
            newconfig["prod_sim"][key] = None
            with self.assertRaises(ValueError):
                c = ROAMSConfig(newconfig)

        for key in ("plume_file","source_file","source_id_name","asset_col","prod_asset_type","midstream_asset_type","coverage_count"):
            newconfig = TEST_CONFIG.copy()
            newconfig["aerial"][key] = None
            with self.assertRaises(ValueError):
                c = ROAMSConfig(newconfig)

        for key in ("productivity_file","productivity_col","productivity_unit","num_wells","well_visit_count","wells_per_site"):
            newconfig = TEST_CONFIG.copy()
            newconfig["coveredRegion"][key] = None
            with self.assertRaises(ValueError):
                c = ROAMSConfig(newconfig)
        
        for key in ("midstream_transition_point",):
            newconfig = TEST_CONFIG.copy()
            newconfig["algorithm"][key] = None
            with self.assertRaises(ValueError):
                c = ROAMSConfig(newconfig)




    
if __name__=="__main__":
    import unittest
    unittest.main()