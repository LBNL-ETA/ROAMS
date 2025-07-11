# 1 meter per second = 2.23694 miles per hour
MPS_TO_MPH = 2.23694
M3_TO_CUFT = 35.3147

# A dictionary of unit : conversion to kg/h, where each dictionary value 
# represents the amount of that unit in one kg/h. The unit of tons here is 
# always metric.
EMISSION_RATE_CONVERSIONS = {
    "g/h"   : 1_000,
    "g/hr"  : 1_000,
    "g/d"   : 24*1_000,
    "g/day" : 24*1_000,
    "kg/h"  : 1,
    "kg/hr" : 1,
    "kgh"   : 1,
    "kg/d"  : 24,
    "kg/day": 24,
    "t/h"   : 1e-3,
    "tons/h": 1e-3,
    "tons/hr": 1e-3,
    "t/hr"  : 1e-3,
    "t/d"   : 24*1e-3,
    "t/day" : 24*1e-3,
}

# A dictionary of unit : conversion to mps, where each dictionary value 
# represents the amount of that unit in mps.
WINDSPEED_CONVERSIONS = {
    "mps"   : 1,
    "m/s"   : 1,
    "mph"   : MPS_TO_MPH,
    "m/h"   : MPS_TO_MPH,
    "mi/h"  : MPS_TO_MPH,
}

# A dictionary of unit : conversion to mscf/day, where each dictionary value 
# represents its conversion to mscf/d (e.g. 1 mscf/d is how many of X)
PRODUCTION_CONVERSIONS = {
    "mscf/day"  : 1,
    "mscf/d"    : 1,
    "mscf/h"    : 1/24,
    "mscf/hr"   : 1/24,
    "scf/d"     : 1e3,
    "scf/h"     : 1e3/24,
    "m3/hr"     : 1e3/M3_TO_CUFT/24,
    "m3/h"      : 1e3/M3_TO_CUFT/24,
    "m3/day"    : 1e3/M3_TO_CUFT,
    "m3/d"      : 1e3/M3_TO_CUFT,
}

def convert_units(value,unit_in : str,unit_out: str):
    """
    Attempt to convert the given value from `unit_in` into `unit_out`, assuming 
    that both are in units of emissions rates, OR both are units of speed for 
    converting wind speeds. Unit conversions must be prescribed in the 
    dictionaries `EMISSION_RATE_CONVERSIONS` and `WINDSPEED_CONVERSIONS`.

    Args:
        value (Any):
            Any type (numpy array, numeric) that can be multiplied with 
            scalars.

        unit_in (str):
            A string representing the physical unit of the given value, which 
            should exist in either `EMISSION_RATE_CONVERSIONS` or 
            `WINDSPEED_CONVERSIONS`.

        unit_out (str):
            A string representing the physical unit into which you want to 
            convert the given value. Should exist in the same unit dictionary 
            as `unit_in`.

    Returns:
        type(value):
            The given value converted into units of `unit_out`.

    Raises:
        KeyError:
            When `unit_in` or `unit_out` aren't in the same unit dictionary, 
            and perhaps not even the same physical units.
    """
    unit_in, unit_out = unit_in.lower(), unit_out.lower()

    if unit_in in EMISSION_RATE_CONVERSIONS.keys() and unit_out in EMISSION_RATE_CONVERSIONS.keys():
        return value * EMISSION_RATE_CONVERSIONS[unit_out]/EMISSION_RATE_CONVERSIONS[unit_in]
    
    if unit_in in WINDSPEED_CONVERSIONS.keys() and unit_out in WINDSPEED_CONVERSIONS.keys():
        return value * WINDSPEED_CONVERSIONS[unit_out]/WINDSPEED_CONVERSIONS[unit_in]
    
    if unit_in in PRODUCTION_CONVERSIONS.keys() and unit_out in PRODUCTION_CONVERSIONS.keys():
        return value * PRODUCTION_CONVERSIONS[unit_out]/PRODUCTION_CONVERSIONS[unit_in]

    raise KeyError(
        f"One of {unit_in = } or {unit_out = } are not in the conversion "
        "dictionary for emissions rates or wind speed. Either you can add "
        "new units to these dictionaries, or you may have mis-specified units."
    )