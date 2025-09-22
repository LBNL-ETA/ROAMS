import logging
import os
from unittest import TestCase

import numpy as np

from roams.conf import REPO_DIR
from roams.model import ROAMSModel
from roams.transition_point import find_transition_point

# These validation files are a small subset of data used in a validation 
# exercise, whose intended outcome under expected behavior and abscense of 
# randomness is known.
SUB_MDL_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_simulated_stratified.csv")
PLUME_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_plumes.csv")
SOURCE_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_sources.csv")
STATE_GHGI_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_stateghgi.csv")
STATE_PROD_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_stateprod.csv")
NATNL_PROD_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_natnlprod.csv")
GHGI_GASPROD_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_ghgi_gasprod.csv")
GHGI_OILPROD_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_ghgi_oilprod.csv")
GHGI_GASPROD_UNC_FILENAME = os.path.join(REPO_DIR,"roams","tests","validation","_validation_ghgi_gasunc.csv")

INPUT = {
    "sim_em_file" : SUB_MDL_FILENAME,
    "sim_em_col" : "sum of emissions [kg/hr]",
    "sim_em_unit" : "kg/hr",
    "sim_prod_col" : None, # not providing simulated production b/c no stratification
    "sim_prod_unit" : None,
    "plume_file" : PLUME_FILENAME, 
    "source_file" : SOURCE_FILENAME,
    "source_id_name" : "emission_source_id",
    "asset_col" : "asset_type",
    "asset_groups": {"production":["Well site"], "midstream": ["Pipeline","Gas processing plant","Compressor station","Unknown"]},
    "coverage_count" : "coverage_count",
    "aerial_em_col" : None,
    "aerial_em_unit" : None,
    "wind_norm_col" : "wind_independent_emission_rate_kghmps",
    "wind_norm_unit" : "kgh:mps",
    "wind_speed_col" : "wind_mps",
    "wind_speed_unit" : "mps",
    "cutoff_col" : None,
    "covered_productivity_dist_file" : None, # don't provide covered productivity. Really really difficult to backwards engineer for stratification
    "covered_productivity_dist_col" : None,
    "covered_productivity_dist_unit" : None,
    "state_ghgi_file" : STATE_GHGI_FILENAME,
    "ghgi_co2eq_unit" : "MMT/yr",
    "production_state_est_file" : STATE_PROD_FILENAME,
    "production_natnl_est_file" : NATNL_PROD_FILENAME,
    "production_est_unit" : "mscf/yr",
    "ghgi_ch4emissions_ngprod_file" : GHGI_GASPROD_FILENAME,
    "ghgi_ch4emissions_ngprod_uncertainty_file" : GHGI_GASPROD_UNC_FILENAME,
    "ghgi_ch4emissions_petprod_file" : GHGI_OILPROD_FILENAME,
    "ghgi_ch4emissions_unit" : "kt/yr",
    "year" : 2019,
    "state" : "NM",
    "frac_aerial_midstream_emissions" : 0.2984769,
    "gas_composition" : {"c1":.9},
    "num_wells_to_simulate" : 1000,
    "well_visit_count" : 500,
    "wells_per_site" : 2.,
    "total_covered_ngprod_mcfd": 2703944,
    "total_covered_oilprod_bbld": 732226,
    "random_seed": 1,
    "stratify_sim_sample" : False,
    "n_mc_samples" : 100,
    "prod_transition_point" : None,
    "midstream_transition_point" : 40, 
    "partial_detection_correction" : True,
    "correction_fn": "power_correction",
    "noise_fn" : {"name":"normal","loc":1.0,"scale":0.0}, # There should be no noise.
    "foldername" : "_deterministic_validation_exercise",
    "save_mean_dist" : False,
    "loglevel" : logging.WARNING,
}

