import os

from matplotlib import pyplot as plt

import numpy as np
import pandas as pd

def gen_plots(emissions_dists : np.ndarray, extra_emissions_for_cdf: np.ndarray, transition_pt : float, outpath : str):
    """
    Take a table of the overall combined emissions distributions, and turn them 
    into plots that include a vertical line to indicate the average transition 
    point.

    Args:
        emissions_dists (np.ndarray):
            A (# infrastructure)x (num MC iterations) table holding the 
            combined simulated + aerial + partial detection samples.
        
        extra_emissions_for_cdf (np.ndarray):
            A (# infrastructure)x(num MC iterations) table holding emissions
            values to be added directly to the cumulative emissions 
            distribution (intended to be used if partial detection is being 
            accounted for in this way, and for literally no other reason.)

        transition_pt (float):
            The average transition point across all MC iterations.
        
        outpath (str):
            The folder into which the resulting plot should be saved.
    """    
    cumsum = emissions_dists.cumsum(axis=0) + extra_emissions_for_cdf.cumsum(axis=0)
    cumsum_pct = 100*(1-cumsum/cumsum.max(axis=0))

    x = np.nanmean(emissions_dists,axis=1)
    y = np.nanmean(cumsum_pct,axis=1)
    plt.step(x,y)
    plt.semilogx()
    max_val = 0
    plt.vlines(
        transition_pt, 0, 100, color='black', linestyle='dotted', 
        label=f'transition point ({transition_pt})'
    )
    max_val = max(x.max(), max_val)
    plt.xlim(1e-2, max_val)
    plt.grid(True)
    plt.ylabel("Fraction of Total Emissions at least x")
    plt.xlabel("Emissions Rate (kg/h)")
    plt.legend()

    plt.savefig(os.path.join(outpath, "combined_cumulative.svg"))
    plt.savefig(os.path.join(outpath, "combined_cumulative.png"))

def summarize(
        total_aerial_sample : np.ndarray,
        only_aerial_sample : np.ndarray,
        partial_detec_sample : np.ndarray,
        extra_emissions_for_cdf : np.ndarray,
        simulated_sample : np.ndarray,
        combined_sample : np.ndarray,
        transition_point : np.ndarray,
) -> pd.DataFrame:
    """
    Return a dataframe with some summary statistics.

    Args:
        total_aerial_sample (np.ndarray): _description_
        only_aerial_sample (np.ndarray): _description_
        partial_detec_sample (np.ndarray): _description_
        simulated_sample (np.ndarray): _description_
        combined_sample (np.ndarray): _description_
        transition_point (np.ndarray): _description_

    Returns:
        pd.DataFrame: _description_
    """
    N = len(transition_point)
    prod_summary = pd.DataFrame(
        np.nan,
        index=[
            "Aerial Only Total CH4 emissions (t/h)",
            "Partial Detection Total CH4 emissions (t/h)",
            "Combined Aerial + Partial Detection Total CH4 emissions (t/h)",
            "Simulated Total CH4 emissions (t/h)", 
            "Overall Combined Total CH4 emissions (t/h)",
            "Transition Point (kg/h)"
        ],
        columns=pd.MultiIndex.from_product(
            [["By Itself","Accounting for Transition Point"],["Avg","Std Dev"]],
        )
    )
    
    sum_emiss_aerial = only_aerial_sample.sum(axis=0)
    prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_aerial.mean()*1e-3
    prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_aerial.std()*1e-3
    sum_emiss_aerial_abovetp = np.array([only_aerial_sample[:,n][only_aerial_sample[:,n]>=transition_point[n]].sum() for n in range(N)])
    prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("Accounting for Transition Point","Avg")] = sum_emiss_aerial_abovetp.mean()*1e-3
    prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("Accounting for Transition Point","Std Dev")] = sum_emiss_aerial_abovetp.std()*1e-3
    
    # In this addition, the expectation is the only one or other is contributing to the sum
    sum_emiss_partial = partial_detec_sample.sum(axis=0) + extra_emissions_for_cdf.sum(axis=0)
    prod_summary.loc["Partial Detection Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_partial.mean()*1e-3
    prod_summary.loc["Partial Detection Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_partial.std()*1e-3
    
    # Like above, in this addition there are either additional copies of sampled emissions in `total_aerial_sample`, or the total missing emissions are included in `extra_emissions_for_cdf`.
    sum_emiss_aer_comb = total_aerial_sample.sum(axis=0) + extra_emissions_for_cdf.sum(axis=0)
    prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_aer_comb.mean()*1e-3
    prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_aer_comb.std()*1e-3
    sum_emiss_aer_comb_abovetp = sum_emiss_aerial_abovetp + np.array([extra_emissions_for_cdf[:,n][only_aerial_sample[:,n]>=transition_point[n]].sum() for n in range(N)])
    prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("Accounting for Transition Point","Avg")] = sum_emiss_aer_comb_abovetp.mean()*1e-3
    prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("Accounting for Transition Point","Std Dev")] = sum_emiss_aer_comb_abovetp.std()*1e-3
    
    sum_emiss_sim = simulated_sample.sum(axis=0)
    prod_summary.loc["Simulated Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_sim.mean()*1e-3
    prod_summary.loc["Simulated Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_sim.std()*1e-3
    sum_emiss_sim_belowtp = np.array([sum_emiss_sim[:,n][sum_emiss_sim[:,n]<transition_point[n]].sum() for n in range(N)])
    prod_summary.loc["Simulated Total CH4 emissions (t/h)",("Accounting for Transition Point","Avg")] = sum_emiss_sim_belowtp.mean()*1e-3
    prod_summary.loc["Simulated Total CH4 emissions (t/h)",("Accounting for Transition Point","Std Dev")] = sum_emiss_sim_belowtp.std()*1e-3
    
    sum_emiss_all_comb = combined_sample.sum(axis=0)
    prod_summary.loc["Overall Combined Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_all_comb.mean()*1e-3
    prod_summary.loc["Overall Combined Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_all_comb.std()*1e-3

    prod_summary.loc["Transition Point (kg/h)",("By Itself","Avg")] = transition_point.mean()
    prod_summary.loc["Transition Point (kg/h)",("By Itself","Std Dev")] = transition_point.std()

    return prod_summary