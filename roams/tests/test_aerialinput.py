import os

from unittest import TestCase

import pandas as pd
import numpy as np

from roams.aerial.input import AerialSurveyData
from roams.constants import COMMON_WIND_NORM_EM_UNITS, COMMON_EMISSIONS_UNITS, COMMON_WIND_SPEED_UNITS
from roams.conf import TEST_DIR

PLUME_FILE = os.path.join(TEST_DIR,"_test_plume.csv")
SOURCE_FILE = os.path.join(TEST_DIR,"_test_src.csv") 

# Create a dummy source table
DUMMY_SOURCE_TABLE = pd.DataFrame(
    {
        "source_id":[1,2,3,4,5],
        "asset_type":["prod","prod","midstream","midstream","other"],
        "coverage_count":[2,3,4,5,1],
    }
)

# Create a dummy plume table (one plume per source)
DUMMY_PLUME_TABLE = pd.DataFrame(
    {
        "source_id":[1,2,3,4,5],
        "emissions":[35,48,210,242,10],
        "wind_norm_em":[5,6,21,22,1],
        "windspeed":[7,8,10,11,10],
        "cutoff":[False,False,True,False,False]
    }
)
# Write dummy source data
DUMMY_SOURCE_TABLE.to_csv(SOURCE_FILE,index=False)

# Write dummy source data
DUMMY_PLUME_TABLE.to_csv(PLUME_FILE,index=False)

