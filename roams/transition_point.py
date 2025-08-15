import logging

import numpy as np

log = logging.getLogger("roams.transition_point.find_transition_point")

def find_transition_point(
    aerial_x,
    aerial_y,
    sim_x,
    sim_y,
    smoothing_window=11,
) -> np.ndarray:
    """
    Return the emissions rate at which the distribution of observed (and 
    corrected) aerial emissions rates matches that of the sub-minimum-
    detection level emissions values.

    This function will interpolate the cumulative emissions distribution for 
    both aerial emissions data and simulated emissions data into the same 
    [1, 1000] kgh range for each monte carlo sample (the columns of the 
    aerial data), and after smoothing the diffs in those interpolated timeseries,
    return the values for each MC iteration where the difference between the 
    two smoothed diffs changes sign (i.e. where the derivatives of the cumulative 
    distributions roughly match up.)

    Args:
        aerial_x (np.ndarray):
            The sampled aerial emissions, sorted by ascending size. The number 
            of columns should be the number of monte-carlo iterations.

        aerial_y (np.ndarray):
            The cumulative emissions distribution, perhaps but not necessarily 
            including accounting for partial detection. The index of x and y 
            are intended to correspond (i.e., the last entry in each column 
            should be 0, corresponding to the largest emissions value comprising
            the last contribution to the cumulative sum.). Like with the "x" 
            data, each column corresponds to one monte-carlo iteration.

        sim_x (np.ndarray):
            The sampled simulated emissions, sorted by ascending size. The number 
            of columns should be the number of monte-carlo iterations.

        sim_y (np.ndarray):
            The cumulative emissions distribution of the simulated x data. The 
            index of x and y simulated data are intended to correspond 
            (i.e., the last entry in each column should be 0, corresponding 
            to the largest emissions value comprising the last contribution to 
            the cumulative sum.). Like with the "x" data, each column 
            corresponds to one monte-carlo iteration.

        smoothing_window (int, optional): 
            The length of the moving-average window. The resulting smoothed 
            timeseries will be cut off to only include values centered in 
            the smoothing_window size. 
            Defaults to 10.

    Raises:
        IndexError: 
            When the input aerial and simulated data don't have the same 
            number of columns, so may not be representing monte-carlo 
            iterations in the correct way.
        
        ValueError:
            When, in any monte-carlo iteration, the smoothed cumulative 
            emissions distribution diff() of the aerial emissions is *higher* 
            than that of the simulated emissions. As a rule, the simulated 
            emissions skew much lower, so the distribution should begin 
            larger.

    Returns:
        np.ndarray:
            An (num MC iterations)-length array, each of whose entries is 
            roughly the value of emissions at which the aerial distribution 
            begins to dominate the combined distribution
    """
    # Assert that the number of columns in all the inputs are identical
    # (Its intended that each column represents a unique monte-carlo run)
    if (aerial_x.shape[1]!=sim_x.shape[1]) or (aerial_y.shape[1]!=sim_y.shape[1]) or (aerial_x.shape[1]!=aerial_y.shape[1]):
        raise IndexError(
            "The columns in the aerial and simulated x and y data are intended to "
            "both be the number of monte-carlo iterations, but the two "
            "tables have different numbers of columns. You should make sure "
            "the correct data is being passed."
        )

    n_mc_runs = aerial_x.shape[1]
    max_interp_emiss = 1000

    xs = np.arange(5,max_interp_emiss,1)

    interp_aerial_dist = np.zeros((len(xs),aerial_x.shape[1]))
    interp_simmed_dist = np.zeros((len(xs),aerial_x.shape[1]))
    
    # Interpolate both cumulative emissions %s into the same x-values, and turn into diff
    # (approx. derivative.)
    for mc_run in range(n_mc_runs):
        a_x, a_y = aerial_x[:,mc_run], aerial_y[:,mc_run]
        interp_aerial_dist[:,mc_run] = np.interp(
            xs,
            a_x[~np.isnan(a_x)],
            a_y[~np.isnan(a_x)],
        )
        
        s_x, s_y = sim_x[:,mc_run], sim_y[:,mc_run]
        interp_simmed_dist[:,mc_run] = np.interp(
            xs,
            s_x[~np.isnan(s_x)],
            s_y[~np.isnan(s_x)],
        )
    
    # Make matrices intended to hold the moving-average smoothed derivatives (diffs)
    # of the aerial and simulated emissions distributions separately.
    smooth_aerial_dist = np.zeros(interp_aerial_dist.shape)
    smooth_simmed_dist = np.zeros(interp_simmed_dist.shape)
    
    for w in range(len(xs)):
        wmin = max(0,w - smoothing_window)

        # Taking diff of the cumulative sum between index wmin and wmax gets you the sum of values between those points
        # Dividing by wmax-wmin gives you the average of values from [wmin:wmax]
        smooth_aerial_dist[w,:] = (interp_aerial_dist[wmin,:] - interp_aerial_dist[w,:])/max(1,w-wmin)
        smooth_simmed_dist[w,:] = (interp_simmed_dist[wmin,:] - interp_simmed_dist[w,:])/max(1,w-wmin)

    # Find x value at which the difference between the smoothed derivatives
    # switches signs (i.e. where they match, approximately).
    diff = smooth_aerial_dist - smooth_simmed_dist
    
    # Raise an error if any diffs start negative (we always expect 
    # simulated to start above aerial).
    col_signs_to_switch = np.where(diff[0,:]<0)
    if len(col_signs_to_switch[0])>0:
        raise ValueError(
            f"In {len(col_signs_to_switch[0])} monte carlo iterations, the "
            "interpolated+smoothed aerial distribution starts *below* the "
            "interpolated and smoothed sub-detection-level sample. You should "
            "check that the smoothing and interpolating is correct."
        )

    # Always measure the transition point by where the sign switches
    # from negative to positive (argmax returns first index of max)
    transition_point = np.argmax(diff>0,axis=0)
    
    # Take the x values at each first transition point.
    # Remove 1 from the transition_point index to account for the fact that the 
    # first value is always 0 in each smoothed distribution diff (think of it as corresponding to 4 kgh)
    tps = xs[transition_point - 1]

    if (tps==xs[0]).any():
        log.warning(
            "At least one of the identified transition points happened to be "
            f"the same as the minimum possible transition point ({xs[0]} kgh)"
            ", which is just the minimum kgh value included in checking for "
            "the transition point, based on what was done in the original "
            "Analytica model. This may mean that you need to define a new "
            "transition point function that can find a smaller transition "
            "point, or be sure that the units of your simulated and aerial "
            "data are correctly specified."
        )
    
    return xs[transition_point-1]