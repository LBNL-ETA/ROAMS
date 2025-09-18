import logging

import numpy as np
import pandas as pd

from roams.constants import COMMON_PRODUCTION_UNITS

# QUANTILES = bins in deciles from 0 -> 50th percentile, then 5% bins up to 95th percentile.
# 1% size bins 95 -> 99, then one .5% bin, then .1% bins to 100.
QUANTILES =  (0,.1,.2,.3,.4,.5,.55,.6,.65,.7,.75,.8,.85,.9,.95,.96,.97,.98,.99,.995,.996,.997,.998,.999,1.)

log = logging.getLogger("roams.aerial.stratify.stratify_sample")

def stratify_sample(
        sim_emissions : np.ndarray,
        sim_production : np.ndarray,
        covered_productivity : np.ndarray,
        n_infra : int,
        n_mc_samples : int,
        quantiles : tuple[float] = QUANTILES,
    ) -> np.ndarray:
    """
    Take an array of simulated emissions and corresponding production, 
    and perform a stratified sampling of the emissions into a 
    `n_infra` x `n_mc_iterations` size table.

    The process of stratification is intended to make it so that the 
    simulated emissions correspond to simulated productivity whose 
    distribution better matches the given covered productivity distribution.

    It begins by defining pre-specified quantiles of simulated productivity. 
    Using these quantile boundaries, the code then computes the fraction of 
    the covered productivity distribution that falls into each bin of 
    simulated productivity. It uses this fraction to then estimate a total 
    number of simulated infrastructure (n_infra) that should be represented 
    by sampling simulated emissions associated to the simulated productivity 
    in this bin.

    This process is repeated for each of the quantile bins specified in 
    the `quantiles` argument.

    Args:
        sim_emissions (np.ndarray):
            A 1-d array of simulated emissions (kg/h) in the whole basin, or 
            at least of an area that's not expected to be completely 
            representative of the infrastructure covered in the survey.

        sim_production (np.ndarray):
            Simulated production, whose values correspond index-wise to those 
            in sim_emissions. Should be in units identical to 
            `covered_productivity`.

        covered_productivity (np.ndarray):
            A 1-d array representing the best estimate distribution of actual 
            production in the surveyed area, in identical units to 
            `sim_production`. The values in this array should correspond to 
            productivity bounds of a uniform quantization of covered 
            productivity. For example, there could be 1000 values, each 
            representing the 0.1 percentile bound, the 0.2 percentile bound, 
            etc. Or there could be 100 values representing the 1% bound, the 
            2% bound, etc. The important things are that (a) each value 
            represents a bin of the same size, and that for best results, (b) 
            the size the bins is at most the size of the smallest bin in 
            `quantiles` (e.g., if the smallest `quantile` bin is a 0.1% 
            increment, covered_productivity should be at most in 0.1% 
            increments, i.e. at least 1000 values).

        n_infra (int):
            The size of the resulting array to return, intended to represent 
            the amount of infrastructure you're trying to create 
            estimates for.

        n_mc_samples (int):
            The number of monte-carlo iterations being done, which will 
            control the size of the returned table, specifically the number 
            of columns.

        quantiles (tuple[float], optional): 
            The quantile bins (including the limits 0 and 1) into which the 
            covered 
            Defaults to QUANTILES.

    Raises:
        ValueError: 
            When the length of simulated emissions and corresponding simulated 
            production don't match.

    Returns:
        np.ndarray: 
            A `n_infra` x `n_mc_iterations` table representing a 
            production-weighted sample of the simulated emissions data, for 
            each monte-carlo iteration of the ROAMS process.
    """    
    if len(sim_emissions)!=len(sim_production):
        raise ValueError(
            f"When trying to create a stratified sample of simulated emissions, "
            f"the code sees {len(sim_emissions)} simulated emissions and "
            f"{len(sim_production)} simulated production values. They should be "
            "the same - each index representing a value from the same simulated "
            "infrastructure."
        )
    
    if covered_productivity.max()>sim_production.max():
        log.warning(
            "The maximum covered productivity value "
            f"({covered_productivity.max()} {COMMON_PRODUCTION_UNITS}) is "
            "above the maximum simulated production value "
            f"({sim_production.max()} {COMMON_PRODUCTION_UNITS}). This could "
            "mean that the simulated emissions associated to the largest "
            "production bin will be over-represented."
        )
    
    # Get the simulated production quantiles (we will count the relative distribution of production in these bins)
    sim_quantiles = np.quantile(sim_production,quantiles)

    # Set the lower and upper bounds by hand (0th percentile and 100th percentile)
    sim_quantiles[0] = 0
    sim_quantiles[-1] = np.inf

    # Convert to pd.Series so that I can use groupby
    covered_productivity = pd.Series(covered_productivity)

    # Count the amount of simulated samples to take in each bin
    prod_count_by_bin = (
        covered_productivity
        .groupby(
            # pd.cut() returns the bins (labeled by right quantile boundary) for each observation
            pd.cut(
                covered_productivity,
                sim_quantiles,
                right=False,
                labels=quantiles[1:]
            ),
            observed=False
        )
        
        # Count the covered productivity in each quantile bin
        .count()

        # Scale the total number to match the n_infra you want
        * n_infra/len(covered_productivity)
    )

    if prod_count_by_bin[prod_count_by_bin<.5].sum()/n_infra >=.20:
        raise ValueError(
            f"At least 20% of {n_infra = } samples are supposed to be drawn "
            "from quantile bins that have so little weight, they'll be "
            "rounded down to 0 samples, leaving remaining bins over-"
            "represented. You probably should choose a different `quantile` "
            "value or revisit the provided simulated production/emissions "
            "data."
        )
    
    # round the result and return it as an int. Use (x+.5).astype(int) to get
    # closest integer rounding, not closest even integer rounding as 
    # implemented in numpy (astype(int) takes floor value).
    prod_count_by_bin = (prod_count_by_bin+.5).astype(int)

    # Because due to rounding there may be ± a few compared to the length we want (n_infra)
    # Change the value in the largest bin to correct for this.
    largest_group = prod_count_by_bin.idxmax()
    prod_count_by_bin.loc[largest_group] += (n_infra - prod_count_by_bin.sum())

    # Create the output array to fill then return
    stratified_sample = np.zeros((n_infra,n_mc_samples))

    # index for inserting into stratified_sample
    _i = 0
    for p_min, p_max, n_samples in zip(sim_quantiles[:-1],sim_quantiles[1:],prod_count_by_bin):
        
        # Define simulated emissions for simulated sites with appropriate production
        em = sim_emissions[(sim_production>p_min) & (sim_production<=p_max)]

        # sample with replacement from these simulated emissions
        sample = np.random.choice(em,(n_samples,n_mc_samples),replace=True)

        # Insert the sample into the stratified sample
        stratified_sample[_i:_i+len(sample),:] = sample

        # Increment the insertion index
        _i += len(sample)

    # Sort the resulting array of sampled emissions values column-wise
    stratified_sample.sort(axis=0)

    return stratified_sample