class AerialSurveyDataTests(TestCase):

    def test_asset_segregation(self):
        """
        Assert that the number of production and midstream plumes and sources 
        is what it should be based on dummy data.
        """        
        survey = AerialSurveyData(
            PLUME_FILE,
            SOURCE_FILE,
            source_id_col="source_id",
            em_col="emissions",
            em_unit="kgh",
            wind_norm_col="wind_norm_em",
            wind_norm_unit="kgh:mps",
            wind_speed_col="windspeed",
            wind_speed_unit="mps",
            coverage_count="coverage_count",
            cutoff_col=None,
            cutoff_handling="drop",
            asset_col="asset_type",
            prod_asset_type=("prod",),
            midstream_asset_type=("midstream",),
        )

        self.assertEqual(
            survey.production_sources.shape[0],2
        )
        self.assertEqual(
            survey.production_plumes.shape[0],2
        )
        np.testing.assert_equal(
            survey.prod_source_ids,np.array([1,2])
        )

        self.assertEqual(
            survey.midstream_sources.shape[0],2
        )
        self.assertEqual(
            survey.midstream_plumes.shape[0],2
        )
        np.testing.assert_equal(
            survey.midstream_source_ids,np.array([3,4])
        )

    def test_cutoff_treatment(self):
        """
        Assert that cutoff treatment with "drop" results in a single
        observation (based on dummy data) being dropped.
        """
        # Create a survey pointing at the "cutoff" column.
        survey = AerialSurveyData(
            PLUME_FILE,
            SOURCE_FILE,
            source_id_col="source_id",
            em_col="emissions",
            em_unit="kgh",
            wind_norm_col="wind_norm_em",
            wind_norm_unit="kgh:mps",
            wind_speed_col="windspeed",
            wind_speed_unit="mps",
            coverage_count="coverage_count",
            cutoff_col="cutoff",
            cutoff_handling="drop",
            asset_col="asset_type",
            prod_asset_type=("prod",),
            midstream_asset_type=("midstream",),
        )
        self.assertEqual(
            len(survey.midstream_plume_emissions),1
        )
        self.assertEqual(
            len(survey.production_plume_emissions),2
        )
        self.assertEqual(
            # Index 2 should be source_id=3, which had a cut off plume
            survey._raw_source.loc[2,"coverage_count"]
            ,3
        )

        # Create a survey not pointing at the "cutoff" column
        # (should have 2 midstream plumes)
        survey = AerialSurveyData(
            PLUME_FILE,
            SOURCE_FILE,
            source_id_col="source_id",
            em_col="emissions",
            em_unit="kgh",
            wind_norm_col="wind_norm_em",
            wind_norm_unit="kgh:mps",
            wind_speed_col="windspeed",
            wind_speed_unit="mps",
            coverage_count="coverage_count",
            cutoff_col=None,
            cutoff_handling="drop",
            asset_col="asset_type",
            prod_asset_type=("prod",),
            midstream_asset_type=("midstream",),
        )
        self.assertEqual(
            len(survey.midstream_plume_emissions),2
        )
        self.assertEqual(
            len(survey.production_plume_emissions),2
        )

    def test_common_unit_no_change(self):
        """
        Assert that when the input units are the same as the common units, 
        the values coming out of the attribute entrypoints are identical to 
        those in the raw data.
        """        
        survey = AerialSurveyData(
            PLUME_FILE,
            SOURCE_FILE,
            source_id_col="source_id",
            em_col="emissions",
            em_unit=COMMON_EMISSIONS_UNITS,
            wind_norm_col="wind_norm_em",
            wind_norm_unit=COMMON_WIND_NORM_EM_UNITS,
            wind_speed_col="windspeed",
            wind_speed_unit=COMMON_WIND_SPEED_UNITS,
            coverage_count="coverage_count",
            cutoff_col=None,
            cutoff_handling="drop",
            asset_col="asset_type",
            prod_asset_type=("prod",),
            midstream_asset_type=("midstream",),
        )
        np.testing.assert_equal(
            survey.production_plume_emissions,np.array([35,48])
        )
        np.testing.assert_equal(
            survey.midstream_plume_emissions,np.array([210,242])
        )
        np.testing.assert_equal(
            survey.production_plume_wind_norm,np.array([5,6])
        )
        np.testing.assert_equal(
            survey.midstream_plume_wind_norm,np.array([21,22])
        )
        np.testing.assert_equal(
            survey.production_plume_windspeed,np.array([7,8])
        )
        np.testing.assert_equal(
            survey.midstream_plume_windspeed,np.array([10,11])
        )
    
    def test_emissions_per_day(self):
        """
        Assert that when the emissions are per day instead of per hour, the 
        resulting values are converted correctly (and windspeed is not 
        altered).
        """        
        survey = AerialSurveyData(
            PLUME_FILE,
            SOURCE_FILE,
            source_id_col="source_id",
            em_col="emissions",
            em_unit="kg/day",
            wind_norm_col="wind_norm_em",
            wind_norm_unit=f"kg/d:{COMMON_WIND_SPEED_UNITS}",
            wind_speed_col="windspeed",
            wind_speed_unit=COMMON_WIND_SPEED_UNITS,
            coverage_count="coverage_count",
            cutoff_col=None,
            cutoff_handling="drop",
            asset_col="asset_type",
            prod_asset_type=("prod",),
            midstream_asset_type=("midstream",),
        )
        np.testing.assert_equal(
            survey.production_plume_emissions,np.array([35,48])/24
        )
        np.testing.assert_equal(
            survey.midstream_plume_emissions,np.array([210,242])/24
        )
        np.testing.assert_equal(
            survey.production_plume_wind_norm,np.array([5,6])/24
        )
        np.testing.assert_equal(
            survey.midstream_plume_wind_norm,np.array([21,22])/24
        )
        np.testing.assert_equal(
            survey.production_plume_windspeed,np.array([7,8])
        )
        np.testing.assert_equal(
            survey.midstream_plume_windspeed,np.array([10,11])
        )
    
    def test_tons_per_h(self):
        """
        Assert that when the emissions are in tons/hr instead of the default 
        kg/h, emissions coming out of unit conversion are 1000x greater (and 
        windspeed is not altered).
        """        
        survey = AerialSurveyData(
            PLUME_FILE,
            SOURCE_FILE,
            source_id_col="source_id",
            em_col="emissions",
            em_unit="t/h",
            wind_norm_col="wind_norm_em",
            wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
            wind_speed_col="windspeed",
            wind_speed_unit=COMMON_WIND_SPEED_UNITS,
            coverage_count="coverage_count",
            cutoff_col=None,
            cutoff_handling="drop",
            asset_col="asset_type",
            prod_asset_type=("prod",),
            midstream_asset_type=("midstream",),
        )
        np.testing.assert_equal(
            survey.production_plume_emissions,np.array([35,48]) * 1000
        )
        np.testing.assert_equal(
            survey.midstream_plume_emissions,np.array([210,242]) * 1000
        )
        np.testing.assert_equal(
            survey.production_plume_wind_norm,np.array([5,6]) * 1000
        )
        np.testing.assert_equal(
            survey.midstream_plume_wind_norm,np.array([21,22]) * 1000
        )
        np.testing.assert_equal(
            survey.production_plume_windspeed,np.array([7,8])
        )
        np.testing.assert_equal(
            survey.midstream_plume_windspeed,np.array([10,11])
        )
    
    def test_missing_col_errors(self):
        """
        Assert that each of source ID column, emission rate, wind-normalized 
        emissions rate, wind speed, and coverage count columns can produce 
        a KeyError on instantiation if they don't exist in the plume data.
        """
        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="THIS COLUMN DOESNT EXIST",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )

        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="THIS COLUMN DOESNT EXIST",
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
       
        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col="THIS COLUMN DOESNT EXIST",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="THIS COLUMN DOESNT EXIST",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="THIS COLUMN DOESNT EXIST",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col="THIS COLUMN DOESNT EXIST",
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(KeyError):
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="THIS COLUMN DOESNT EXIST",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )

    def test_consistent_input_errors(self):
        """
        Assert that inconsistent inputs produce ValueErrors.
        """
        with self.assertRaises(ValueError):
            # Emissions and wind-normalized are missing
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col=None,
                em_unit="t/h",
                wind_norm_col=None,
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col="windspeed",
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(ValueError):
            # Emissions and wind speed are missing
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col=None,
                em_unit="t/h",
                wind_norm_col="wind_norm_em",
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col=None,
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(ValueError):
            # wind-normalized emissions and wind speed are missing
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col="emissions",
                em_unit="t/h",
                wind_norm_col=None,
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col=None,
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )
        
        with self.assertRaises(ValueError):
            # emissions, wind-normalized emissions, and wind speed are missing
            survey = AerialSurveyData(
                PLUME_FILE,
                SOURCE_FILE,
                source_id_col="source_id",
                em_col=None,
                em_unit="t/h",
                wind_norm_col=None,
                wind_norm_unit=f"tons/hr:{COMMON_WIND_SPEED_UNITS}",
                wind_speed_col=None,
                wind_speed_unit=COMMON_WIND_SPEED_UNITS,
                coverage_count="coverage_count",
                cutoff_col=None,
                cutoff_handling="drop",
                asset_col="asset_type",
                prod_asset_type=("prod",),
                midstream_asset_type=("midstream",),
            )

if __name__=="__main__":
    import unittest
    unittest.main()