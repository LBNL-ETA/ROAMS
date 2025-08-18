from unittest import TestCase

import numpy as np

from roams.transition_point import find_transition_point

class TransitionPointTests(TestCase):

    def test_raisesIndexError(self):
        """
        Assert that input data in the wrong shape will raise IndexError
        """
        n = 10
        m = 5
        w = 100
        
        # n columns
        aerial_x = np.random.uniform(size=(w,n))
        aerial_data = aerial_x.cumsum(axis=0)[::-1,:]
        
        # m columns
        sim_x = np.random.uniform(size=(w,m))
        sim_data = sim_x.cumsum(axis=0)[::-1,:]
        
        # Raise an error if the cumulative distributions have different 
        # numbers of columns
        with self.assertRaises(IndexError):
            find_transition_point(
                aerial_x,
                aerial_data,
                sim_x,
                sim_data,
            )
        
        # Raise an error if the x values aren't the same length
        with self.assertRaises(IndexError):
            find_transition_point(
                aerial_x,
                aerial_data,
                aerial_x[:10,:],
                aerial_data,
            )
        
        # Raise an error if the y values aren't the same length
        with self.assertRaises(IndexError):
            find_transition_point(
                aerial_x,
                aerial_data,
                aerial_x,
                aerial_data[:10,:],
            )
    
    def test_nan_raisesValueError(self):
        """
        Assert that when the smoothed aerial distribution diff starts above 
        that of the simulated distribution
        """
        n = 10
        xs = np.arange(5,1000,1)*1.
        
        # n columns
        aerial_x = np.tile(xs,(n,1)).T
        
        # n columns
        hasnan = aerial_x.copy()
        hasnan[5,5] = np.nan
        
        with self.assertRaises(ValueError):
            find_transition_point(
                hasnan,
                aerial_x,
                aerial_x,
                aerial_x,
            )
        
        with self.assertRaises(ValueError):
            find_transition_point(
                aerial_x,
                hasnan,
                aerial_x,
                aerial_x,
            )
        
        with self.assertRaises(ValueError):
            find_transition_point(
                aerial_x,
                aerial_x,
                hasnan,
                aerial_x,
            )
        
        with self.assertRaises(ValueError):
            find_transition_point(
                aerial_x,
                aerial_x,
                aerial_x,
                hasnan,
            )
    
    def test_AerialDistDropsFaster_raisesValueError(self):
        """
        Assert that when the smoothed aerial distribution diff starts above 
        that of the simulated distribution. Assert that when the opposite 
        is true, the code will execute without error.
        """
        n = 10
        sim_xs = np.array([10,50,50,100,100])
        
        # n columns
        sim_x = np.tile(sim_xs,(n,1)).T
        
        # Sim data will be based on the cumulative distribution of 
        # these emissions
        sim_data = sim_x.cumsum(axis=0)
        sim_data = sim_data.max(axis=0) - sim_data

        aerial_xs = np.array([1,1,1,5,5,5,50])
        aerial_x = np.tile(aerial_xs,(n,1)).T
        aerial_data = aerial_x.cumsum(axis=0)
        aerial_data = aerial_data.max(axis=0) - aerial_data

        with self.assertRaises(ValueError):
            tp = find_transition_point(
                aerial_x,
                aerial_data,
                sim_x,
                sim_data
            )
        
        # Switch sim and aerial datasets: if the above raised an error, then 
        # this should NOT.
        tp = find_transition_point(
            sim_x,
            sim_data,
            aerial_x,
            aerial_data,
        )
    
    def test_correctValue(self):
        """
        Assert that in a contrived example, the transition point is computed 
        to be a pre-determined value, and that it translates with translations 
        of the underlying x (i.e. emissions size) values.
        """
        n = 10
        
        # xs = emissions size (x axis of cumulative distribution) values
        sim_xs = np.array([13.,14.,15,16.,17.])
        
        # n columns
        sim_x = np.tile(sim_xs,(n,1)).T
        
        # Sim data will be based on the cumulative distribution of 
        # these emissions
        # Over the range [13,17], drops at a slope of 2, then .5
        sim_data = sim_x.cumsum(axis=0)[::-1]
        sim_data[:2,:]*=2.  # Before 15: 2x slope 
        sim_data[3:,:]*=.5  # ≥15: half the slope (makes for large slope value at 15)

        # Over the range [13,17], drops at a slope of 1
        aerial_xs = sim_xs
        aerial_x = np.tile(aerial_xs,(n,1)).T
        aerial_data = aerial_x.cumsum(axis=0)[::-1]
        
        # Use a smoothing window of 1 to make the intuition much easier
        tp = find_transition_point(
            aerial_x,
            aerial_data,
            sim_x,
            sim_data,
            smoothing_window=1
        )

        # Assert that the transition point is 16
        # (first integer emissions size value where the aerial slope will be 
        # greater than simulated. Simulated slope at 15 will be large: going 
        # from 2x values to .5x values. But starting at 16, will be .5 that 
        # of aerial dummy data.)
        np.testing.assert_array_equal(tp,np.array([16]*n))

        # Do everything over again, but with the x values translated.
        # Should just shift the transition point to the right by 100
        sim_xs += 100
        
        # n columns
        sim_x = np.tile(sim_xs,(n,1)).T
        
        # Sim data will be based on the cumulative distribution of 
        # these emissions
        # Over the range [13,17], drops at a slope of 2
        sim_data = sim_x.cumsum(axis=0)[::-1]
        sim_data[:2,:]*=2.  # Before 15: 2x slope 
        sim_data[3:,:]*=.5  # ≥15: half the slope

        # Over the range [13,17], drops at a slope of 1
        aerial_xs = sim_xs
        aerial_x = np.tile(aerial_xs,(n,1)).T
        aerial_data = aerial_x.cumsum(axis=0)[::-1]
        
        # Use a smoothing window of 1 to make the intuition much easier
        tp = find_transition_point(
            aerial_x,
            aerial_data,
            sim_x,
            sim_data,
            smoothing_window=1
        )
        
        np.testing.assert_array_equal(tp,np.array([16+100]*n))
        

if __name__=="__main__":
    import unittest
    unittest.main()