from collections.abc import Callable

import numpy as np

def PoD_bin(wind_normalized_emm: np.ndarray) -> np.ndarray:
    """
    Take an array of values representing wind-normalized emissions, and 
    return a probability of detection for each value, representing the fraction 
    of coverages during which you'd expect to observe that value aerially 
    if it were in fact always emitting.

    This function takes the "bin" approach, based on the empirical field studies 
    reported here (p. 48):

    https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-07117-5/MediaObjects/41586_2024_7117_MOESM1_ESM.pdf

    Args:
        wind_normalized_emm (np.ndarray): 
            An array containing wind-normalized emissions values (e.g. kgh/mps).

    Returns:
        np.ndarray:
            An array that's the same shape as the input, but whose values are 0≤val≤1.
            These values represent the probability of detection.
    """    
    # Return P(detection) of wind-normalized emissions rate
    # Note that this returns P(0) = 1, which is a convention only intended to end up having the code avoid sampling "true 0s" any extra times.
    pod = np.ones(wind_normalized_emm.shape)

    # For those below empirical detection level, just insert 4 additional samples (P=1/5)
    pod[(wind_normalized_emm>0) & (wind_normalized_emm<6)] = (1/5) # <- this is a way to conservatively insert extra observations of the smallest observed emissions, even though empirically the probability is much smaller
    
    # Values here are empirical.
    # pod[(wind_normalized_emm>=6) & (wind_normalized_emm<8)] = 0.08695652173913043 # <- this is empirical but maybe adding too many emissions, not consistent with analytica
    pod[(wind_normalized_emm>=6) & (wind_normalized_emm<8)] = 0.24242424242424243
    pod[(wind_normalized_emm>=8) & (wind_normalized_emm<10)] = 0.35294117647058826
    pod[(wind_normalized_emm>=10) & (wind_normalized_emm<12)] = 0.696969696969697
    pod[(wind_normalized_emm>=12) & (wind_normalized_emm<14)] = 0.9090909090909091

    return pod

def PoD_linear(wind_normalized_emm: np.ndarray) -> np.ndarray:
    """
    Take an array of values representing wind-normalized emissions, and 
    return a probability of detection for each value, representing the fraction 
    of coverages during which you'd expect to observe that value aerially 
    if it were in fact always emitting.

    This function takes the "linear interpolation" approach, based on a mix of
    empirical field studies reported here (p. 48):

    https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-024-07117-5/MediaObjects/41586_2024_7117_MOESM1_ESM.pdf

    and simple linear interpolation. The interpolation assumes that the 
    probabilities of detection at each wind-normalized emissions value are:
        * 4 kgh/mps -> 20%
        * 6 kgh/mps -> 20%
        * 8 kgh/mps -> 24.242424%
        * 10 kgh/mps-> 35.29411765%
        * 12 kgh/mps-> 69.696970%
        * 14 kgh/mps-> 90.90909091%
        * 16 kgh/mps-> 100%
        * infinity  -> 100%

    Values below 4kgh/mps are just assigned 1 (i.e. do not add any extra correction emissions).

    Args:
        wind_normalized_emm (np.ndarray): 
            An array containing wind-normalized emissions values (e.g. kgh/mps).

    Returns:
        np.ndarray:
            An array that's the same shape as the input, but whose values are 0≤val≤1.
            These values represent the probability of detection.
    """    
    xs = np.array([4,6,8,10,12,14,16])
    ys = np.array([.2,.2,8/33,12/34,23/33,20/22,1.])
    
    # Return P(detection) of wind-normalized emissions rate
    # Note that this returns P(0) = 1, which is a convention only intended to end up having the code avoid sampling "true 0s" any extra times.
    pod = np.ones(wind_normalized_emm.shape)

    for col in range(wind_normalized_emm.shape[1]):
        pod[:,col] = np.interp(wind_normalized_emm[:,col],xs,ys)
    
    # Set all values where wind-normalized emissions are <4 to 1 (i.e. don't add any extra samples)
    pod[wind_normalized_emm<4] = 1

    return pod