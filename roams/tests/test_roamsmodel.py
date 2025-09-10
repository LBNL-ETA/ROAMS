from copy import deepcopy
import os
import logging

from unittest import TestCase

import yaml
import numpy as np

from roams.conf import RESULT_DIR

from roams.input import ROAMSConfig
from roams.model import ROAMSModel
from roams.aerial.assumptions import zero_out

from roams.tests.test_aerialinput import SOURCE_FILE, PLUME_FILE
from roams.tests.test_siminput import SIM_FILE
from roams.tests.test_ghgiinput import STATE_GHGI_FILENAME, STATE_PROD_FILENAME, NATNL_PROD_FILENAME, NATNL_NGPROD_GHGI_FILENAME, NATNL_NGPROD_UNCERT_GHGI_FILENAME, NATNL_PETPROD_GHGI_FILENAME

def _half_pod(windnorm_em: np.ndarray) -> np.ndarray:
    """
    A function just for these test. Return P = .5 for nonzero emissions.
    Have to return 1 for everything else.
    """    
    pod = np.ones(windnorm_em.shape)
    pod[windnorm_em>0] = .5
    return pod

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
    "asset_groups": {"production":["prod"], "midstream":["midstream"]},
    "coverage_count" : "coverage_count",
    "aerial_em_col" : None,
    "aerial_em_unit" : None,
    "wind_norm_col" : "wind_norm_em",
    "wind_norm_unit" : "kgh:mps",
    "wind_speed_col" : "windspeed",
    "wind_speed_unit" : "mps",
    "cutoff_col" : None,
    "total_covered_ngprod_mcfd" : 100_000,
    "total_covered_oilprod_bbld" : 10_000,
    "num_wells_to_simulate" : 1000,
    "well_visit_count" : 1_000_000_000,
    "wells_per_site" : 3.14159,
    "state_ghgi_file" : STATE_GHGI_FILENAME,
    "ghgi_co2eq_unit" : "MMT/yr",
    "enverus_state_production_file" : STATE_PROD_FILENAME,
    "enverus_natnl_production_file" : NATNL_PROD_FILENAME,
    "enverus_prod_unit" : "mscf/yr",
    "ghgi_ch4emissions_ngprod_file" : NATNL_NGPROD_GHGI_FILENAME,
    "ghgi_ch4emissions_ngprod_uncertainty_file" : NATNL_NGPROD_UNCERT_GHGI_FILENAME,
    "ghgi_ch4emissions_petprod_file" : NATNL_PETPROD_GHGI_FILENAME,
    "ghgi_ch4emissions_unit" : "kt/yr",
    "year" : 1900,
    "state" : "State1",
    "frac_aerial_midstream_emissions": 0.25,
    "gas_composition" : {"C1":.8,"C2":.1,"C3":.1},
    "stratify_sim_sample" : False,
    "n_mc_samples" : 100,
    "prod_transition_point" : 10,
    "partial_detection_correction" : True,
    "simulate_error" : False,
    "PoD_fn" : "bin",
    "correction_fn" : "power_correction",
    "midstream_transition_point" : 1000,
    "foldername" : "_roamsmodeltest",
    "save_mean_dist" : True,
    "loglevel" : logging.WARNING,
}

log = logging.getLogger("roams.tests.test_roamsmodel.ROAMSModelTests")