class DeterministicROAMSModel(ROAMSModel):
    """
    A ROAMSModel with randomness mostly taken out.

    Aerial samples will still be generated, but the underlying aerial data 
    has intermittency removed by virtue of having only one plume per source, 
    and setting the coverage count to 1 for all sources.
    """
    
    def make_simulated_sample(self) -> np.ndarray:
        """
        Rather than sampling stratified simulated emissions into the 
        simulated sample table, just copy the list of emissions for each 
        iteration.

        The number of observations has to match the "number of wells to simulated"
        in the input.

        Returns:
            np.ndarray
        """
        sub_mdl_dist = self.cfg.prodSimResults.simulated_emissions.copy()

        sub_mdl_sample = np.tile(
            sub_mdl_dist,(self.cfg.n_mc_samples,1)
        ).T

        return sub_mdl_sample
    
    def combine_prod_samples(self):
        emiss, pd_correction = self.aerial_samples["production"]

        aerial_cumsum = emiss.cumsum(axis=0) + pd_correction.cumsum(axis=0)
        
        # Convert it into a decreasing cumulative total
        aerial_cumsum = aerial_cumsum.max(axis=0) - aerial_cumsum
        
        sim_data = np.sort(self.simulated_sample,axis=0)
        simmed_cumsum = sim_data.cumsum(axis=0)
        
        # Convert into decreasing cumulative total
        simmed_cumsum = simmed_cumsum.max(axis=0) - simmed_cumsum
        
        if self.cfg.prod_transition_point is None:
                self.prod_tp = find_transition_point(
                    aerial_x = emiss,
                    aerial_y = aerial_cumsum,
                    sim_x = sim_data,
                    sim_y = simmed_cumsum,
                )
        elif isinstance(self.cfg.prod_transition_point,(int,float,)):
            self.prod_tp = np.array([self.cfg.prod_transition_point]*self.cfg.n_mc_samples)

        self.prod_combined_samples = self.simulated_sample.copy()
        pd_samples = np.zeros(self.prod_combined_samples.shape)

        # For each of the n_samples columns, replace emissions below transition point with 
        # samples (w/ replacement) from the simulated values < transition point
        for n in range(self.cfg.n_mc_samples):
            
            # Get the transition point for this MC run
            tp = self.prod_tp[n]
            
            # Set simulated emissions above TP to 0
            self.prod_combined_samples[self.prod_combined_samples[:,n]>=tp,n] = 0

            # Get the aerial sample above transition point and corresponding partial detection
            aerial_sample = emiss[emiss[:,n]>=tp,n]
            pd_emissions = pd_correction[emiss[:,n]>=tp,n]

            # For all preceding indices, insert random simulated emissions below the transition point
            # self.combined_samples[:idx_above_transition,n] = sim_below_transition[-min(len(sim_below_transition),idx_above_transition):]
            self.prod_combined_samples[:len(aerial_sample),n] = aerial_sample
            pd_samples[:len(aerial_sample),n] = pd_emissions
        
        # Re-sort the newly combined records.
        combined_sort_idx = self.prod_combined_samples.argsort(axis=0)
        for n in range(self.cfg.n_mc_samples):
            # Sort the combined samples column-wise
            self.prod_combined_samples[:,n] = self.prod_combined_samples[combined_sort_idx[:,n],n]

            # Sort the corresponding extra_emissions_for_cdf
            pd_samples[:,n] = pd_samples[combined_sort_idx[:,n],n]

        self.prod_partial_detection_emissions = pd_samples
    
