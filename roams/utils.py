import logging

log = logging.getLogger("roams.utils")

# 1 meter per second = 2.23694 miles per hour
MPH_PER_MPS = 2.23694

# 35.3147 cubic feet = 1 cubic meter
CUFT_PER_M3 = 35.3147

# Assumed density of gaseous CH4, kgCH4/mcfCH4
# NOTE: This differs form the effective assumption made in Analytica, which is 19.25 (~18/.935)
# CH4_DENSITY_KGMCF = 19.1773453
CH4_DENSITY_KGMCF = 18/.935
CH4_DENSITY_KGCUFT = CH4_DENSITY_KGMCF/1000         # [kg/mcf] * [1 mcf/ 1000 cuft] = [kg/cuft]
CH4_DENSITY_KGM3 = CH4_DENSITY_KGCUFT * CUFT_PER_M3 # [kg/cuft]*[35.3147 cuft/1 m3] = [kg/m3]

# CO2 equivalent warming potential of CH4
# (Per IPCC AR4, was revised higher in later estimates)
GWP_CH4 = 25.

# MCF of NG per kmol NG
# (GPSA. Section 1 general information. In Engineering Data Book, 13th Edition (Electronic) Volume I II. United States, 2011.)
NG_MCF_KMOL = .83656

# Megajoules per barrel crude oil equivalent
# Per EIA calculator (https://www.eia.gov/energyexplained/units-and-calculators/energy-conversion-calculators.php), Aug 2025, last updated Oct 2024
MJ_PER_BOE = 5996.94

# Energy density in MJ/kg of each NG component
ENERGY_DENSITY_MJKG = {
    "c1": 55.5,
    "c2": 51.9,
    "c3": 50.4,
    "nc4": 49.1,
    "ic4": 49.1,
    "nc5": 48.6,
    "ic5": 48.6,
    "c6+": 47.743,
    "h2s": 17.396,
    "h2": 141.7,
}

MOLAR_DENSITY_KGKMOL = {
    "c1": 16.043,
    "c2": 30.07,
    "c3": 44.1,
    "nc4": 58.12,
    "ic4": 58.12,
    "nc5": 72.15,
    "ic5": 72.15,
    "c6+": 86.18,
    "h2s": 34.08,
    "h2": 2.016,
}

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
    "mcf/d"     : 1,
    "mcf/day"   : 1,
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

def energycontent_mj_mcf(gas_composition : dict) -> float:
    """
    Take a natural gas composition dictionary, and return the volumetric 
    energy density, in MJ per mcf.

    Args:
        gas_composition (dict):
            A dictionary of {gas : fraction} pairs whose keys are the chemical
            components of natural gas. No more than 20% of the weights 
            provided in this dictionary should belong to gases without 
            available energy density and molar density information.

    Raises:
        KeyError:
            When >20% of the provided molar composition of NG isn't 
            accounted for in terms of energy content.

    Returns:
        float: 
            The composition-weighted energy density of a given natural gas 
            composition, in MJ/MCF.
    """
    # Missing keys = chemical components that won't be captured by this 
    # computation
    # E.g. missing_keys = ["c7","c8"]
    missing_keys = [
        key for key in gas_composition.keys()
        if (key not in ENERGY_DENSITY_MJKG.keys()) or (key not in MOLAR_DENSITY_KGKMOL.keys())
    ]
    
    # E.g. missing_weight = gas_composition["c7"] + gas_composition["c8"]
    missing_weight = sum([gas_composition[key] for key in missing_keys])

    # Raise an error if >20% of molar composition is from gases that aren't 
    # known in the energy and molar density records.
    if missing_weight>.2:
        raise KeyError(
            f"There are gases in the given composition ({missing_keys}) "
            "that don't have a known energy density or molar density, that "
            "make up more than 20% of your composition. "
            f"The only available gases are: {MOLAR_DENSITY_KGKMOL.keys()}."
        )
    
    # Log a warning if there's >0 missing gases, but their collective weight 
    # doesn't trigger an error.
    if len(missing_keys)>0:
        log.warning(
            f"Some gases in the given gas composition ({missing_keys}) don't "
            "exist in the energy density and molar density records. "
            f"The only available gases are: {MOLAR_DENSITY_KGKMOL.keys()}."
        )

    return sum(
        [
            frac*ENERGY_DENSITY_MJKG[gas]*MOLAR_DENSITY_KGKMOL[gas]/NG_MCF_KMOL
            for gas, frac in gas_composition.items()
        ]
    )