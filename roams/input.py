from datetime import datetime
from collections.abc import Iterable, Callable
from copy import deepcopy
import logging

import yaml
import numpy as np

log = logging.getLogger("roams.input.ROAMSConfig")

from roams.constants import ALVAREZ_ET_AL_CH4_FRAC, COMMON_EMISSIONS_UNITS, COMMON_PRODUCTION_UNITS
from roams.utils import ch4_volume_to_mass, convert_units

import roams.aerial.partial_detection
import roams.aerial.assumptions

from roams.aerial.input import AerialSurveyData
from roams.simulated.input import SimulatedProductionAssetData
from roams.production.input import CoveredProductionDistData
from roams.midstream_ghgi.input import GHGIDataInput

# This constant controls what missing keys in an input file will raise an error.
# All highest-level keys, and listed keys within, have to exist.
# It also controls what types each input has to be.
_REQUIRED_CONFIGS = {
    # Simulated production data 
    "sim_em_file" :  str,
    "sim_em_col" :  str,
    "sim_em_unit" :  str,
    
    # Aerial data specification
    "plume_file" : str,
    "source_file" : str,
    "source_id_name" : str,
    "asset_col" : str,
    "asset_groups" : dict,
    "coverage_count" : str,
        
    # Attributes of covered region (not derived here)
    "gas_composition" : dict,
    "num_wells_to_simulate" : int,
    "well_visit_count" : int,
    "wells_per_site" : float,
    "total_covered_ngprod_mcfd" : (float,int),
    "total_covered_oilprod_bbld" : (float,int),

    # Midstream required GHGI inputs
    "state_ghgi_file" : str,
    "ghgi_co2eq_unit" : str,
    "production_state_est_file" : str,
    "production_natnl_est_file" : str,
    "production_est_unit" : str,
    "ghgi_ch4emissions_ngprod_file" : str,
    "ghgi_ch4emissions_ngprod_uncertainty_file" : str,
    "ghgi_ch4emissions_petprod_file" : str,
    "ghgi_ch4emissions_unit" : str,
    "year" : int,
    "state" : str,
    "frac_aerial_midstream_emissions" : float,
    
    # Algorithmic required inputs
    "midstream_transition_point" : (float,int),
}

# This constant controls the defaults for the optional parts of the input 
# specification.
_DEFAULT_CONFIGS = {
    # Name of production column and unit in simulated data defaults
    "sim_prod_col" : None,
    "sim_prod_unit" : None,

    # Covered productivity attributes
    "covered_productivity_dist_file" : None,
    "covered_productivity_dist_col" : None,
    "covered_productivity_dist_unit" : None,

    # Aerial emissions and data specification defaults
    "aerial_em_col" : None,
    "aerial_em_unit" : None,
    "wind_norm_col" : None,
    "wind_norm_unit" : None,
    "wind_speed_col" : None,
    "wind_speed_unit" : None,
    "cutoff_col" : None,

    # Algorithmic input defaults
    # `None` may result in some opinionated assignment behavior in ROAMSConfig class.
    "random_seed" : None,
    "stratify_sim_sample" : True,
    "n_mc_samples" : 100,
    "prod_transition_point" : None,
    "partial_detection_correction" : True,
    "handle_negative" : "zero_out",
    "PoD_fn" : "bin",
    "correction_fn" : None,
    "simulate_error": True,
    "noise_fn" : {"name":"normal","loc":1.07,"scale":0.4},
    
    # Output specification defaults. 
    # `None` may result in some opinionated assignment behavior in ROAMSConfig class.
    "foldername" : None,
    "save_mean_dist" : True,
    "loglevel" : logging.INFO,
}

