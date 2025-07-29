from datetime import datetime
import logging
import json
from collections.abc import Iterable

log = logging.getLogger("roams.input.ROAMSConfig")

from roams.constants import ALVAREZ_ET_AL_CH4_FRAC
import roams.aerial.partial_detection
import roams.aerial.assumptions

from roams.aerial.input import AerialSurveyData
from roams.simulated.input import SimulatedProductionAssetData
from roams.production.input import CoveredProductionData

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
    "prod_asset_type" : Iterable,
    "midstream_asset_type" : Iterable,
    "coverage_count" : str,
        
    # Attributes of covered region (not derived here)
    "covered_productivity_file" : str,
    "covered_productivity_col" : str,
    "covered_productivity_unit" : str,
    "num_wells_to_simulate" : int,
    "well_visit_count" : int,
    "wells_per_site" : float,
    
    # Algorithmic required inputs
    "midstream_transition_point" : (float,int),
}

# This constant controls the defaults for the optional parts of the input 
# specification.
_DEFAULT_CONFIGS = {
    # Name of production column and unit in simulated data defaults
    "sim_prod_col" : None,
    "sim_prod_unit" : None,

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
    "frac_production_ch4" : ALVAREZ_ET_AL_CH4_FRAC,
    "stratify_sim_sample" : True,
    "n_mc_samples" : 100,
    "prod_transition_point" : None,
    "partial_detection_correction" : True,
    "simulate_error" : True,
    "handle_negative" : "zero_out",
    "PoD_fn" : "bin",
    "correction_fn" : "power_correction",
    "noise_fn" : "normal",
    
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
            coveredProdDataClass : CoveredProductionData = CoveredProductionData,
            simDataClass : SimulatedProductionAssetData = SimulatedProductionAssetData,
            surveyClass : AerialSurveyData = AerialSurveyData,
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
                coming from such a file.

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

            coveredProdDataClass (CoveredProductionData, optional): 
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

        Raises:
            KeyError:
                When a required part of the input specification is missing.

            ValueError:
                When the type of a required input specification is incorrect.
        """
        # Convert config_dict to dictionary if it's a string
        if isinstance(config,str):
            log.info(f"Reading the input configuration from: {config}")
            with open(config,"r") as f:
                config = json.load(f)
                
        # Go through the required configs and assert that they exist, and 
        # that they're the correct type
        for k,v in _reqs.items():
            if k not in config.keys():
                raise KeyError(
                    f"Input value '{k}' is required, but was not specified."
                )
            
            if not isinstance(config[k],v):
                raise ValueError(
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
                config[k] = v

        # By this point all the keys in _req and _def are in `config`. We 
        # assign them all as attributes
        for k,v in config.items():
            log.debug(
                f"Setting self.{k} = {v} from provided config (perhaps with some "
                f"defaults)."
            )
            setattr(self,k,v)
            if k not in _reqs.keys() and k not in _def.keys():
                log.warning(
                    f"You specified an argument '{k}'={v} in your input, but "
                    "this argument isn't required and doesn't have an associated "
                    "default. Chances are the code will do nothing with it. "
                    "Did you misspecify an input value?"
                )

        # Do some after-the-fact assignment with specific behaviors   
        self.default_input_behavior()

        # Load the covered productivity data, if a file is given 
        # (otherwise assign None - it's up to analysis code to care about 
        # whether or not this is provided).
        if self.covered_productivity_file is not None:
            self.coveredProductivity = coveredProdDataClass(
                covered_production_file = self.covered_productivity_file,
                covered_production_col = self.covered_productivity_col,
                covered_production_unit = self.covered_productivity_unit,
                frac_production_ch4 = self.frac_production_ch4,
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
            prod_asset_type = self.prod_asset_type,
            midstream_asset_type = self.midstream_asset_type,
            loglevel = self.loglevel,
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
        
        # Look up the bias correction function
        if isinstance(self.correction_fn,str):
            self.correction_fn = getattr(roams.aerial.assumptions,self.correction_fn)
        
        # Look up the error-simulating noise function
        if isinstance(self.noise_fn,str):
            self.noise_fn = getattr(roams.aerial.assumptions,self.noise_fn)
        
        # Look up the handle-negative-emissions function
        if isinstance(self.handle_negative,str):
            self.handle_negative = getattr(roams.aerial.assumptions,self.handle_negative)