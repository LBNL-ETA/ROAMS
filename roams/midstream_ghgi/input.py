import logging

import pandas as pd

from roams.constants import COMMON_EMISSIONS_UNITS
from roams.utils import convert_units, GWP_CH4, CH4_DENSITY_KGMCF

class GHGIDataInput:
    """
    A class to wrap around multiple data inputs that contain summary national 
    GHGI emissions information, as well as state and national production data 
    to which it can be compared.

    The one and only piece of data provided by this class to the ROAMS model 
    is intended to be the property `submdl_midstream_ch4_loss_rate`. This is 
    supposed to return an estimate (with upper and lower bounds) of the 
    rate at which produced natural gas in a covered region (represented by the 
    chosen state) results in fugitive CH4 from midstream infrastructure, 
    that's below the aerial detection level.
    
    Args:
        
        state_ghgi_file (str): 
            A path to the downloaded GHGI for the identified state, whose 
            values are supposed to be an amount of CO2eq produced in each 
            year from each state.
            The code will expect that it has rows "Methane","Carbon dioxide", 
            "Nitrous oxide", and "Total". The code further expects that each 
            column is a year, and that the given `year` is one of them. These 
            values are supposed to be CO2eq emissions from the prescribed 
            `state`.
        
        enverus_state_production_file (str): 
            A path to the downloaded Enverus production data, whose first 
            column will be used as an index and holds the state labels, one 
            of which should be the given `state` argument. The code expects 
            that columns are years, and values are total state production, 
            whose units are given by the `enverus_prod_unit` argument. 
        
        enverus_natnl_production_file (str): 
            A path to the downloaded national Enverus production data, 
            which is monthly data. The code will try to aggregate the 
            gas and oil production data by year, and then use the result to 
            define national production.
            NOTE: The code will assume that the units of gas production in 
            this file are the same as that in `enverus_state_production_file`.
        
        ghgi_ch4emissions_ngprod_file (str): 
            The path to a downloaded GHGI result table "CH4 Emissions from 
            Natural Gas Systems". The code has some really specific 
            expectations about the structure of this file (how many rows 
            and columns to skip, conversion of the underlying values 
            expecting they'll be loaded as strings). The columns of the table
            drawn out of this file are expected to be years, one of which 
            is `year`.
            The units of the underlying values are given in 
            `ghgi_ch4emissions_unit`.
        
        ghgi_ch4emissions_ngprod_uncertainty_file (str): 
            A path to the downloaded GHGI result table "Approach 2 
            Quantitative Uncertainty Estimates for CH4 and 
            Non-combustion CO2 Emissions from Natural Gas Systems". Like 
            other tables, the code has really specific expectations of 
            where the relevant values live in this table.
            It will specifically look for and find the fractional uncertainty 
            bounds from the file.
        
        ghgi_ch4emissions_petprod_file (str): 
            A path to the downloaded GHGI result table "CH4 Emissions from 
            Petroleum Systems". The code has some specific expectations about 
            the structure of this file.
            The units are also implicitly assumed to be 
            `ghgi_ch4emissions_unit`.
        
        year (int): 
            The data year for which data will be pulled from the provided 
            tables. This is supposed to be the most representative year for 
            which the aerial survey was conducted.
        
        state (str): 
            The state abbreviation for the state whose state-level GHGI data 
            is perhaps the closest to representing the covered region. This 
            value specifically has to exist in the first column of 
            `state_ghgi_file`.
        
        gas_composition (dict): 
            A dictionary describing the composition of produced gas in the 
            provided datasets. The code will care about the "c1" (methane) 
            entry.
        
        frac_aerial_midstream_emissions (float): 
            The fraction of the total estimated midstream emissions that 
            are likely aerially detectable.
        
        state_ghgi_unit (str, optional):
            The unit of values in `state_ghgi_file`. Numerator and 
            denominator of this unit should be separated with "/".
            Defaults to "MMT/yr".

        ghgi_ch4emissions_unit (str, optional):
            The unit of values in `ghgi_ch4emissions_ngprod_file` and 
            `ghgi_ch4emissions_petprod_file`. Numerator and denominator of 
            this unit should be separated with "/".
            Defaults to "kt/yr".
        
        enverus_prod_unit (str, optional): 
            The units of NG production in the enverus state and national 
            production files. Numerator and denominator of this unit should 
            be separated with "/".
            Defaults to "mcf/yr".

    Raises:
        ValueError:
            When the provided CH4 fraction of produced NG 
            (in `gas_composition`) or fraction of midstream emissions that 
            are aerially detectable (`frac_aerial_midstream_emissions`) aren't 
            a number that's in [0,1].
    """
    def __init__(
            self,
            state_ghgi_file : str,
            enverus_state_production_file : str,
            enverus_natnl_production_file : str,
            ghgi_ch4emissions_ngprod_file : str,
            ghgi_ch4emissions_ngprod_uncertainty_file : str,
            ghgi_ch4emissions_petprod_file : str,
            year : int,
            state : str,
            gas_composition : dict,
            frac_aerial_midstream_emissions : float,
            ghgi_co2eq_unit = "MMT/yr",
            ghgi_ch4emissions_unit = "kt/yr",
            enverus_prod_unit = "mcf/yr",
            loglevel = logging.INFO
        ):
        self.log = logging.getLogger("roams.midstream_ghgi.input.GHGIDataInput")
        self.log.setLevel(loglevel)

        self.state_ghgi_file = state_ghgi_file
        self.enverus_state_production_file = enverus_state_production_file
        self.enverus_natnl_production_file = enverus_natnl_production_file
        
        self.ghgi_ch4emissions_ngprod_file = ghgi_ch4emissions_ngprod_file
        self.ghgi_ch4emissions_ngprod_uncertainty_file = ghgi_ch4emissions_ngprod_uncertainty_file
        self.ghgi_ch4emissions_petprod_file = ghgi_ch4emissions_petprod_file
        self.ghgi_ch4emissions_unit = ghgi_ch4emissions_unit
        
        self.year = year
        self.state = state
        frac_production_ch4 = gas_composition.get("c1")
        if not isinstance(frac_production_ch4,(float,int)) or not 0<=frac_production_ch4<=1.:
            raise ValueError(
                f"{gas_composition.get('c1') = } should be a value from 0 "
                "through 1."
            )
        self.frac_production_ch4 = frac_production_ch4

        if not isinstance(frac_aerial_midstream_emissions,(float,int)) or not 0<=frac_aerial_midstream_emissions<=1.:
            raise ValueError(
                f"{frac_aerial_midstream_emissions = } should be a value "
                "from 0 through 1"
            )
        self.frac_aerial_midstream_emissions = frac_aerial_midstream_emissions
        
        self.state_ghgi_unit = ghgi_co2eq_unit
        
        self.enverus_prod_unit = enverus_prod_unit

        # Load input datasets
        self.natnl_prod_data = self.load_national_prod_data()
        self.petr_em_data = self.load_petroleum_emissions_data()
        self.nat_gas_em_data = self.load_ng_emissions_data()
        self.state_prod_data = self.load_state_ng_production_data()

    def compute_natnl_midstream_loss(self) -> pd.Series:
        """
        Return an estimate (with bounds) of the national average midstream 
        loss rate, by dividing [CH4 lost in midstream infrastructure] by 
        [total CH4 produced] in the selected year.

        Returns:
            pd.Series:
                Return a pd.Series with "low","mid", and "high" indices, 
                whose values are the estimate ("mid") and bounds ("low", 
                "high").
        """
        uncertainty_mul = self.get_natl_midstream_ch4_uncertainty()

        # E.g. _, denom = "tcf", "yr"
        _, denom = self.enverus_prod_unit.split("/")
        
        # Convert to mcf/<time> so that we can multiply directly with the CH4 density
        # (in kg/mcf)
        natnl_prod = self.natnl_prod_data.loc[self.year,"Gas"]
        # E.g. _, denom = "tcf", "yr"
        _, denom = self.enverus_prod_unit.split("/")

        natnl_prod_mcf = convert_units(
            natnl_prod,
            self.enverus_prod_unit,
            f"mcf/{denom}"
        )
        
        # E.g. 100000 [mcfNG/yr] * .9 [mcfCH4/mcfNG] * 19.17 [kgCH4/mcfCH4] = 1.7e6 [kgCH4/yr]
        natnl_prod_ch4 = natnl_prod_mcf * self.frac_production_ch4 * CH4_DENSITY_KGMCF
        
        # E.g. Convert [kg/yr] into [kg/h] 
        natnl_production_ch4_commonunits = convert_units(
            natnl_prod_ch4,
            f"kg/{denom}",
            COMMON_EMISSIONS_UNITS
        )

        # National midstream CH4 emissions
        natnl_midstream_ch4emiss = (
            self.nat_gas_em_data.loc["Gathering and Boosting",self.year]
            + self.nat_gas_em_data.loc["Processing",self.year]
            + self.nat_gas_em_data.loc["Transmission and Storage",self.year]
        )

        natnl_midstream_ch4emiss_commonunits = convert_units(
            natnl_midstream_ch4emiss,
            self.ghgi_ch4emissions_unit,
            COMMON_EMISSIONS_UNITS
        )

        natnl_midstream_loss = (
            natnl_midstream_ch4emiss_commonunits
            / natnl_production_ch4_commonunits
        ) * uncertainty_mul

        return natnl_midstream_loss

    def compute_natnl_midstream_em_frac(self) -> pd.Series:
        """
        Estimate the fraction of national oil and gas industry CH4 emissions 
        that are from midstream infrastructure.

        Do this by dividing [emissions from 'gathering and boosting', 
        'processing', and 'transmission and storage' activities] by 
        [total emissions from gas and oil systems].

        Returns:
            pd.Series:
                Return a pd.Series with "low","mid", and "high" indices, 
                whose values are the estimate ("mid") and bounds ("low", 
                "high").
        """        
        uncertainty_multiplier = self.get_natl_midstream_ch4_uncertainty()

        # Estimated midstream emissions = "Gathering and Boosting”, “Processing”, and “Transmission and Storage”
        # (in the desired year), multiplied with the uncertainty multiplier
        midstream_em = (
            self.nat_gas_em_data.loc["Gathering and Boosting",self.year]
            + self.nat_gas_em_data.loc["Processing",self.year]
            + self.nat_gas_em_data.loc["Transmission and Storage",self.year]
        ) * uncertainty_multiplier
        
        # total emissions = total natural gas + petroleum-related CH4 emissions
        total_emissions = (
            self.nat_gas_em_data.loc["Total",self.year]
            + self.petr_em_data.loc["Total",self.year]
        )

        return midstream_em / total_emissions

    def compute_state_lossrate(self) -> float:
        """
        Use the state-level GHGI estimate and Enverus state-level production 
        data to compute [CH4 lost in the state]/[CH4 produced in the state].

        Returns:
            float: 
                A fraction representing how much CH4 is lost compared to 
                how much is produced in the given state.
        """
        # Load provided GHGI downloaded for a given state
        self.log.info(f"Reading state GHGI summary from: `{self.state_ghgi_file}`")
        state_ghgi_data = pd.read_csv(self.state_ghgi_file,index_col=0)
        state_ghgi_data.index = state_ghgi_data.index.str.lower()

        # Convert CO2eq methane emissions to CH4 in common units of mass. 
        state_methane_emissions_co2eq = state_ghgi_data.loc["methane",str(self.year)]
        state_methane_emissions_ch4 = state_methane_emissions_co2eq/GWP_CH4
        state_methane_emissions_common = convert_units(state_methane_emissions_ch4,self.state_ghgi_unit,COMMON_EMISSIONS_UNITS)
        self.log.info(
            f"Converted {state_methane_emissions_co2eq:,.2f} {self.state_ghgi_unit} "
            f"CO2eq of methane to {state_methane_emissions_ch4:,.2f} "
            f"{self.state_ghgi_unit} of actual CH4. This was then turned into "
            f"{state_methane_emissions_common} {COMMON_EMISSIONS_UNITS} of CH4."
        )
        
        # E.g. state_prod = 100000 mcf/yr
        state_prod = self.state_prod_data.loc[self.state,self.year]

        # E.g. _, denom = "mcf", "yr"
        _, denom = self.enverus_prod_unit.split("/")
        
        # Convert to mcf/<time> so that we can multiply directly with the CH4 density
        # (in kg/mcf)
        state_prod_mcf = convert_units(
            state_prod,
            self.enverus_prod_unit,
            f"mcf/{denom}"
        )
        
        # E.g. 100000 [mcfNG/yr] * .9 [mcfCH4/mcfNG] * 19.17 [kgCH4/mcfCH4] = 1.7e6 [kgCH4/yr]
        state_prod_ch4 = state_prod_mcf * self.frac_production_ch4 * CH4_DENSITY_KGMCF
        
        # E.g. Convert [kg/yr] into [kg/h]
        state_prod_common_units = convert_units(
            state_prod_ch4,
            f"kg/{denom}",
            COMMON_EMISSIONS_UNITS
        )
        self.log.info(
            f"Converted {state_prod:,.0f} {self.enverus_prod_unit} of NG production "
            f"into {state_prod_common_units:,.0f} {COMMON_EMISSIONS_UNITS} "
            f"of CH4 production at an assumed density of {CH4_DENSITY_KGMCF:.2f} "
            f"and CH4/NG fraction of {self.frac_production_ch4}."
        )

        # State methane loss rate is just the ratio of reported emissions
        # to reported production (converting both to mass of CH4/year)
        state_methane_loss_rate = (
            state_methane_emissions_common 
            / state_prod_common_units
        )

        return state_methane_loss_rate
    
    @property
    def submdl_midstream_ch4_loss_rate(self) -> pd.Series:
        """
        This is the primary product of this class from the prospective of the 
        ROAMS model.

        This is an estimate (with bounds) of the ratio of sub-detection-level 
        midstream emissions to CH4 production in the state. This can be used 
        to estimate sub-detection-level emissions in a covered region given 
        known (or estimated) production in the region.

        Returns:
            pd.Series:
                Return a pd.Series with "low","mid", and "high" indices, 
                whose values are the estimate ("mid") and bounds ("low", 
                "high").
        """
        return (
            self.total_midstream_ch4_loss_rate
            * (1 - self.frac_aerial_midstream_emissions)
        )

    
    @property
    def total_midstream_ch4_loss_rate(self) -> pd.Series:
        """
        The total CH4 loss rate of midstream infrastructure for the given 
        state and year, as estimated by the given GHGI data.

        Returns:
            pd.Series:
                Return a pd.Series with "low","mid", and "high" indices, 
                whose values are the estimate ("mid") and bounds ("low", 
                "high").
        """
        if not hasattr(self,"_total_midstream_ch4_loss_rate"):

            # State CH4 loss rate = [fugitive CH4 from NG production] / [All CH4 produced]
            state_ch4_lossrate = self.compute_state_lossrate()
            self.log.info(
                f"Estimated state methane loss is {state_ch4_lossrate:.3f}"
            )

            # National midstream emissions fraction = [est. national midstream CH4 emissions] / [est. total national NG + Pet CH4 emissions]
            natnl_midstream_emiss_frac = self.compute_natnl_midstream_em_frac()
            self.log.info(
                "Estimated national fraction of fugitive CH4 emissions from "
                "midstream infrastructure is: "
                f"{', '.join(
                    [
                        f'{i = } {natnl_midstream_emiss_frac.loc[i]:.3f}' 
                        for i in natnl_midstream_emiss_frac.index
                    ])
                }"
            )
            
            # State midstream ch4 loss = Estimated fraction of state CH4 produced that is lost in midstream
            # = [state-level CH4 loss rate] * [national midstream emissions fraction]
            state_midstream_ch4_loss = (
                state_ch4_lossrate * natnl_midstream_emiss_frac
            )
            self.log.info(
                f"Estimated fraction of {self.state} CH4 production that is lost "
                "in midstream infrastructure is: "
                f"{', '.join(
                    [
                        f'{i = } {state_midstream_ch4_loss.loc[i]:.3f}' 
                        for i in state_midstream_ch4_loss.index
                    ])
                }"
            )
            
            natl_midstream_ch4_loss = self.compute_natnl_midstream_loss()

            if state_midstream_ch4_loss["mid"]<=natl_midstream_ch4_loss["mid"]:
                midstream_loss_est = state_midstream_ch4_loss.copy()
            else:
                midstream_loss_est = natl_midstream_ch4_loss.copy()
            
            self._total_midstream_ch4_loss_rate = midstream_loss_est

        return self._total_midstream_ch4_loss_rate
    
    def load_national_prod_data(self) -> pd.DataFrame:
        """
        Read the given Enverus national production file, which is expected 
        to be a monthly record of national production for both oil and gas.
        The code will create a "Year" column based on the given monthly dates, 
        then aggregate the results into each year.

        Return the resulting DataFrame.

        Only the resulting `self.year` is relevant for informing the results.

        Returns:
            pd.DataFrame:
                The parsed and aggregated national production data, with 
                an index of "Year", and columns of "Oil", and "Gas". The 
                "Gas" column is in units of `self.enverus_prod_unit`.
        """
        self.log.info(
            "Loading national gas + oil production data from "
            f"`{self.enverus_natnl_production_file}`."
        )
        natnl_prod_data = pd.read_csv(
            self.enverus_natnl_production_file
        )
        
        # E.g. "December 1, 1950" -> 1950
        natnl_prod_data["Year"] = (
            natnl_prod_data["Enverus production month"]
            .str[-4:]
            .astype(int)
        )
        
        # Aggregate monthly oil and gas production by year
        natnl_prod_data = (
            natnl_prod_data
            .groupby(["Year"])
            [["Oil","Gas"]]
            .sum()
        )
        
        return natnl_prod_data
    
    def load_petroleum_emissions_data(self) -> pd.DataFrame:
        """
        Read the given GHGI summary table of CH4 emissions from national 
        petroleum systems, and throw out the first two rows and first column.
        It will assume that "Activity" is a remaining column that can serve 
        as an index.

        The code will convert the year column names to int, and turn the 
        stringified numeric values to floats (the last row is a data note 
        that creates a row of NaN).

        Returns:
            pd.DataFrame:
                The GHGI data describing CH4 emissions in national 
                petroleum systems, with year columns and an `Activity` 
                index.
        """
        self.log.info(
            "Loading national petroleum system CH4 emissions from : "
            f"`{self.ghgi_ch4emissions_petprod_file}`"
        )
        # Load national petroleum-related CH4 emissions estimates
        # Data has to be loaded starting on 3rd row, skipping first 
        # (blank) column
        petr_em_data = pd.read_csv(
            self.ghgi_ch4emissions_petprod_file,
            skiprows=2,
        ).iloc[:,1:].set_index("Activity")
        
        # Adding strip() here because trailing space seems to be included.
        petr_em_data.index = petr_em_data.index.str.strip()

        # Convert string columns to int ("2020" -> 2020)
        petr_em_data.rename(
            columns={
                c: int(c) 
                for c in petr_em_data.columns
            },
            inplace=True
        )
        
        # Convert the data in this year's column to float (hard to do from read_csv)
        # Just take each value (e.g. "1,500" and turn into a float)
        for yr in petr_em_data.columns:
            petr_em_data[yr] = (
                petr_em_data[yr]
                .str
                .replace(",","")
                .astype(float)
            )

        return petr_em_data
    
    def load_ng_emissions_data(self) -> pd.DataFrame:
        """
        Read the given GHGI summary table of CH4 emissions from national 
        natural gas systems, and throw out the first two rows and first 
        column. It will assume that "Stage" is a remaining column that can 
        serve as an index.

        The code will convert the year column names to int, and turn the 
        stringified numeric values to floats (the last row is a data note 
        that creates a row of NaN).

        Returns:
            pd.DataFrame:
                The GHGI data describing CH4 emissions in national 
                petroleum systems, with year columns and an `Activity` 
                index.
        """
        self.log.info(
            "Loading national NG system emissions from : "
            f"`{self.ghgi_ch4emissions_ngprod_file}`"
        )
        
        # Load national NG-related CH4 emissions estimates
        # Data has to be loaded starting on 3rd row, skipping first 
        # (blank) column
        nat_gas_em_data = pd.read_csv(
            self.ghgi_ch4emissions_ngprod_file,
            skiprows=2,
        ).iloc[:,1:].set_index("Stage")

        # Convert string columns to int ("2020" -> 2020)
        nat_gas_em_data.rename(
            columns={
                c: int(c) 
                for c in nat_gas_em_data.columns
            },
            inplace=True
        )

        # Convert the data in this year's column to float (hard to do from read_csv)
        # Just take each value (e.g. "1,500" and turn into a float)
        for yr in nat_gas_em_data.columns:
            nat_gas_em_data[yr] = (
                nat_gas_em_data[yr]
                .str
                .replace(",","")
                .astype(float)
            )

        return nat_gas_em_data
    
    def load_state_ng_production_data(self) -> pd.DataFrame:
        """
        Read the given state-level GHGI summary table of CO2eq emissions 
        (assumed to be for the given `self.state`). Set the first column as 
        an index, and convert each column name into an `int`.

        Returns:
            pd.DataFrame:
                The GHGI data describing CH4 emissions in national 
                petroleum systems, with year columns and an index whose 
                values should include "Methane".
        """

        # Load provided production data
        self.log.info(
            f"Reading state NG production from: `{self.enverus_state_production_file}`"
        )
        # Make the first column an index. Should include "Methane".
        state_prod_data = pd.read_csv(
            self.enverus_state_production_file,
            index_col=0
        )

        # Turn string years to int
        # E.g. "2020" -> 2020
        state_prod_data.rename(
            columns={
                c: int(c) 
                for c in state_prod_data.columns
            },
            inplace=True
        )

        return state_prod_data
    
    def get_natl_midstream_ch4_uncertainty(self) -> pd.Series:
        """
        Read the GHGI summary table describing the uncertainty bounds for 
        estimates of natural gas CH4 emissions, and pull out the percentages 
        for the upper and lower CI bounds.

        It will specifically skip the first 4 rows, and only use the 
        2nd, 6th, and 7th columns (0-indexed), expecting that the values in 
        the 6th and 7th columns have the percentage values.

        The percentage values will be converted from strings into floats, then 
        put into a pd.Series that can be used as an "uncertainty multiplier"
        for CH4 midstream emissions estimates, as:

            [1 - lower bound, 1, 1 + upper bound]

        The idea is that multiplying with these values allows estimate of 
        the 95% CI for midstream CH4 emissions quantities coming from these 
        GHGI-based estimates.

        Returns:
            pd.Series:
                A pd.Series with an index of ["low","mid","high"], whose 
                values are multipliers for estimates of midstream emissions.
        """
        # This is a highly opinionated parsing of this human-readable
        # style of table. Will almost certainly break with formatting updates.
        nat_gas_uncertainty_data = pd.read_csv(
            self.ghgi_ch4emissions_ngprod_uncertainty_file,
            skiprows=4,
            usecols=[2,6,7],
            index_col=0,
        )
        # E.g. lower = "-15%"
        lower = nat_gas_uncertainty_data.loc["CH4","Lower.1"]
        # E.g. lower = -.15
        lower = float(lower.strip("%"))/100
        # E.g. upper = "19%"
        upper = nat_gas_uncertainty_data.loc["CH4","Upper.1"]
        # E.g. upper = .19
        upper = float(upper.strip("%"))/100

        # Multiplier to apply to national midstrea emissions.
        uncertainty_multiplier = pd.Series(
            [1+lower,1,1+upper],
            index=["low","mid","high"]
        )

        return uncertainty_multiplier