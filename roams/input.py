from datetime import datetime
import logging
import json
from collections.abc import Iterable

log = logging.getLogger("roams.input.ROAMSConfig")

from roams.constants import ALVAREZ_ET_AL_CH4_FRAC
import roams.aerial.partial_detection
import roams.aerial.assumptions

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
    default behavior, and error-raising of the ROAMS input specification.

    The input is intended to come in the form of a nested dictionary (handed 
    over directly in memory, or in a JSON file).

    See the root-level README for a description of what should be in the 
    input file.
    """
    def __init__(
            self,
            config : str | dict,
            _reqs : dict = _REQUIRED_CONFIGS,
            _def : dict = _DEFAULT_CONFIGS
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

        Raises:
            KeyError:
                When a required part of the input specification is missing.

            ValueError:
                When the type of a required input specification is incorrect.
        """
        # Convert config_dict to dictionary if it's a string
        if isinstance(config,str):
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

        ### Do some after-the-fact assignment with specific behaviors
            
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