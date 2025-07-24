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
    "prod_sim" : [
        ("em_file", str),
        ("em_col", str),
        ("em_unit", str)
    ],
    "aerial" : [
        ("plume_file",str),
        ("source_file",str),
        ("source_id_name",str),
        ("asset_col",str),
        ("prod_asset_type",Iterable),
        ("midstream_asset_type",Iterable),
        ("coverage_count",str)
    ],
    "coveredRegion" : [
        ("productivity_file",str),
        ("productivity_col",str),
        ("productivity_unit",str),
        ("num_wells",int),
        ("well_visit_count",int),
        ("wells_per_site",float),
    ],
    "algorithm" : [
        ("midstream_transition_point",(float,int)),
    ],
    "output" : [],
}

# This constant controls the defaults for the optional parts of the input 
# specification.
_DEFAULT_CONFIGS = {
    "prod_sim" : [
        ("prod_col",None),
        ("prod_unit",None),
    ],
    "aerial" : [
        ("em_col",None),
        ("em_unit",None),
        ("wind_norm_col",None),
        ("wind_norm_unit",None),
        ("wind_speed_col",None),
        ("wind_speed_unit",None),
        ("cutoff_col",None),
    ],
    "coveredRegion" : [
        ("frac_production_ch4",ALVAREZ_ET_AL_CH4_FRAC),
    ],
    "algorithm" : [
        ("stratify_sim_sample",True),
        ("n_mc_samples",100),
        ("prod_transition_point",None),
        ("partial_detection_correction",True),
        ("simulate_error",True),
        ("handle_negative","zero_out"),
        ("PoD_fn","bin"),
        ("correction_fn","power_correction"),
        ("noise_fn","normal"),
    ],
    "output" : [
        ("foldername",None),
        ("save_mean_dist",True),
        ("loglevel",logging.INFO),
    ],
}

# Config will be a base class that does the basic parsing of nested 
# information in an input JSON file, in a very un-opinionated fashion.
class Config:

    def __init__(self,config : str | dict):
        """
        Take an input file path (str) or dictionary, and use the content 
        thereof to set nested attributes representing the provided 
        information.

        This class has absolutely no opinion about the content or structure of 
        the provided configuration, except that the keys of the corresponding 
        dictionary must be valid class attribute names in Python, and the 
        original content (if in a file) should be valid JSON.

        E.g. 
        >>> config = {
                "A":{"B":10,"C":[1,2,3]},
                "B":true,
            }
        >>> cfg = Config(config)
        >>> cfg.B
            
            True

        >>> cfg.A

            <class Config at location 0x10dff910>

        >>> cfg.A.B

            10

        Args:
            config (str | dict):
                Either the path to an input specification file (str), or 
                an already-read dictionary of inputs. If it's a path to a 
                file, it will immediately be turned into a dictionary.
        """
        # If the input value is a string, assume it's a file path and try 
        # to read it.
        if isinstance(config,str):
            log.info(f"Reading input configuration from {config}")
            with open(config,"r") as f:
                config = json.load(f)

        # For each key : value pair, assign an attribute to this instance
        for k, v in config.items():
            
            # If the value is a dictionary, make it a nested attribute
            if isinstance(v,dict):
                log.debug(f"Setting {k} to the nested attributes held in {v}")
                setattr(self,k,Config(v))
            
            # If the value isn't a dictionary, assign it as an attribute
            else:
                log.debug(f"Setting {k} to {v}")
                setattr(self,k,v)

class ROAMSConfig(Config):
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
        # Call parent method to create nested attribute structure
        super().__init__(config)
        
        # After having parsed the file content, do some checking of what was 
        # provided and fill in defaults.
        for cfg, reqs in _reqs.items():
            
            # Assert that each of the highest-level keys of prescribed 
            # requirements exist on the class as attributes.
            if not hasattr(self,cfg):
                raise KeyError(
                    f"Your input specification should have '{cfg}' as a key, "
                    "but it's missing. Revisit your input and make sure it's "
                    "put together correctly."
                )

            # E.g. cfg_field = self.prod_sim
            cfg_field = getattr(self,cfg)

            for name, _type in reqs:
                # For each (sub-attribute, type) pair, assert that the given 
                # required attribute is the correct type.
                if not hasattr(cfg_field,name):
                    raise KeyError(
                        f"Your input specification should have '{name}' as a key "
                        f"under '{cfg}', but it's missing. Revisit your input "
                        "and make sure it's put together correctly."
                    )

                # E.g. value = self.prod_sim.em_file
                value = getattr(cfg_field,name)
                
                if not isinstance(value,_type):
                    raise ValueError(
                        f"The input configuration '{name}' under '{cfg}' is "
                        f"intended to be of type '{_type}'. Instead, '{value}' "
                        "was provided."
                    )
                
            defaults = _def.get(cfg,dict())
            for name, default in defaults:
                
                # If the attribute doesn't exist, set it with an info message
                if getattr(cfg_field,name,None) is None:
                    log.info(
                        f"{cfg}.{name} is being set to the {default = }"
                    )
                    setattr(cfg_field,name,default)
                else:
                    log.debug(
                        f"{cfg}.{name} is given as {getattr(cfg_field,name)}"
                    )

        ### Do some after-the-fact assignment with specific behaviors
            
        # If foldername is None: provide a timestamp
        if self.output.foldername is None:
            # E.g. foldername = "1 Jan 2000 01-23-45"
            self.output.foldername = datetime.now().strftime("%d %b %Y %H-%M-%S")
            log.debug(
                "The folder-name wasn't specied. So will use a timestamp: "
                f"'{self.output.foldername}'"
            )
    
        # If loglevel is None, set to logging.INFO
        if self.output.loglevel is None:
            log.debug(
                "Loglevel was set to None, so setting to logging.INFO"
            )
            self.output.loglevel = logging.INFO

        # Look up the partial detection function
        if isinstance(self.algorithm.PoD_fn,str):
            self.algorithm.PoD_fn = getattr(roams.aerial.partial_detection,self.algorithm.PoD_fn)
        
        # Look up the bias correction function
        if isinstance(self.algorithm.correction_fn,str):
            self.algorithm.correction_fn = getattr(roams.aerial.assumptions,self.algorithm.correction_fn)
        
        # Look up the error-simulating noise function
        if isinstance(self.algorithm.noise_fn,str):
            self.algorithm.noise_fn = getattr(roams.aerial.assumptions,self.algorithm.noise_fn)
        
        # Look up the handle-negative-emissions function
        if isinstance(self.algorithm.handle_negative,str):
            self.algorithm.handle_negative = getattr(roams.aerial.assumptions,self.algorithm.handle_negative)