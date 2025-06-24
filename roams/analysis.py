import os

import pandas as pd
import numpy as np

from roams.aerial.assumptions import power_correction, normal, zero_out
from roams.aerial.sample import get_aerial_sample
from roams.aerial.preprocess import account_for_cutoffs
from roams.aerial.partial_detection import PoD_bin, get_partial_detection_samples

from roams.simulated.sample import stratify_sample

from roams.output import gen_plots

def cumdist(emissions_dist):
    cumsum = emissions_dist.cumsum(axis=0)
    cumsum_pct = 100*(1-cumsum/cumsum.max(axis=0))

    x = np.nanmean(emissions_dist,axis=1)
    y = np.nanmean(cumsum_pct,axis=1)

    return x, y

def find_transition_point(
    aerial_x,
    aerial_y,
    sim_x,
    sim_y,
    smoothing_window=11,
) -> np.ndarray:
    """
    Return the emissions rate at which the distribution of observed (and 
    corrected) aerial emissions rates matches that of the sub-minimum-
    detection level emissions values.

    This function will interpolate the cumulative emissions distribution for 
    both aerial emissions data and simulated emissions data into the same 
    [1, 1000] kgh range for each monte carlo sample (the columns of the 
    aerial data), and after smoothing the diffs in those interpolated timeseries,
    return the values for each MC iteration where the difference between the 
    two smoothed diffs changes sign (i.e. where the derivatives of the cumulative 
    distributions roughly match up.)

    Args:
        aerial_x (np.ndarray):
            The sampled aerial emissions, sorted by ascending size. The number 
            of columns should be the number of monte-carlo iterations.

        aerial_y (np.ndarray):
            The cumulative emissions distribution, perhaps but not necessarily 
            including accounting for partial detection. The index of x and y 
            are intended to correspond (i.e., the last entry in each column 
            should be 0, corresponding to the largest emissions value comprising
            the last contribution to the cumulative sum.). Like with the "x" 
            data, each column corresponds to one monte-carlo iteration.

        sim_x (np.ndarray):
            The sampled simulated emissions, sorted by ascending size. The number 
            of columns should be the number of monte-carlo iterations.

        sim_y (np.ndarray):
            The cumulative emissions distribution of the simulated x data. The 
            index of x and y simulated data are intended to correspond 
            (i.e., the last entry in each column should be 0, corresponding 
            to the largest emissions value comprising the last contribution to 
            the cumulative sum.). Like with the "x" data, each column 
            corresponds to one monte-carlo iteration.

        smoothing_window (int, optional): 
            The length of the moving-average window. The resulting smoothed 
            timeseries will be cut off to only include values centered in 
            the smoothing_window size. 
            Defaults to 10.

    Raises:
        IndexError: 
            When the input aerial and simulated data don't have the same 
            number of columns, so may not be representing monte-carlo 
            iterations in the correct way.
        
        ValueError:
            When, in any monte-carlo iteration, the smoothed cumulative 
            emissions distribution diff() of the aerial emissions is *higher* 
            than that of the simulated emissions. As a rule, the simulated 
            emissions skew much lower, so the distribution should begin 
            larger.

    Returns:
        np.ndarray:
            A 1x(num MC iterations) array, each of whose entries is roughly 
            the value of emissions at which the aerial distribution begins 
            to dominate the combined distribution (i.e. where the derivative 
            becomes greater.)
    """    
    if (aerial_x.shape[1]!=sim_x.shape[1]) or (aerial_y.shape[1]!=sim_y.shape[1]) or (aerial_x.shape[1]!=aerial_y.shape[1]):
        raise IndexError(
            "The columns in the aerial and simulated x and y data are intended to "
            "both be the number of monte-carlo iterations, but the two "
            "tables have different numbers of columns. You should make sure "
            "the correct data is being passed."
        )

    n_mc_runs = aerial_x.shape[1]
    max_interp_emiss = 1000
    window = np.array([1]*smoothing_window)

    xs = np.arange(5,max_interp_emiss,1)

    interp_aerial_dist = np.zeros((len(xs),aerial_x.shape[1]))
    interp_simmed_dist = np.zeros((len(xs),aerial_x.shape[1]))
    
    # Interpolate both cumulative emissions %s into the same x-values, and turn into diff
    # (approx. derivative.)
    for mc_run in range(n_mc_runs):
        a_x, a_y = aerial_x[:,mc_run], aerial_y[:,mc_run]
        interp_aerial_dist[:,mc_run] = np.interp(
            xs,
            a_x[~np.isnan(a_x)],
            a_y[~np.isnan(a_x)],
        )
        
        s_x, s_y = sim_x[:,mc_run], sim_y[:,mc_run]
        interp_simmed_dist[:,mc_run] = np.interp(
            xs,
            s_x[~np.isnan(s_x)],
            s_y[~np.isnan(s_x)],
        )
    # interp_aerial_dist = np.diff(interp_aerial_dist,axis=0)
    # interp_simmed_dist = np.diff(interp_simmed_dist,axis=0)
    
    # Make matrices intended to hold the moving-average smoothed derivatives (diffs)
    # of the aerial and simulated emissions distributions separately.
    smooth_aerial_dist = np.zeros(interp_aerial_dist.shape)
    smooth_simmed_dist = np.zeros(interp_simmed_dist.shape)
    
    # This was the method I was using. But analytica does the average over the past smoothing_window length
    # smooth_aerial_dist = np.zeros((interp_aerial_dist.shape[0]-smoothing_window+1,interp_aerial_dist.shape[1]))
    # smooth_simmed_dist = np.zeros((interp_simmed_dist.shape[0]-smoothing_window+1,interp_simmed_dist.shape[1]))
    # for col in range(smooth_aerial_dist.shape[1]):
    #     # Convolve performs the summation over the length of the window (mode="valid" functionally 0-pads)
    #     # Dividing by smoothing_window turns the sum into an average
    #     smooth_aerial_dist[:,col] = np.convolve(window,interp_aerial_dist[:,col],mode="valid")/smoothing_window
    #     smooth_simmed_dist[:,col] = np.convolve(window,interp_simmed_dist[:,col],mode="valid")/smoothing_window
    
    # interp_aerial_dist = interp_aerial_dist.cumsum(axis=0)
    # interp_simmed_dist = interp_simmed_dist.cumsum(axis=0)
    for w in range(len(xs)):
        wmin = max(0,w - smoothing_window)

        # Taking diff of the cumulative sum between index wmin and wmax gets you the sum of values between those points
        # Dividing by wmax-wmin gives you the average of values from [wmin:wmax]
        smooth_aerial_dist[w,:] = (interp_aerial_dist[wmin,:] - interp_aerial_dist[w,:])/max(1,w-wmin)
        smooth_simmed_dist[w,:] = (interp_simmed_dist[wmin,:] - interp_simmed_dist[w,:])/max(1,w-wmin)

    # Find x value at which the difference between the smoothed derivatives
    # switches signs (i.e. where they match, approximately).
    diff = smooth_aerial_dist - smooth_simmed_dist
    
    # Switch signs for any distributions that start negative, so that to 
    # measure transition point we only worry about going from pos-to-neg
    col_signs_to_switch = np.where(diff[0,:]<0)
    if len(col_signs_to_switch[0])>0:
        raise ValueError(
            f"In {len(col_signs_to_switch[0])} monte carlo iterations, the "
            "interpolated+smoothed aerial distribution starts *below* the "
            "interpolated and smoothed sub-detection-level sample. You should "
            "check that the smoothing and interpolating is correct."
        )

    # Always measure the transition point by where the sign switches
    # (and with the above correction, only care about pos-to-negative switch.)
    transition_point = np.argmax(diff>0,axis=0)
    
    # Return the x values at each first transition point.
    # Remove 1 from the transition_point index to account for the fact that the 
    # first value is always 0 in each smoothed distribution diff (think of it as corresponding to 4 kgh)
    return xs[transition_point-1]

