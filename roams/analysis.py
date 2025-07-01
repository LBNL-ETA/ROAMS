import os

import pandas as pd
import numpy as np

from matplotlib import pyplot as plt

from roams.aerial.assumptions import power_correction, normal, zero_out
from roams.aerial.sample import get_aerial_sample
from roams.aerial.preprocess import account_for_cutoffs
from roams.aerial.partial_detection import PoD_bin, PoD_linear
from roams.transition_point import find_transition_point

from roams.simulated.sample import stratify_sample

class ROAMSModel:
    """
    The ROAMSModel is a class intended to hold the logic necessary for 
    implementing the Regional Oil and gas Aerial Methane Synthesis (ROAMS) 
    Model.

    At it's core, the goal of this model is to take two separate estimates of 
    fugitive methane emissions of specific types of infrastructure, and 
    combine them into a single distributions of emissions that is the most 
    reflective of reality. The two separate estimates of emissions in the 
    region come from:

    (a) Simulated or reported estimates from an external source, anticipated 
        to be a better estimate of smaller emissions.
    (b) Records of emissions from aerial or satellite surveys, anticipated to 
        be much better at capturing large and less frequent emissions, but 
        almost useless for smaller-scale emissions.
    
    There are multiple expectations placed on each of these input datasets, 
    and also additional meta-information required for being able to compute 
    all the desired results.

    The ROAMS model prescribes a method for combining these distributions and 
    accommodates the inherent uncertainty of measurement by performing the 
    combination many different times, each with a different sample of the 
    underlying data and each with different random noise applied to the 
    sampled aerial data. In combination, these effects are intended to allow 
    users to quantify the resulting uncertainty in summary statistics of the 
    resulting emissions estimates, as well as the overall distributions.

    Args:
        
        simmed_emission_file (str): 
            An excel file with the simulated emissions distribution in 
            tabular form in one of the sheets. In addition, the table should 
            have simulated productivity associated to each simulated 
            observation.
        
        simmed_emission_sheet (str): 
            The name of the sheet in `simmed_emission_file` with simulated 
            emissions and productivity.
        
        plume_file (str): 
            The file path to the reported plume-level emissions. It's required 
            that each plume record can be matched to each recorded source in 
            the `source_file` by some source identifier.
        
        source_file (str): 
            The file path to the covered sources. Should share a column 
            identifier with `plume_file`, and should also contain a descriptor 
            of the asset that best represents the source.
        
        covered_productivity_file (str): 
            The name of a file with an estimated distribution of regional 
            productivity, which will be used to re-weight the simulated 
            data according to the "actual" productivity of the region (this 
            process is called 'stratification' in the code).
        
        campaign_name (str, optional): 
            A string descriptor of the campaign name that will be used to 
            look up meta-information about the campaign like the total number 
            of wells, and the average number of wells per site. It will also 
            be used in the outputs to help identify the source of the aerial 
            data.
            If None, the code will break and not be able to compute all the 
            outputs.
            Defaults to None.
        
        stratify_sim_sample (bool, optional): 
            Whether or not the simulated emissions should be stratified to 
            better reflect the true production estimated in this region (per 
            the `covered_productivity_file`).
            Defaults to True.
        
        n_mc_samples (int, optional): 
            The number of monte-carlo iterations to do. In each monte-carlo 
            iteration, the (perhaps stratified) simulated emissions are 
            sampled, and the aerial emissions are sampled and noised as well.
            The resulting distributions are then combined. All monte-carlo 
            iterations are in the end part of the quantified results.
            Defaults to 100.
        
        num_wells_to_simulate (int, optional): 
            This is supposed to reflect the total number of unique well sites 
            covered in this aerial campaign.
            Defaults to 18030.
        
        well_visit_count (int, optional): 
            This is supposed to reflect the total number of wells visited 
            during the aerial campaign.
            Defaults to 81564.
        
        wells_per_site (int, optional): 
            This is supposed to reflect the average number of wells per 
            well site in the covered aerial survey region.
            Defaults to 1.2.
        
        noise_fn (Callable, optional): 
            A function that can take a numpy array, and return a properly 
            noised version of it.
            Defaults to normal.
        
        handle_zeros (Callable, optional): 
            A function that can take an array of values (will be sampled and 
            noised aerial data), as well as the noise function, and do 
            something with below-zero values.
            Defaults to zero_out.
        
        transition_point (float, optional): 
            A prescribed transition point, if applicable. If no such known 
            transition point exists, supplying `None` will indicate to the 
            code to find it by itself.
            Defaults to None.
        
        partial_detection_correction (bool, optional): 
            Whether or not to apply a partial detection correction to sampled 
            aerial emissions, reflecting the fact that some observed emissions 
            are unlikely to be picked up, and having observed them likely 
            means there is more in the overall region to model that would 
            otherwise not be accounted for.
            Defaults to True.
        
        simulate_error (bool, optional): 
            Whether or not to apply `self.noise_fn` to sampled and corrected 
            aerial emissions in order to help simulate error.
            Defaults to True.
        
        PoD_fn (Callable, optional): 
            A function that can take an array of wind-normalized emissions 
            values, and return a probability of detection for each value. The 
            result of this function will be fed into the equation to 
            determine the multiplier for corresponding sampled emissions 
            values:
                (1/PoD -1), where `PoD` is the outcome of this function.
            As such, this should not return any 0 values. If you don't want 
            to add any additional weight to values with small probability, 
            write your `PoD_fn` to limit the output probabilities, and set 
            the probability to 1 for all observations that you don't want to 
            add partial detection weight to.
            Defaults to PoD_bin.
        
        correction_fn (Callable, optional): 
            A function that can take raw sampled aerial emissions data (equal 
            to [wind normalized emissions]*[wind speed]), and applies a 
            deterministic correction to account for macroscopic average 
            measurement bias.
            Defaults to power_correction.
        
        wind_norm_col (str, optional): 
            The name of the column in the `plume_file` plume emissions table 
            that describes the wind-normalized emissions rate.
            Defaults to "wind_independent_emission_rate_kghmps".
        
        wind_speed_col (str, optional): 
            The name of the column in the `plume_file` plume emissions table 
            that describes the wind speed.
            Defaults to "wind_mps".
        
        cutoff_col (str, optional): 
            The name of the column in the `plume_file` plume emissions table
            that holds a flag for whether or not the plume was cut by the 
            field of view of the survey equipment.
            Defaults to "cutoff".
        
        coverage_count (str, optional): 
            The name of the column in the `source_file` source table that 
            holds the number of times the given piece of infrastructure was 
            viewed (whether or not emissions were observed).
            Defaults to "coverage_count".
        
        asset_type (tuple, optional): 
            A tuple of asset types under an "asset_type" column to include 
            in the estimation of aerial emissions.
            Defaults to ("Well site",).
        
        outpath (str, optional): 
            A folder name into which given outputs will be saved.
            Defaults to "evan_output".
        
        save_mean_dist (bool, optional): 
            Whether or not to save a "mean" distribution of all the components
            of the estimated production distributions (i.e. aerial, partial 
            detection, simulated).
            Defaults to True.
    """
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
        well_visit_count = 81564,
        wells_per_site = 1.2,
        noise_fn = normal,
        handle_zeros = zero_out,
        transition_point = None,
        partial_detection_correction = True,
        simulate_error = True,
        PoD_fn = PoD_bin,
        correction_fn = power_correction,
        wind_norm_col = "wind_independent_emission_rate_kghmps",
        wind_speed_col = "wind_mps",
        cutoff_col = "cutoff",
        coverage_count = "coverage_count",
        asset_type = ("Well site",),
        outpath="evan_output",
        save_mean_dist = True,
        ):

        # The simulation input file
        self.simmed_emission_file = simmed_emission_file
        self.simmed_emission_sheet = simmed_emission_sheet

        # Estimate of covered production in survey region
        self.covered_productivity_file = covered_productivity_file
        
        # Specification of aerial input data
        self.plume_file = plume_file
        self.source_file = source_file
        self.wind_norm_col = wind_norm_col
        self.wind_speed_col = wind_speed_col
        self.cutoff_col = cutoff_col
        self.coverage_count = coverage_count
        self.asset_type = asset_type
        
        # Specifications of algorithm behavior
        self.stratify_sim_sample = stratify_sim_sample
        self.n_mc_samples = n_mc_samples
        self.noise_fn = noise_fn
        self.handle_zeros = handle_zeros
        self.transition_point = transition_point
        self.partial_detection_correction = partial_detection_correction
        self.simulate_error = simulate_error
        self.PoD_fn = PoD_fn
        self.correction_fn = correction_fn

        if not (
            self.transition_point==None 
            or 
            isinstance(self.transition_point,(int,float))
        ):
            raise ValueError(
                "The `transition_point` argument to the ROAMSModel class can "
                "only be `None` or a numerical value."
            )
        
        # Properties of surveyed infrastructure
        self.num_wells_to_simulate = num_wells_to_simulate
        self.well_visit_count = well_visit_count
        self.wells_per_site = wells_per_site
        
        # Output specification
        self.outpath = outpath
        self.save_mean_dist = save_mean_dist

        # Quantiles used in quantification of MC results 
        # (no reason to mess with this)
        self._quantiles = (.025,.975)

    def perform_analysis(self):
        """
        The method that will actually perform the analysis as specified.

        It will:
            
            1. Load simulated production data and aerial survey data
            2. Perform sampling operations to create samples of aerial and 
                simulated data for each monte carlo iteration.
            3. Use the ROAMS methodology to combine the simulated and aerial 
                production data.
            4. Summarize all the available information, to the degree 
                specified, into the location specified.
        """
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
        """
        Call methods that will make the sample of simulated production 
        emissions and sampled aerial emissions.
        """        
        self.simulated_sample = self.make_simulated_sample()
        (
            self.tot_aerial_sample, 
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

        # Number of required extra rows to simulate all covered wells
        # (these padding 0s may not be required)
        required_extra_zeros = (
            self.num_wells_to_simulate 
            - aerial_site_sample.shape[0] 
        )
        padding_zeros = np.zeros((required_extra_zeros,self.n_mc_samples))
        
        # Concatenate the extra samples onto the original draws, with zero padding
        # representing all of the remaining wells up to num_wells_to_simulate
        tot_aerial_sample = np.concat([aerial_site_sample,padding_zeros],axis=0)
        tot_windnorm_sample = np.concat([wind_norm_sample,padding_zeros],axis=0)

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
        if self.partial_detection_correction:
            PoD = self.PoD_fn(tot_windnorm_sample)
            extra_emissions_for_cdf = (1/PoD - 1)*tot_aerial_sample
        else:
            extra_emissions_for_cdf = np.zeros(tot_aerial_sample.shape)

        return tot_aerial_sample, extra_emissions_for_cdf, aerial_site_sample
    
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

        if self.save_mean_dist:
            output_tables["Mean Distributions"] = self.make_mean_production_distributions()
        
        if not os.path.exists(self.outpath):
            os.mkdir(self.outpath)

        self.gen_plots()

        for name, table in output_tables.items():
            if not name.endswith(".csv"):
                name += ".csv"
            
            table.to_csv(os.path.join(self.outpath,name))

    def summarize_run(self) -> dict[str,pd.DataFrame]:
        N = len(self.tp)
        quantity_cols = ["Avg",*[str(100*q)+"% CI" for q in self._quantiles]]
        prod_summary = pd.DataFrame(
            index=[
                "Aerial Only Total CH4 emissions (t/h)",
                "Partial Detection Total CH4 emissions (t/h)",
                "Combined Aerial + Partial Detection Total CH4 emissions (t/h)",
                "Simulated Total CH4 emissions (t/h)", 
                "Overall Combined Total Production CH4 emissions (t/h)",
                "Transition Point (kg/h)"
            ],
            columns=pd.MultiIndex.from_product(
                [["By Itself","Accounting for Transition Point"],quantity_cols],
            )
        )
        
        # Report the sampled aerial emissions distribution, regardless of transition point
        sum_emiss_aerial = self.aerial_site_sample.sum(axis=0)/1e3
        prod_summary.loc["Aerial Only Total CH4 emissions (t/h)","By Itself"] = self.mean_and_quantiles(sum_emiss_aerial)[quantity_cols].values

        # Report sampled aerial emissions distributions above transition point
        sum_emiss_aerial_abovetp = np.array([self.aerial_site_sample[:,n][self.aerial_site_sample[:,n]>=self.tp[n]].sum() for n in range(N)])/1e3
        prod_summary.loc["Aerial Only Total CH4 emissions (t/h)","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_aerial_abovetp)[quantity_cols].values

        # In this addition, the expectation is the only one or other is contributing to the sum
        sum_emiss_partial = self.extra_emissions_for_cdf.sum(axis=0)/1e3
        prod_summary.loc["Partial Detection Total CH4 emissions (t/h)","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_partial)[quantity_cols].values
        
        # Like above, in this addition there are either additional copies of sampled emissions in `total_aerial_sample`, or the total missing emissions are included in `extra_emissions_for_cdf`.
        sum_emiss_aer_comb = (self.tot_aerial_sample.sum(axis=0) + self.extra_emissions_for_cdf.sum(axis=0))/1e3
        prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)","By Itself"] = self.mean_and_quantiles(sum_emiss_aer_comb)[quantity_cols].values

        # This will be aerial+partial detection, but ONLY total contributions above each transition point
        sum_emiss_aer_comb_abovetp = sum_emiss_aerial_abovetp + np.array([self.extra_emissions_for_cdf[:,n][self.tot_aerial_sample[:,n]>=self.tp[n]].sum() for n in range(N)])/1e3
        prod_summary.loc["Combined Aerial + Partial Detection Total CH4 emissions (t/h)","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_aer_comb_abovetp)[quantity_cols].values
        
        # The total amount of simulated emissions
        sum_emiss_sim = self.simulated_sample.sum(axis=0)/1e3
        prod_summary.loc["Simulated Total CH4 emissions (t/h)","By Itself"] = self.mean_and_quantiles(sum_emiss_sim)[quantity_cols].values

        # The total amount of simulated emissions below transition point
        sum_emiss_sim_belowtp = np.array([self.simulated_sample[:,n][self.simulated_sample[:,n]<self.tp[n]].sum() for n in range(N)])/1e3
        prod_summary.loc["Simulated Total CH4 emissions (t/h)","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_sim_belowtp)[quantity_cols].values
        
        # Report from total combined distribution: only "By Itself" (doesn't make sense to 'account for transition point' in combined distribution)
        sum_emiss_all_comb = (self.combined_samples.sum(axis=0) + self.extra_emissions_for_cdf.sum(axis=0))/1e3
        prod_summary.loc["Overall Combined Total Production CH4 emissions (t/h)","By Itself"] = self.mean_and_quantiles(sum_emiss_all_comb)[quantity_cols].values

        # Report the same quantities for the transition point.
        prod_summary.loc["Transition Point (kg/h)","By Itself"] = self.mean_and_quantiles(self.tp)[quantity_cols].values

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
    
    def mean_and_quantiles(self,values: np.ndarray) -> pd.Series:
        """
        Return the average of the given values, as well as the estimated 
        quantiles, based on the observed quantiles and visits per site.

        Args:
            values (np.ndarray):
                A 1-d array of values to statistically summarize.

        Returns:
            pd.Series:
                A series indexed by "Avg", "2.5% CI","97.5% CI", (e.g.), whose
                values are the estimates of the corresponding statistic for 
                given values.
        """
        lbl = "{}% CI"

        output = pd.Series(
            index=["Avg",*[lbl.format(str(100*q)) for q in self._quantiles]]
        )
        output["Avg"] = values.mean()
        quantiles = np.quantile(values,self._quantiles)
        
        # Denominator = sqrt(Total site visits including re-visits / total sites to simulate)
        denominator = np.sqrt((self.well_visit_count/self.wells_per_site)/self.num_wells_to_simulate)
        for q, val in zip(self._quantiles, quantiles):
            diff = abs(output["Avg"]-val) / denominator

            output[lbl.format(str(100*q))] = (
                output["Avg"] - diff 
                if val<output["Avg"] 
                else output["Avg"] + diff
            )

        return output
    
    def make_mean_production_distributions(self) -> pd.DataFrame:
        """
        Return a summary of the production emissions distributions by taking 
        the mean over all the monte-carlo iterations of all wells to 
        simulate. This is reported for (a) aerial emissions, (b) partial 
        detection emissions, and (c) simulated emissions.

        Returns:
            pd.DataFrame: 
                A [num_wells_to_simulate]x18 Data Frame. For each of 
                aerial, partial detection, and simulated emissions, 
                it will create:
                    * Mean emissions at each well site, across all MC runs
                    * 2.5% emissions at each well site, across all MC runs
                    * 97.5% emissions at each well site, across all MC runs
                    * Mean cumulative emissions, across all MC runs
                    * 2.5% cumulative emissions at each well site, across all MC runs
                    * 97.5% cumulative emissions at each well site, across all MC runs

                In the context of plots created for papers, the "emissions" 
                are the X, and the "cumulative emissions" are the Y.
        """
        output = pd.DataFrame()
        
        # Define factor for translating observed percentiles to confidence
        # intervals
        denominator = np.sqrt((self.well_visit_count/self.wells_per_site)/self.num_wells_to_simulate)
        
        # Make copies of zero-padded aerial and partial detection emissions.
        aerial_em = self.tot_aerial_sample.copy()
        pd_corr = self.extra_emissions_for_cdf.copy()

        # Find the sorting index of the aerial sample
        sort_aerial = np.argsort(aerial_em,axis=0)

        # Sort both partial detection correction and aerial sample together 
        # (they shouldn't need sorting, but just to be safe...)
        for mc_run in range(self.aerial_site_sample.shape[1]):
            aerial_em[:,mc_run] = aerial_em[sort_aerial[:,mc_run],mc_run]
            pd_corr[:,mc_run] = pd_corr[sort_aerial[:,mc_run],mc_run]

        aerial_cumsum = aerial_em.sum(axis=0) - aerial_em.cumsum(axis=0)
        aer_cumsum_quantiles = np.quantile(aerial_cumsum,self._quantiles,axis=1).T
        aer_em_quantiles = np.quantile(aerial_em,self._quantiles,axis=1).T
        
        # Save the mean aerial sample cumsum value
        output["Aerial Only, Mean Cumulative Dist (kg/h)"] = aerial_cumsum.mean(axis=1)
        output["Mean Aerial Emissions (kg/h)"] = aerial_em.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Aerial Only, Cumulative Dist (kg/h), {str(100*q)}% CI"
            lbl_em = f"Aerial Only Emissions (kg/h), {str(100*q)}% CI"

            diff_cum = (aer_cumsum_quantiles[:,i] - output["Aerial Only, Mean Cumulative Dist (kg/h)"])/denominator
            diff_em = (aer_em_quantiles[:,i] - output["Mean Aerial Emissions (kg/h)"])/denominator

            output[lbl_cum] = output["Aerial Only, Mean Cumulative Dist (kg/h)"] + diff_cum
            output[lbl_em] = output["Mean Aerial Emissions (kg/h)"] + diff_em
        
        
        partial_detection_cumsum = pd_corr.sum(axis=0) - pd_corr.cumsum(axis=0)
        pd_cumsum_quantiles = np.quantile(partial_detection_cumsum,self._quantiles,axis=1).T
        pd_em_quantiles = np.quantile(pd_corr,self._quantiles,axis=1).T
        
        # Save the mean partial detection cumsum value
        output["Partial Detection Only, Mean Cumulative Dist (kg/h)"] = partial_detection_cumsum.mean(axis=1)
        output["Mean Partial Detection Emissions (kg/h)"] = pd_corr.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Partial Detection Only, Cumulative Dist (kg/h), {str(100*q)}% CI"
            lbl_em = f"Partial Detection Only Emissions (kg/h), {str(100*q)}% CI"

            diff_cum = (pd_cumsum_quantiles[:,i] - output["Partial Detection Only, Mean Cumulative Dist (kg/h)"])/denominator
            diff_em = (pd_em_quantiles[:,i] - output["Mean Partial Detection Emissions (kg/h)"])/denominator

            output[lbl_cum] = output["Partial Detection Only, Mean Cumulative Dist (kg/h)"] + diff_cum
            output[lbl_em] = output["Mean Partial Detection Emissions (kg/h)"] + diff_em
        

        simulated_em = np.sort(self.simulated_sample,axis=0)
        simulated_cumsum = simulated_em.sum(axis=0) - simulated_em.cumsum(axis=0)
        sim_cumsum_quantiles = np.quantile(simulated_cumsum,self._quantiles,axis=1).T
        sim_em_quantiles = np.quantile(simulated_em,self._quantiles,axis=1).T
        
        # Save the mean simulated cumsum value
        output["Simulated Only, Mean Cumulative Dist (kg/h)"] = simulated_cumsum.mean(axis=1)
        output["Mean Simulated Emissions (kg/h)"] = simulated_em.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Simulated Only, Cumulative Dist (kg/h), {str(100*q)}% CI"
            lbl_em = f"Simulated Only Emissions (kg/h), {str(100*q)}% CI"

            diff_cum = (sim_cumsum_quantiles[:,i] - output["Simulated Only, Mean Cumulative Dist (kg/h)"])/denominator
            diff_em = (sim_em_quantiles[:,i] - output["Mean Simulated Emissions (kg/h)"])/denominator

            output[lbl_cum] = output["Simulated Only, Mean Cumulative Dist (kg/h)"] + diff_cum
            output[lbl_em] = output["Mean Simulated Emissions (kg/h)"] + diff_em
        
        return output
    
    def gen_plots(self):
        """
        Take a table of the overall combined emissions distributions of 
        production, and turn them into plots that include a vertical line 
        to indicate the average transition point.
        """    
        cumsum = self.combined_samples.cumsum(axis=0) + self.extra_emissions_for_cdf.cumsum(axis=0)
        cumsum_pct = 100*(1-cumsum/cumsum.max(axis=0))

        x = np.nanmean(self.combined_samples,axis=1)
        y = np.nanmean(cumsum_pct,axis=1)
        
        plt.plot(x,y)
        plt.semilogx()
        max_val = 0
        plt.vlines(
            self.tp.mean(), 0, 100, color='black', linestyle='dotted', 
            label=f'transition point ({self.tp.mean()})'
        )
        max_val = max(x.max(), max_val)
        plt.xlim(1e-2, max_val)
        plt.grid(True)
        plt.ylabel("Fraction of Total Emissions at least x")
        plt.xlabel("Emissions Rate (kg/h)")
        plt.legend()

        plt.savefig(os.path.join(self.outpath, "combined_cumulative.svg"))
        plt.savefig(os.path.join(self.outpath, "combined_cumulative.png"))