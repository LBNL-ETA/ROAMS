# 1 meter per second = 2.23694 miles per hour
MPH_PER_MPS = 2.23694

# 35.3147 cubic feet = 1 cubic meter
CUFT_PER_M3 = 35.3147

# Methane density at 1 atm and 25C, in kg/m3 and kg/cuft
CH4_DENSITY_KGM3 = 0.657
CH4_DENSITY_KGCUFT = CH4_DENSITY_KGM3 / CUFT_PER_M3 # .657 kg/m3 * [1 m3 / 35.3147 cuft] = .0186 kg/cuft

# A dictionary of unit : conversion to kg/h, where each dictionary value 
# represents the amount of that unit in one kg/h. The unit of tons here is 
# always metric.
EMISSION_RATE_CONVERSIONS = {
    "mmt/yr"      : .000008766, # 1kgh = .000008766 t/yr
    "mmt/year"    : .000008766,
    "kt/yr"      : .008766, # 1kgh = .008766 t/yr
    "kt/year"    : .008766,
    "t/yr"      : 8.766, # 1kgh = 8.766 t/yr
    "t/year"    : 8.766,
    "ton/year"  : 8.766,
    "tons/year" : 8.766,
    "tons/yr"   : 8.766,
    "kg/yr"  : 8766, # 1kgh = 8676 kg/yr
    "kg/year": 8766,
    "g/h"   : 1_000,
    "g/hr"  : 1_000,
    "g/d"   : 24*1_000,
    "g/day" : 24*1_000,
    "kg/h"  : 1,
    "kg/hr" : 1,
    "kgh"   : 1,
    "kg/d"  : 24, # e.g. 1kgh = 24 kg/d
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
    "mph"   : MPH_PER_MPS,
    "m/h"   : MPH_PER_MPS,
    "mi/h"  : MPH_PER_MPS,
}

# A dictionary of unit : conversion to mscf/day, where each dictionary value 
# represents its conversion to mscf/d (e.g. 1 mscf/d is how many of X)
PRODUCTION_CONVERSIONS = {
    "mcf/y"     : 365.25, # E.g. 1 mscf/day = 365.25 mscf/yr
    "mcf/yr"    : 365.25,
    "mcf/year"  : 365.25,
    "mscf/y"    : 365.25,
    "mscf/yr"   : 365.25,
    "mscf/year" : 365.25,
    "mscf/day"  : 1,
    "mscf/d"    : 1,
    "mscf/h"    : 1/24, # e.g. 1 mscf/day = 1/24 mscf/h
    "mscf/hr"   : 1/24,
    "scf/d"     : 1e3,
    "scf/h"     : 1e3/24,
    "m3/hr"     : 1e3/CUFT_PER_M3/24,
    "m3/h"      : 1e3/CUFT_PER_M3/24,
    "m3/day"    : 1e3/CUFT_PER_M3,
    "m3/d"      : 1e3/CUFT_PER_M3,
}

def convert_units(value,unit_in : str,unit_out: str):
    """
    Attempt to convert the given value from `unit_in` into `unit_out`, assuming 
    that both are in units of emissions rates, OR both are units of speed for 
    converting wind speeds. Unit conversions must be prescribed in the 
    dictionaries `EMISSION_RATE_CONVERSIONS`, `WINDSPEED_CONVERSIONS`, or 
    `PRODUCTION_CONVERSIONS`.

    Args:
        value (Any):
            Any type (numpy array, numeric) that can be multiplied with 
            scalars.

        unit_in (str):
            A string representing the physical unit of the given value, which 
            should exist in either `EMISSION_RATE_CONVERSIONS`,
            `WINDSPEED_CONVERSIONS`, or `PRODUCTION_CONVERSIONS`.

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
        "dictionary for emissions rates, wind speed, or volumetric production "
        "rate. Either you can add new units to these dictionaries, or you may "
        "be able to re-specify units."
    )

def ch4_volume_to_mass(value, unit_in : str, unit_out : str):
    """
    Use available density information to convert a volumetric rate of 
    CH4 production (e.g. mscf/day) to a rate of mass production (e.g. kg/h).

    Args:
        value (float, np.ndarray):
            A value that will be multiplied with a conversion
            factor to turn volume of CH4 into mass of CH4.

        unit_in (str):
            A volumetric rate of CH4 production.
            E.g. "m3/day".

        unit_out (str):
            A mass rate of CH4 production.
            E.g. "kg/hr"
    """
    unit_in, unit_out = unit_in.lower(), unit_out.lower()
    
    # E.g. vol, t_in = "mscf", "day"
    vol, t_in = unit_in.split("/")
    
    # Based on the volume unit, convert to kg with density
    if vol=="m3":
        kg = CH4_DENSITY_KGM3 * value
    elif vol=="mscf" or vol=="mcf":
        kg = CH4_DENSITY_KGCUFT * value * 1000
    elif vol=="cuft":
        kg = CH4_DENSITY_KGCUFT * value
    elif vol=="scf":
        kg = CH4_DENSITY_KGCUFT * value
    else:
        raise ValueError(
            f"The volumetric rate of CH4 production: `{unit_in}` can't "
            "be parsed. You can either commit changes to the code to "
            "accommodate this, or try a unit like 'mscf/d', 'm3/h'."
        )

    # Return the converted emissions rate from kg/<time in> to unit_out
    return convert_units(kg,f"kg/{t_in}",unit_out)