class ROAMSModel:

    def __init__(
        self,
        simmed_emission_file,
        simmed_emission_sheet,
        plume_file, 
        source_file,
        covered_productivity_file,
        stratify_sim_sample = True,
        n_mc_samples = 100,
        num_wells_to_simulate = 18030,
        noise_fn = normal,
        handle_zeros = zero_out,
        transition_point = True,
        partial_detection_correction = "add samples",
        simulate_error = True,
        PoD_fn = PoD_bin,
        correction_fn = power_correction,
        wind_norm_col = "wind_independent_emission_rate_kghmps",
        wind_speed_col = "wind_mps",
        cutoff_col = "cutoff",
        coverage_count = "coverage_count",
        asset_type = ("Well site",),
        outpath="evan_output"
        ):

        self.simmed_emission_file = simmed_emission_file
        self.simmed_emission_sheet = simmed_emission_sheet
        self.plume_file = plume_file
        self.source_file = source_file
        self.covered_productivity_file = covered_productivity_file
        self.stratify_sim_sample = stratify_sim_sample
        self.n_mc_samples = n_mc_samples
        self.num_wells_to_simulate = num_wells_to_simulate
        self.noise_fn = noise_fn
        self.handle_zeros = handle_zeros
        self.transition_point = transition_point
        self.partial_detection_correction = partial_detection_correction
        self.simulate_error = simulate_error
        self.PoD_fn = PoD_fn
        self.correction_fn = correction_fn
        self.wind_norm_col = wind_norm_col
        self.wind_speed_col = wind_speed_col
        self.cutoff_col = cutoff_col
        self.coverage_count = coverage_count
        self.asset_type = asset_type
        self.outpath = outpath

    def perform_analysis(self):
        self.load_data()
        self.make_samples()
        self.combine_samples()
        self.produce_outputs()

    def load_data(self):
        self.simulated_em, self.simulated_prod = self.read_simulated_data()
        self.aerial_plumes, self.aerial_sources = self.read_aerial_data()

    def read_simulated_data(self) -> tuple[np.ndarray]:
        """
        Return a numpy array of simulated emissions values. By default, this 
        assumes a specific column name and implicit unit.

        Returns:
            tuple[np.ndarray]:
                A tuple of (simulated emissions, simulated productivity)
        """
        sub_mdl_sims = pd.read_excel(
            self.simmed_emission_file,
            sheet_name=self.simmed_emission_sheet
        )
        sub_mdl_prod = sub_mdl_sims["Gas productivity [mscf/site/day]"].values
        sub_mdl_em = (sub_mdl_sims["sum of emissions [kg/hr]"] / 24).values
        
        return sub_mdl_em, sub_mdl_prod
    
    def read_aerial_data(self) -> tuple[np.ndarray]:
        """
        Return a tuple of plume and source data, restricted to sources of 
        the given values in `self.asset_type`.

        Raises:
            KeyError:
                When no sources remain after filtering for the desired 
                asset type.

        Returns:
            tuple[np.ndarray]:
                A tuple of (plume data, source data).
        """        
        sources = pd.read_csv(self.source_file)
        
        # Restrict to sources whose asset type is 
        sources = sources.loc[sources["asset_type"].isin(self.asset_type)]
        if len(sources)==0:
            raise KeyError(
                f"After filtering {self.source_file = } for {self.asset_type = }"
                ", there are no rows left. You should check that these values "
                "of `asset_type` exist in the dataset."
            )
        sources.set_index("emission_source_id",inplace=True)

        plumes = pd.read_csv(self.plume_file)
        
        # Resample cutoff observations before any adjustment or sampling.
        plumes = account_for_cutoffs(plumes,self.cutoff_col,self.wind_norm_col)
        
        # Only keep plumes who are coming from the remaining sources
        plumes = plumes.loc[plumes["emission_source_id"].isin(sources.index)]
        
        return plumes, sources
    
    def read_covered_productivity(self) -> np.ndarray:
        covered_productivity = pd.read_csv(self.covered_productivity_file)
        return covered_productivity["New Mexico Permian 2021 (mscf/site/day)"].values
    
    def make_samples(self):
        self.simulated_sample = self.make_simulated_sample()
        (
            self.tot_aerial_sample, 
            self.partial_detec_sample, 
            self.extra_emissions_for_cdf, 
            self.aerial_site_sample
        ) = self.make_aerial_sample()

    def make_simulated_sample(self):
        if self.stratify_sim_sample:
            if self.covered_productivity_file is None:
                raise ValueError(
                    "`stratify_sim_sample` is True, but there is no "
                    "productivity file specified to use for the stratification."
                )
            covered_productivity = self.read_covered_productivity()
            sub_mdl_dist = stratify_sample(
                self.simulated_em,
                self.simulated_prod,
                covered_productivity,
                n_infra=self.num_wells_to_simulate
            )
        else:
            sub_mdl_dist = self.simulated_em

        # Sample the stratified representation for each monte carlo iteration
        sub_mdl_sample = np.random.choice(
            sub_mdl_dist,
            (self.num_wells_to_simulate,self.n_mc_samples),
            replace=True
        )
        sub_mdl_sample.sort(axis=0)

        return sub_mdl_sample
    
    def make_aerial_sample(self) -> tuple[np.ndarray]:
        """
        Do the aerial sampling (including intermittency), and also the partial 
        detection correction as specified by self.partial_detection_correction, 
        which will either take the form of duplicated samples added directly to 
        the record of aerial emissions samples, or an account of total extra 
        emissions to add directly to the cdf (indexed identically to the 
        final record of aerial emissions).

        Returns:
            tuple[np.ndarray]: 
                A 4-tuple of total aerial emissions (emissions sampled for 
                each source, which may or may not include duplicated partial 
                detection samples), the partial detection samples that were 
                added (length 0 if none), extra emissions that may be 
                added in lieu of duplicated samples, and the sample of 
                aerial emissions (incl intermittency) by itself, without 
                any partial detection samples added.
        """
        aerial_site_sample, wind_norm_sample = get_aerial_sample(
            plumes = self.aerial_plumes,
            sources = self.aerial_sources,
            n_mc_samples = self.n_mc_samples,
            noise_fn = self.noise_fn,
            handle_zeros = self.handle_zeros,
            simulate_error = self.simulate_error,
            correction_fn = self.correction_fn,
            wind_speed_col = self.wind_speed_col,
            coverage_count = self.coverage_count,
        )

        if self.partial_detection_correction.lower()=="add samples":
            #   You need to essentially add a new (many x N) array, filled with copies of the sampled values 
            #   (based on the partial detection probability)
            #   So that for each new_array[:,i], you have addiitonal copies of the sampled values below the 100% detection thresshold.
            #   (its a long list of additional low-value emissions values)
            partial_detec_samples = get_partial_detection_samples(self.PoD_fn,wind_norm_sample,aerial_site_sample)
        else:
            # if partial_detection_correction doesn't happen, there are no extra samples
            # i.e. 0 rows.
            partial_detec_samples = np.zeros((0,aerial_site_sample.shape[1]))

        # Number of required extra rows to simulate all covered wells
        # (these padding 0s may not be required)
        required_extra_zeros = (
            self.num_wells_to_simulate 
            - aerial_site_sample.shape[0] 
            - partial_detec_samples.shape[0]
        )
        padding_zeros = np.zeros((required_extra_zeros,self.n_mc_samples))
        
        # Concatenate the extra samples onto the original draws, with zero padding
        # representing all of the remaining wells up to num_wells_to_simulate
        tot_aerial_sample = np.concat([aerial_site_sample,partial_detec_samples,padding_zeros],axis=0)
        tot_windnorm_sample = np.concat([wind_norm_sample,partial_detec_samples*0,padding_zeros],axis=0)

        # aerial_data_idx = index that sorts the sampled aerial emissions column-wise.
        aerial_data_idx = np.argsort(tot_aerial_sample,axis=0)
        
        # In this loop, use the same index to sort each of the corresponding tables:
        #   * Sampled aerial emissions
        #   * corresponding wind-normalized emissions
        for n in range(self.n_mc_samples):
            tot_aerial_sample[:,n] = tot_aerial_sample[aerial_data_idx[:,n],n]
            tot_windnorm_sample[:,n] = tot_windnorm_sample[aerial_data_idx[:,n],n]
        
        # Define an addition to the cumulative sum based on the wind-normalized
        # emissions, if the form of the partial detection correction is "add to cumsum"
        # (otherwise maintain the calculation structure, but just use a table of 0s)
        if self.partial_detection_correction=="add to cumsum":
            PoD = self.PoD_fn(tot_windnorm_sample)
            extra_emissions_for_cdf = (1/PoD - 1)*tot_aerial_sample
        else:
            extra_emissions_for_cdf = np.zeros(tot_aerial_sample.shape)

        return tot_aerial_sample, partial_detec_samples, extra_emissions_for_cdf, aerial_site_sample
    
    def combine_samples(self):
        aerial_cumsum = self.tot_aerial_sample.cumsum(axis=0) + self.extra_emissions_for_cdf.cumsum(axis=0)
        # Convert it into a decreasing cumulative total
        aerial_cumsum = aerial_cumsum.max(axis=0) - aerial_cumsum
        
        sim_data = np.sort(self.simulated_sample,axis=0)
        simmed_cumsum = sim_data.cumsum(axis=0)
        # Convert into decreasing cumulative total
        simmed_cumsum = simmed_cumsum.max(axis=0) - simmed_cumsum
        
        if self.transition_point is None:
            self.tp = find_transition_point(
                aerial_x = self.tot_aerial_sample,
                aerial_y = aerial_cumsum,
                sim_x = sim_data,
                sim_y = simmed_cumsum,
            )
        elif isinstance(self.transition_point,(int,float,)):
            self.tp = np.array([self.transition_point]*self.n_mc_samples)

        self.combined_samples = self.tot_aerial_sample.copy()

        # For each of the n_samples columns, replace emissions below transition point with 
        # samples (w/ replacement) from the simulated values < transition point
        for n in range(self.n_mc_samples):
            
            # Get the transition point for this MC run
            tp = self.tp[n]
            
            # Define simulations below this iteration's transition point
            sim_below_transition = self.simulated_sample[:,n][self.simulated_sample[:,n]<tp]

            # Find the first index where the aerial emissions in this column are ≥transition point
            idx_above_transition = np.argmin(self.combined_samples[:,n]<tp)

            # For all preceding indices, insert random simulated emissions below the transition point
            self.combined_samples[:idx_above_transition,n] = np.random.choice(sim_below_transition,idx_above_transition,replace=True)
            
            # In any partial detection emissions tracked to be added directly to the cdf, zero out contributions associated to emissions below transition point.
            self.extra_emissions_for_cdf[:idx_above_transition,n] = 0
        
        # Re-sort the newly combined records.
        combined_sort_idx = self.combined_samples.argsort(axis=0)
        for n in range(self.n_mc_samples):
            # Sort the combined samples column-wise
            self.combined_samples[:,n] = self.combined_samples[combined_sort_idx[:,n],n]

            # Sort the corresponding extra_emissions_for_cdf
            self.extra_emissions_for_cdf[:,n] = self.extra_emissions_for_cdf[combined_sort_idx[:,n],n]

    def produce_outputs(self):
        output_tables = self.summarize_run()

        gen_plots(
            self.combined_samples, 
            self.extra_emissions_for_cdf, 
            np.mean(self.tp), 
            self.outpath
        )
        
        if not os.path.exists(self.outpath):
            os.mkdir(self.outpath)

        for name, table in output_tables.items():
            if not name.endswith(".csv"):
                name += ".csv"
            
            table.to_csv(os.path.join(self.outpath,name))

    def summarize_run(self) -> dict[str,pd.DataFrame]:
        N = len(self.tp)
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
        
        sum_emiss_aerial = self.aerial_site_sample.sum(axis=0)
        prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_aerial.mean()*1e-3
        prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_aerial.std()*1e-3
        sum_emiss_aerial_abovetp = np.array([self.aerial_site_sample[:,n][self.aerial_site_sample[:,n]>=self.tp[n]].sum() for n in range(N)])
        prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("Accounting for Transition Point","Avg")] = sum_emiss_aerial_abovetp.mean()*1e-3
        prod_summary.loc["Aerial Only Total CH4 emissions (t/h)",("Accounting for Transition Point","Std Dev")] = sum_emiss_aerial_abovetp.std()*1e-3
        
        # In this addition, the expectation is the only one or other is contributing to the sum
        sum_emiss_partial = self.partial_detec_sample.sum(axis=0) + self.extra_emissions_for_cdf.sum(axis=0)
        prod_summary.loc["Partial Detection Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_partial.mean()*1e-3
        prod_summary.loc["Partial Detection Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_partial.std()*1e-3
        
        # Like above, in this addition there are either additional copies of sampled emissions in `total_aerial_sample`, or the total missing emissions are included in `extra_emissions_for_cdf`.
        sum_emiss_aer_comb = self.tot_aerial_sample.sum(axis=0) + self.extra_emissions_for_cdf.sum(axis=0)
        prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_aer_comb.mean()*1e-3
        prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_aer_comb.std()*1e-3
        sum_emiss_aer_comb_abovetp = sum_emiss_aerial_abovetp + np.array([self.extra_emissions_for_cdf[:,n][self.tot_aerial_sample[:,n]>=self.tp[n]].sum() for n in range(N)])
        prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("Accounting for Transition Point","Avg")] = sum_emiss_aer_comb_abovetp.mean()*1e-3
        prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)",("Accounting for Transition Point","Std Dev")] = sum_emiss_aer_comb_abovetp.std()*1e-3
        
        sum_emiss_sim = self.simulated_sample.sum(axis=0)
        prod_summary.loc["Simulated Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_sim.mean()*1e-3
        prod_summary.loc["Simulated Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_sim.std()*1e-3
        sum_emiss_sim_belowtp = np.array([self.simulated_sample[:,n][self.simulated_sample[:,n]<self.tp[n]].sum() for n in range(N)])
        prod_summary.loc["Simulated Total CH4 emissions (t/h)",("Accounting for Transition Point","Avg")] = sum_emiss_sim_belowtp.mean()*1e-3
        prod_summary.loc["Simulated Total CH4 emissions (t/h)",("Accounting for Transition Point","Std Dev")] = sum_emiss_sim_belowtp.std()*1e-3
        
        sum_emiss_all_comb = self.combined_samples.sum(axis=0) + self.extra_emissions_for_cdf.sum(axis=0)
        prod_summary.loc["Overall Combined Total CH4 emissions (t/h)",("By Itself","Avg")] = sum_emiss_all_comb.mean()*1e-3
        prod_summary.loc["Overall Combined Total CH4 emissions (t/h)",("By Itself","Std Dev")] = sum_emiss_all_comb.std()*1e-3

        prod_summary.loc["Transition Point (kg/h)",("By Itself","Avg")] = self.tp.mean()
        prod_summary.loc["Transition Point (kg/h)",("By Itself","Std Dev")] = self.tp.std()

        cumsum_y = self.combined_samples.cumsum(axis=0) + self.extra_emissions_for_cdf.cumsum(axis=0)
        cumsum_y = 100*(1-cumsum_y/cumsum_y.max(axis=0)).mean(axis=1)
        dist_x = self.combined_samples.mean(axis=1)

        dist_summary = pd.DataFrame(
            columns=["Emissions Value","Cumulative Distribution Percentile"]
        )
        
        # Where the first 10% of emissions have been accounted for
        tenth_pctl = np.argmin(cumsum_y>90)
        # Where 50% of emissions have been accounted for
        median_idx = np.argmin(cumsum_y>50)
        # Where 90% of emissions have been accounted for
        ninetieth_pctl = np.argmin(cumsum_y>10)
        # Where 100% of emissions have been accounted for
        hundred_pctl = np.argmin(cumsum_y>0)

        # at least 10 kgh
        ten_kgh = np.argmin(dist_x<10)
        # at least 100 kgh
        hundred_kgh = np.argmin(dist_x<100)
        # at least 1000 kgh
        thousand_kgh = np.argmin(dist_x<1000)

        dist_summary["Emissions Value"] = [
            dist_x[ten_kgh],
            dist_x[hundred_kgh],
            dist_x[thousand_kgh],
            dist_x[tenth_pctl],
            dist_x[median_idx],
            dist_x[ninetieth_pctl],
            dist_x[hundred_pctl],
        ]
        dist_summary["Cumulative Distribution Percentile"] = [
            cumsum_y[ten_kgh],
            cumsum_y[hundred_kgh],
            cumsum_y[thousand_kgh],
            cumsum_y[tenth_pctl],
            cumsum_y[median_idx],
            cumsum_y[ninetieth_pctl],
            cumsum_y[hundred_pctl],
        ]

        dist_summary.sort_values("Emissions Value",inplace=True,ascending=True)

        return {"Production Summary": prod_summary,"Distribution Summary":dist_summary}