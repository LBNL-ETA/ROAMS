import logging

import pandas as pd

from roams.constants import COMMON_EMISSIONS_UNITS, GWP_CH4
from roams.utils import convert_units, ch4_volume_to_mass

class GHGIDataInput:

    def __init__(
            self,
            state_ghgi_file : str,
            enverus_state_production_file : str,
            natnl_nat_gas_ch4emissions_file : str,
            natnl_petr_ch4emissions_file : str,
            year : int,
            state : str,
            state_ghgi_unit = "MMT/yr",
            enverus_prod_index = "GHGI state",
            enverus_prod_unit = "mcf/yr",
            prod_density = 17.3262, # kg/mcf, at this point has to cancel volumetric unit with production
            prod_density_unit = "kg/mcf",
            loglevel = logging.INFO
        ):

        self.log = logging.getLogger("roams.midstream_ghgi.input.GHGIDataInput")
        self.log.setLevel(loglevel)

        self.state_ghgi_file = state_ghgi_file
        self.enverus_state_production_file = enverus_state_production_file
        self.natnl_nat_gas_ch4emissions_file = natnl_nat_gas_ch4emissions_file
        self.natnl_petr_ch4emissions_file = natnl_petr_ch4emissions_file
        self.year = year
        self.state = state
        self.state_ghgi_unit = state_ghgi_unit
        self.enverus_prod_index = enverus_prod_index
        self.enverus_prod_unit = enverus_prod_unit
        self.prod_density = prod_density
        self.prod_density_unit = prod_density_unit

        # State CH4 loss rate = [fugitive CH4 from NG production] / [CH4 produced]
        state_ch4_lossrate = self.compute_state_midstream_lossrate()
        self.log.info(
            f"Estimated state methane loss is {state_ch4_lossrate:.3f}"
        )

        # National midstream emissions fraction = [est. national midstream CH4 emissions] / [est. total national NG + Pet CH4 emissions]
        natnl_midstream_emiss_frac = self.compute_natnl_midstream_frac()
        self.log.info(
            "Estimated national fraction of fugitive CH4 emissions from "
            f"midstream infrastructure is: {natnl_midstream_emiss_frac:.3f}"
        )
        
        # State midstream ch4 loss = Estimated fraction of state CH4 produced that is lost in midstream
        state_midstream_ch4_loss = (
            state_ch4_lossrate * natnl_midstream_emiss_frac
        )
        self.log.info(
            f"Estimated fraction of {self.state} CH4 production that is lost "
            f"in midstream infrastructure is: {state_midstream_ch4_loss:.3f}"
        )

    def compute_natnl_midstream_frac(self):

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

        # Convert the data in this year's column to float (hard to do from read_csv)
        nat_gas_em_data[str(self.year)] = (
            nat_gas_em_data[(str(self.year))]
            .str
            .replace(",","")
            .astype(float)
        )

        
        self.log.info(
            "Loading national petroleum system emissions from : "
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

        # Convert the data in this year's column to float (hard to do from read_csv)
        petr_em_data[str(self.year)] = (
            petr_em_data[(str(self.year))]
            .str
            .replace(",","")
            .astype(float)
        )

        # Estimated midstream emissions = "Gathering and Boosting”, “Processing”, and “Transmission and Storage”
        # (in the desired year)
        midstream_em = (
            nat_gas_em_data.loc["Gathering and Boosting",str(self.year)]
            + nat_gas_em_data.loc["Processing",str(self.year)]
            + nat_gas_em_data.loc["Transmission and Storage",str(self.year)]
        )
        
        # total emissions = total natural gas + petroleum-related CH4 emissions
        total_emissions = (
            nat_gas_em_data.loc["Total",str(self.year)]
            + petr_em_data.loc["Total",str(self.year)]
        )

        return midstream_em / total_emissions

    def compute_state_midstream_lossrate(self):
        """
        Define state-level CH4 volumetric loss rate.

        Raises:
            ValueError:
                When the denominator of the provided production density unit 
                (<mass>/<vol>) and numerator of production unit (<vol>/<time>)
                aren't the same.
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

        # Load provided production data and pick out the value for the chosen 
        # state and year. 
        self.log.info(
            f"Reading state NG production from: `{self.enverus_state_production_file}"
        )
        state_prod_data = (
            pd.read_csv(self.enverus_state_production_file)
            .set_index(self.enverus_prod_index)
        )
        
        # Convert production of NG to production of CH4 using a required 
        # volumetric fraction of CH4 content in this NG
        dens_num, dens_denom = self.prod_density_unit.lower().split("/")
        prod_num, prod_denom = self.enverus_prod_unit.lower().split("/")
        if dens_denom!=prod_num:
            raise ValueError(
                f"The production is in `{self.enverus_prod_unit}` and the density "
                f"is in `{self.prod_density_unit}`. This code can really only take "
                "these when the numerator of production and denominator of "
                "density are the same (including the string representation)."
            )
        
        # E.g. state_prod = 100000 mcf/yr
        state_prod = state_prod_data.loc[self.state,str(self.year)]
        
        # E.g. Convert [mcf/yr * kg/mcf] into [kg/h]
        state_prod_common_units = convert_units(
            self.prod_density * state_prod,
            f"{dens_num}/{prod_denom}",
            COMMON_EMISSIONS_UNITS
        )
        self.log.info(
            f"Converted {state_prod:,.0f} {self.enverus_prod_unit} of NG production "
            f"into {state_prod_common_units:,.0f} {COMMON_EMISSIONS_UNITS} "
            f"of CH4 production at an assumed density of {self.prod_density:.2f} "
            f"{self.prod_density_unit}."
        )

        # State methane loss rate is just the ratio of reported emissions
        # to reported production (converting both to mass of CH4/year)
        state_methane_loss_rate = (
            state_methane_emissions_common 
            / state_prod_common_units
        )

        return state_methane_loss_rate

if __name__=="__main__":
    c = GHGIDataInput(
        '/Users/eneill/repos/ROAMS/data/Midstream Data/State_level_GHGI2021_forTX.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/Enverus_prod_by_sta1_MCFNGperYear.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/GHGI 2022 Table 3-69.csv',
        '/Users/eneill/repos/ROAMS/data/Midstream Data/GHGI 2022 Table 3-43.csv',
        2020,
        "TX",
        state_ghgi_unit = "MMT/yr",
        enverus_prod_index = "GHGI state",
        enverus_prod_unit = "mcf/yr",
        prod_density=17.3262,
        prod_density_unit="kg/mcf"
    )