import logging

from roams.analysis import ROAMSModel
from roams.aerial.partial_detection import PoD_bin
from roams.aerial.assumptions import power_correction

COVERED_PRODUCTIVITY_FILE = "/Users/eneill/repos/ROAMS/data/production/Covered_gas_prod_percentiles_all_basins_by_well_Kairos_NM_Permian20221021.csv"
SUB_MDL_FILENAME = "/Users/eneill/repos/ROAMS/data/Rutherford_million_samples_PERMIAN_20220917.xlsx" # <- Used in Analytica
# SUB_MDL_FILENAME = "/Users/eneill/repos/ROAMS/data/Stanford_Modeling_Results_20220822.xlsx" # <- Used by Ross
SUB_MDL_SHEETNAME = "Permian_sitelevel"

# This is the permian plume/source data Ross was using, which is maybe more recent than Analytica
# KAIROS_PERMIAN_PLUME_FILENAME = "/Users/eneill/repos/ROAMS/data/stanford_nm_data_2021/plume_table.csv"
# KAIROS_PERMIAN_EMISSIONS_FILENAME = "/Users/eneill/repos/ROAMS/data/stanford_nm_data_2021/emission_source_table.csv"

# This is the permian "well" plume data ripped out of analytica, with spoofed source data that describes everything as wells
# (i.e. only the production subset of the data Analytica was using)
# KAIROS_PERMIAN_PLUME_FILENAME = "/Users/eneill/repos/ROAMS/data/analytica_permian_data/old_permian_plumedata.csv"
# KAIROS_PERMIAN_EMISSIONS_FILENAME = "/Users/eneill/repos/ROAMS/data/analytica_permian_data/old_source_data.csv"

# This is all the permian data being used by Analytica described as "Kairos Permian", but ONLY the first plumes
KAIROS_PERMIAN_PLUME_FILENAME = '/Users/eneill/repos/ROAMS/data/no random noise data/plumes_20250702.csv'
KAIROS_PERMIAN_EMISSIONS_FILENAME = '/Users/eneill/repos/ROAMS/data/no random noise data/sources_20250702.csv'

if __name__=="__main__":
    log = logging.getLogger("run_nm_permian")
    log.setLevel(logging.INFO)

    from argparse import ArgumentParser
    parser = ArgumentParser(
        description = "Script to run the ROAMS model for the New Mexico Permian campaign"
    )

    parser.add_argument("--debug",action="store_true",default=False,help="Whether to log debug messages to the console (they are always logged to a log file)")

    args = parser.parse_args()
    loglevel = logging.DEBUG if args.debug else logging.INFO

    log.info("Starting run")

    r = ROAMSModel(
        simmed_emission_file = SUB_MDL_FILENAME,
        simmed_emission_sheet = SUB_MDL_SHEETNAME,
        plume_file = KAIROS_PERMIAN_PLUME_FILENAME, 
        source_file = KAIROS_PERMIAN_EMISSIONS_FILENAME,
        covered_productivity_file = COVERED_PRODUCTIVITY_FILE,
        num_wells_to_simulate = 18030,
        well_visit_count = 81564,
        wells_per_site = 1.2,
        stratify_sim_sample = True,
        n_mc_samples = 100,
        prod_transition_point = None,
        midstream_transition_point = 40, # kgh
        partial_detection_correction=True,
        simulate_error = False,
        PoD_fn = PoD_bin,
        correction_fn = power_correction,
        source_id_name = "emission_source_id",
        cutoff_col = None,
        em_col = None,
        em_unit = None,
        wind_norm_col = "wind_independent_emission_rate_kghmps",
        wind_norm_unit = "kgh:mps",
        wind_speed_col = "wind_mps",
        wind_speed_unit = "mps",
        asset_col="asset_type",
        prod_asset_type = ("Well site",),
        midstream_asset_type = ("Pipeline","Compressor station","Unknown","Gas processing plant"),
        coverage_count = "coverage_count",
        foldername = "evan output",
        save_mean_dist = True,
        loglevel = loglevel
    )

    r.perform_analysis()
    
    log.info("Run finished")