class ROAMSConfig:
    """
    The ROAMSConfig class is intended to handle the parsing, typing, 
    default behavior, and error-raising of all the ROAMS input specification.

    The ROAMSConfig will go through the following steps:
        * Read the content of the `config` (if a file) into dictionary format
        * Assert that each key in `_reqs` exists in the dictionary
        * Assert that each value type in `reqs` matches the value type in `config`
        * Assign defaults from `_def` into `config` if they aren't there or 
            are `None`.
        * Assign each resulting key: value pair to a class attribute, whose 
            name is the dictionary key.
        * Call `self.default_input_behavior` to do some after-the-fact 
            application of slightly more complicated default opinions.
        * Assign a `coveredProductivity` attribute based on provided 
            covered productivity data.
        * Assign a `prodSimResults` attribute based on provided simulated 
            data inputs.
        * Assign a `aerialSurvey` attribute based on provided aerial survey 
            data inputs.

    See the root-level README for a description of what should be in the 
    input file.
    """
    def __init__(
            self,
            config : str | dict,
            _reqs : dict = _REQUIRED_CONFIGS,
            _def : dict = _DEFAULT_CONFIGS,
            coveredProdDistDataClass : CoveredProductionDistData = CoveredProductionDistData,
            simDataClass : SimulatedProductionAssetData = SimulatedProductionAssetData,
            surveyClass : AerialSurveyData = AerialSurveyData,
            midstreamGHGHIDataClass : GHGIDataInput = GHGIDataInput,
        ):
        """
        The config_dict is passed directly to the __init__ of the parent 
        class, where it is unpacked into nested attributes.

        The resulting attributes are then inspected with strong opinions 
        about what is required to exist, and with what types. Missing but 
        optional inputs will be filled with defaults.

        Missing but required inputs will result in an error.

        _ref (required) and _def (optional default) arguments are given to 
        the function in the hope that future developers won't have such a 
        difficult time altering the otherwise strict parsing behavior, should 
        they need to do the same thing for similar but different models.

        This method will also instantiate `coveredProductivity`, 
        `prodSimResults`, and `aerialSurvey` attributes based on provided 
        parsing classes in order to make sense 

        Args:
            config_dict (str | dict): 
                Either path to the specification JSON file, or a parsed 
                dictionary coming from such a file.

            _req (dict, optional):
                A dictionary of lists, where in each list are tuples of 
                (attribute name, type) that will be used to assert that 
                (a) the attribute exists, and (b) it is an instance of the 
                given type.
                Defaults to _REQUIRED_CONFIGS.

            _def (dict, optional):
                A dictionary of lists, where in each list are tuples of 
                (attribute name, default value) that will be used to set 
                default values of missing but optional attributes.
                Defaults to _DEFAULT_CONFIGS.

            coveredProdDistDataClass (CoveredProductionDistData, optional): 
                A class that is either `CoveredProductionData` or a child 
                class thereof. Intended to serve as an entrypoint for 
                the estimated covered production data for the actual analysis 
                logic.
                Defaults to CoveredProductionData.
            
            simDataClass (SimulatedProductionAssetData, optional):
                A class that is either `SimulatedProductionAssetData` or a 
                child class thereof. Intended to serve as an entrypoint to 
                the simulated production asseet data for the actual analysis 
                logic.
                Defaults to SimulatedProductionAssetData.

            aerialSurveyClass (AerialSurveyData, optional):
                A class that is either `AerialSurveyData` or a child class
                thereof. Intended to serve as an entrypoint to the aerial 
                survey data for the actual analysis logic.
                Defaults to AerialSurveyData.
            
            midstreamGHGHIDataClass (GHGIDataInput, optional):
                A class that is either `GHGIDataInput` or a child class
                thereof. Intended to serve as an entrypoint to the midstream 
                sub-detection-level midstream loss rate, as estimated per the 
                GHGI data.
                Defaults to GHGIDataInput.

        Raises:
            TypeError:
                When the given `config` is not a string or dictionary.
                When the `correction_fn` and/or `noise_fn` isn't either None 
                or a dictionary.


            KeyError:
                When a required part of the input specification is missing.
                When `correction_fn` or `noise_fn` are passed as dictionaries, 
                but don't have "name" keys.
                When "production" and/or "midstream" are missing designations 
                from `asset_groups`.

            ValueError:
                When the type of a required input specification is incorrect.
                When gas composition of CH4 isn't a number.
                When gas composition adds up to more than 1.
                When gas composition adds up to less than 0.8.
                When the "production" and "midstream" asset groups describe the same infrastructure.

        """
        # Convert config_dict to dictionary if it's a string
        if isinstance(config,str):
            log.info(f"Reading the input configuration from: {config}")
            with open(config,"r") as f:
                # Load content which may include non-JSON-safe windows paths ("C:\path\to\file.csv")
                config = yaml.safe_load(f)

        elif isinstance(config,dict):
            config = deepcopy(config)

        else:
            raise TypeError(
                f"`config` can only be passed as a dictionary or json file"
            )
        
        # Apply global random seed ASAP
        # This is important for any input classes that require resampling or 
        # replacement before providing data to ROAMS model
        seed = config.get("random_seed")
        log.info(f"Setting seed with {seed = }")
        np.random.seed(seed)
                
        # Go through the required configs and assert that they exist, and 
        # that they're the correct type
        for k,v in _reqs.items():
            if k not in config.keys():
                raise KeyError(
                    f"Input value '{k}' is required, but was not specified."
                )
            
            if not isinstance(config[k],v):
                raise TypeError(
                    f"The input value '{k}'={config[k]} is expected to be "
                    f"type {v}, but it wasn't. You'll have to update your "
                    "input."
                )
            
        # Go through each of the defaults and assign default value if it 
        # doesn't exist or is None
        for k,v in _def.items():
            if config.get(k) is None:
                log.info(
                    f"{k} not provided as an argument. Will set it to {v}."
                )
                # Copy the value so that application of default behavior after 
                # this can't alter the value in _DEFAULT_CONFIGS
                config[k] = deepcopy(v)

        # By this point all the keys in _req and _def are in `config`. We 
        # assign them all as attributes
        for k,v in config.items():
            log.debug(
                f"Setting self.{k} = {v} from provided config (if None, "
                "default may be applied later)."
            )
            setattr(self,k,v)
            if k not in _reqs.keys() and k not in _def.keys():
                log.warning(
                    f"You specified an argument '{k}'={v} in your input, but "
                    "this argument isn't required and doesn't have an associated "
                    "default. Chances are the code will do nothing with it. "
                    "Did you misspecify an input value?"
                )

        # lower() all the keys of gas composition
        lower_composition = {k.lower() : v for k,v in self.gas_composition.items()}
        self.gas_composition = lower_composition

        # Assert that methane composition is provided, and is numeric
        if not isinstance(self.gas_composition.get("c1"),(float,int)):
            raise ValueError(
                "The code expects that your gas composition dictionary at "
                "least includes methane ('c1') as a float/int. But that's not "
                "what was provided."
            )
        
        # Assert that at least 80% of NG composition is accounted for in 
        # the gas composition dictionary, and no more than 100%
        if sum(self.gas_composition.values()) < .80:
            raise ValueError(
                f"The gas composition (= {self.gas_composition}) in your "
                "input file accounts for less than 80% of the molar "
                "composition of gas. You should probably provide more "
                "descriptive gas composition estimates to get a more faithful "
                "fractional energy loss."
            )

        # Assert that gas composition fractions don't add to >1
        if sum(self.gas_composition.values())>1.:
            raise ValueError(
                f"The gas composition (= {self.gas_composition}) in your "
                "input file accounts adds up to more than 100%. The values "
                "in the dictionary should be fractions (<=1), not "
                "percentage values out of 100."
            )
        
        # lower() the keys in the dictionary
        # (and turn any non-string keys to string)
        lower_asset_groups = {
            (str(k).lower()) : v
            for k,v in self.asset_groups.items()
        }
        self.asset_groups = lower_asset_groups

        # Assert that production and midstream are both in the described aerial 
        # assets
        for group in ["production","midstream"]:
            if group not in self.asset_groups.keys():
                raise KeyError(
                    f"The {self.asset_groups.keys() = } should contain an "
                    f"entry for '{group}'. The ROAMSModel will need this to "
                    "compute emissions distributions."
                )
            
        production_assets = set(self.asset_groups["production"])
        midstream_assets = set(self.asset_groups["midstream"])
        if shared := production_assets.intersection(midstream_assets):
            raise ValueError(
                "There are several assets that you listed as being both "
                f"midstream and production infrastructure: {shared}. You "
                "should revisit your input file, and if necessary reclassify "
                "sources in your data. If you want to characterize an "
                "additional asset group, just avoid naming it 'midstream' or "
                "'production'."
            )
        
        if isinstance(config["correction_fn"],dict) and "name" not in config["correction_fn"].keys():
            raise KeyError(
                "The 'correction_fn' argument needs to be either `None` (in "
                "which case no mean correction will be applied to sampled "
                "aerial emissions) or a dictionary with at least a 'name' key."
                " See the README for more details."
            )
        elif (not isinstance(config["correction_fn"],dict)) and (config["correction_fn"] is not None):
            raise TypeError(
                "The `correction_fn` argument can only either be `None` (in "
                "which case no mean correction will be applied to sampled "
                "aerial emissions), or a dictionary that specifies a method "
                "of roams.aerial.assumptions to use. See the README for more "
                "details."
            )
        
        if isinstance(config["noise_fn"],dict) and "name" not in config["noise_fn"].keys():
            raise KeyError(
                "The 'noise_fn' argument needs to be either `None` (in which "
                "case no noise will be applied to sampled aerial emissions) "
                "or a dictionary with at least a 'name' key. See the README "
                "for more details."
            )
        elif (not isinstance(config["noise_fn"],dict)) and (config["noise_fn"] is not None):
            raise TypeError(
                "The `noise_fn` argument can only either be `None` (in which "
                "case no noise will be applied to sampled aerial emissions), "
                " or a dictionary that specifies a method of numpy.random to use. "
                "See the README for more details."
            )
        
        # self._config is a record of the read & default-filled input, before 
        # additional default behavior (e.g. turning method specification into 
        # actual methods).
        self._config = deepcopy(config)
        
        # Do some after-the-fact assignment with specific behaviors   
        self.default_input_behavior()

        # Load the covered productivity data, if a file is given 
        # (otherwise assign None - it's up to analysis code to care about 
        # whether or not this is provided).
        if self.covered_productivity_dist_file is not None:
            self.coveredProductivity = coveredProdDistDataClass(
                covered_production_dist_file = self.covered_productivity_dist_file,
                covered_production_dist_col = self.covered_productivity_dist_col,
                covered_production_dist_unit = self.covered_productivity_dist_unit,
                gas_composition = self.gas_composition,
                loglevel = self.loglevel,
            )
        else:
            self.coveredProductivity = None
        
        # Load the simulated production data
        self.prodSimResults = simDataClass(
            self.sim_em_file,
            emissions_col = self.sim_em_col,
            emissions_units = self.sim_em_unit,
            production_col = self.sim_prod_col,
            production_units = self.sim_prod_unit,
            loglevel = self.loglevel
        )
        
        # Load the aerial survey data
        self.aerialSurvey = surveyClass(
            self.plume_file,
            self.source_file,
            self.source_id_name,
            em_col = self.aerial_em_col,
            em_unit = self.aerial_em_unit,
            wind_norm_col = self.wind_norm_col,
            wind_norm_unit = self.wind_norm_unit,
            wind_speed_col = self.wind_speed_col,
            wind_speed_unit = self.wind_speed_unit,
            cutoff_col = self.cutoff_col,
            cutoff_handling = "drop",
            coverage_count = self.coverage_count,
            asset_col = self.asset_col,
            asset_groups = self.asset_groups,
            loglevel = self.loglevel,
        )

        self.midstreamGHGIData = midstreamGHGHIDataClass(
            self.state_ghgi_file,
            self.production_state_est_file,
            self.production_natnl_est_file,
            self.ghgi_ch4emissions_ngprod_file,
            self.ghgi_ch4emissions_ngprod_uncertainty_file,
            self.ghgi_ch4emissions_petprod_file,
            self.year,
            self.state,
            self.gas_composition,
            frac_aerial_midstream_emissions=self.frac_aerial_midstream_emissions,
            ghgi_co2eq_unit=self.ghgi_co2eq_unit,
            ghgi_ch4emissions_unit=self.ghgi_ch4emissions_unit,
            production_est_unit=self.production_est_unit,
            loglevel=self.loglevel,
        )

    def default_input_behavior(self):
        """
        This method applies slightly more complicated logic to assign 
        attributes based on whether given arguments are default.
        
        For `foldername` and `loglevel`, it assigns defaults if the given 
        value is `None`.
            * `foldername` -> gets timestamp
            * `loglevel` -> logging.INFO

        For `PoD_fn`, it overwrites the attribute with the function whose 
        name matches the given string in the `roams.aerial.partial_detection` 
        submodule.

        For `correction_fn`, `noise_fn`, and `handle_negative`, this method 
        will overwrite the attribute with the function whose name matches the 
        given string in the `roams.aerial.assumptions` submodule.
        """
        # If foldername is None: provide a timestamp
        if self.foldername is None:
            # E.g. foldername = "1 Jan 2000 01-23-45"
            self.foldername = datetime.now().strftime("%d %b %Y %H-%M-%S")
            log.debug(
                "The folder-name wasn't specified. So will use a timestamp: "
                f"'{self.foldername}' instead."
            )
    
        # If loglevel is None, set to logging.INFO
        if self.loglevel is None:
            log.debug(
                "Loglevel was set to None, so setting to logging.INFO"
            )
            self.loglevel = logging.INFO

        # Look up the partial detection function
        if isinstance(self.PoD_fn,str):
            self.PoD_fn = getattr(roams.aerial.partial_detection,self.PoD_fn)
        
        # Look up the mean correction function
        if isinstance(self.correction_fn,dict):
            # E.g. name = "power"
            name = self.correction_fn["name"]
            
            # E.g. kwargs = {"constant":4.08,"power":0.77}
            kwargs = {k:v for k,v in self.correction_fn.items() if k!="name"}
            
            # E.g. fn = roams.aerial.assumptions.power
            fn = getattr(roams.aerial.assumptions,name)

            log.info(
                f"The function `roams.aerial.assumptions.{name}` will be used "
                "to do mean correction of sampled emissions values, with "
                "named arguments: "
                f"{', '.join([f'{k}={v}' for k,v in kwargs.items()])}"
            )
            # E.g. self.correction_fn = lambda emissions: power(constant=4.08,power=0.77,emissions_rate=emissions)
            # (i.e. Apply prescribed power correction to emissions)
            self.correction_fn = lambda emissions: fn(**kwargs,emissions_rate=emissions)
        
        # Look up the error-simulating noise function
        if isinstance(self.noise_fn,dict):
            # E.g. name = "normal"
            name = self.noise_fn["name"]
            
            # E.g. kwargs = {"loc":1.07,"scale":0.4}
            kwargs = {k:v for k,v in self.noise_fn.items() if k!="name"}
            
            # E.g. fn = np.random.normal
            fn = getattr(np.random,name)

            log.info(
                f"The function `np.random.{name}` will be used to generate "
                "noise to sampled emissions values, with named arguments: "
                f"{', '.join([f'{k}={v}' for k,v in kwargs.items()])}"
            )
            # E.g. self.noise_fn = lambda emissions: np.random.normal(loc=1.0,scale=1.0,size=emissions.shape) * emissions
            # (i.e. take random noise the same shape as emissions, and multiply element-wise with emissions)
            self.noise_fn = lambda emissions: fn(**kwargs,size=emissions.shape) * emissions
        
        # Look up the handle-negative-emissions function
        if isinstance(self.handle_negative,str):
            self.handle_negative = getattr(roams.aerial.assumptions,self.handle_negative)


    def to_dict(self) -> dict:
        """
        Return a dictionary embodying the final content of the parsed config 
        (including the application of default behavior, and including any 
        configs that are nonstandard but were passed anyway).

        Do this by reading the assigned attributes, as opposed to reading 
        the input values directly (i.e. inclusive of the applied default 
        behavior).

        Returns:
            dict:
                The key: value pairs resulting from the reading of the given 
                config file.
        """
        return deepcopy(self._config)
    
    @property
    def ch4_total_covered_production_mass(self) -> float:
        """
        Return total covered production of the surveyed region in 
        COMMON_EMISSIONS_UNITS of CH4.

        Returns:
            float:
                The estimated production rate of CH4 (in 
                COMMON_EMISSIONS_UNITS) in the covered region.
        """
        ch4_mcf_per_day = (
            self.gas_composition["c1"]
            * self.total_covered_ngprod_mcfd
        )
        
        return ch4_volume_to_mass(
            ch4_mcf_per_day,
            "mcf/d",
            COMMON_EMISSIONS_UNITS
        )
    
    @property
    def ch4_total_covered_production_volume(self) -> float:
        """
        Return total covered production of the surveyed region in 
        COMMON_EMISSIONS_UNITS of CH4.

        Returns:
            float:
                The estimated production rate of CH4 (in 
                COMMON_EMISSIONS_UNITS) in the covered region.
        """
        ch4_mcf_per_day = (
            self.gas_composition["c1"]
            * self.total_covered_ngprod_mcfd
        )
        
        return convert_units(
            ch4_mcf_per_day,
            "mcf/d",
            COMMON_PRODUCTION_UNITS
        )