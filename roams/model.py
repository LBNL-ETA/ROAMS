import os
import logging
import json

import pandas as pd
import numpy as np

from matplotlib import pyplot as plt

from roams.constants import COMMON_EMISSIONS_UNITS, COMMON_PRODUCTION_UNITS, COMMON_ENERGY_UNITS
from roams.conf import RESULT_DIR

from roams.input import ROAMSConfig

from roams.simulated.stratify import stratify_sample
from roams.transition_point import find_transition_point
from roams.utils import energycontent_mj_mcf, MJ_PER_BOE, ENERGY_DENSITY_MJKG, convert_units

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
        
        input_file (str | dict):
            Either a path to a JSON input file (str), or the dict embodied 
            therein (dict). This will be given to ROAMSConfig for parsing, 
            type checking, and the assignment of defaults. For more 
            information, head on over to roams.input.ROAMSConfig to get more 
            information about what information is required.

        parser (ROAMSConfig, optional):
            A class that is inherited (or is) ROAMSConfig, which will be used 
            to read the input content. Inclusion of the parser here allows 
            users to adopt new input behavior with inherited classes that have 
            altered behavior.
            Defaults to ROAMSConfig.
    """
    def __init__(self,input_file : str | dict, parser : ROAMSConfig = ROAMSConfig):

        # Use the parser to read through the input JSON file
        # (or provided dictionary)
        self.cfg = parser(input_file)

        ### Output specification
        # self.outfolder is a directory into which result tables will be 
        self.outfolder =            os.path.join(RESULT_DIR,self.cfg.foldername)
        self.save_mean_dist =       self.cfg.save_mean_dist
        self.loglevel =             self.cfg.loglevel
        
        # Set the log using prescribed level
        self.log = logging.getLogger("roams.model.ROAMSModel")
        self.log.setLevel(self.loglevel)
        # A dictionary attribute into which output tables will be put before writing
        self.table_outputs = dict()

        # Properties of surveyed infrastructure
        self.well_visit_count =         self.cfg.well_visit_count
        self.wells_per_site =           self.cfg.wells_per_site
        
        # Quantiles used in quantification of MC results 
        # (no reason to mess with this)
        self._quantiles = (.025,.975)
        # Label format into which quantiles should be put
        self._lbl = "{}% CI"
        self.log.debug(f"{self._quantiles = }")
    
    def perform_analysis(self):
        """
        The method that will actually perform the analysis as specified.

        It will:
            
            1. Perform sampling operations to create samples of aerial and 
                simulated data for each monte carlo iteration.
            2. Use the ROAMS methodology to combine the simulated and aerial 
                production data.
            3. Estimate the sub-detection-level midstream emissions
            4. Summarize all the available information, to the degree 
                specified, into the location specified.
        """
        self.make_samples()
        self.combine_prod_samples()
        self.compute_simulated_midstream_emissions()
        self.generate_and_write_outputs()
    
    def make_samples(self):
        """
        Call methods that will make the sample of simulated production 
        emissions, and also the aerial sample for production and midstream 
        assets (meaning both the sampled aerial emissions and corresponding 
        partial detection correction.)
        """
        self.simulated_sample = self.make_simulated_sample()
        self.aerial_samples = self.make_aerial_samples()

    def make_aerial_samples(self) -> dict:
        """
        Make a dictionary of the form:
            
            {asset group : (aerial emissions, partial detection emissions)}

        and return it. The result will be the non-zero-padded aerial 
        emissions sampling for each asset group identified in the input file.

        Returns:
            dict:
                A dictionary with asset group (string) keys, and tuple 
                values. The first entry in each tuple is sampled and adjusted 
                aerial emissions. The second entry is the corresponding 
                partial detection correction.
        """
        aerial_samples = dict()

        for group in self.cfg.asset_groups.keys():
            emiss, wind_norm_emiss = self.get_aerial_survey_sample(infra=group)
            
            self.log.info(
                f"The {group} aerial sample has size {emiss.shape}."
            )
            self.log.debug(
                f"The mean total {group} aerial sample emissions are "
                f"{emiss.sum(axis=0).mean():.2f} {COMMON_EMISSIONS_UNITS}"
            )
            
            # Define an addition to the cumulative sum based on the wind-normalized
            # emissions, if the form of the partial detection correction is "add to cumsum"
            # (otherwise maintain the calculation structure, but just use a table of 0s)
            if self.cfg.partial_detection_correction:
                self.log.info(
                    f"Using {self.cfg.PoD_fn} on the sorted wind-normalized sample "
                    f"of {group} emissions to define the probability of detection."
                )
                PoD = self.cfg.PoD_fn(wind_norm_emiss)
                partial_detection_emiss = (1/PoD - 1)*emiss
            else:
                self.log.info(
                    "No partial detection correction will be applied to the "
                    "aerial sample."
                )
                partial_detection_emiss = np.zeros(emiss.shape)

            sort_idx = np.argsort(emiss,axis=0)
            for mc_run in range(emiss.shape[1]):
                emiss[:,mc_run] = emiss[sort_idx[:,mc_run],mc_run]
                partial_detection_emiss[:,mc_run] = partial_detection_emiss[sort_idx[:,mc_run],mc_run]
            
            aerial_samples[group] = (emiss, partial_detection_emiss)

        return aerial_samples
    
    def make_simulated_sample(self) -> np.ndarray:
        """
        Take the long list of simulated emissions, and return a sample of 
        this data for each monte carlo iteration.

        If directed to stratify the simulated sample, it will use externally 
        provided production data that describes the distribution of production 
        in the covered basin, and re-sample the simulated data so that the 
        distribution of production in the simulated data is as similar as 
        possible.

        Raises:
            ValueError:
                When the code is directed to do stratification, but there is 
                no corresponding file that provides productivity in the 
                covered basin.

        Returns:
            np.ndarray:
                A (number of simulated wells)x(number monte-carlo iterations) 
                table of values. Each value is a simulated emissions value.
        """        
        if self.cfg.stratify_sim_sample:
            self.log.info(
                "Doing stratified sampling of simulated emissions into a "
                f"{self.cfg.num_wells_to_simulate}x{self.cfg.n_mc_samples} table."
            )
            # The simulated sample is drawn is drawn in a stratified manner 
            # directly.
            sub_mdl_sample = stratify_sample(
                self.cfg.prodSimResults.simulated_emissions,
                self.cfg.prodSimResults.simulated_production,
                self.cfg.coveredProductivity.ng_production_dist_volumetric*self.wells_per_site,
                n_infra=self.cfg.num_wells_to_simulate,
                n_mc_samples=self.cfg.n_mc_samples,
            )
        
        else:
            # Sample the raw data directly into the simulated sample
            self.log.info(
                "Sampling raw simulated emissions data into a "
                f"{self.cfg.num_wells_to_simulate}x{self.cfg.n_mc_samples} table."
            )
            sub_mdl_sample = np.random.choice(
                self.cfg.prodSimResults.simulated_emissions,
                (self.cfg.num_wells_to_simulate,self.cfg.n_mc_samples),
                replace=True
            )

        # Sort the simulated sample column-wise
        sub_mdl_sample.sort(axis=0)

        return sub_mdl_sample
    
    def get_aerial_survey_sample(self,infra="production") -> tuple[np.ndarray]:
        """
        A function that can take a record of covered sources and corresponding 
        plumes (it's OK if there are plumes that dont correspond to any listed source - 
        they are excluded) for the prescribed infrastructure, and samples the 
        plume observations, accounting for observed intermittency. It then 
        applies noise and deterministic correction.

        It's supposed to return the sample of emissions and their corresponding 
        wind-normalized counterparts.

        Args:
            infra (str):
                This string will be used directly to look up values under 
                dictionary properties of an asset group in the input class
                `self.cfg.aerialSurvey`.

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
        # Define sources and plumes tables for this infrastructure
        infra_sources = self.cfg.aerialSurvey.source_groups[infra]
        infra_plumes = self.cfg.aerialSurvey.plume_groups[infra]

        # Define emissions and wind-normalized emissions
        infra_em = self.cfg.aerialSurvey.plume_emissions[infra]
        infra_windnorm = self.cfg.aerialSurvey.plume_wind_norm[infra]
        
        # max_count = maximum number of coverages
        max_count = infra_sources[self.cfg.aerialSurvey.coverage_count].max()
        
        # df = DataFrame with columns [0, 1, ..., <max coverage - 1>, "coverage_count"]
        # and a number of rows equal to the number of unique sources.
        df = infra_sources[
            [self.cfg.aerialSurvey.source_id_col,self.cfg.aerialSurvey.coverage_count]
        ].copy()
        df.set_index(self.cfg.aerialSurvey.source_id_col,inplace=True)

        plume_data = infra_plumes.copy()
        
        # Create a column in common wind-normalized emissions units
        plume_data["windnorm_em"] = infra_windnorm

        # Create an emissions rate column in common emissions rate units
        plume_data["em"] = infra_em

        # get separate lists of the observed wind-normalized emissions rates and wind speeds
        emiss_and_windnorm_emiss = (
            plume_data
            .groupby(self.cfg.aerialSurvey.source_id_col)
            [["em","windnorm_em"]]
            .agg(list)
        )

        self.log.debug(f"The highest coverage count of {infra=} is {max_count}")
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
        
            self.log.debug(
                f"Source plume number {col+1} was covered and emitting for "
                f"{(~df[col].isna()).sum()} plumes. It was covered but not "
                f"emitting for {((df[self.cfg.aerialSurvey.coverage_count]>col) & (df[col].isna())).sum()} plumes. "
                "The remainder were not covered."
            )
            # For any observations remaining nan that should still count as coverage instance, set them to 0 (i.e., it was observed and was not emitting)
            df.loc[(df[self.cfg.aerialSurvey.coverage_count]>col) & (df[col].isna()),col] = 0
        
        # Drop the coverage_count column, no longer needed
        df.drop(columns=self.cfg.aerialSurvey.coverage_count,inplace=True)

        # Sample each row N times, excluding NaN values
        # This results in an `emission_source_id`-indexed series whose values are each a 1D np.array type, each representing the sampled observations
        # The values in the sampled 1-D array can be 0 (no emissions observed), or a (wind-normalized emissions, wind speed) pair.
        sample = df.apply(
            lambda row: row.sample(self.cfg.n_mc_samples,replace=True,weights=1*(~row.isna())).values,
            axis=1
        )

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
        if self.cfg.correction_fn is not None:
            self.log.debug(
                f"Applying {self.cfg.correction_fn} to sampled {infra} emissions"
            )
            emissions = self.cfg.correction_fn(emissions)

        if self.cfg.simulate_error:
            self.log.debug(
                f"Applying {self.cfg.simulate_error} to sampled {infra} emissions"
            )
            emissions = self.cfg.noise_fn(emissions)
        
        # Use function to handle 0s
        self.log.debug(
            f"The resulting aerial {infra} emissions sample has a mean of "
            f"{(emissions<=0).sum(axis=0).mean()} values ≤0 in each "
            "monte-carlo iteration."
        )
        emissions = self.cfg.handle_negative(emissions)

        return emissions, wind_normalized_em
    
    def combine_prod_samples(self):
        """
        Combine the aerial and simulated distributions into a new attribute 
        called `self.combined_samples` which will have self.cfg.num_wells_to_simulate
        rows and self.cfg.n_mc_samples columns.
          
        It creates this with aerial sampled data, partial detection emissions, 
        and sampled simulated emissions. By the time of calling this method, 
        these should be in the form of:
            
            * `self.aerial_samples["production"]` : 
                A tuple of (emissions, partial detection correction). The 
                emissions should be (num emitting wells)x(self.cfg.n_mc_samples) 
                table of sampled, corrected, and perhaps noised aerial 
                observations, where intermittency has also been taken into 
                account.
                The partial detection correction should be a 
                (num emitting wells)x(self.cfg.n_mc_samples) table of estimated 
                extra emissions from the entire basin under study, intended to 
                reflect the "missed" emissions from the partial detection 
                correction.
            * `self.simulated_sample` : 
                A (self.cfg.num_wells_to_simulate)x(self.cfg.n_mc_samples) table of 
                sampled simulated emissions, which should have already been 
                stratified if relevant.

        Obviously these all have to be in the same physical units.

        This function will combine these distributions by first finding the 
        transition point based on the cumulative emissions distributions of 
        (aerial + partial detection correction) on the one hand, and simulated 
        emissions on the other. A transition point will be calculated for each 
        individual monte-carlo iteration.

        After finding the transition point, we create a combined distribution 
        by taking (a) all sampled aerial emissions that are at least as large 
        as the transition point, together with corresponding partial detection 
        corrections, and (b) a sample of all simulated values below the 
        transition point that fit into the remainder of the 
        `self.num_wells_to_simulate` records not filled by aerial observations.

        Lastly, the resulting combined distributions are sorted ascending.
        """
        # Get (emissions, partial detection correction) paris for production
        aerial_emissions, partial_detection = self.aerial_samples["production"]

        if self.cfg.prod_transition_point is None:
            self.log.info(
                "No transition point was provided, it will be computed by "
                "comparing the simulated and aerial distributions."
            )
            # aerial_cumsum = combined increasing cumulative sum of sampled aerial 
            #   emissions AND contributions from partial detection.
            aerial_cumsum = aerial_emissions.cumsum(axis=0) + partial_detection.cumsum(axis=0)
            
            # Turn the cumulative sum into a decreasing quantity
            aerial_cumsum = aerial_cumsum.max(axis=0) - aerial_cumsum
            
            # Sort then cumsum each sampling of the simulated emissions
            sim_data = np.sort(self.simulated_sample,axis=0)
            simmed_cumsum = sim_data.cumsum(axis=0)
            
            # Convert into decreasing cumulative total of simulated emissions
            simmed_cumsum = simmed_cumsum.max(axis=0) - simmed_cumsum
            
            # Define the transition point based on the cumulative emissions 
            # distributions.
            self.prod_tp = find_transition_point(
                aerial_x = aerial_emissions,
                aerial_y = aerial_cumsum,
                sim_x = sim_data,
                sim_y = simmed_cumsum,
            )
            self.log.debug(
                f"The computed average transition point is {self.prod_tp.mean()}"
            )
        elif isinstance(self.cfg.prod_transition_point,(int,float,)):
            self.log.info(
                f"The transition point was provided as {self.cfg.prod_transition_point}, "
                "and will be used directly to combine aerial and simulated "
                "emissions distributions."
            )
            self.prod_tp = np.array([self.cfg.prod_transition_point]*self.cfg.n_mc_samples)

        # To start the process, define `self.combined_samples` and `
        # self.prod_partial_detection_emissions` as [num wells to simulate]x[N MC samples]
        # that hold the result of aerial sampling. Simulated values are to be 
        # inserted into these tables.
        # np.pad() adds a bunch of rows with 0s preceding the sampled values
        self.prod_combined_samples = np.pad(
            aerial_emissions,
            ((self.cfg.num_wells_to_simulate-aerial_emissions.shape[0],0),(0,0)),
            mode="constant",
            constant_values=((0,0),(0,0))
        )

        self.prod_partial_detection_emissions = np.pad(
            partial_detection,
            ((self.cfg.num_wells_to_simulate-partial_detection.shape[0],0),(0,0)),
            mode="constant",
            constant_values=((0,0),(0,0))
        )

        # Now go through each monte carlo iteration and combine the samples.
        for n in range(self.cfg.n_mc_samples):
            
            # Get the transition point for this MC run
            tp = self.prod_tp[n]
            
            # Define simulations below this iteration's transition point
            sim_below_transition = self.simulated_sample[:,n][self.simulated_sample[:,n]<tp]

            # Find the first index where the aerial emissions in this column are ≥transition point
            idx_above_transition = np.argmin(self.prod_combined_samples[:,n]<tp)

            if len(sim_below_transition)<idx_above_transition:
                raise IndexError(
                    f"In monte-carlo iteration {n}, there are "
                    f"{len(sim_below_transition)} simulated emissions values "
                    f"below the transition point (={tp}), but "
                    f"{idx_above_transition} infrastructure sites to try to "
                    f"simulate (out of {self.cfg.num_wells_to_simulate} total). "
                    "The code usually fills each such site by choosing with "
                    "replacement from the available simulated emissions, but "
                    "in this case the code doesn't know what to do without "
                    "either leaving some 0s between them, or perhaps "
                    "over-estimating the simulated contribution by adding "
                    "extra simulated records."
                )

            # For all preceding indices, insert random simulated emissions below the transition point
            self.prod_combined_samples[:idx_above_transition,n] = np.random.choice(sim_below_transition,idx_above_transition,replace=True)
            
            # In any partial detection emissions tracked to be added directly to the cdf, zero out contributions associated to emissions below transition point.
            self.prod_partial_detection_emissions[:idx_above_transition,n] = 0
        
        # Re-sort the newly combined records. Maintain correspondence with the 
        # partial detection correction by getting the sorted index and using
        # for both.
        combined_sort_idx = self.prod_combined_samples.argsort(axis=0)
        for n in range(self.cfg.n_mc_samples):
            # Sort the combined samples column-wise
            self.prod_combined_samples[:,n] = self.prod_combined_samples[combined_sort_idx[:,n],n]

            # Sort the corresponding extra_emissions_for_cdf
            self.prod_partial_detection_emissions[:,n] = self.prod_partial_detection_emissions[combined_sort_idx[:,n],n]

    def compute_simulated_midstream_emissions(self):
        """
        Use the available midstream loss information (e.g. midstreamGHGIData) 
        of the input data to define an amount of estimated midstream loss 
        from sub-detection-level emissions.

        This is computed as [fractional loss rate] * [total covered prdouction],
        where the fractional loss rate is either total (inclusive of emissions 
        likely detected aerially), or sub-detection-level only (attempting 
        to remove some of the estimate to leave only sub-detection-level).

        For GHGI data, it's expected that the loss rates are given as a 
        pd.Series with "low", "mid", and "high" indices, which are supposed 
        to be mapped to the confidence intervals.
        """
        # sub-detection-level CH4 midstream emissions, in COMMON_EMISSIONS_UNITS
        self.submdl_ch4_midstream_emissions = (
            self.cfg.midstreamGHGIData.submdl_midstream_ch4_loss_rate
            * self.cfg.ch4_total_covered_production_mass
        )
        
        # All CH4 midstream emissions, in COMMON_EMISSIONS_UNITS
        self.total_ch4_midstream_emissions = (
            self.cfg.midstreamGHGIData.total_midstream_ch4_loss_rate
            * self.cfg.ch4_total_covered_production_mass
        )
    
    def generate_and_write_outputs(self):
        """
        Call methods that can add tabular outputs to self.table_outputs, and 
        also generate plots. All of the tables in the self.table_outputs 
        dictionary will be saved with their index.

        All outputs are intended to be saved into `self.outpath`.
        """
        # Make the outpath folder if it doesn't exist.
        if not os.path.exists(self.outfolder):
            os.mkdir(self.outfolder)

        # Save the input configs that were used for this run
        self.save_config()
        
        # Call methods that add content to self.table_outputs
        self.make_tabular_outputs()

        # For each table name : pd.DataFrame pair, write it to the outpath.
        for name, table in self.table_outputs.items():
            if not name.endswith(".csv"):
                name += ".csv"
            
            self.log.info(f"Saving {name} to {self.outfolder}")
            table.to_csv(os.path.join(self.outfolder,name),index=False)
        
        self.gen_plots()

    def save_config(self):
        """
        Save the dictionary representation of the config as a json file 
        into the output. This is supposed to include all of the parsed 
        default behavior, as well as what was specified in the input file.
        """
        config = self.cfg.to_dict()
        path = os.path.join(self.outfolder,"used_config.json")
        
        self.log.info(f"Saving used config options to {path}.")
        with open(path,"w") as f:
            json.dump(config,f)
    
    def make_tabular_outputs(self):
        """
        Call methods to add tabular (pd.DataFrame) outputs to self.table_outputs.
        """
        self.log.info("Creating the production summary tables")
        # Add a summary table of key results from component distributions
        self.make_key_results()
        
        # Add summary table of production distribution
        self.make_prod_distr_summary()

        # Summarize fractional loss using covered production
        self.make_fractional_loss()

        # Summarize aerial survey samples per asset group
        self.make_aerial_characterization()

        if self.save_mean_dist:
            # Add summary of production distributions (larger table)
            self.make_mean_production_cumdist_tables()

    def make_fractional_loss(self):
        """
        Make a small new table to summarize production and fractional loss.
        """
        result = pd.DataFrame({
            f"Covered Production (CH4 {COMMON_PRODUCTION_UNITS})" : [np.nan],
            f"Covered Production (CH4 {COMMON_EMISSIONS_UNITS})" : [np.nan],
            f"Mean fractional CH4 Loss in production ({COMMON_EMISSIONS_UNITS} lost / {COMMON_EMISSIONS_UNITS} produced)":[np.nan],
            f"Mean fractional CH4 Loss in midstream ({COMMON_EMISSIONS_UNITS} lost / {COMMON_EMISSIONS_UNITS} produced)":[np.nan],
            f"Mean fractional Energy Loss in production ({COMMON_ENERGY_UNITS} lost / {COMMON_ENERGY_UNITS} produced)":[np.nan],
            f"Mean fractional Energy Loss in midstream ({COMMON_ENERGY_UNITS} lost / {COMMON_ENERGY_UNITS} produced)":[np.nan]
        })

        # Fill with a single value: total covered volumetric and mass productivity of CH4
        result[f"Covered Production (CH4 {COMMON_PRODUCTION_UNITS})"] = self.cfg.ch4_total_covered_production_volume
        result[f"Covered Production (CH4 {COMMON_EMISSIONS_UNITS})"] = self.cfg.ch4_total_covered_production_mass
        
        # Volumetric production fractional loss = [combined production distribution total emissions rate] / [covered productivity production rate]
        result[f"Mean fractional CH4 Loss in production ({COMMON_EMISSIONS_UNITS} lost / {COMMON_EMISSIONS_UNITS} produced)"] = (
            (
                self.prod_combined_samples.sum(axis=0).mean() 
                + self.prod_partial_detection_emissions.sum(axis=0).mean()
            )
            /self.cfg.ch4_total_covered_production_mass
        )
        
        mid_emiss, mid_pd_corr = self.aerial_samples["midstream"]
        
        # Compute midstream aerial contribution above midstream transition point
        midstream_aerial_em_abovetp = (
            (
                # midstream aerial samples total emissions, only including those ≥ tp
                np.array([mid_emiss[:,n][mid_emiss[:,n]>=self.cfg.midstream_transition_point].sum() for n in range(self.cfg.n_mc_samples)])
                
                # midstream partial detection emissions, only including those with corresponding emissions ≥ tp
                +np.array([mid_pd_corr[:,n][mid_emiss[:,n]>=self.cfg.midstream_transition_point].sum() for n in range(self.cfg.n_mc_samples)])
            ).mean()/1e3
        )
        
        # midstream loss = sub-MDL emissions + aerial (above MDL) emissions
        midstream_lost_emiss = (
            self.submdl_ch4_midstream_emissions["mid"]
            + midstream_aerial_em_abovetp
        )
        
        # Volumetric midstream fractional loss = [sub-mdl estimate + above-tp aerial total emissions rate] / [covered productivity production rate]
        result[f"Mean fractional CH4 Loss in midstream ({COMMON_EMISSIONS_UNITS} lost / {COMMON_EMISSIONS_UNITS} produced)"] = (
            midstream_lost_emiss/self.cfg.ch4_total_covered_production_mass
        )

        # Fractional Energy Loss denominator = 
        #   Energy produced per day, total from oil + gas
        #   (MJ/d)
        energy_loss_denominator = (
            # Bbl oil -> MJ
            self.cfg.total_covered_oilprod_bbld * MJ_PER_BOE + 
            
            # Mcf NG -> MJ
            self.cfg.total_covered_ngprod_mcfd * energycontent_mj_mcf(self.cfg.gas_composition)
        )
        # Fractional Energy Loss production numerator = 
        #   [Energy content of production CH4 emissions]
        
        # E.g. Desired emissions unit = "kg/d" (same time horizon as produced energy)
        desired_num_unit = COMMON_EMISSIONS_UNITS.split("/")[0] + "/d"
        prod_energy_loss_num = (
            # MJ/kg of CH4
            ENERGY_DENSITY_MJKG["c1"] 
            # x kgCH4/h <- COMMON_EMISSIONS_UNITS
            * (
                self.prod_combined_samples.sum(axis=0).mean() 
                + self.prod_partial_detection_emissions.sum(axis=0).mean()
            )
            # x [24 kg/d per 1 kg/h]
            * convert_units(1,COMMON_EMISSIONS_UNITS,desired_num_unit)
        )
        
        # Fractional energy loss = [embodied energy of emitted CH4]/(embodied energy of produced gas + oil)
        
        result[f"Mean fractional Energy Loss in production ({COMMON_ENERGY_UNITS} lost / {COMMON_ENERGY_UNITS} produced)"] = (
            prod_energy_loss_num / energy_loss_denominator
        )
        result[f"Mean fractional Energy Loss in midstream ({COMMON_ENERGY_UNITS} lost / {COMMON_ENERGY_UNITS} produced)"] = (
            (
                midstream_lost_emiss 
                * ENERGY_DENSITY_MJKG["c1"] 
                * convert_units(1,COMMON_EMISSIONS_UNITS,desired_num_unit)
            )
            / energy_loss_denominator
        )

        self.table_outputs["Fractional Loss Summary"] = result
    
    def make_key_results(self):
        """
        This tabular output summarizes the total emissions contributions from 
        each component distribution, and in total. To the extent possible, the 
        contribution of each is measured both before and after accounting 
        for the transition point.
        """
        # E.g. quantity_cols = ["Avg","2.5% CI","97.5% CI"]
        quantity_cols = ["Avg",*[str(100*q)+"% CI" for q in self._quantiles]]

        # Create an empty table that will summarize each component of the 
        # combined production emissions distribution.
        prod_and_mid_summary = pd.DataFrame(
            index=[
                f"Production Aerial Only Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Production Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Production Combined Aerial + Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Production Simulated Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})", 
                f"Production overall Combined Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Production Transition Point ({COMMON_EMISSIONS_UNITS})",
                f"Midstream GHGI-based CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Midstream Aerial Only Total CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Midstream Partial Detection Total CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Midstream Combined Aerial + Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})",
                f"Total Production + Midstream CH4 Emissions Estimate, All Sources (thousand {COMMON_EMISSIONS_UNITS})",
            ],
            columns=pd.MultiIndex.from_product(
                [["By Itself","Accounting for Transition Point"],quantity_cols],
            )
        )
        
        # Get the production emissions and partial detection for quantification
        prod_emiss, prod_partial_detec = self.aerial_samples["production"]

        # Report the sampled aerial production emissions distribution, regardless of transition point
        sum_emiss_aerial = prod_emiss.sum(axis=0)/1e3
        prod_and_mid_summary.loc[f"Production Aerial Only Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_aerial)[quantity_cols].values

        # Report sampled aerial production emissions distributions above transition point
        sum_emiss_aerial_abovetp = np.array([prod_emiss[:,n][prod_emiss[:,n]>=self.prod_tp[n]].sum() for n in range(len(self.prod_tp))])/1e3
        prod_and_mid_summary.loc[f"Production Aerial Only Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_emiss_aerial_abovetp)[quantity_cols].values

        # Report total partial detection of aerially surveyed production infrastructure
        sum_emiss_partial = prod_partial_detec.sum(axis=0)/1e3
        prod_and_mid_summary.loc[f"Production Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_partial)[quantity_cols].values
        
        # Report sampled partial detection corrections corresponding to emissions above transition point
        sum_pd_abovetp = np.array([prod_partial_detec[:,n][prod_emiss[:,n]>=self.prod_tp[n]].sum() for n in range(len(self.prod_tp))])/1e3
        prod_and_mid_summary.loc[f"Production Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_pd_abovetp)[quantity_cols].values

        # Report combined production emissions from aerial sample AND partial detection correction
        sum_emiss_aer_comb = (prod_emiss.sum(axis=0) + prod_partial_detec.sum(axis=0))/1e3
        prod_and_mid_summary.loc[f"Production Combined Aerial + Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_aer_comb)[quantity_cols].values

        # This will be combined production aerial+partial detection, but ONLY total contributions above each transition point
        sum_emiss_aer_comb_abovetp = (sum_emiss_aerial_abovetp + sum_pd_abovetp)/1e3
        prod_and_mid_summary.loc[f"Production Combined Aerial + Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_emiss_aer_comb_abovetp)[quantity_cols].values
        
        # The total amount of simulated emissions
        sum_emiss_sim = self.simulated_sample.sum(axis=0)/1e3
        prod_and_mid_summary.loc[f"Production Simulated Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_sim)[quantity_cols].values

        # The total amount of simulated emissions below transition point, that end up being coounted in the resulting distribution.
        sum_emiss_sim_belowtp = np.array([self.prod_combined_samples[:,n][self.prod_combined_samples[:,n]<self.prod_tp[n]].sum() for n in range(len(self.prod_tp))])/1e3
        prod_and_mid_summary.loc[f"Production Simulated Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_emiss_sim_belowtp)[quantity_cols].values
        
        # Report from total combined distribution: only "By Itself" (doesn't make sense to 'account for transition point' in combined distribution)
        sum_emiss_all_comb = (self.prod_combined_samples.sum(axis=0) + self.prod_partial_detection_emissions.sum(axis=0))/1e3
        prod_and_mid_summary.loc[f"Production overall Combined Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_all_comb)[quantity_cols].values

        # Report the same quantities for the transition point.
        prod_and_mid_summary.loc[f"Production Transition Point ({COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(self.prod_tp)[quantity_cols].values
        
        # Get the midstream emissions and partial detection for quantification
        mid_emiss, mid_partial_detec = self.aerial_samples["midstream"]
        
        # Report the total estimated midstream emissions based on the GHGI estimation, as well as the estimated sub-detection-level estimate
        prod_and_mid_summary.loc[f"Midstream GHGI-based CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromghgi(self.total_ch4_midstream_emissions/1e3)[quantity_cols].values
        prod_and_mid_summary.loc[f"Midstream GHGI-based CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromghgi(self.submdl_ch4_midstream_emissions/1e3)[quantity_cols].values
        
        # Report the sampled aerial midstream emissions distribution, regardless of transition point
        sum_emiss_aerial = mid_emiss.sum(axis=0)/1e3
        prod_and_mid_summary.loc[f"Midstream Aerial Only Total CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_aerial)[quantity_cols].values

        # Report sampled aerial midstream emissions distributions above transition point
        sum_emiss_aerial_abovetp = np.array([mid_emiss[:,n][mid_emiss[:,n]>=self.cfg.midstream_transition_point].sum() for n in range(self.cfg.n_mc_samples)])/1e3
        prod_and_mid_summary.loc[f"Midstream Aerial Only Total CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_emiss_aerial_abovetp)[quantity_cols].values

        # Report total partial detection of aerially surveyed midstream infrastructure
        sum_emiss_partial = mid_partial_detec.sum(axis=0)/1e3
        prod_and_mid_summary.loc[f"Midstream Partial Detection Total CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_partial)[quantity_cols].values
        sum_emiss_partial_abovetp = np.array([mid_partial_detec[:,n][mid_emiss[:,n]>=self.cfg.midstream_transition_point].sum() for n in range(self.cfg.n_mc_samples)])/1e3
        prod_and_mid_summary.loc[f"Midstream Partial Detection Total CH4 Emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_emiss_partial_abovetp)[quantity_cols].values
        
        # Report combined midstream emissions from aerial sample AND partial detection correction
        sum_emiss_aer_comb = (mid_emiss.sum(axis=0) + mid_partial_detec.sum(axis=0))/1e3
        prod_and_mid_summary.loc[f"Midstream Combined Aerial + Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = self.mean_and_quantiles_fromsamples(sum_emiss_aer_comb)[quantity_cols].values

        # This will be combined midstream aerial+partial detection, but ONLY total contributions above each transition point
        sum_emiss_aer_comb_abovetp = sum_emiss_aerial_abovetp + sum_emiss_partial_abovetp
        prod_and_mid_summary.loc[f"Midstream Combined Aerial + Partial Detection Total CH4 emissions (thousand {COMMON_EMISSIONS_UNITS})","Accounting for Transition Point"] = self.mean_and_quantiles_fromsamples(sum_emiss_aer_comb_abovetp)[quantity_cols].values

        # Total emissions across all emissions sizes and production+midstream asset types
        total_emissions = (
            # Production aerial above transition point
            np.array([prod_emiss[:,n][prod_emiss[:,n]>=self.prod_tp[n]].sum() for n in range(len(self.prod_tp))])/1e3

            # Production partial detection (only above TP)
            + np.array([prod_partial_detec[:,n][prod_emiss[:,n]>=self.prod_tp[n]].sum() for n in range(len(self.prod_tp))])/1e3

            # Contribution of simulated production emissions below TP
            + np.array([self.prod_combined_samples[:,n][self.prod_combined_samples[:,n]<self.prod_tp[n]].sum() for n in range(len(self.prod_tp))])/1e3

            # Midstream aerial above transition point
            + np.array([mid_emiss[:,n][mid_emiss[:,n]>=self.cfg.midstream_transition_point].sum() for n in range(self.cfg.n_mc_samples)])/1e3

            # Midstream partial detection (only above TP)
            + np.array([mid_partial_detec[:,n][mid_emiss[:,n]>=self.cfg.midstream_transition_point].sum() for n in range(self.cfg.n_mc_samples)])/1e3
        )
        # Quantify everything except sub-detection-level midstream emissions
        total_quant = self.mean_and_quantiles_fromsamples(total_emissions)[quantity_cols]

        # Add sub-MDL midstream emissions
        total_quant["Avg"] += self.submdl_ch4_midstream_emissions["mid"]/1e3
        
        # The CI can't be computed normally because the midstream value is a point estimate.
        total_quant["2.5% CI"] = np.nan
        total_quant["97.5% CI"] = np.nan
        prod_and_mid_summary.loc[f"Total Production + Midstream CH4 Emissions Estimate, All Sources (thousand {COMMON_EMISSIONS_UNITS})","By Itself"] = total_quant.values

        # Put the resulting table into self.table_outputs
        self.table_outputs["Production and Midstream Summary"] = prod_and_mid_summary.reset_index()
    
    def make_prod_distr_summary(self):
        """
        Make an output that tries to characterize the resulting combined 
        cumulative emissions distribution of production emissions by finding 
        some key points of interest, like what the kg/h values are at certain 
        percentiles, and what the percentile values are at certain kg/h values.

        One column will be "Emissions Value"
        """
        cumsum_y = self.prod_combined_samples.cumsum(axis=0) + self.prod_partial_detection_emissions.cumsum(axis=0)
        cumsum_y = 100*(1-cumsum_y/cumsum_y.max(axis=0)).mean(axis=1)
        dist_x = self.prod_combined_samples.mean(axis=1)

        dist_summary = pd.DataFrame()
        
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

        dist_summary[f"Emissions Value ({COMMON_EMISSIONS_UNITS})"] = [
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

        dist_summary.sort_values(
            f"Emissions Value ({COMMON_EMISSIONS_UNITS})",
            inplace=True,
            ascending=True
        )
        dist_summary.reset_index(drop=True,inplace=True)

        # Put the resulting table into self.table_outputs
        self.table_outputs["Combined Production Distribution Summary"] = dist_summary
    
    def mean_and_quantiles_fromsamples(self,values: np.ndarray) -> pd.Series:
        """
        Return the average of the given values, as well as the estimated 
        quantiles, based on the observed quantiles across all the given 
        samples and visits per site.

        Args:
            values (np.ndarray):
                A 1-d array of values to statistically summarize.

        Returns:
            pd.Series:
                A series indexed by "Avg", "2.5% CI","97.5% CI", (e.g.), whose
                values are the estimates of the corresponding statistic for 
                given values.
        """
        output = pd.Series(
            index=["Avg",*[self._lbl.format(str(100*q)) for q in self._quantiles]]
        )
        output["Avg"] = values.mean()
        quantiles = np.quantile(values,self._quantiles)
        
        # Denominator = sqrt(Total site visits including re-visits / total sites to simulate)
        denominator = np.sqrt((self.well_visit_count/self.wells_per_site)/self.cfg.num_wells_to_simulate)
        for q, val in zip(self._quantiles, quantiles):
            diff = abs(output["Avg"]-val) / denominator

            output[self._lbl.format(str(100*q))] = (
                output["Avg"] - diff 
                if val<output["Avg"] 
                else output["Avg"] + diff
            )

        return output
    
    def mean_and_quantiles_fromghgi(self,values: pd.Series) -> pd.Series:
        """
        Return the given ghgi-based estimate with a new index labeled with 
        the 2.5% and 97.5% confidence labels for the output summary tables.
        (It won't use self._quantiles because the underlying quantities are 
        at least based on this 95% interval. So if you really want to change 
        the confidence intervals, it's up to you what to do with the 
        interpretation of the underlying data.

        Args:
            values (pd.Seires):
                A length 3 pd.Series with indices "low","mid","high"

        Returns:
            pd.Series:
                A series indexed by "Avg", "2.5% CI","97.5% CI", (e.g.), whose
                values are the estimates of the corresponding statistic for 
                given values.
        """
        output = pd.Series()

        output["Avg"] = values["mid"]
        output["2.5% CI"] = values["low"]
        output["97.5% CI"] = values["high"]

        return output
    
    def make_aerial_characterization(self):
        """
        Create a table holding the characterization of the sampled and 
        adjusted aerial data, for each of the provided asset groups.
        """
        # Instantiate empty dataframe
        result = pd.DataFrame()

        # Emissions unit into which CH4 emissions should be converted,
        # for combination with ENERGY_DENSITY_MJKG
        # E.g. desired_num_unit = "kg/d"
        desired_num_unit = COMMON_EMISSIONS_UNITS.split("/")[0] + "/d"

        # This is the denominator of fractional energy loss, in MJ/d
        energy_loss_denominator = (
            # Bbl oil -> MJ
            self.cfg.total_covered_oilprod_bbld * MJ_PER_BOE + 
            
            # Mcf NG -> MJ
            self.cfg.total_covered_ngprod_mcfd * energycontent_mj_mcf(self.cfg.gas_composition)
        )
        
        for group, (emiss, pd_corr) in self.aerial_samples.items():

            # Compute total emissions & PD correction for each iteration
            total_emiss = emiss.sum(axis=0)
            total_pd = pd_corr.sum(axis=0)

            # Compute the combined total emissions for each iteration
            total_combined = total_emiss + total_pd

            # Characterize the resulting sample of emissions values (mean and percentiles)
            emiss_quant = self.mean_and_quantiles_fromsamples(total_emiss)
            pd_quant = self.mean_and_quantiles_fromsamples(total_pd)
            combined_quant = self.mean_and_quantiles_fromsamples(total_combined)

            # Define volumetric fractional loss as [mass emitted]/[mass produced]
            frac_loss_emiss = emiss_quant/self.cfg.ch4_total_covered_production_mass
            frac_loss_pd = pd_quant/self.cfg.ch4_total_covered_production_mass
            frac_loss_tot = combined_quant/self.cfg.ch4_total_covered_production_mass

            # Define energy fractional loss

            # Fractional energy loss is defined as, e.g.:
            # (energy in emitted CH4)/(produced energy)
            # ([MJ/kg] * [kg/h] * [h/d]) / ([MJ/d])
            energy_frac_loss_emiss = (
                ENERGY_DENSITY_MJKG["c1"] 
                * convert_units(emiss_quant,COMMON_EMISSIONS_UNITS,desired_num_unit)
                /energy_loss_denominator
            )
            energy_frac_loss_pd = (
                ENERGY_DENSITY_MJKG["c1"] 
                * convert_units(pd_quant,COMMON_EMISSIONS_UNITS,desired_num_unit)
                /energy_loss_denominator
            )
            energy_frac_loss_tot = (
                ENERGY_DENSITY_MJKG["c1"] 
                * convert_units(combined_quant,COMMON_EMISSIONS_UNITS,desired_num_unit)
                /energy_loss_denominator
            )
            
            group_df = pd.DataFrame(
                index=pd.MultiIndex.from_product(
                    [
                        # Index level 0 = Emissions distribution being characterized
                        ["Aerial Only","Partial Detection Correction","Aerial + Partial Detection"],
                        
                        # Index level 1 = How the distribution is being characterized
                        [f"Total Emissions ({COMMON_EMISSIONS_UNITS})","Fractional Volumetric Loss (kgCH4 emitted / kgCH4 produced)","Fractional Energy Loss (MJ CH4 emitted/MJ oil+gas produced)"],

                        # Index level 2 = Quantification (mean/2.5%/97.5%)
                        ["Avg",*[self._lbl.format(str(100*q)) for q in self._quantiles]],
                    ],
                    names=["Distribution","Quantity","Quantification"]
                )
            )
            group_df.sort_index(inplace=True)
            
            # Assign a column "Asset Group" with the asset group name
            group_df["Asset Group"] = group

            # Assign an empty "value" column to fill out
            group_df["value"] = np.nan

            for q in emiss_quant.index:
                # Assign aerial-only characterization
                group_df.loc[("Aerial Only",f"Total Emissions ({COMMON_EMISSIONS_UNITS})",q),"value"] = emiss_quant.loc[q]
                group_df.loc[("Aerial Only","Fractional Volumetric Loss (kgCH4 emitted / kgCH4 produced)",q),"value"] = frac_loss_emiss.loc[q]
                group_df.loc[("Aerial Only","Fractional Energy Loss (MJ CH4 emitted/MJ oil+gas produced)",q),"value"] = energy_frac_loss_emiss.loc[q]
                
                # Assign partial detection characterization
                group_df.loc[("Partial Detection Correction",f"Total Emissions ({COMMON_EMISSIONS_UNITS})",q),"value"] = pd_quant.loc[q]
                group_df.loc[("Partial Detection Correction","Fractional Volumetric Loss (kgCH4 emitted / kgCH4 produced)",q),"value"] = frac_loss_pd.loc[q]
                group_df.loc[("Partial Detection Correction","Fractional Energy Loss (MJ CH4 emitted/MJ oil+gas produced)",q),"value"] = energy_frac_loss_pd.loc[q]
                
                # Assign combined distribution characterization
                group_df.loc[("Aerial + Partial Detection",f"Total Emissions ({COMMON_EMISSIONS_UNITS})",q),"value"] = combined_quant.loc[q]
                group_df.loc[("Aerial + Partial Detection","Fractional Volumetric Loss (kgCH4 emitted / kgCH4 produced)",q),"value"] = frac_loss_tot.loc[q]
                group_df.loc[("Aerial + Partial Detection","Fractional Energy Loss (MJ CH4 emitted/MJ oil+gas produced)",q),"value"] = energy_frac_loss_tot.loc[q]

            group_df.reset_index(inplace=True)

            result = pd.concat([result,group_df],axis=0)

        self.table_outputs["Aerial Characterization"] = result
    
    def make_mean_production_cumdist_tables(self):
        """
        Save a production emissions distributions to `self.table_outputs` by 
        taking the mean over all the monte-carlo iterations of all wells to 
        simulate. This is reported for (a) aerial emissions, (b) partial 
        detection emissions, (c) simulated emissions, and (d) the 
        combined production emissions distribution.

        Returns:
            pd.DataFrame: 
                A [num_wells_to_simulate]x24 Data Frame. For each of aerial, 
                partial detection, simulated emissions, and combined emissions
                distributions, it will create:
                    * Mean emissions at each well site, across all MC runs
                    * 2.5% emissions at each well site, across all MC runs
                    * 97.5% emissions at each well site, across all MC runs
                    * Mean cumulative emissions, across all MC runs
                    * 2.5% cumulative emissions at each well site, across all MC runs
                    * 97.5% cumulative emissions at each well site, across all MC runs

                In the context of plots created for papers, the "emissions" 
                are the X, and the "cumulative emissions" are the Y.
        """
        self.log.info("Creating the mean production distribution tables")
        output = pd.DataFrame()
        
        # Define factor for translating observed percentiles to confidence
        # intervals
        denominator = np.sqrt((self.well_visit_count/self.wells_per_site)/self.cfg.num_wells_to_simulate)
        
        # Get sampled production emissions and partial detection correction
        prod_emiss, prod_pd = self.aerial_samples["production"]

        # Create zero-padded versions of sampled production emissions and 
        # partial detection correction
        aerial_em = np.pad(
            prod_emiss,
            ((self.cfg.num_wells_to_simulate-prod_emiss.shape[0],0),(0,0)),
            mode="constant",
            constant_values=((0,0),(0,0))
        )
        pd_corr = np.pad(
            prod_pd,
            ((self.cfg.num_wells_to_simulate-prod_pd.shape[0],0),(0,0)),
            mode="constant",
            constant_values=((0,0),(0,0))
        )

        # Find the sorting index of the aerial sample
        sort_aerial = np.argsort(aerial_em,axis=0)

        # Sort both partial detection correction and aerial sample together 
        # (they shouldn't need sorting, but just to be safe...)
        for mc_run in range(aerial_em.shape[1]):
            aerial_em[:,mc_run] = aerial_em[sort_aerial[:,mc_run],mc_run]
            pd_corr[:,mc_run] = pd_corr[sort_aerial[:,mc_run],mc_run]

        aerial_cumsum = aerial_em.sum(axis=0) - aerial_em.cumsum(axis=0)
        aer_cumsum_quantiles = np.quantile(aerial_cumsum,self._quantiles,axis=1).T
        aer_em_quantiles = np.quantile(aerial_em,self._quantiles,axis=1).T
        
        # Save the mean aerial sample cumsum value
        output[f"Aerial Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] = aerial_cumsum.mean(axis=1)
        output[f"Mean Aerial Emissions ({COMMON_EMISSIONS_UNITS})"] = aerial_em.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Aerial Only, Cumulative Dist ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"
            lbl_em = f"Aerial Only Emissions ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"

            diff_cum = (
                aer_cumsum_quantiles[:,i] 
                - output[f"Aerial Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"]
                )/denominator
            diff_em = (
                aer_em_quantiles[:,i] 
                - output[f"Mean Aerial Emissions ({COMMON_EMISSIONS_UNITS})"]
                )/denominator

            output[lbl_cum] = output[f"Aerial Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] + diff_cum
            output[lbl_em] = output[f"Mean Aerial Emissions ({COMMON_EMISSIONS_UNITS})"] + diff_em
        
        
        partial_detection_cumsum = pd_corr.sum(axis=0) - pd_corr.cumsum(axis=0)
        pd_cumsum_quantiles = np.quantile(partial_detection_cumsum,self._quantiles,axis=1).T
        pd_em_quantiles = np.quantile(pd_corr,self._quantiles,axis=1).T
        
        # Save the mean partial detection cumsum value
        output[f"Partial Detection Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] = partial_detection_cumsum.mean(axis=1)
        output[f"Mean Partial Detection Emissions ({COMMON_EMISSIONS_UNITS})"] = pd_corr.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Partial Detection Only, Cumulative Dist ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"
            lbl_em = f"Partial Detection Only Emissions ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"

            diff_cum = (
                pd_cumsum_quantiles[:,i] 
                - output[f"Partial Detection Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"]
                )/denominator
            diff_em = (
                pd_em_quantiles[:,i] 
                - output[f"Mean Partial Detection Emissions ({COMMON_EMISSIONS_UNITS})"]
                )/denominator

            output[lbl_cum] = output[f"Partial Detection Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] + diff_cum
            output[lbl_em] = output[f"Mean Partial Detection Emissions ({COMMON_EMISSIONS_UNITS})"] + diff_em
        

        simulated_em = np.sort(self.simulated_sample,axis=0)
        simulated_cumsum = simulated_em.sum(axis=0) - simulated_em.cumsum(axis=0)
        sim_cumsum_quantiles = np.quantile(simulated_cumsum,self._quantiles,axis=1).T
        sim_em_quantiles = np.quantile(simulated_em,self._quantiles,axis=1).T
        
        # Save the mean simulated cumsum value
        output[f"Simulated Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] = simulated_cumsum.mean(axis=1)
        output[f"Mean Simulated Emissions ({COMMON_EMISSIONS_UNITS})"] = simulated_em.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Simulated Only, Cumulative Dist ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"
            lbl_em = f"Simulated Only Emissions ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"

            diff_cum = (
                sim_cumsum_quantiles[:,i] 
                - output[f"Simulated Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"]
                )/denominator
            diff_em = (
                sim_em_quantiles[:,i] 
                - output[f"Mean Simulated Emissions ({COMMON_EMISSIONS_UNITS})"]
                )/denominator

            output[lbl_cum] = output[f"Simulated Only, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] + diff_cum
            output[lbl_em] = output[f"Mean Simulated Emissions ({COMMON_EMISSIONS_UNITS})"] + diff_em
        
        overall_dist = self.prod_combined_samples.copy()
        overall_cumsum = (
            overall_dist.sum(axis=0) + self.prod_partial_detection_emissions.sum(axis=0) 
            - overall_dist.cumsum(axis=0) - self.prod_partial_detection_emissions.cumsum(axis=0)
        )
        overall_cumsum_quantiles = np.quantile(overall_cumsum,self._quantiles,axis=1).T
        overall_em_quantiles = np.quantile(overall_dist,self._quantiles,axis=1).T
        
        # Save the mean simulated cumsum value
        output[f"Combined Distribution, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] = overall_cumsum.mean(axis=1)
        output[f"Mean Combined Distribution Emissions ({COMMON_EMISSIONS_UNITS})"] = overall_dist.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Combined Distribution, Cumulative Dist ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"
            lbl_em = f"Combined Distribution Emissions ({COMMON_EMISSIONS_UNITS}), {str(100*q)}% CI"

            diff_cum = (
                overall_cumsum_quantiles[:,i] 
                - output[f"Combined Distribution, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"]
                )/denominator
            diff_em = (
                overall_em_quantiles[:,i] 
                - output[f"Mean Combined Distribution Emissions ({COMMON_EMISSIONS_UNITS})"]
                )/denominator

            output[lbl_cum] = output[f"Combined Distribution, Mean Cumulative Dist ({COMMON_EMISSIONS_UNITS})"] + diff_cum
            output[lbl_em] = output[f"Mean Combined Distribution Emissions ({COMMON_EMISSIONS_UNITS})"] + diff_em
        
        self.table_outputs["Mean Production Distributions"] = output
    
    def gen_plots(self):
        """
        Take a table of the overall combined emissions distributions of 
        production, and turn them into plots that include a vertical line 
        to indicate the average transition point.
        """
        cumsum = self.prod_combined_samples.cumsum(axis=0) + self.prod_partial_detection_emissions.cumsum(axis=0)
        cumsum_pct = 100*(1-cumsum/cumsum.max(axis=0))

        x = np.nanmean(self.prod_combined_samples,axis=1)
        y = np.nanmean(cumsum_pct,axis=1)
        
        plt.plot(x,y)
        plt.semilogx()
        max_val = 0
        plt.vlines(
            self.prod_tp.mean(), 0, 100, color='black', linestyle='dotted', 
            label=f'transition point ({self.prod_tp.mean()})'
        )
        max_val = max(x.max(), max_val)
        plt.xlim(1e-2, max_val)
        plt.grid(True)
        plt.ylabel("Fraction of Total Emissions at least x")
        plt.xlabel("Emissions Rate (kg/h)")
        plt.legend()

        self.log.info(
            "Saving the combined cumulative distribution plot to "
            f"{os.path.join(self.outfolder, 'combined_cumulative.svg/png')}"
        )
        plt.savefig(os.path.join(self.outfolder, "combined_cumulative.svg"))
        plt.savefig(os.path.join(self.outfolder, "combined_cumulative.png"))