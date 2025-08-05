import os

import logging

from roams.model import ROAMSModel
from roams.conf import REPO_DIR

DUMMY_DATA_FOLDER = os.path.join(REPO_DIR,"data","dummy")

SIMULATED_PROD_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"simulated_prod.csv")
PLUME_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"plumes.csv")
SOURCE_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"sources.csv")

STATE_GHGI_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"state_ghgi.csv")
NATNL_NGPROD_GHGI_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"natl_ng_ch4_ghgi.csv")
NATNL_NGPROD_UNCERT_GHGI_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"natl_ng_ch4_uncertainty_ghgi.csv")
NATNL_PETPROD_GHGI_FILENAME = os.path.join(DUMMY_DATA_FOLDER,"natl_pet_ch4_ghgi.csv")
STATE_PROD_FILE = os.path.join(DUMMY_DATA_FOLDER,"state_production_est.csv")
NATNL_PROD_FILE = os.path.join(DUMMY_DATA_FOLDER,"natnl_production_est.csv")

DUMMY_INPUT = {
        "sim_em_file" : SIMULATED_PROD_FILENAME,
        "sim_em_col" : "sum of emissions [kg/hr]",
        "sim_em_unit" : "kg/hr",
        "sim_prod_col" : None, # not providing simulated production b/c no stratification
        "sim_prod_unit" : None,
        "plume_file" : PLUME_FILENAME, 
        "source_file" : SOURCE_FILENAME,
        "source_id_name" : "emission_source_id",
        "asset_col" : "asset_type",
        "prod_asset_type" : ["Well site"],
        "midstream_asset_type" : ["Pipeline",],
        "coverage_count" : "coverage_count",
        "aerial_em_col" : None,
        "aerial_em_unit" : None,
        "wind_norm_col" : "wind_independent_emission_rate_kghmps",
        "wind_norm_unit" : "kgh:mps",
        "wind_speed_col" : "wind_mps",
        "wind_speed_unit" : "mps",
        "cutoff_col" : None,
        "covered_productivity_file" : None, # don't provide covered productivity. Really really difficult to backwards engineer for stratification
        "covered_productivity_col" : None,
        "covered_productivity_unit" : None,
        "state_ghgi_file" : STATE_GHGI_FILENAME,
        "ghgi_co2eq_unit" : "MMT/yr",
        "enverus_state_production_file" : STATE_PROD_FILE,
        "enverus_natnl_production_file" : NATNL_PROD_FILE,
        "enverus_prod_unit" : "mscf/yr",
        "ghgi_ch4emissions_ngprod_file" : NATNL_NGPROD_GHGI_FILENAME,
        "ghgi_ch4emissions_ngprod_uncertainty_file" : NATNL_NGPROD_UNCERT_GHGI_FILENAME,
        "ghgi_ch4emissions_petprod_file" : NATNL_PETPROD_GHGI_FILENAME,
        "ghgi_ch4emissions_unit" : "kt/yr",
        "year" : 1900,
        "state" : "TX",
        "frac_aerial_midstream_emissions": 0.25,
        "frac_production_ch4" : .9,
        "num_wells_to_simulate" : 1000,
        "well_visit_count" : 500,
        "wells_per_site" : 2.,
        "total_covered_ngprod_mcfd": 1_000_000,
        "random_seed": 1,
        "stratify_sim_sample" : False,
        "n_mc_samples" : 100,
        "prod_transition_point" : None,
        "midstream_transition_point" : 40, 
        "partial_detection_correction" : True,
        "simulate_error" : False,
        "foldername" : "dummy data run",
        "save_mean_dist" : True,
        "loglevel" : None,
}

if __name__=="__main__":
    log = logging.getLogger("run_dummy_data")
    log.setLevel(logging.INFO)

    log.info("Starting run")

    r = ROAMSModel(DUMMY_INPUT)

    r.perform_analysis()
    
    log.info("Run finished")