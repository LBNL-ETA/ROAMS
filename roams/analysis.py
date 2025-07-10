import os
import logging

import pandas as pd
import numpy as np

from matplotlib import pyplot as plt

from roams.conf import RESULT_DIR

from roams.aerial.assumptions import power_correction, normal, zero_out
from roams.aerial.input import AerialSurveyData
from roams.aerial.partial_detection import PoD_bin, PoD_linear
from roams.transition_point import find_transition_point
from roams.simulated.stratify import stratify_sample

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
            The code won't work if this isn't specified, but it's required 
            to be derived from external analysis.
            Defaults to None.
        
        well_visit_count (int, optional): 
            This is supposed to reflect the total number of wells visited 
            during the aerial campaign.
            The code won't work if this isn't specified, but it's required 
            to be derived from external analysis.
            Defaults to None.
        
        wells_per_site (int, optional): 
            This is supposed to reflect the average number of wells per 
            well site in the covered aerial survey region. This gets used to 
            derive confidence intervals based on experimental distributions.
            The code won't work if this isn't specified, but it's required 
            to be derived from external analysis.
            Defaults to None.
        
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
        
        source_id_name (str, optional):
            The column name in both `plume_file` and `source_file` that 
            holds the unique source identifiers. The code will use the values 
            in this column in order to link the tables together.
            The code will raise an error if not specified.
            Defaults to None.
        
        em_col (str, optional): 
            The name of the column in the `plume_file` plume emissions table 
            that describes the emissions rate.
            If None, you MUST be specifying wind-normalized emissions rate 
            and wind-speed to be able to infer this.
            Defaults to None.
        
        em_unit (str, optional): 
            The physical unit of emissions rate, if the corresponding column 
            in the plume file (`emm_col`) has been specified.
            E.g. "kgh".
            Defaults to None.

        wind_norm_col (str, optional): 
            The name of the column in the `plume_file` plume emissions table 
            that describes the wind-normalized emissions rate.
            If None, you MUST be specifying emissions and wind-speed to be 
            able to infer this.
            Defaults to "wind_independent_emission_rate_kghmps".
        
        wind_norm_unit (str, optional): 
            The physical unit of wind-normalized emissions, if specified. Use 
            a ":" to differentiate between the nominator (emissions rate) and 
            the denominator (wind speed).
            E.g. "kgh:mps".
            Defaults to None.

        wind_speed_col (str, optional): 
            The name of the column in the `plume_file` plume emissions table 
            that describes the wind speed.
            If None, it's assumed it won't be needed.
            Defaults to None.
        
        wind_speed_unit (str, optional): 
            The physical unit of the specified wind speed column, if given.
            E.g. "mps".
            Defaults to None.
        
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
        
        asset_col (str, optional): 
            The name of the column in the source table that describes the 
            type of infrastructure producing the corresponding plumes. This, 
            together with `asset_type`, is used to segregate the aerial 
            survey data.
            Defaults to None.

        asset_type (tuple, optional): 
            A tuple of asset types under an "asset_type" column to include 
            in the estimation of aerial emissions.
            Defaults to ("Well site",).
        
        foldername (str, optional): 
            A folder name into which given outputs will be saved under 
            "run_results" (=roams.conf.RESULT_DIR).
            If None, will use a timestamp.
            Defaults to None.
        
        save_mean_dist (bool, optional): 
            Whether or not to save a "mean" distribution of all the components
            of the estimated production distributions (i.e. aerial, partial 
            detection, simulated).
            Defaults to True.
        
        loglevel (int, optional): 
            The log level to apply to analysis happening within the ROAMSModel 
            and submodules that it calls on.
            Defaults to logging.INFO
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
        num_wells_to_simulate = None,
        well_visit_count = None,
        wells_per_site = None,
        noise_fn = normal,
        handle_zeros = zero_out,
        transition_point = None,
        partial_detection_correction = True,
        simulate_error = True,
        PoD_fn = PoD_bin,
        correction_fn = power_correction,
        source_id_name = "emission_source_id",
        em_col = None,
        em_unit = None,
        wind_norm_col = "wind_independent_emission_rate_kghmps",
        wind_norm_unit = "kgh:mps",
        wind_speed_col = "wind_independent_emission_rate_kghmps",
        wind_speed_unit = "mps",
        cutoff_col = None,
        coverage_count = "coverage_count",
        asset_col = None,
        prod_asset_type = ("Well site",),
        midstream_asset_type = ("Pipeline","Compressor Station"),
        foldername=None,
        save_mean_dist = True,
        loglevel=logging.INFO,
        ):
        # If result folder name not specified, use a timestamp.
        if foldername is None:
            import datetime
            # E.g. foldername = "1 Jan 2000 01-23-45"
            foldername = datetime.now().strftime("%d %b %Y %H%M%S")
        
        self.outfolder = os.path.join(RESULT_DIR,foldername)

        # Set the log using prescribed level
        self.log = logging.getLogger("roams.analysis.ROAMSModel")
        self.log.setLevel(loglevel)
        self.loglevel = loglevel

        # The simulation input file
        self.simmed_emission_file = simmed_emission_file
        self.simmed_emission_sheet = simmed_emission_sheet

        # Estimate of covered production in survey region
        self.covered_productivity_file = covered_productivity_file
        
        # Specification of aerial input data
        self.plume_file = plume_file
        self.source_file = source_file
        self.source_id_name = source_id_name
        self.em_col = em_col
        self.em_unit = em_unit
        self.wind_norm_col = wind_norm_col
        self.wind_norm_unit = wind_norm_unit
        self.wind_speed_col = wind_speed_col
        self.wind_speed_unit = wind_speed_unit
        self.cutoff_col = cutoff_col
        self.coverage_count = coverage_count
        self.asset_col = asset_col
        self.prod_asset_type = prod_asset_type
        self.midstream_asset_type = midstream_asset_type
        
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
                "only be `None` or a Python-native numerical value."
            )
        
        # Properties of surveyed infrastructure
        self.num_wells_to_simulate = num_wells_to_simulate
        self.well_visit_count = well_visit_count
        self.wells_per_site = wells_per_site
        
        # Output specification, including making blank dictionary of table 
        # outputs.
        self.save_mean_dist = save_mean_dist
        self.table_outputs = dict()

        # Quantiles used in quantification of MC results 
        # (no reason to mess with this)
        self._quantiles = (.025,.975)
        self.log.debug(f"{self._quantiles = }")

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
        self.generate_and_write_outputs()

    def load_data(self):
        """
        Load the simulated data, segregated separately into simulated 
        emissions and production.

        Load the aerial data, segregated into records of plumes and sources 
        separately.
        """
        self.log.info("Loading simulated and aerial data...")
        self.read_simulated_data()
        self.read_aerial_data()

    def read_simulated_data(self):
        """
        Return a numpy array of simulated emissions values. By default, this 
        assumes a specific column name and implicit unit.

        Returns:
            tuple[np.ndarray]:
                A tuple of (simulated emissions, simulated productivity)
        """
        self.log.info(
            f"Reading simulated data from {self.simmed_emission_file = }"
        )
        sub_mdl_sims = pd.read_excel(
            self.simmed_emission_file,
            sheet_name=self.simmed_emission_sheet
        )
        sub_mdl_prod = sub_mdl_sims["Gas productivity [mscf/site/day]"].values
        sub_mdl_em = (sub_mdl_sims["sum of emissions [kg/hr]"] / 24).values
        
        self.simulated_em, self.simulated_prod = sub_mdl_em, sub_mdl_prod
    
    def read_aerial_data(self,surveyClass : AerialSurveyData = AerialSurveyData):
        """
        Return a tuple of plume and source data, restricted to sources of 
        the given values in `self.asset_type`.

        Args:

            surveyClass (AerialSurveyData, optional):
                An optional class (intended to be a child of AerialSurveyData)
                to be used to parse the aerial plume and source data.
        """
        self.survey = surveyClass(
            self.plume_file,
            self.source_file,
            self.source_id_name,
            em_col = self.em_col,
            em_unit = self.em_unit,
            wind_norm_col = self.wind_norm_col,
            wind_norm_unit = self.wind_norm_unit,
            wind_speed_col = self.wind_speed_col,
            wind_speed_unit = self.wind_speed_unit,
            cutoff_col = self.cutoff_col,
            cutoff_handling = "drop",
            coverage_count = self.coverage_count,
            asset_col = self.asset_col,
            prod_asset_type = self.prod_asset_type,
            midstream_asset_type = self.midstream_asset_type,
            loglevel=self.loglevel,
        )
    
    def read_covered_productivity(self) -> np.ndarray:
        """
        Read the file containing the covered productivity (supposed to be 
        a file just containing a list of estimated production values for all 
        covered production assets.).

        Returns:
            np.ndarray: 
                A 1-d array of estimated gas production. 
        """
        self.log.info(
            f"Reading covered productivity from {self.covered_productivity_file}"
        )
        covered_productivity = pd.read_csv(self.covered_productivity_file)
        return covered_productivity["New Mexico Permian 2021 (mscf/site/day)"].values
    
    def make_samples(self):
        """
        Call methods that will make the sample of simulated production 
        emissions, and also the aerial sample (meaning both the sampled 
        aerial emissions and corresponding partial detection correction.)
        """
        self.simulated_sample = self.make_simulated_sample()
        (
            self.tot_aerial_sample, 
            self.partial_detection_emissions
        ) = self.make_aerial_sample()

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
        self.log.info(
            "Sampling simulated emissions data into a "
            f"{self.num_wells_to_simulate}x{self.n_mc_samples} table."
        )
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
        detection correction as specified by self.partial_detection_correction.

        Returns:
            tuple[np.ndarray]: 
                A 2-tuple of total aerial emissions (emissions sampled for 
                each source, which may or may not include duplicated partial 
                detection samples), and extra emissions that may be added in 
                lieu of duplicated samples
        """
        aerial_prod_site_sample, prod_wind_norm_sample = self.get_aerial_survey_sample()
        self.log.info(
            f"The aerial sample is size={aerial_prod_site_sample.shape}, "
            f"and will be put into a table with {self.num_wells_to_simulate} "
            "rows (with 0-padding)."
        )
        self.log.debug(
            "The mean total aerial sample emissions are "
            f"{aerial_prod_site_sample.sum(axis=0).mean():.2f} "
            f"{self.survey.emissions_units}"
        )

        # Number of required extra rows to simulate all covered wells
        # (these padding 0s may not be required)
        required_extra_zeros = (
            self.num_wells_to_simulate 
            - aerial_prod_site_sample.shape[0] 
        )
        padding_zeros = np.zeros((required_extra_zeros,self.n_mc_samples))
        
        # Concatenate the extra samples onto the original draws, with zero padding
        # representing all of the remaining wells up to num_wells_to_simulate
        tot_aerial_sample = np.concat([aerial_prod_site_sample,padding_zeros],axis=0)
        tot_windnorm_sample = np.concat([prod_wind_norm_sample,padding_zeros],axis=0)

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
            self.log.info(
                f"Using {self.PoD_fn} on the sorted wind-normalized sample "
                "to define the probability of detection."
            )
            PoD = self.PoD_fn(tot_windnorm_sample)
            extra_emissions_for_cdf = (1/PoD - 1)*tot_aerial_sample
        else:
            self.log.info(
                "No partial detection correction will be applied to the "
                "aerial sample."
            )
            extra_emissions_for_cdf = np.zeros(tot_aerial_sample.shape)

        return tot_aerial_sample, extra_emissions_for_cdf
    
    def get_aerial_survey_sample(self) -> np.ndarray:
        """
        A function that can take a record of covered sources and corresponding 
        plumes (it's OK if there are plumes that dont correspond to any listed source - 
        they are excluded), and samples the plume observations, accounting for 
        observed intermittency. It then applies noise and deterministic 
        correction.

        It's supposed to return the sample of emissions and their corresponding 
        wind-normalized counterparts.

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
        max_count = self.survey.production_sources[self.survey.coverage_count].max()
        
        # df = DataFrame with columns [0, 1, ..., <max coverage - 1>, "coverage_count"]
        # and a number of rows equal to the number of unique sources.
        df = self.survey.production_sources[
            [self.survey.source_id_col,self.survey.coverage_count]
        ].copy()
        df.set_index(self.survey.source_id_col,inplace=True)

        plume_data = self.survey.production_plumes.copy()
        
        # Create a column in common wind-normalized emissions units
        plume_data["windnorm_em"] = self.survey.prod_plume_wind_norm

        # Create an emissions rate column in common emissions rate units
        plume_data["em"] = self.survey.prod_plume_emissions

        # get separate lists of the observed wind-normalized emissions rates and wind speeds
        emiss_and_windnorm_emiss = (
            plume_data
            .groupby(self.survey.source_id_col)
            [["em","windnorm_em"]]
            .agg(list)
        )

        self.log.debug(f"The highest coverage count is {max_count}")
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
                f"emitting for {((df[self.survey.coverage_count]>col) & (df[col].isna())).sum()} plumes."
            )
            # For any observations remaining nan that should still count as coverage instance, set them to 0 (i.e., it was observed and was not emitting)
            df.loc[(df[self.survey.coverage_count]>col) & (df[col].isna()),col] = 0
        
        # Drop the coverage_count column, no longer needed
        df.drop(columns=self.survey.coverage_count,inplace=True)

        # Sample each row N times, excluding NaN values
        # This results in an `emission_source_id`-indexed series whose values are each a 1D np.array type, each representing the sampled observations
        # The values in the sampled 1-D array can be 0 (no emissions observed), or a (wind-normalized emissions, wind speed) pair.
        sample = df.apply(
            lambda row: row.sample(self.n_mc_samples,replace=True,weights=1*(~row.isna())).values,
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
        if self.correction_fn is not None:
            self.log.debug(f"Applying {self.correction_fn} to sampled emissions")
            emissions = self.correction_fn(emissions)

        if self.simulate_error:
            self.log.debug(f"Applying {self.simulate_error} to sampled emissions")
            emissions = self.noise_fn(emissions)
        
        # Use function to handle 0s
        self.log.debug(
            "The resulting aerial emissions sample has a mean of "
            f"{(emissions<=0).sum(axis=0).mean()} values ≤0 in each "
            "monte-carlo iteration."
        )
        emissions = self.handle_zeros(emissions,self.noise_fn)

        return emissions, wind_normalized_em
    
    def combine_samples(self):
        """
        Combine the aerial and simulated distributions into a new attribute 
        called `self.combined_samples` which will have self.num_wells_to_simulate
        rows and self.n_mc_samples columns.
          
        It creates this with aerial sampled data, partial detection emissions, 
        and sampled simulated emissions. By the time of calling this method, 
        these should be in the form of:
            
            * `self.tot_aerial_sample` : 
                A (self.num_wells_to_simulate)x(self.n_mc_samples) table of 
                sampled, corrected, and perhaps noised aerial observations,
                where intermittency has also been taken into account.
            * `self.extra_emissions_for_cdf` : 
                A (self.num_wells_to_simulate)x(self.n_mc_samples) table of 
                estimated extra emissions from the entire basin under study, 
                intended to reflect the "missed" emissions from the partial 
                detection correction.
            * `self.simulated_sample` : 
                A (self.num_wells_to_simulate)x(self.n_mc_samples) table of 
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
        if self.transition_point is None:
            self.log.info(
                "No transition point was provided, it will be computed by "
                "comparing the simulated and aerial distributions."
            )
            # aerial_cumsum = combined increasing cumulative sum of sampled aerial 
            #   emissions AND contributions from partial detection.
            aerial_cumsum = self.tot_aerial_sample.cumsum(axis=0) + self.partial_detection_emissions.cumsum(axis=0)
            
            # Turn the cumulative sum into a decreasing quantity
            aerial_cumsum = aerial_cumsum.max(axis=0) - aerial_cumsum
            
            # Sort then cumsum each sampling of the simulated emissions
            sim_data = np.sort(self.simulated_sample,axis=0)
            simmed_cumsum = sim_data.cumsum(axis=0)
            
            # Convert into decreasing cumulative total of simulated emissions
            simmed_cumsum = simmed_cumsum.max(axis=0) - simmed_cumsum
            
            # Define the transition point based on the cumulative emissions 
            # distributions.
            self.tp = find_transition_point(
                aerial_x = self.tot_aerial_sample,
                aerial_y = aerial_cumsum,
                sim_x = sim_data,
                sim_y = simmed_cumsum,
            )
            self.log.debug(
                f"The computed average transition point is {self.tp.mean()}"
            )
        elif isinstance(self.transition_point,(int,float,)):
            self.log.info(
                f"The transition point was provided as {self.transition_point}, "
                "and will be used directly to combine aerial and simulated "
                "emissions distributions."
            )
            self.tp = np.array([self.transition_point]*self.n_mc_samples)

        # To start the process, define `self.combined_samples` as the aerial sample.
        # This is the desired shape, and some of the values are already what we want.
        self.combined_samples = self.tot_aerial_sample.copy()

        # Now go through each monte carlo iteration and combine the samples.
        for n in range(self.n_mc_samples):
            
            # Get the transition point for this MC run
            tp = self.tp[n]
            
            # Define simulations below this iteration's transition point
            sim_below_transition = self.simulated_sample[:,n][self.simulated_sample[:,n]<tp]

            # Find the first index where the aerial emissions in this column are ≥transition point
            idx_above_transition = np.argmin(self.combined_samples[:,n]<tp)

            if len(sim_below_transition)<idx_above_transition:
                raise IndexError(
                    f"In monte-carlo iteration {n}, there are "
                    f"{len(sim_below_transition)} simulated emissions values "
                    f"below the transition point (={tp}), but "
                    f"{idx_above_transition} infrastructure sites to try to "
                    f"simulate (out of {self.num_wells_to_simulate} total). "
                    "The code usually fills each such site by choosing with "
                    "replacement from the available simulated emissions, but "
                    "in this case the code doesn't know what to do without "
                    "either leaving some 0s between them, or perhaps "
                    "over-estimating the simulated contribution by adding "
                    "extra simulated records."
                )

            # For all preceding indices, insert random simulated emissions below the transition point
            self.combined_samples[:idx_above_transition,n] = np.random.choice(sim_below_transition,idx_above_transition,replace=True)
            
            # In any partial detection emissions tracked to be added directly to the cdf, zero out contributions associated to emissions below transition point.
            self.partial_detection_emissions[:idx_above_transition,n] = 0
        
        # Re-sort the newly combined records. Maintain correspondence with the 
        # partial detection correction by getting the sorted index and using
        # for both.
        combined_sort_idx = self.combined_samples.argsort(axis=0)
        for n in range(self.n_mc_samples):
            # Sort the combined samples column-wise
            self.combined_samples[:,n] = self.combined_samples[combined_sort_idx[:,n],n]

            # Sort the corresponding extra_emissions_for_cdf
            self.partial_detection_emissions[:,n] = self.partial_detection_emissions[combined_sort_idx[:,n],n]

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

        # Call methods that add content to self.table_outputs
        self.make_tabular_outputs()

        # For each table name : pd.DataFrame pair, write it to the outpath.
        for name, table in self.table_outputs.items():
            if not name.endswith(".csv"):
                name += ".csv"
            
            self.log.info(f"Saving {name} to {self.outfolder}")
            table.to_csv(os.path.join(self.outfolder,name))
        
        self.gen_plots()

    def make_tabular_outputs(self):
        """
        Call methods to add tabular (pd.DataFrame) outputs to self.table_outputs.
        """
        # Add summary tables of production distributions 
        self.make_production_summary_tables()

        if self.save_mean_dist:
            # Add summary of production distributions
            self.make_mean_production_dist_tables()

    def make_production_summary_tables(self):
        """
        Make two separate tables to summarize the production emissions 
        distributions (both component distributions and the combined one).

        One output just summarizes the total emissions contributions from 
        each component distribution, and in total. To the extent possible, the 
        contribution of each is measured both before and after accounting 
        for the transition point.

        The other output tries to characterize the resulting combined 
        cumulative emissions distribution by finding some key points of 
        interest, like what the kg/h values are at certain percentages, and
        what the percentage values are at certain kg/h values.
        """
        self.log.info("Creating the production summary tables")
        # E.g. quantity_cols = ["Avg","2.5% CI","97.5% CI"]
        quantity_cols = ["Avg",*[str(100*q)+"% CI" for q in self._quantiles]]

        # Create an empty table that will summarize each component of the 
        # combined production emissions distribution.
        prod_summary = pd.DataFrame(
            index=[
                f"Aerial Only Total CH4 emissions (thousand {self.survey.emissions_units})",
                f"Partial Detection Total CH4 emissions (thousand {self.survey.emissions_units})",
                f"Combined Aerial + Partial Detection Total CH4 emissions (thousand {self.survey.emissions_units})",
                "Simulated Total CH4 emissions (t/h)", 
                "Overall Combined Total Production CH4 emissions (t/h)",
                "Transition Point (kg/h)"
            ],
            columns=pd.MultiIndex.from_product(
                [["By Itself","Accounting for Transition Point"],quantity_cols],
            )
        )
        
        # Report the sampled aerial emissions distribution, regardless of transition point
        sum_emiss_aerial = self.tot_aerial_sample.sum(axis=0)/1e3
        prod_summary.loc[f"Aerial Only Total CH4 emissions (thousand {self.survey.emissions_units})","By Itself"] = self.mean_and_quantiles(sum_emiss_aerial)[quantity_cols].values

        # Report sampled aerial emissions distributions above transition point
        sum_emiss_aerial_abovetp = np.array([self.tot_aerial_sample[:,n][self.tot_aerial_sample[:,n]>=self.tp[n]].sum() for n in range(self.n_mc_samples)])/1e3
        prod_summary.loc[f"Aerial Only Total CH4 emissions (thousand {self.survey.emissions_units})","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_aerial_abovetp)[quantity_cols].values

        # In this addition, the expectation is the only one or other is contributing to the sum
        sum_emiss_partial = self.partial_detection_emissions.sum(axis=0)/1e3
        prod_summary.loc[f"Partial Detection Total CH4 emissions (thousand {self.survey.emissions_units})","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_partial)[quantity_cols].values
        
        # Like above, in this addition there are either additional copies of sampled emissions in `total_aerial_sample`, or the total missing emissions are included in `extra_emissions_for_cdf`.
        sum_emiss_aer_comb = (self.tot_aerial_sample.sum(axis=0) + self.partial_detection_emissions.sum(axis=0))/1e3
        prod_summary.loc[f"Combined Aerial + Partial Detection Total CH4 emissions (thousand {self.survey.emissions_units})","By Itself"] = self.mean_and_quantiles(sum_emiss_aer_comb)[quantity_cols].values

        # This will be aerial+partial detection, but ONLY total contributions above each transition point
        sum_emiss_aer_comb_abovetp = sum_emiss_aerial_abovetp + np.array([self.partial_detection_emissions[:,n][self.tot_aerial_sample[:,n]>=self.tp[n]].sum() for n in range(self.n_mc_samples)])/1e3
        prod_summary.loc[f"Combined Aerial + Partial Detection Total CH4 emissions (thousand {self.survey.emissions_units})","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_aer_comb_abovetp)[quantity_cols].values
        
        # The total amount of simulated emissions
        sum_emiss_sim = self.simulated_sample.sum(axis=0)/1e3
        prod_summary.loc["Simulated Total CH4 emissions (t/h)","By Itself"] = self.mean_and_quantiles(sum_emiss_sim)[quantity_cols].values

        # The total amount of simulated emissions below transition point, that end up being coounted in the resulting distribution.
        sum_emiss_sim_belowtp = np.array([self.combined_samples[:,n][self.combined_samples[:,n]<self.tp[n]].sum() for n in range(self.n_mc_samples)])/1e3
        prod_summary.loc["Simulated Total CH4 emissions (t/h)","Accounting for Transition Point"] = self.mean_and_quantiles(sum_emiss_sim_belowtp)[quantity_cols].values
        
        # Report from total combined distribution: only "By Itself" (doesn't make sense to 'account for transition point' in combined distribution)
        sum_emiss_all_comb = (self.combined_samples.sum(axis=0) + self.partial_detection_emissions.sum(axis=0))/1e3
        prod_summary.loc["Overall Combined Total Production CH4 emissions (t/h)","By Itself"] = self.mean_and_quantiles(sum_emiss_all_comb)[quantity_cols].values

        # Report the same quantities for the transition point.
        prod_summary.loc["Transition Point (kg/h)","By Itself"] = self.mean_and_quantiles(self.tp)[quantity_cols].values

        #### Next, try to characterize the resulting combined distribution by 
        #### identifying some key intercepts:
        ####    * What are the kgh values of the first 10%, 50%, 90%, 100% of emissions?
        ####    * What are the percentages of emissions above 10, 100, 1000 kgh?
        ####    
        #### All these answers are put into the same table and sorted.
        cumsum_y = self.combined_samples.cumsum(axis=0) + self.partial_detection_emissions.cumsum(axis=0)
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

        self.table_outputs["Production Summary"] = prod_summary
        self.table_outputs["Distribution Summary"] = dist_summary
    
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
    
    def make_mean_production_dist_tables(self) -> pd.DataFrame:
        """
        Return a summary of the production emissions distributions by taking 
        the mean over all the monte-carlo iterations of all wells to 
        simulate. This is reported for (a) aerial emissions, (b) partial 
        detection emissions, and (c) simulated emissions.

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
        denominator = np.sqrt((self.well_visit_count/self.wells_per_site)/self.num_wells_to_simulate)
        
        # Make copies of zero-padded aerial and partial detection emissions.
        aerial_em = self.tot_aerial_sample.copy()
        pd_corr = self.partial_detection_emissions.copy()

        # Find the sorting index of the aerial sample
        sort_aerial = np.argsort(aerial_em,axis=0)

        # Sort both partial detection correction and aerial sample together 
        # (they shouldn't need sorting, but just to be safe...)
        for mc_run in range(self.tot_aerial_sample.shape[1]):
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
        
        overall_dist = np.sort(self.combined_samples,axis=0)
        overall_cumsum = overall_dist.sum(axis=0) - overall_dist.cumsum(axis=0)
        overall_cumsum_quantiles = np.quantile(overall_cumsum,self._quantiles,axis=1).T
        overall_em_quantiles = np.quantile(overall_dist,self._quantiles,axis=1).T
        
        # Save the mean simulated cumsum value
        output["Combined Distribution, Mean Cumulative Dist (kg/h)"] = overall_cumsum.mean(axis=1)
        output["Mean Combined Distribution Emissions (kg/h)"] = overall_dist.mean(axis=1)
        
        # Go through each quantile and define an output column based on [diff/correction],
        # for both cumulative values and emissions point estimates at individual plumes
        for i, q in enumerate(self._quantiles):
            lbl_cum = f"Combined Distribution, Cumulative Dist (kg/h), {str(100*q)}% CI"
            lbl_em = f"Combined Distribution Emissions (kg/h), {str(100*q)}% CI"

            diff_cum = (overall_cumsum_quantiles[:,i] - output["Combined Distribution, Mean Cumulative Dist (kg/h)"])/denominator
            diff_em = (overall_em_quantiles[:,i] - output["Mean Combined Distribution Emissions (kg/h)"])/denominator

            output[lbl_cum] = output["Combined Distribution, Mean Cumulative Dist (kg/h)"] + diff_cum
            output[lbl_em] = output["Mean Combined Distribution Emissions (kg/h)"] + diff_em
        
        self.table_outputs["Mean Distributions"] = output
    
    def gen_plots(self):
        """
        Take a table of the overall combined emissions distributions of 
        production, and turn them into plots that include a vertical line 
        to indicate the average transition point.
        """
        cumsum = self.combined_samples.cumsum(axis=0) + self.partial_detection_emissions.cumsum(axis=0)
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

        self.log.info(
            "Saving the combined cumulative distribution plot to "
            f"{os.path.join(self.outfolder, 'combined_cumulative.svg/png')}"
        )
        plt.savefig(os.path.join(self.outfolder, "combined_cumulative.svg"))
        plt.savefig(os.path.join(self.outfolder, "combined_cumulative.png"))