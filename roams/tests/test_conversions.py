from unittest import TestCase

from roams.utils import convert_units
from roams.conversions import MPS_TO_MPH

class ConversionTests(TestCase):

    def test_convert_emissions_rates(self):
        """
        Assert that some typical emissions rates can be converted correctly
        """
        # Format is convert(1,unit_in,unit_out) = amount of unit_out per 1 unit_in
        self.assertEqual(
            convert_units(1,"kgh","g/h"),1_000
        )
        self.assertEqual(
            convert_units(1,"kgh","g/hr"),1_000
        )
        self.assertEqual(
            convert_units(1,"kgh","g/d"),24*1_000
        )
        self.assertEqual(
            convert_units(1,"kgh","g/day"),24*1_000
        )
        self.assertEqual(
            convert_units(1,"kgh","kg/h"),1
        )
        self.assertEqual(
            convert_units(1,"kgh","kg/hr"),1
        )
        self.assertEqual(
            convert_units(1,"kgh","kgh"),1
        )
        self.assertEqual(
            convert_units(1,"kgh","kg/d"),24
        )
        self.assertEqual(
            convert_units(1,"kgh","kg/day"),24
        )
        self.assertEqual(
            convert_units(1,"kgh","t/h"),1e-3
        )
        self.assertEqual(
            convert_units(1,"kgh","t/hr"),1e-3
        )
        self.assertEqual(
            convert_units(1,"kgh","t/d"),24*1e-3
        )
        self.assertEqual(
            convert_units(1,"kgh","t/day"),24*1e-3
        )

    def test_convert_speeds(self):
        """
        Assert that speeds are being correctly converted.
        """
        self.assertEqual(
            convert_units(1,"mps","mps" ),1
        )
        self.assertEqual(
            convert_units(1,"mps","m/s" ),1
        )
        self.assertEqual(
            convert_units(1,"mps","mph" ),MPS_TO_MPH
        )
        self.assertEqual(
            convert_units(1,"mps","m/h" ),MPS_TO_MPH
        )
        self.assertEqual(
            convert_units(1,"mps","mi/h"),MPS_TO_MPH
        )
        
        

if __name__=="__main__":
    import unittest
    unittest.main()
