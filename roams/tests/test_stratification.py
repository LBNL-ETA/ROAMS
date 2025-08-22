import logging
from unittest import TestCase

import numpy as np

from roams.simulated.stratify import stratify_sample

class StratificationTests(TestCase):
    
    def test_mismatched_simulateddata(self):
        """
        Assert that mismatched simulated data produces a VaeluError
        """
        with self.assertRaises(ValueError):
            s = stratify_sample(
                np.array([1,2,3]),
                np.array([1,2,3,4]),
                np.array([1,2,3,4]),
                10,
            )
    
    def test_reproduce_initialdist(self):
        """
        Assert that when the covered production data is the same as the 
        simulated production data, and the quantile bins exactly match each 
        input value, and it's asked to sample a number of values equal to the 
        number of simulated values, you get the original simulated emissions 
        values back.

        (1 production value <-> 1 bin <-> 1 simulated emissions value)
        """
        s = stratify_sample(
            np.arange(1,1001), # Emissions are 1 -> 1000
            np.arange(1,1001), # simulated production is 1 -> 1000
            np.arange(1,1001), # covered production is 1 -> 1000
            1000,
            quantiles = (0,*[i*.001 for i in range(1,1001)])
        )

        np.testing.assert_array_equal(s,np.arange(1,1001))
    
        s = stratify_sample(
            np.arange(1,5), # Emissions are 1 -> 4
            np.arange(1,5), # simulated production is 1 -> 4
            np.arange(1,5), # covered production is 1 -> 4
            4,
            quantiles = (0,.25,.5,.75,1.)
        )

        np.testing.assert_array_equal(s,np.arange(1,5))
    
    def test_half_production_overlap(self):
        """
        Assert that when the covered production data only overlaps with half 
        of the simulated production data, and the function is asked to return 
        a sample half the size of the emissions data, you just end up 
        with half of the emissions data.
        """
        s = stratify_sample(
            np.arange(1,1001), # Emissions are 1 -> 1000
            np.arange(1,1001), # simulated production is 1 -> 1000
            np.arange(1,501), # covered production is 1 -> 500
            500,
            quantiles = (0,*[i*.001 for i in range(1,1001)])
        )

        np.testing.assert_array_equal(s,np.arange(1,501))
    
        s = stratify_sample(
            np.arange(1,5), # Emissions are 1 -> 4
            np.arange(1,5), # simulated production is 1 -> 4
            np.array([1,2]), # covered production is 1 -> 2
            2,
            quantiles = (0,.25,.5,.75,1.)
        )

        np.testing.assert_array_equal(s,np.array([1,2]))
    
    def test_half_simulated_overlap(self):
        """
        Assert that when the simulated production data only overlaps with half 
        of the covered production data, and the function is asked to return 
        a sample equal to the size of the emissions data, you just end up 
        with the original emissions data.
        """
        s = stratify_sample(
            np.arange(1,1001), # Emissions are 1 -> 1000
            np.arange(1,1001), # simulated production is 1 -> 1000
            np.arange(1,2000), # covered production is 1 -> 1999
            1000,
            quantiles = (0,*[i*.001 for i in range(1,1001)])
        )

        np.testing.assert_array_equal(s,np.arange(1,1001))
    
        s = stratify_sample(
            np.arange(1,5), # Emissions are 1 -> 4
            np.arange(1,5), # simulated production is 1 -> 4
            np.arange(1,8), # covered production is 1 -> 7
            4,
            quantiles = (0,.25,.5,.75,1.)
        )

        np.testing.assert_array_equal(s,np.arange(1,5))

    def test_assertraises_ValueError(self):
        """
        Assert that when >20% of probability mass is associated to quantile 
        bins whose sample count will be rounded to 0, a ValueError will 
        be raised.
        """
        with self.assertRaises(ValueError):
            # quantile bins are 1 -> 1000
            # quantile weights are 1000/2001 from 1 -> 999, and 1001/2000 at 1000
            #   (because last bin is [99.9 percentile < x <= np.inf])
            # almost 50% of all weight will be rounded down to 0 samples
            # So raise an error.
            s = stratify_sample(
                np.arange(1,1001), # Emissions are 1 -> 1000
                np.arange(1,1001), # simulated production is 1 -> 1000
                np.arange(1,2002), # covered production is 1 -> 2001
                1000,
                quantiles = (0,*[i*.001 for i in range(1,1001)])
            )

    def test_logswarning(self):
        """
        Assert that when maximum covered productivity is above maximum 
        simulated productivity, a warning is logged.
        """
        with self.assertLogs("roams.aerial.stratify.stratify_sample", logging.WARNING):
            s = stratify_sample(
                np.arange(1000),
                np.arange(1000),
                np.arange(1001),
                1000
            )


if __name__=="__main__":
    import unittest
    unittest.main()

