# Common wind-normalized emissions units fixed to what the partial detection
# functions require as input.
COMMON_WIND_NORM_EM_UNITS = "kg/h:m/s"

# The numerator of the common wind-normalized emissions unit
COMMON_EMISSIONS_UNITS = COMMON_WIND_NORM_EM_UNITS.split(":")[0]

# A denominator of the common wind-normalized emissions unit
COMMON_WIND_SPEED_UNITS = COMMON_WIND_NORM_EM_UNITS.split(":")[1]

# A choice of 1000 standard cubic feet per day for volumetric NG production rate
COMMON_PRODUCTION_UNITS = "mscf/day"

# A choice of energy units for accounting of energy loss etc.
COMMON_ENERGY_UNITS = "MJ"

# Fraction of Methane in produced NG: estimate
ALVAREZ_ET_AL_CH4_FRAC = .9