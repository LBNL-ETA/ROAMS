import logging

import pandas as pd

from roams.constants import COMMON_EMISSIONS_UNITS, GWP_CH4, CH4_DENSITY_KGMCF
from roams.utils import convert_units, ch4_volume_to_mass

class GHGIDataInput:

    def __init__(
            self,
            state_ghgi_file : str,
            enverus_state_production_file : str,
            enverus_natnl_production_file : str,
            natnl_nat_gas_ch4emissions_file : str,
            natnl_nat_gas_ch4emissions_uncertainty_file : str,
            natnl_petr_ch4emissions_file : str,
            natnl_petr_ch4emissions_uncertainty_file : str,
            year : int,
            state : str,
            frac_ch4_production : float,
            frac_aerial_midstream_emissions : float = .28,
            state_ghgi_unit = "MMT/yr", # for docs: has to have "/"
            natnl_nat_gas_ch4emisssions_unit = "kt/yr",
            enverus_prod_index = "GHGI state",
            enverus_prod_unit = "mcf/yr", # for docs: has to have "/"
            loglevel = logging.INFO
        ):

        self.log = logging.getLogger("roams.midstream_ghgi.input.GHGIDataInput")
        self.log.setLevel(loglevel)

        self.state_ghgi_file = state_ghgi_file
        self.enverus_state_production_file = enverus_state_production_file
        self.enverus_natnl_production_file = enverus_natnl_production_file
        
        self.natnl_nat_gas_ch4emissions_file = natnl_nat_gas_ch4emissions_file
        self.natnl_nat_gas_ch4emissions_uncertainty_file = natnl_nat_gas_ch4emissions_uncertainty_file
        self.natnl_nat_gas_ch4emisssions_unit = natnl_nat_gas_ch4emisssions_unit
        self.natnl_petr_ch4emissions_file = natnl_petr_ch4emissions_file
        self.natnl_petr_ch4emissions_uncertainty_file = natnl_petr_ch4emissions_uncertainty_file
        
        self.year = year
        self.state = state
        self.frac_ch4_production = frac_ch4_production
        self.frac_aerial_midstream_emissions = frac_aerial_midstream_emissions
        
        self.state_ghgi_unit = state_ghgi_unit
        
        self.enverus_prod_index = enverus_prod_index
        self.enverus_prod_unit = enverus_prod_unit

        # Load input datasets
        self.natnl_prod_data = self.load_national_prod_data()
        self.petr_em_data = self.load_petroleum_emissions_data()
        self.nat_gas_em_data = self.load_ng_emissions_data()
        self.state_prod_data = self.load_state_ng_production_data()

        self.submdl_midstream_ch4_loss_rate+1

    def compute_natnl_midstream_loss(self) -> pd.Series:

        
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
        natnl_prod_ch4 = natnl_prod_mcf * self.frac_ch4_production * CH4_DENSITY_KGMCF
        
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
            self.natnl_nat_gas_ch4emisssions_unit,
            COMMON_EMISSIONS_UNITS
        )

        natnl_midstream_loss = (
            natnl_midstream_ch4emiss_commonunits
            / natnl_production_ch4_commonunits
        ) * uncertainty_mul

        return natnl_midstream_loss

    def compute_natnl_midstream_frac(self) -> pd.Series:

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

    def compute_state_midstream_lossrate(self) -> float:
        """
        Define state-level CH4 volumetric loss rate.
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
            f"Converted {state_methane_emissions_co2eq:,.2f} CO2eq of methane "
            f"to {state_methane_emissions_ch4:,.2f} of actual CH4. This was "
            f"then turned into {state_methane_emissions_common} "
            f"{COMMON_EMISSIONS_UNITS} of CH4."
        )
        
        # E.g. state_prod = 100000 mcf/yr
        state_prod = self.state_prod_data.loc[self.state,self.year]

        # E.g. _, denom = "tcf", "yr"
        _, denom = self.enverus_prod_unit.split("/")
        
        # Convert to mcf/<time> so that we can multiply directly with the CH4 density
        # (in kg/mcf)
        state_prod_mcf = convert_units(
            state_prod,
            self.enverus_prod_unit,
            f"mcf/{denom}"
        )
        
        # E.g. 100000 [mcfNG/yr] * .9 [mcfCH4/mcfNG] * 19.17 [kgCH4/mcfCH4] = 1.7e6 [kgCH4/yr]
        state_prod_ch4 = state_prod_mcf * self.frac_ch4_production * CH4_DENSITY_KGMCF
        
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
            f"and CH4/NG fraction of {self.frac_ch4_production}."
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
        if not hasattr(self,"_midstream_ch4_loss_rate"):

            # State CH4 loss rate = [fugitive CH4 from NG production] / [All CH4 produced]
            state_ch4_lossrate = self.compute_state_midstream_lossrate()
            self.log.info(
                f"Estimated state methane loss is {state_ch4_lossrate:.3f}"
            )

            # National midstream emissions fraction = [est. national midstream CH4 emissions] / [est. total national NG + Pet CH4 emissions]
            natnl_midstream_emiss_frac = self.compute_natnl_midstream_frac()
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

            midstream_loss_est = state_midstream_ch4_loss.copy()
            for case in midstream_loss_est.index:
                midstream_loss_est.loc[case] = min(
                    midstream_loss_est.loc[case],
                    natl_midstream_ch4_loss.loc[case]
                )
            
            self._midstream_ch4_loss_rate = (
                (1 - self.frac_aerial_midstream_emissions)
                * midstream_loss_est
            )

        return self._midstream_ch4_loss_rate
    
    def load_national_prod_data(self) -> pd.DataFrame:
        self.log.info(
            "Loading national gas + oil production data from "
            f"`{self.enverus_natnl_production_file}`."
        )
        natnl_prod_data = pd.read_csv(
            self.enverus_natnl_production_file
        )
        natnl_prod_data["Year"] = (
            natnl_prod_data["Enverus production month"]
            .str[-4:]
            .astype(int)
        )
        natnl_prod_data = (
            natnl_prod_data
            .groupby(["Year"])
            [["Oil","Gas"]]
            .sum()
        )
        return natnl_prod_data
    
    def load_petroleum_emissions_data(self) -> pd.DataFrame:
        self.log.info(
            "Loading national petroleum system CH4 emissions from : "
            f"`{self.natnl_petr_ch4emissions_file}`"
        )
        # Load national petroleum-related CH4 emissions estimates
        # Data has to be loaded starting on 3rd row, skipping first 
        # (blank) column
        petr_em_data = pd.read_csv(
            self.natnl_petr_ch4emissions_file,
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
        self.log.info(
            "Loading national NG system emissions from : "
            f"`{self.natnl_nat_gas_ch4emissions_file}`"
        )
        
        # Load national NG-related CH4 emissions estimates
        # Data has to be loaded starting on 3rd row, skipping first 
        # (blank) column
        nat_gas_em_data = pd.read_csv(
            self.natnl_nat_gas_ch4emissions_file,
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

        # Load provided production data
        self.log.info(
            f"Reading state NG production from: `{self.enverus_state_production_file}`"
        )
        state_prod_data = (
            pd.read_csv(self.enverus_state_production_file)
            .set_index(self.enverus_prod_index)
        )
        state_prod_data.rename(
            columns={
                c: int(c) 
                for c in state_prod_data.columns
            },
            inplace=True
        )

        return state_prod_data
    
    def get_natl_midstream_ch4_uncertainty(self) -> pd.Series:
        # Returns: pd.Series

        # This is a highly opinionated parsing of this human-readable
        # style of table. Will almost certainly break with formatting updates.
        nat_gas_uncertainty_data = pd.read_csv(
            self.natnl_nat_gas_ch4emissions_uncertainty_file,
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

if __name__=="__main__":
    c = GHGIDataInput(
        '/Users/eneill/repos/ROAMS/data/Midstream Data/State_level_GHGI2021_forTX.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/Enverus_prod_by_sta1_MCFNGperYear.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/Enverus_prod_natnl_monthly_gas_oil_prod.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/GHGI 2022 Table 3-69.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/GHGI 2022 Table 3-74.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/GHGI 2022 Table 3-43.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/GHGI 2022 Table 3-48.csv',
        2020,
        "TX",
        .9,
        state_ghgi_unit = "MMT/yr",
        enverus_prod_index = "GHGI state",
        enverus_prod_unit = "mcf/yr",
    )