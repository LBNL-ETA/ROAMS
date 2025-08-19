import logging

import numpy as np
import pandas as pd

from roams.constants import COMMON_EMISSIONS_UNITS, COMMON_WIND_SPEED_UNITS, COMMON_WIND_NORM_EM_UNITS
from roams.utils import convert_units

class AerialSurveyData:
    """
    This class is intended to serve as a generic entrypoint for aerial survey 
    data from whichever source for code that will have to interact with it.

    At its core, this class expects that the aerial data have:
        * A record of each observed plume, with wind-normalized emissions 
            and wind speeds. Both are needed in order to define (a) overall 
            emissions, and (b) partial detection emissions.
        * A record of the sources from which the plumes are coming, and how 
            many times they were visited during the survey.
        * [Optional] A description of what type of infrastructure best 
            represents each source. If not given, assumes that each source
            is to be included in the analysis.

    Importantly, the class has a collection of property attributes that return 
    information like emissions and wind-normalized emissions in fixed units. 
    These are supposed to serve as the entrypoint to the aerial data from 
    the actual ROAMS model part of this codebase (so that such code doesn't 
    have to actually care about unit specification or dividing up the data 
    sets by asset type).

    When creating an instance of this class, at least two out of three of:
        * emissions rate (em_col)
        * wind-normalized emissions rate (wind_norm_col)
        * wind speed (wind_speed_col)
    
    MUST be specified, as the third can always be inferred (if necessary) 
    based on the relation:

        <emissions rate> = <wind-normalized emissions rate> * <wind speed>

    At the end of the day, the ROAMS model is generically only expected to be 
    using the emissions rate and wind-normalized emissions rate. So wind speed 
    is only required if one of the others is missing. 
    
    IF YOU SPECIFY ALL THREE, the code *WILL NOT* check that they are 
    inter-consistent according to this relation. This hopefully allows for 
    other inter-relationships to be implicitly modeled and provided, since the 
    code always takes the provided column of values in lieu of computation, 
    when available.

    The unit of any given quantity MUST be specified.
            
    Args:
        plume_file (str): 
            Path to the csv holding a record of each plume observed during the 
            aerial survey.

        source_file (str): 
            Path to the csv holding a description of each source from which 
            plumes are being emitted, and how many times they were visited 
            during the survey.
        
        source_id_col (str): 
            The name of the column in the plume and source tables that hold 
            the common source identifier. The code will expect that it's the 
            same column name in both tables, and that the sources identified 
            in the plume table can be found in the source table.
        
        em_col (str, optional): 
            The name of the column in the plumes table that holds the 
            emissions rate in dimensions of [mass]/[time].
        
        em_unit (str, optional): 
            The unit of the emissions rate column given in `em_col`. The 
            physical unit is always expected to be in the dimensions of 
            [mass / time], e.g. "kg/h".
            Defaults to None.

        wind_norm_col (str, optional): 
            The name of the column in the plumes table that holds the 
            wind-normalized emissions values (in some physical unit). 
            Defaults to None.
        
        wind_norm_unit (str, optional): 
            The unit of wind-normalized emissions given in `wind_norm_col`. 
            The physical unit is always expected to be in the form of 
            [emissions rate / windspeed].
            This should always be specified with a ":" separating the 
            wind-normalized emissions unit and the wind-speed unit.
            E.g. "kgh:mps", "kgh:mi/h"
            Defaults to None.
        
        wind_speed_col (str, optional): 
            The name of the column in the plumes table that holds the wind 
            speed values for each plume observation.
            Defaults to None.
        
        wind_speed_unit (str, optional): 
            The units of wind speed in `wind_speed_col`.
            E.g. "mps".
            Defaults to None.
        
        cutoff_col (str, optional): 
            The name of the column in the plume table to indicate whether or 
            not the plume was cut off by the survey field-of-view.
            When present, the code will assume that the values in this column 
            are boolean, indicating whether the plume is cut off (True) or 
            not (False).
            If None, the code just assumes that there is either no such 
            column, or there is and you don't want to give those observations 
            any special treatment.
            Defaults to None.
        
        cutoff_handling (str, optional): 
            How to handle cutoffs flagged in the data. Only option at this 
            point is "drop", in which case values flagged as True/1 will be 
            removed from the raw data.
            If some plumes are cut off but you don't want the code to do 
            anything, you can set `cutoff_col = None`.
            Defaults to "drop".
        
        coverage_count (str, optional): 
            The name of the colum in the sources table that holds the number 
            of times each source was visited in this aerial campaign. 
            Defaults to None.
        
        asset_col (str, optional): 
            The name of the column in the sources table that holds the type 
            of asset that best describes the corresponding infrastructure. 
            This is used with `prod_asset_type` and `midstream_asset_type` to 
            segregate the aerial plume observations into different types 
            of infrastructure for the ROAMS model.
            Defaults to None.
        
        prod_asset_type (tuple, optional): 
            A tuple of values in the `asset_col` of the source table that 
            correspond to what should be counted as production infrastructure. 
            Defaults to None.
        
        midstream_asset_type (tuple, optional): 
            A tuple of values in the `asset_col` of the source table that 
            correspond to what should be counted as midstream infrastructure.
            Defaults to None.

        loglevel (int, optional):
            The level to which events in this submodule should be logged.
            Defaults to logging.INFO.
    """
    def __init__(
        self,
        plume_file : str,
        source_file: str,
        source_id_col : str,
        em_col : str = None,
        em_unit : str = None,
        wind_norm_col : str = None,
        wind_norm_unit : str = None,
        wind_speed_col : str = None,
        wind_speed_unit : str = None,
        cutoff_col : str = None,
        cutoff_handling : str = "drop",
        coverage_count : str = None,
        asset_col : str = None,
        prod_asset_type : tuple = None,
        midstream_asset_type : tuple = None,
        loglevel : int = logging.INFO,
    ):
        self.log = logging.getLogger("roams.aerial.input.AerialSurveyData")
        self.log.setLevel(loglevel)
        self.loglevel = loglevel

        # E.g. self.source_id_col = "emission_source_id"
        self.source_id_col = source_id_col

        # Read the plume data
        self.log.info(f"Reading plume data from {plume_file}")
        self._raw_plumes = pd.read_csv(plume_file)

        # If the emissions rate column is given, assert that the column is 
        # in the table and the unit is specified.
        if em_col is not None:
            
            if em_unit is None:
                raise ValueError(
                    f"The {em_col = } is specified, but em_unit "
                    "is not specified. The AerialSurveyData class can't "
                    "make use of this column without knowing what the units are."
                )
            
            if em_col not in self._raw_plumes.columns:
                raise KeyError(
                    f"{em_col = } is given in the input to AerialSurveyData, "
                    f"but it isn't in the associated {plume_file = }. You should make "
                    "sure you're using the right column name and file."
                )
        
        # If the wind-normalized emissions rate column is given, assert that 
        # the column is in the table and the unit is specified.
        if wind_norm_col is not None:
            
            if wind_norm_unit is None:
                raise ValueError(
                    f"The {wind_norm_col = } is specified, but wind_norm_unit "
                    "is not specified. The AerialSurveyData class can't "
                    "make use of this column without knowing what the units are."
                )
            
            if wind_norm_col not in self._raw_plumes.columns:
                raise KeyError(
                    f"{wind_norm_col = } is given in the input to AerialSurveyData, "
                    f"but it isn't in the associated {plume_file = }. You should make "
                    "sure you're using the right column name and file."
                )
        
        # If the wind speed column is given, assert that the column is in the 
        # table and the unit is specified.
        if wind_speed_col is not None:
            
            if wind_speed_unit is None:
                raise ValueError(
                    f"The {wind_speed_col = } is specified, but wind_speed_unit "
                    "is not specified. The AerialSurveyData class can't "
                    "make use of this column without knowing what the units are."
                )
            
            if wind_speed_col not in self._raw_plumes.columns:
                raise KeyError(
                    f"{wind_speed_col = } is given in the input to AerialSurveyData, "
                    f"but it isn't in the associated {plume_file = }. You should make "
                    "sure you're using the right column name and file."
                )
        
        if sum(
            [em_col is None,wind_norm_col is None, wind_speed_col is None]
            )>1:
            raise ValueError(
                "At least two of em_unit, wind_norm_unit, and wind_speed_unit "
                "are `None` in the input to AerialSurveyData. But at least two "
                "of them must be provided."
            )
            
        self._em_col = em_col
        self._data_em_unit = em_unit
        self._wind_norm_col = wind_norm_col
        self._data_wind_norm_unit = wind_norm_unit
        self._wind_speed_col = wind_speed_col
        self._data_wind_speed_unit = wind_speed_unit
        self._cutoff_col = cutoff_col

        self.log.debug(f"Emissions column '{self._em_col}' has units of '{self._data_em_unit}'")
        self.log.debug(f"Wind-normalized emissions column '{self._wind_norm_col}' has units of '{self._data_wind_norm_unit}'")
        self.log.debug(f"Wind speed column '{self._wind_speed_col}' has units of '{self._data_wind_speed_unit}'")
        
        # Read the source data
        self.log.info(f"Reading source data from {source_file}")
        self._raw_source = pd.read_csv(source_file)
        
        # Assert that the coverage count and asset description columns are 
        # in the source table.
        for col in (coverage_count, asset_col, source_id_col):
            if col not in self._raw_source.columns:
                raise KeyError(
                    f"'{col}' isn't in the {source_file = }. This will "
                    "be necessary for all of the ensuing computations."
                )
            
        self.coverage_count = coverage_count
        self.asset_col = asset_col
        self.source_id_col = source_id_col
            
        if prod_asset_type is None:
            raise ValueError(
                f"{prod_asset_type = } is None, but to be able to separate "
                "the plumes into production and midstream assets, this should "
                f"be an iterable of values in `{asset_col}` that correspond "
                "to production assets."
            )
        self.prod_asset_type = prod_asset_type
        
        if midstream_asset_type is None:
            raise ValueError(
                f"{midstream_asset_type = } is None, but to be able to separate "
                "the plumes into production and midstream assets, this should "
                f"be an iterable of values in `{asset_col}` that correspond "
                "to midstream assets."
            )
        self.midstream_asset_type = midstream_asset_type

        self.handle_cutoffs(cutoff_handling)
        self.differentiate_sources()

    def handle_cutoffs(self,cutoff_handling):
        """
        Use the given `cutoff_handling` methodlogy to do something with plume 
        observations that have been.

        Args:
            cutoff_handling (str):
                A descriptor for what to do with the cut off plumes. Currently 
                can only be "drop", in which case cut off plumes will be 
                removed from the raw plume table.
                (if you want to just keep all the cut off
                plumes and do nothing with them, set `cutoff_col` to None).

        Raises:
            KeyError:
                When you specified a `cutoff_col` to the class, but it doesn't 
                exist in the plumes table.

            ValueError:
                When the choice for `cutoff_handling` isn't a known choice 
                of behavior.
        """        
        if self._cutoff_col is None:
            self.log.info(
                "No cutoff column was given to the survey class, "
                "so it will assume there are no cutoff plumes to handle."
            )
            return
        
        if self._cutoff_col not in self._raw_plumes.columns:
            raise KeyError(
                f"You specified {self._cutoff_col = }, but it doesn't exist in "
                " the plume table. You can set it to `None` to have the code "
                "do nothing, or choose the correct column name."
            )
        
        if cutoff_handling=="drop":
            self.log.info(
                f"The code will drop plumes with '{self._cutoff_col}'=True "
                "in the plume table, and decrement the coverage count before "
                "removing sources with 0 remaining coverage counts."
            )
            # Pick out all the cut off plumes
            cutoff_plumes = self._raw_plumes.loc[
                self._raw_plumes[self._cutoff_col]
            ]
            self.log.debug(
                f"There are {len(cutoff_plumes)} cut off plumes in the entire "
                "dataset."
            )
            # Remove cutoff plumes from the plume dataset
            self._raw_plumes = self._raw_plumes.loc[
                ~self._raw_plumes[self._cutoff_col]
            ]
            
            # E.g. count_col = "Wind Normalized Emissions (kgh/mps)"
            if self._wind_norm_col in self._raw_plumes.columns:
                count_col = self._wind_norm_col
            else:
                count_col = self._em_col

            # Count the number of `count_col` observations for each 
            # source ID.
            source_ids = (
                cutoff_plumes
                .groupby(self.source_id_col)
                [[count_col]]
                .count()
            )
            self.log.debug(
                f"There are {len(source_ids)} unique sources with at least "
                "one cutoff."
            )

            # Reduce the coverage count for each source with a cut off plume.
            for source_id in source_ids.index:
                count = source_ids.loc[source_id,count_col]
                self.loc[
                    (self._raw_source.loc[self.source_id_col]==source_id),
                    self.coverage_count
                ] -= count

            # Remove the sources with 0 coverage count remaining
            self._raw_source = self._raw_source.loc[
                self._raw_source[self.coverage_count]>0
            ]
        # if cutoff_handling == "resample":
        #      ...
        
        else:
            raise ValueError(
                f"The choice of {cutoff_handling = } isn't currently "
                "recognized by the AerialSurveyData class."
            )
    
    def differentiate_sources(self):
        """
        Define `self.production_plumes`, `self.production_sources`, 
        `self.midstream_plumes`, and `self.midstream_sources` based on the 
        prescribed asset types and descriptions in the source data.

        Each will be just a subset of the corresponding raw data. No unit 
        conversion is done here, really only segregating the data.

        This method intentionally does not raise any errors when the resulting 
        tables have 0 rows - it's possible that data from a survey may 
        only observe plumes from one type of source or another.
        """
        self.log.info(
            f"Filtering production assets based on {self.asset_col} being "
            f"one of: {', '.join(self.prod_asset_type)}."
        )
        # Production sources = 100% of the content of the raw source table, 
        # but only the rows whose asset description column have values that 
        # match those prescribed by self.prod_asset_type
        self.production_sources = self._raw_source.loc[
            self._raw_source[self.asset_col].isin(self.prod_asset_type)
        ]
        self.log.debug(
            f"After filtering for specified production assets "
            f"({', '.join(self.prod_asset_type)}), "
            f"there are {len(self.production_sources)} records left in the "
            "production sources table."
        )
        
        # Production plumes = 100% of the content of the raw plumes table, 
        # but only the rows whose sources have been identified as production 
        # assets.
        self.production_plumes = self._raw_plumes.loc[
            self._raw_plumes[self.source_id_col].isin(self.production_sources[self.source_id_col])
        ]
        self.log.debug(
            f"After filtering for specified production assets "
            f"({', '.join(self.prod_asset_type)}), "
            f"there are {len(self.production_plumes)} records left in the "
            "production plumes table."
        )

        self.log.info(
            f"Filtering midstream assets based on {self.asset_col} being "
            f"one of: {', '.join(self.midstream_asset_type)}."
        )
        # Midstream sources = 100% of the content of the raw source table, 
        # but only the rows whose asset description column have values that 
        # match those prescribed by self.midstream_asset_type
        self.midstream_sources = self._raw_source.loc[
            self._raw_source[self.asset_col].isin(self.midstream_asset_type)
        ]
        self.log.debug(
            f"After filtering for specified midstream assets "
            f"({', '.join(self.midstream_asset_type)}), "
            f"there are {len(self.midstream_sources)} records left in the "
            "midstream sources table."
        )
        
        # Midstream plumes = 100% of the content of the raw plumes table, 
        # but only the rows whose sources have been identified as midstream 
        # assets.
        self.midstream_plumes = self._raw_plumes.loc[
            self._raw_plumes[self.source_id_col].isin(self.midstream_sources[self.source_id_col])
        ]
        self.log.debug(
            f"After filtering for specified midstream assets "
            f"({', '.join(self.midstream_asset_type)}), "
            f"there are {len(self.midstream_plumes)} records left in the "
            "midstream plumes table."
        )
    
    @property
    def production_plume_emissions(self) -> np.ndarray:
        # Always return emissions in COMMON_EMISSIONS_UNITS

        # If the emissions column was given, then just return that value
        # converted into the appropriate unit
        if self._em_col is not None:
            return convert_units(
                self.production_plumes[self._em_col].values,
                self._data_em_unit,
                COMMON_EMISSIONS_UNITS
            )
        
        # Otherwise compute using the remaining quantities
        return (self.production_plume_wind_norm * self.production_plume_windspeed)
    
    @property
    def midstream_plume_emissions(self) -> np.ndarray:
        # Always return emissions in COMMON_EMISSIONS_UNITS

        # If the emissions column was given, then just return that value
        # converted into the appropriate unit
        if self._em_col is not None:
            return convert_units(
                self.midstream_plumes[self._em_col].values,
                self._data_em_unit,
                COMMON_EMISSIONS_UNITS
            )

        # Otherwise compute using the remaining quantities
        return self.midstream_plume_wind_norm * self.midstream_plume_windspeed
    
    @property
    def production_plume_wind_norm(self) -> np.ndarray:
        # Wind normalized emissions to always be returned in COMMON_WIND_NORM_EM_UNITS
        
        # If the wind-normalized emissions column is given, just return the converted
        # value (accounting for conversion of numerator and denominator in 
        # [emissions rate]/[windspeed]).
        if self._wind_norm_col is not None:
            # E.g. numer, denom = "kg/d", "mph"
            numer, denom = self._data_wind_norm_unit.lower().split(":")
            
            # E.g. target_numer, target_denom = "kgh", "mps"
            target_numer, target_denom = COMMON_WIND_NORM_EM_UNITS.lower().split(":")

            # Interim output in converted numerator units
            # E.g. "kgh / mph"
            output = convert_units(
                self.production_plumes[self._wind_norm_col].values,
                numer,
                target_numer
            )

            # Convert denominators (switch the order in the function call, 
            # to reflect we are converting a denominator, not numerator - i.e. 
            # flip the multiplication)
            return convert_units(output,target_denom,denom)

        # Otherwise compute using the remaining quantities
        return self.production_plume_emissions/self.production_plume_windspeed
    
    @property
    def midstream_plume_wind_norm(self) -> np.ndarray:
        # Wind normalized emissions to always be returned in COMMON_WIND_NORM_EM_UNITS
        
        # If the wind-normalized emissions column is given, just return the converted
        # value (accounting for conversion of numerator and denominator in 
        # [emissions rate]/[windspeed]).
        if self._wind_norm_col is not None:
            # E.g. numer, denom = "kg/d", "mph"
            numer, denom = self._data_wind_norm_unit.lower().split(":")
            
            # E.g. target_numer, target_denom = "kgh", "mps"
            target_numer, target_denom = COMMON_WIND_NORM_EM_UNITS.lower().split(":")

            # Interim output in converted numerator units
            # E.g. "kgh / mph"
            output = convert_units(
                self.midstream_plumes[self._wind_norm_col].values,
                numer,
                target_numer
            )

            # Convert denominators (switch the order in the function call, 
            # to reflect we are converting a denominator, not numerator - i.e. 
            # flip the multiplication)
            return convert_units(output,target_denom,denom)

        # Otherwise compute using the remaining quantities
        return self.midstream_plume_emissions/self.midstream_plume_windspeed
    
    @property
    def production_plume_windspeed(self) -> np.ndarray:
        # Wind normalized emissions to always be returned in COMMON_WIND_SPEED_UNITS
        
        # If the wind speed col is given, just return the converted version of that column
        if self._wind_speed_col is not None:
            return convert_units(
                self.production_plumes[self._wind_speed_col].values,
                self._data_wind_speed_unit,
                COMMON_WIND_SPEED_UNITS
            )

        # Otherwise compute using the remaining quantities
        return self.production_plume_emissions/self.production_plume_wind_norm
    
    @property
    def midstream_plume_windspeed(self) -> np.ndarray:
        # Wind normalized emissions to always be returned in COMMON_WIND_SPEED_UNITS

        # If the wind speed col is given, just return the converted version of that column
        if self._wind_speed_col is not None:
            return convert_units(
                self.midstream_plumes[self._wind_speed_col].values,
                self._data_wind_speed_unit,
                COMMON_WIND_SPEED_UNITS
            )

        # Otherwise compute using the remaining quantities
        return self.midstream_plume_emissions/self.midstream_plume_wind_norm
    
    @property
    def prod_source_ids(self) -> np.ndarray:
        # The identifiers of production sources in the aerial data
        return self.production_sources[self.source_id_col].values
    
    @property
    def midstream_source_ids(self) -> np.ndarray:
        # The identifiers of midstream sources in the aerial data
        return self.midstream_sources[self.source_id_col].values