from collections.abc import Callable

import numpy as np

def power_correction(emissions_rate: np.ndarray) -> np.ndarray:
    """
    Apply a correction to observed emissions rates based on empirical field 
    calibration studies.

    See p. S19 of supplementary files for "Quantifying regional methane 
    emissions in the New Mexico Permian Basin with a comprehensive aerial survey":
    https://pubs.acs.org/doi/suppl/10.1021/acs.est.1c06458/suppl_file/es1c06458_si_001.pdf

    Args:
        emissions_rate (np.ndarray): 
            An np.ndarray of aerially observed emissions rates.

    Returns:
        np.ndarray:
            A record of observed emissions rate adjusted for measured bias 
            in the aerial measurement.
    """    
    return 4.08 * (emissions_rate ** .77)

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

