import pandas as pd
import numpy as np

from roams.aerial.input import AerialSurveyData
from roams.aerial.assumptions import power_correction, zero_out, normal

def get_aerial_survey(
    survey : AerialSurveyData,
    simulate_error=True,
    n_mc_samples=100,
    noise_fn = normal,
    handle_zeros = zero_out,
    correction_fn = power_correction,
    ) -> np.ndarray:
    """
    A function that can take a record of covered sources and corresponding 
    plumes (it's OK if there are plumes that dont correspond to any listed source - 
    they are excluded), and samples the plume observations, accounting for 
    observed intermittency, before applying noise, corrections, and creating 
    additional partial detection samples.

    Args:
        survey (AerialSurveyData):
            An instance of the AerialSurveyData class, or a child thereof.

        simulate_error (bool, optional): 
            Whether or not to simulate error by introducing normal noise to 
            the sampled aerial emissions.
            Defaults to True.

        n_mc_samples (int, optional): 
            The number of monte-carlo sampling iterations to do. This 
            controls the number of columns that the resulting table will 
            have.
            Defaults to 100.

        correction_fn (function, optional): 
            The function that deterministically corrects for measurement bias 
            in the sampled emissions values.
            Defaults to power_correction.

    Returns:
        tuple:
            A tuple of (aerial sample, wind-normalized sample) tables. Each 
            table has n_mc_samples columns - each corresponding to its own 
            monte carlo iteration (consistent between the two), and a number 
            of rows equal to the number of unique sources in the input tables.
            Based on the input arguments, these emissions have noise applied, 
            and may be bias corrected. The wind-normalized emissions values
            will not be altered in any way from their original.
    """
    # max_count = maximum number of coverages
    max_count = survey.production_sources[survey.coverage_count].max()
    
    # df = DataFrame with columns [0, 1, ..., <max coverage - 1>, "coverage_count"]
    # and a number of rows equal to the number of unique sources.
    df = survey.production_sources[[survey.source_id_col,survey.coverage_count]].copy()
    df.set_index(survey.source_id_col,inplace=True)

    plume_data = survey.production_plumes.copy()
    
    # Create a column in common wind-normalized emissions units
    plume_data["windnorm_em"] = survey.prod_plume_wind_norm

    # Create an emissions rate column in common emissions rate units
    plume_data["em"] = survey.prod_plume_emissions

    # get separate lists of the observed wind-normalized emissions rates and wind speeds
    emiss_and_windnorm_emiss = (
        plume_data
        .groupby(survey.source_id_col)
        [["em","windnorm_em"]]
        .agg(list)
    )

    # For each possible coverage instance...
    for col in range(max_count):

        # Instantiate the colum representing the `col`th coverage instance of each source
        df[col] = np.nan

        # Assign the nth observed (emissions, wind-normalized emissions) 
        # value if the nth value exists (i.e., it was observed and emitting), otherwise nan
        df[col] = emiss_and_windnorm_emiss.apply(
            lambda row: 
                # nth (emissions, wind-normalized emissions) if nth observation exists
                (row["em"][col],row["windnorm_em"][col]) 
                # else nan
                if len(row["em"])>col else np.nan,
            axis=1,
        )
    
        # For any observations remaining nan that should still count as coverage instance, set them to 0 (i.e., it was observed and was not emitting)
        df.loc[(df[survey.coverage_count]>col) & (df[col].isna()),col] = 0
    
    # Drop the coverage_count column, no longer needed
    df.drop(columns=survey.coverage_count,inplace=True)

    # Sample each row N times, excluding NaN values
    # This results in an `emission_source_id`-indexed series whose values are each a 1D np.array type, each representing the sampled observations
    # The values in the sampled 1-D array can be 0 (no emissions observed), or a (wind-normalized emissions, wind speed) pair.
    sample = df.apply(lambda row: row.sample(n_mc_samples,replace=True,weights=1*(~row.isna())).values,axis=1)

    # Emissions rate = 1st entry in tuple, where present
    emissions = np.array(
        sample.apply(lambda v: [s[0] if type(s)==tuple else s for s in v])
        .values
        .tolist()
    )

    # Wind-normalized emissions rate = 2nd entry in tuple, where present
    wind_normalized_em = np.array(
        sample.apply(lambda v: [s[1] if type(s)==tuple else s for s in v])
        .values
        .tolist()
    )

    # Apply given correction, if not None
    if correction_fn is not None:
        emissions = correction_fn(emissions)

    if simulate_error:
        emissions = noise_fn(emissions)
    
    # Use function to handle 0s
    emissions = handle_zeros(emissions,noise_fn)

    return emissions, wind_normalized_em