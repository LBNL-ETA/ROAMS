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

def get_partial_detection_samples(
        PoD_fn : Callable[[np.ndarray], np.ndarray],
        wind_normalized_em : np.ndarray, 
        emissions : np.ndarray
    ) -> np.ndarray:
    """
    Take an array representing the probability of detection (PoD) of each aerial 
    observation in a (num_samples x num monte-carlo iterations) array, and use it 
    to generate a new set of samples with duplicated emissions values.

    Args:
        PoD_fn (Callable):
            A function that can take the array of wind-normalized emissions, 
            and return an array of probability-of-detection. The function 
            should return 1 for wind-normalized emissions of 0.
        
        wind_normalized_em (np.ndarray):
            A np.ndarray holding wind-normalized emissions values, which are 
            intended to be used in the probability-of-detection function.

        emissions (np.ndarray):
            A np.ndarray holding emissions values, who should be duplicated 
            according to the corresponding probability of detection.

    Returns:
        np.ndarray:
            An (M x num monte-carlo iterations) np.ndarray, where M is the 
            maximum number of duplicated emissions values across all the 
            monte-carlo iterations.
    """
    PoD = PoD_fn(wind_normalized_em)
    if (PoD<=0.).any() or (PoD>1).any():
        raise ValueError(
            "The probability-of-detection for some observation in 0<PoD≤1. "
            "The partial detection re-sampling code doesn't know what to do "
            "with this."
        )
    
    # Number of columns in emissions table = number of monte-carlo iterations
    n_mc_samples = emissions.shape[1]
    
    # Regardless of how detection probability is computed, (1/pod) - 1 is 
    # is how you calculated how many undetected emissions are likely.
    # (0s have already been excluded by this point)
    n_undetected = np.int64(np.round((1./PoD) - 1.))

    # max_extra_samples = maximum length of newly invented samplees.
    max_extra_samples = n_undetected.sum(axis=0).max()

    # An array to hold Probability-of-detection duplicated samples
    partial_detection_samples = np.zeros(shape = (int(max_extra_samples),n_mc_samples))
    for col in range(n_mc_samples):
        # s = all the sampled emissions in this iteration
        s = emissions[:,col]
        
        # n = the # times each sampled value should duplicated
        n = n_undetected[:,col]
        
        # repeated_emiss_vals = the repeated values
        repeated_emiss_vals = np.repeat(s,n)
        
        # Insert repeated values into extra_samples
        partial_detection_samples[:len(repeated_emiss_vals),col] = repeated_emiss_vals

    return partial_detection_samples