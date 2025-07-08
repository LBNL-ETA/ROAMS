import numpy as np
import pandas as pd

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
KAIROS_PERMIAN_PLUME_FILENAME = "/Users/eneill/repos/ROAMS/data/analytica_permian_data/old_permian_plumedata.csv"
KAIROS_PERMIAN_EMISSIONS_FILENAME = "/Users/eneill/repos/ROAMS/data/analytica_permian_data/old_source_data.csv"

if __name__=="__main__":
    from datetime import datetime

    now = datetime.now()
    print(f"Starting run with at {now.hour}:{now.minute}:{now.second}")

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
        transition_point = None,
        partial_detection_correction=True,
        simulate_error = True,
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
        coverage_count = "coverage_count",
        outpath = "evan output",
        save_mean_dist = True,
    )

    r.perform_analysis()
    now = datetime.now()
    print(f"Run finished at {now.hour}:{now.minute}:{now.second}")