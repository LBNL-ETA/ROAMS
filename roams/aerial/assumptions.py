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

def zero_out(emissions : np.ndarray, noise_fn : Callable[[np.ndarray],np.ndarray]) -> np.ndarray:
    """
    An adjustment intended for sampled, corrected, and noise-adjusted 
    aerial emissions data. Take the emissions data, and 

    Args:
        emissions (np.ndarray):
            Aerially observed and sampled emissions, that have presumably
            been adjusted with noise that may have created values below 0.
        
        noise_fn (Callable):
            A function that can take an array of emissions, and return 
            a noise-adjusted version that can be used to simulate error.

    Returns:
        np.ndarray:
            An array of the same shape as emissions, whose values below 
            0 have been replaced with 0.
    """    
    emissions[emissions<0] = 0
    return emissions

def normal(emissions: np.ndarray) -> np.ndarray:
    """
    Use a pre-determined normal distribution to apply noise to the 
    given aerial emissions table, and return the result of:

    emissions * noise

    This is intended to help quantify error in the resulting samples.

    Args:
        emissions (np.ndarray): 
            A sample of aerially observed emissions data. Should have 
            a number of rows equal to the number of sources included, and 
            a number of columns equal to the number of monte-carlo iterations.

    Returns:
        np.ndarray: 
            An array of the same shape as the input table, but to which 
            normal noise has been applied.
    """    
    error = np.random.normal(1+0.07, 0.4,size=emissions.shape)

    # Simulate error by "spreading out" the emissions values with normal distribution (this is optional)
    emissions = emissions * error
    
    return emissions

