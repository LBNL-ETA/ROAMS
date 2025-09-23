import numpy as np

def linear(emissions_rate : np.ndarray, slope : float,intercept : float) -> np.ndarray:
    """
    Apply a linear correction to observed emissions rates, in the form of:
    
    $$
    m*E + b
    $$

    Where:
        * m is the `slope`
        * E is the `emissions_rate`
        * b is the `intercept`

    This form of mean correction was studied in "Technological Maturity of 
    Aircraft-Based Methane Sensing for Greenhouse Gas Mitigation" (Abbadi 
    et al, 2024):
    https://doi.org/10.1021/acs.est.4c02439

    In that work, the authors found that slope was dependent on data provider.
    Slopes ranged from around 0.75 to about 1.3, with intercepts from 
    around -20 to about +20 or higher. Without clear information about what 
    mean correction to apply to your data, best practice is to forego this 
    correction.

    Args:
        emissions_rate (np.ndarray): 
            An np.ndarray of aerially observed emissions rates.

        slope (float):
            The slope m in the equation $m*E + b$.

        intercept (float):
            The intercept b in the equation $m*E + b$. Expected to be the same 
            units of emissions being handled by the code, specifically 
            COMMON_EMISSIONS_UNITS.
        
    Returns:
        np.ndarray:
            A record of observed emissions rate adjusted for measured bias 
            in the aerial measurement.
    """
    return slope*emissions_rate + intercept

def power(emissions_rate: np.ndarray, constant : float,power : float) -> np.ndarray:
    """
    Apply a power correction to observed emissions rates, in the form of:
    
    $$
    CE^p
    $$

    Where:
        * C is the `constant`
        * E is the `emissions_rate`
        * p is the `power`

    This form of mean correction was established in "Quantifying regional 
    methane emissions in the New Mexico Permian Basin with a comprehensive 
    aerial survey" (Chen et al, 2021), see p. S19:
    https://pubs.acs.org/doi/suppl/10.1021/acs.est.1c06458/suppl_file/es1c06458_si_001.pdf

    In that work, the constant was 4.08, and power was 0.77.

    Args:
        emissions_rate (np.ndarray): 
            An np.ndarray of aerially observed emissions rates.

        constant (float):
            The constant C in the equation $Ce^p$.

        power (float):
            The exponent p in the equation $Ce^p$.
        
    Returns:
        np.ndarray:
            A record of observed emissions rate adjusted for measured bias 
            in the aerial measurement.
    """
    return constant * (emissions_rate ** power)

def zero_out(emissions : np.ndarray) -> np.ndarray:
    """
    An adjustment intended for sampled, corrected, and noise-adjusted 
    aerial emissions data. Take the emissions data, and zero out all the 
    values that are <0.

    Args:
        emissions (np.ndarray):
            Aerially observed and sampled emissions, that have presumably
            been adjusted with noise that may have created values below 0.

    Returns:
        np.ndarray:
            An array of the same shape as emissions, whose values below 
            0 have been replaced with 0.
    """    
    emissions[emissions<0] = 0
    return emissions

