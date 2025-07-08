# Common wind-normalized emissions units fixed to what the partial detection
# functions require as input.
COMMON_WIND_NORM_EM_UNITS = "kgh:mps"

# The numerate of the common wind-normalized emissions unit
COMMON_EMISSIONS_UNITS = COMMON_WIND_NORM_EM_UNITS.split(":")[0]

# A somewhat arbitrary choice of common wind speed units to maintain
COMMON_WIND_SPEED_UNITS = COMMON_WIND_NORM_EM_UNITS.split(":")[1]