class ROAMSValidationTests(TestCase):
    """
    A class to run the analysis on some dummy inputs, and assert that 
    specific results are being generated.
    """

    @classmethod
    def setUpClass(cls):
        # Set a model on the class and run it
        cls.model = DeterministicROAMSModel(INPUT)
        cls.model.perform_analysis()

    def test_prod_aerial_dists(self):
        """
        Assert that the aerial production distribution is producing the 
        expected value, as well as correct associated partial 
        detection values.
        """
        prod_emiss, prod_pd = self.model.aerial_samples["production"]

        # Total aerial emissions, regardless of transition point
        np.testing.assert_array_almost_equal(
            prod_emiss.sum(axis=0)*1e-3,
            np.array([76.8050266393258]*100),
            9
        )
        
        # Total aerial emissions, above transition point only
        np.testing.assert_array_almost_equal(
            # [sum of ith emissions≥ith transition point for i in range(100)]
            np.array([prod_emiss[prod_emiss[:,i]>=self.model.prod_tp[i],i].sum() for i in range(100)])*1e-3,
            np.array([76.591769194947]*100),
            9
        )
        
        # Partial detection emissions, accounting for transition point
        # (no record not accounting for it)
        np.testing.assert_array_almost_equal(
            np.array([prod_pd[prod_emiss[:,i]>=self.model.prod_tp[i],i].sum() for i in range(100)])*1e-3,
            np.array([4.1519379448231]*100),
            9
        )

    def test_midstream_aerial_dists(self):
        """
        Assert that the aerial midstream distribution is producing the 
        expected value, as well as correct associated partial 
        detection values.
        """
        mid_emiss, mid_pd = self.model.aerial_samples["midstream"]

        # Total aerial emissions, regardless of transition point
        np.testing.assert_array_almost_equal(
            mid_emiss.sum(axis=0)*1e-3,
            np.array([15.1410791296653]*100),
            9
        )
        
        # Total aerial emissions, above transition point only
        np.testing.assert_array_almost_equal(
            # [sum of ith emissions≥transition point for i in range(100)]
            np.array([mid_emiss[mid_emiss[:,i]>=self.model.cfg.midstream_transition_point,i].sum() for i in range(100)])*1e-3,
            np.array([15.1410791296653]*100),
            9
        )
        
        # Partial detection emissions, accounting for transition point
        # (no record not accounting for it)
        np.testing.assert_array_almost_equal(
            mid_pd.sum(axis=0)*1e-3,
            np.array([0.944727993180192]*100),
            9
        )

    def test_simulated_dist(self):
        """
        Assert that the simulated distribution results in the expected 
        characterization by itself and when accounting for the transition point.
        """
        # Total aerial emissions, regardless of transition point
        np.testing.assert_array_almost_equal(
            self.model.simulated_sample.sum(axis=0)*1e-3,
            np.array([5.237061385025]*100),
            9
        )
        
        # Total aerial emissions, above transition point only
        np.testing.assert_array_almost_equal(
            # [sum of ith emissions < ith transition point for i in range(100)]
            np.array([self.model.prod_combined_samples[self.model.prod_combined_samples[:,i]<self.model.prod_tp[i],i].sum() for i in range(100)])*1e-3,
            np.array([3.036252812503]*100),
            9
        )

    def test_prod_tp(self):
        """
        Assert that the production transition point is the expected 
        value in all MC iterations
        """
        self.assertTrue((self.model.prod_tp==57).all())

    def test_midstream_ghgi_est(self):
        """
        Assert that the midstream emissions estimate based on GHGI and 
        production data tables are producing the expected values.
        """
        self.assertAlmostEqual(
            self.model.total_ch4_midstream_emissions["mid"]*1e-3,
            10.1663925943552,
            9
        )
        self.assertAlmostEqual(
            self.model.total_ch4_midstream_emissions["low"]*1e-3,
            8.33644192737126,
            9
        )
        self.assertAlmostEqual(
            self.model.total_ch4_midstream_emissions["high"]*1e-3,
            11.9963432613391,
            9
        )
        
        self.assertAlmostEqual(
            self.model.submdl_ch4_midstream_emissions["mid"]*1e-3,
            7.1319592486091,
            9
        )
        self.assertAlmostEqual(
            self.model.submdl_ch4_midstream_emissions["low"]*1e-3,
            5.84820658385946,
            9
        )
        self.assertAlmostEqual(
            self.model.submdl_ch4_midstream_emissions["high"]*1e-3,
            8.41571191335874,
            9
        )

    
    @classmethod
    def tearDownClass(cls):
        # Remove the written outputs, if any
        f = cls.model.outfolder
        if os.path.exists(f):
            for file in os.listdir(f):
                os.remove(os.path.join(f, file))
            os.rmdir(f)

if __name__=="__main__":
    # model = DeterministicROAMSModel(INPUT)
    # model.perform_analysis()
    import unittest
    unittest.main()