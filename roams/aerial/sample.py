import pandas as pd
import numpy as np

from roams.aerial.partial_detection import PoD_bin
from roams.aerial.assumptions import power_correction, zero_out, normal

def get_aerial_sample(
    plumes = None,
    sources = None,
    simulate_error=True,
    n_mc_samples=100,
    noise_fn = normal,
    handle_zeros = zero_out,
    correction_fn = power_correction,
    wind_norm_col="wind_independent_emission_rate_kghmps",
    wind_speed_col="wind_mps",
    coverage_count="coverage_count",
    ) -> np.ndarray:
    """
    A function that can take a record of covered sources and corresponding 
    plumes (it's OK if there are plumes that dont correspond to any listed source - 
    they are excluded), and samples the plume observations, accounting for 
    observed intermittency, before applying noise, corrections, and creating 
    additional partial detection samples.

    Args:
        plumes (pd.DataFrame, optional): 
            The table holding the plume-level data. 
            Defaults to None.

        sources (pd.DataFrame, optional): 
            The table holding the source-level data. It's expected that the 
            index of this table is the unique source id.
            Defaults to None.

        simulate_error (bool, optional): 
            Whether or not to simulate error by introducing normal noise to 
            the sampled aerial emissions.
            Defaults to SIMULATE_ERROR.

        n_mc_samples (int, optional): 
            The number of monte-carlo sampling iterations to do. This 
            controls the number of columns that the resulting table will 
            have.
            Defaults to N.

        correction_fn (function, optional): 
            The function that deterministically corrects for measurement bias 
            in the sampled emissions values.
            Defaults to power_correction.

        wind_norm_col (str, optional): 
            The name of the column in the plume file that holds the wind-normalized 
            emissions values. 
            Defaults to "wind_independent_emission_rate_kghmps".

        wind_speed_col (str, optional): 
            The name of the column in the plumes dataset that contain the wind 
            speed values.  
            Defaults to "wind_mps".

        coverage_count (str, optional): 
            The name of the column in the source file that describes how many 
            times each source was observed during the survey.
            Defaults to "coverage_count".


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
    max_count = sources[coverage_count].max()
    
    # df = DataFrame with columns [0, 1, ..., <max coverage - 1>, "coverage_count"]
    # and a number of rows equal to the number of unique sources.
    df = pd.DataFrame(np.nan,columns=range(max_count),index=sources.index)
    df[coverage_count] = sources[coverage_count]

    # get separate lists of the observed wind-normalized emissions rates and wind speeds
    emissions_and_wind = (
        plumes
        .groupby("emission_source_id")
        [[wind_norm_col,wind_speed_col]]
        .agg(list)
    )
    # Restrict the plume data to only sources in the source data.
    emissions_and_wind = emissions_and_wind.loc[sources.index]

    # For each possible coverage instance...
    for col in range(max_count):
        # Assign the nth observed (wind-normalized, wind_mps) value if the nth value exists (i.e., it was observed and emitting), otherwise nan
        df[col] = emissions_and_wind.apply(
            lambda row: 
                # nth (wind normalized emm, wind speed) if nth observation exists
                (row[wind_norm_col][col],row[wind_speed_col][col]) 
                # else nan
                if len(row[wind_speed_col])>col else np.nan,
            axis=1,
        )
    
        # For any observations remaining nan that should still count as coverage instance, set them to 0 (i.e., it was observed and was not emitting)
        df.loc[(df[coverage_count]>col) & (df[col].isna()),col] = 0
    
    # Drop the coverage_count column, no longer needed
    df.drop(columns=coverage_count,inplace=True)

    # Sample each row N times, excluding NaN values
    # This results in an `emission_source_id`-indexed series whose values are each a 1D np.array type, each representing the sampled observations
    # The values in the sampled 1-D array can be 0 (no emissions observed), or a (wind-normalized emissions, wind speed) pair.
    sample = df.apply(lambda row: row.sample(n_mc_samples,replace=True,weights=1*(~row.isna())).values,axis=1)

    # Wind normalized emissions = 1st entry in tuple, where present
    wind_normalized_em = np.array(
        sample.apply(lambda v: [s[0] if type(s)==tuple else s for s in v])
        .values
        .tolist()
    )

    # Wind speed = 2nd entry in tuple, where present
    wind = np.array(
        sample.apply(lambda v: [s[1] if type(s)==tuple else s for s in v])
        .values
        .tolist()
    )

    # This is definition of emissions as a function of wind and wind-normalized emissions
    # TODO (in input layer): make sure that units always align here
    emissions = wind_normalized_em * wind
    # Apply given correction, if not None
    if correction_fn is not None:
        emissions = correction_fn(emissions)

    if simulate_error:
        # TODO : This has to be factored. Create a function that does this? take shape -> return noise multiplier? Or what?
        emissions = noise_fn(emissions)
    
    # Use function to handle 0s
    emissions = handle_zeros(emissions,noise_fn)

    return emissions, wind_normalized_em