class ROAMSModelTests(TestCase):
    """
    A class to test the internal behavior of ROAMSModel, specifically the 
    generation and treatment of methane emissions size distributions.

    This handles a lot of the behavior, but does exclude the testing of 
    the sub-MDL midstream estimate, whose computation is tested in 
    `test_ghgiinput.py`.
    """

    @classmethod
    def setUpClass(cls):
        # Before any tests: make an instance of the model to be reused
        cls.model = ROAMSModel(TEST_CONFIG)
        
        # Before any tests: make a copy of the original config to re-apply
        cls.cfg = ROAMSConfig(TEST_CONFIG)

    @classmethod
    def tearDownClass(cls):
        # At the end of tests:
        if os.path.exists(cls.model.outfolder):
            files = os.listdir(cls.model.outfolder)
            for file in files:
                os.remove(os.path.join(cls.model.outfolder,file))
            os.rmdir(cls.model.outfolder)

    def setUp(self):
        """
        Reset the input config to the original.
        """        
        self.model.cfg = deepcopy(self.cfg)

    def test_init(self):
        """
        Assert that attributes set after parsing of the input file hold 
        specific values.
        """
        self.assertEqual(self.model.outfolder,os.path.join(RESULT_DIR,"_roamsmodeltest"))
        self.assertEqual(self.model.save_mean_dist,True)
        self.assertEqual(self.model.loglevel,logging.WARNING)
        self.assertEqual(self.model.log.name,"roams.model.ROAMSModel")
        self.assertEqual(self.model.log.level,logging.WARNING)
        self.assertEqual(self.model.table_outputs,dict())
        self.assertEqual(self.model.well_visit_count,1_000_000_000)
        self.assertEqual(self.model.wells_per_site,3.14159)
        self.assertEqual(self.model._quantiles,(.025,.975))

    def test_make_simulated_sample(self):
        """
        Assert that `make_simulated_sample` is producing the right sample 
        based on the input data.

        The resulting sample should be of the right shape, and should 
        be the sampling with a replacement over a uniform distribution 
        of [1,2,3,4,5] (the data in the test data).
        """
        # The simulated sample is not stratified, so the emissions 
        # values are drawn directly from [1,2,3,4,5] (emissions values 
        # in the table)
        np.random.seed(1)
        sim_sample = self.model.make_simulated_sample()
        
        # Assert the shape is [Num wells to simulate] x [N MC samples]
        self.assertEqual(sim_sample.shape,(1000,100))

        # Assert the number of times each sample should appear under normal 
        # operation and this seed
        self.assertEqual((sim_sample==1).sum(),20128)
        self.assertEqual((sim_sample==2).sum(),19871)
        self.assertEqual((sim_sample==3).sum(),20095)
        self.assertEqual((sim_sample==4).sum(),19879)
        self.assertEqual((sim_sample==5).sum(),20027)
        
        # Assert the mean of all sampled values, given normal operation and 
        # this seed.
        self.assertAlmostEqual(sim_sample.mean(),2.99806)

    def test_correction_fn(self):
        """
        Assert that the get_aerial_survey_sample applies the correction 
        function as expected.
        """
        # No correction function
        self.model.cfg.correction_fn = None
        
        # Don't simulate error and apply noise
        self.model.cfg.simulate_error = False
        
        # Don't do anything to the negative values, just return it all
        self.model.cfg.handle_negative = lambda em: em
        
        # Create reference values that are only the sampled valued
        # emissions, wind-normalized emissions
        np.random.seed(1)
        em_ref, windnorm_ref = self.model.get_aerial_survey_sample()

        # Correction function = 2x
        self.model.cfg.correction_fn = lambda em: em*2
        np.random.seed(1)
        em_2x, windnorm_2x = self.model.get_aerial_survey_sample()

        # The emissions should be doubled after this correction
        np.testing.assert_equal(
            em_2x,em_ref*2
        )
        # No adjustments should modify the wind-normalized sample
        np.testing.assert_equal(
            windnorm_2x,windnorm_ref
        )
    
    def test_noise_fn(self):
        """
        Assert that the get_aerial_survey_sample applies the noise
        fn as expected.
        """
        # No correction function
        self.model.cfg.correction_fn = None
        
        # Don't simulate error and apply noise
        self.model.cfg.simulate_error = False
        
        # Don't do anything to the negative values, just return it all
        self.model.cfg.handle_negative = lambda em: em
        
        # Create reference values that are only the sampled valued
        # emissions, wind-normalized emissions
        np.random.seed(1)
        em_ref, windnorm_ref = self.model.get_aerial_survey_sample()

        # "noise" function is just multiplying by 2.
        self.model.cfg.noise_fn = lambda em: em*2
        # Simulate error using this noise_fn
        self.model.cfg.simulate_error = True
        np.random.seed(1)
        em_2x, windnorm_2x = self.model.get_aerial_survey_sample()

        # If the noise function multiplies by 2, the resulting 
        # sampled emissions should be multiplied by 2
        np.testing.assert_equal(
            em_2x,em_ref*2
        )
        
        # No adjustments should affect the wind-normalized sample
        np.testing.assert_equal(
            windnorm_2x,windnorm_ref
        )
    
    def test_handle_negatives(self):
        """
        Assert that the default handle_negatives is applied (and acts) as 
        intended.
        """
        # No correction function
        self.model.cfg.correction_fn = None
        
        # Don't simulate error and apply noise
        self.model.cfg.simulate_error = False
        
        # Don't do anything to the negative values, just return it all
        self.model.cfg.handle_negative = lambda em : em
        
        # Create reference values that are only the sampled valued
        # emissions, wind-normalized emissions
        np.random.seed(1)
        em_ref, windnorm_ref = self.model.get_aerial_survey_sample()

        # Set the handle_negative function to zero out negatives
        self.model.cfg.handle_negative = zero_out
        
        # Use a noise function that turns all values negative
        self.model.cfg.simulate_error = True
        self.model.cfg.noise_fn = lambda em : -1*em
        np.random.seed(1)
        em_0, windnorm_0 = self.model.get_aerial_survey_sample()

        # Assert that the remaining emissions is all 0: all the negative 
        # values were turned into 0
        np.testing.assert_equal(
            em_0,em_ref*0
        )
        
        # No adjustments should affect the wind-normalized sample
        np.testing.assert_equal(
            windnorm_0,windnorm_ref
        )
    
    def test_make_aerial_prod_sample(self):
        """
        Assert that `make_aerial_prod_sample` is producing the right sample 
        based on the input data.

        There are two production sources in the test dataset. They have the 
        following properties:

        Source 1:
            * Coverage count 2
            * Emissions 35
            * Wind-normalized emissions 7
        Source 2:
            * Coverage count 3
            * Emissions 48
            * Wind-normalized emissions 8
        """
        self.model.cfg.correction_fn = None         # No correction function: don't adjust the sampled emissions
        self.model.cfg.simulate_error = False       # Don't add random noise
        self.model.cfg.partial_detection_correction = True  # Tell it to add partial detection
        self.model.cfg.PoD_fn = _half_pod           # Use PoD where pos emissions get P = .5 -> add 1x emissions
        self.model.cfg.n_mc_samples = 100          # Use 1000 MC samples
        self.model.cfg.num_wells_to_simulate = 10   # Simulate 10 wells only

        # Set a seed to control what the expected random behavior is
        np.random.seed(1)

        # Generate the samples
        aerial_sample, pd_sample = self.model.make_aerial_prod_sample()

        # Resulting samples should both be [num wells to simulate] x [N MC samples]
        self.assertEqual(aerial_sample.shape,(10,100))
        self.assertEqual(pd_sample.shape,(10,100))

        # Assert the partial detection emissions are exactly equal to 
        # the sampled emissions (what you get when PoD=.5 everywhere where 
        # measured emissions were sampled, and 0 emissions <-> 0 wind-norm).
        self.assertTrue((aerial_sample==pd_sample).all())

        # Assert that each underlying plume value appears in at least 
        # one sample
        self.assertEqual((aerial_sample==35).sum(),51)
        self.assertEqual((aerial_sample==48).sum(),40)
        
        # Assert that the mean is supposed to be based on the given seed.
        self.assertTrue(
            aerial_sample[-2:,:].sum(axis=0).mean(),37.05
        )

    def test_make_aerial_midstream_sample(self):
        """
        Assert that `make_aerial_midstream_sample` is producing the right sample 
        based on the input data.

        There are two midstream sources in the test dataset. They have the 
        following properties:

        Source 1:
            * Coverage count 4
            * Emissions 210
            * Wind-normalized emissions 10
        Source 2:
            * Coverage count 5
            * Emissions 242
            * Wind-normalized emissions 11
        """
        self.model.cfg.correction_fn = None         # No correction function: don't adjust the sampled emissions
        self.model.cfg.simulate_error = False       # Don't add random noise
        self.model.cfg.partial_detection_correction = True  # Tell it to add partial detection
        self.model.cfg.PoD_fn = _half_pod           # Use PoD where >0 emissions -> P = .5
        self.model.cfg.n_mc_samples = 100          # Use 1000 MC samples
        self.model.cfg.num_wells_to_simulate = 10   # Simulate 10 wells only

        # Set a seed to control what the expected random behavior is
        np.random.seed(1)

        # Generate the samples
        aerial_sample, pd_sample = self.model.make_aerial_midstream_sample()

        # Resulting samples should both be [2] x [N MC samples]
        # (for midstream, there's no associated infrastructure to simulated
        # with a sample of some size. Just the sources observed.)
        self.assertEqual(aerial_sample.shape,(2,100))
        self.assertEqual(pd_sample.shape,(2,100))

        # Assert the partial detection emissions are exactly equal to 
        # the sampled emissions (what you get when PoD=.5 everywhere where 
        # measured emissions were sampled, and 0 emissions <-> 0 wind-norm).
        self.assertTrue((aerial_sample==pd_sample).all())

        # Assert that each underlying plume appears a fixed number of times 
        # based on the seed and current implementation
        self.assertEqual((aerial_sample==210).sum(),27)
        self.assertEqual((aerial_sample==242).sum(),26)
        
        # Assert that the mean is supposed to be based on the given seed.
        self.assertEqual(aerial_sample.sum(axis=0).mean(),119.62)

    def test_raises_toofew_sim_data(self):
        """
        Assert that when there are fewer sampled emissions values below the 
        transition point than the are slots to fill, an IndexError is raised,
        and not otherwise.
        """
        self.model.cfg.partial_detection_correction = True
        self.model.cfg.pod_fn = _half_pod
        self.model.cfg.correction_fn = None
        

        # Make the up the samples: pretend like the two aerial plumes
        # got sampled in each MC run
        self.model.prod_tot_aerial_sample = np.zeros((1000,100))
        self.model.prod_tot_aerial_sample[-2,:] = 35
        self.model.prod_tot_aerial_sample[-1,:] = 48

        self.model.prod_partial_detection_emissions = np.zeros((1000,100))
        self.model.prod_partial_detection_emissions[-2,:] = 35
        self.model.prod_partial_detection_emissions[-1,:] = 48
        
        # Make up a simulated sample, where for each MC run it's [1,2,3,4,5]
        # repeated
        self.model.simulated_sample = np.tile([1,2,3,4,5],(100,200)).T

        # transition point excludes highest simulated emission
        # (leaving 800 simulated values in each MC run to fill 998 slots)
        # -> there will be too few simulated values to use
        self.model.cfg.prod_transition_point = 5 
        with self.assertRaises(IndexError):
            self.model.combine_prod_samples()
        
        # transition point no long excludes any simulated emissions
        # (leaving 1000 simulated values in each MC run to fill 998 slots)
        # -> there are sufficient simulated emissions values
        self.model.cfg.prod_transition_point = 6
        self.model.combine_prod_samples()
    
    def test_prod_dist_combination(self):
        """
        Assert that production distributions get combined in a fixed way, 
        given input aerial distributions
        """
        self.model.cfg.partial_detection_correction = True
        self.model.cfg.prod_transition_point = None
        
        # Make the up the samples: pretend like the two aerial plumes
        # got sampled in each MC run
        self.model.prod_tot_aerial_sample = np.zeros((1000,100))
        self.model.prod_tot_aerial_sample[-2,:] = 35
        self.model.prod_tot_aerial_sample[-1,:] = 48

        self.model.prod_partial_detection_emissions = np.zeros((1000,100))
        self.model.prod_partial_detection_emissions[-2,:] = 35
        self.model.prod_partial_detection_emissions[-1,:] = 48
        
        np.random.seed(1)
        self.model.simulated_sample = np.random.choice(
            [5,6,7,8,9,10],(1000,100),replace=True
        )

        # Have the model combined the invented samples.
        self.model.combine_prod_samples()

        # Assert that, based on the seed, the resulting combined sample 
        # results in a very specific mean emissions (sans partial detection).
        self.assertEqual(
            self.model.combined_samples.sum(axis=0).mean(),
            7567.55
        )

        # Assert that the transition point is 20 for all iterations, as it 
        # should under normal operation.
        self.assertTrue((self.model.prod_tp==20).all())

        # Assert that the ordering of partial detection is maintained. 
        # Because each partial detection correction should be equal to 
        # the corresponding emissions (P=.5), just assert the values are 
        # equal wherever there's a partial detection.
        
        # pd_over0 = where partial detection emissions are >0
        pd_over0 = self.model.prod_partial_detection_emissions>0
        self.assertTrue(
            (   
                (self.model.prod_partial_detection_emissions[pd_over0])
                ==
                (self.model.combined_samples[pd_over0])
            ).all()
        )

    def test_prod_dist_fixedtp(self):
        """
        Assert that when the production emissions transition point is fixed, 
        the distributions are combined as expected under a fixed seed.
        """
        self.model.cfg.partial_detection_correction = True
        self.model.cfg.pod_fn = _half_pod
        self.model.cfg.correction_fn = None
        
        # transition point excludes highest simulated emission
        self.model.cfg.prod_transition_point = 6 

        # Make the up the samples: pretend like the two aerial plumes
        # got sampled in each MC run
        self.model.prod_tot_aerial_sample = np.zeros((1000,100))
        self.model.prod_tot_aerial_sample[-2,:] = 35
        self.model.prod_tot_aerial_sample[-1,:] = 48

        self.model.prod_partial_detection_emissions = np.zeros((1000,100))
        self.model.prod_partial_detection_emissions[-2,:] = 35
        self.model.prod_partial_detection_emissions[-1,:] = 48
        
        np.random.seed(1)
        self.model.simulated_sample = np.random.choice(
            [1,2,3,4,5],(1000,100),replace=True
        )

        self.model.combine_prod_samples()

        self.assertEqual(
            self.model.combined_samples.sum(axis=0).mean(),
            3079.51
        )

    def test_saves_config(self):
        """
        Assert that the config is saved to the `self.outputfolder` of the 
        class, and that it's content is identical to TEST_CONFIG.
        """
        # Do the first 3 parts of perform_analysis()
        self.model.make_samples()
        self.model.combine_prod_samples()
        self.model.compute_simulated_midstream_emissions()
        
        # Make the outpath folder if it doesn't exist.
        if not os.path.exists(self.model.outfolder):
            os.mkdir(self.model.outfolder)

        # Save the input configs that were used for this run
        self.model.save_config()

        config = os.path.join(self.model.outfolder,"used_config.json")
        # Assert the config was written to this path
        self.assertTrue(os.path.exists(config))
        
        with open(config,"r") as f:
            # Load content which may include non-JSON-safe windows paths ("C:\path\to\file.csv")
            config = yaml.safe_load(f)

        # Assert the loaded config is the same as that used for the test
        self.assertEqual(config,TEST_CONFIG)
    
if __name__=="__main__":
    import unittest
    unittest.main()