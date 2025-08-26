# ROAMS

This repository holds python code intended to implement the logic behind the **R**egional **O**il and gas **A**erial **M**ethane **S**ynthesis (ROAMS) model. 

It is intended to serve both as a source of documented methodology, and an implementation of it.

This method was established by Evan Sherwin et al in [this paper](https://doi.org/10.1038/s41586-024-07117-5) for the aerial surveys described there.

## Installation

I suggest you install this package from a local clone of this repository. 

1. Clone this repository locally
2. Create a new python environment, e.g. `python -m venv /path/to/envs/roamsmodeling`
3. Activate the new python environment, e.g. `source /path/to/envs/roamsmodeling/bin/activate` (on unix) or `C:\path\to\envs\roamsmodeling\Scripts\Activate.bat` (windows)
4. Navigate to the root of the cloned repository in your terminal or command prompt
5. Run `pip install .` to install the content of the repo as a package in your environment
6. (Optional) you can verify the validity of your installation by running `python -m unittest`, which will run prescribed tests in the repository.

## Usage

The intended use-case of the code here is in scripts that instantiate a `roams.model.ROAMSModel` class, and then call it's `perform_analysis()` method.

An example script:

```python3

from roams.model import ROAMSModel

if __name__=="__main__":
    m = ROAMSModel("path/to/my/input.json")
    m.perform_analysis()

```

After calling `perform_analysis()`, the model that's ran will produce a folder in `run_results/` of the repository, named by the `foldername` specified in the input file. If the folder already existed, the content will be overwritten.

To get started with creating your own input file, read the [input file structure section](#input-file-format)

## Tests and Validation

A collection of unit tests exist to help verify that individual and collected components of the codebase are acting as intended. You can run the unit tests from the root of the repository with:

```
python -m unittest
```

These tests cover a lot of specific behavior (e.g. the data parsing of each input class), and also functional behavior (e.g. the outcome of the transition point computation). In addition, a small validation exercise is ran on dummy data using a deterministic version of the `ROAMSModel`, in which the tests will assert that it produces some very specific numerical results.

It's strongly encouraged to use the passing or failing of these unit tests as an indication for whether or not changes break previous expectations about code behavior. They do not comprehensively assess whether changes to the code are "good" or not, just whether the behavior of many individual components meets specific expectations. As such, it's expected that tests will have to be updated and augmented as the code gets new behavior and accommodates more use-cases.

In addition to running the unit tests as a whole, you can choose to run the dummy-data validation exercise by itself:

```
python roams/tests/validation/deterministic_validation.py
```

## Structure

The code that executes the model is supposed to be separated into three distinct "layers": the input layer, the processing layer, and the output layer. 

The input layer concerns itself with units, column names, and table structures. By caring about these things, it allows the processing layer to only care about the algorithm.

The processing layer implements the true logic of the ROAMS model, and is primarily concerned only with the algorithmic logic.

The output layer is supposed to make human-readable results that are important to users.

### Input Layer

The input "layer" is responsible for not only reading the input file and applying default behavior, but instantiating specialized classes that wrap around the data in given input files. These classes hold accessible properties intended to serve as a source of truth for important information contained in the data.

For example, the `roams.aerial.input.AerialSurveyData` class has a `production_plume_emissions` property that returns the emissions values from all production-associated plumes in fixed units.

The input layer is embodied by `roams.input.ROAMSConfig`, which is used to read the input file. This class is instantiated with an input file (or the content of the dictionary embodied therein), and uses classes defined in the `input` submodules to wrap around the given input data.

### Processing Layer

The processing "layer" is embodied in the `perform_analysis` method of the `roams.model.ROAMSModel` class. In this layer the simulated and aerial production distributions are created the put together for each monte-carlo iteration. The midstream aerial emissions are sampled and combined with derived GHGI-based estimates.

### Output Layer (in development)

The output "layer" is supposed to be responsible for making human-readable summaries, plots, or more highly derived information based on what was computed. This is currently embodied by the `generate_and_write_results` method of the `roams.model.ROAMSModel` class.

## Input file format

The code is capable of of reading a JSON input file, which holds a simple flat dictionary structure. Here's a table that describes the keys of this flat dictionary input structure. Note that when reading JSON files, `null` will become `None` in python, and the booleans `true/false` become `True/False`.

| Field | Usage | Example |
|---|---|---|
| "sim_em_file" | The file path to a file holding the simulated production emissions to sample from, and optionally the simulated production for each simulated well | `"/path/to/my/sim/results.csv"` |
| "sim_em_col" | The name of the column in `sim_em_file` that holds the estimates of emissions from a well in the covered study region. This is required for the ROAMSModel to operate. | `"emissions kgh"` |
| "sim_em_unit" | The units of the emissions rate described in `sim_em_col`. This is required for the ROAMSModel to opearate. | `"kgh"`, `"kg/h"` |
| "sim_prod_col" | The name of the column in `sim_em_file` that holds the estimates of production from a well in the covered study region. If not specified, the code will later break if this ends up  being required for stratification. Defaults to `None`. | `"well production mscf/site/day"` |
| "sim_prod_unit" | The units of production described in `sim_prod_col`. Defaults to `None`. | `"mscf/day"`  |
| "plume_file" | The file path to the reported plume-level emissions. It's required that each plume record can be matched to each recorded source in the `source_file` by some source identifier. | `"/path/to/my/plume/observations.csv"` |
| "source_file" | The file path to the covered sources. Should share a column identifier with `plume_file`, and should also contain a descriptor of the asset that best represents the source. | `"/path/to/my/source/descriptions.csv"` |
| "source_id_name" | The column name in both `plume_file` and `source_file` that holds the unique source identifiers. The code will use the values in this column in order to link the tables together. The code will raise an error if not specified. | `"source_id"` |
| "asset_col" | The name of the column in the source table that describes the type of infrastructure producing the corresponding plumes. This, together with `asset_type`, is used to segregate the aerial survey data. | `"asset_type"` |
| "prod_asset_type" |  tuple of production asset types under the `asset_col` column to include in the estimation of aerial emissions. | `("Well site",)` |
| "midstream_asset_type" |  tuple of midstream asset types under the `asset_col` column to include in the estimation of aerial emissions. | `("Pipeline","Compressor Station","Other")` |
| "coverage_count" | The name of the column in the `source_file` source table that holds the number of times the given piece of infrastructure was viewed (whether or not emissions were observed). | `"coverage count"` |
| "aerial_em_col" | The name of the column in the `plume_file` plume emissions table that describes the (not wind-normalized) emissions rate. If None, you MUST be specifying wind-normalized emissions rate and wind-speed to be able to infer this. Defaults to `None`. | `"plume emissions kgh"` |
| "aerial_em_unit" | The physical unit of emissions rate, if the corresponding column in the plume file (`emm_col`) has been specified. Defaults to `None`. | `"kgh"` |
| "wind_norm_col" | The name of the column in the `plume_file` plume emissions table that describes the wind-normalized emissions rate. If None, you MUST be specifying emissions and wind-speed to be  able to infer this. Defaults to `None`. | `"wind-normalized emissions - kgh/mps"` |
| "wind_norm_unit" | The physical unit of wind-normalized emissions, if specified. Use a ":" to differentiate between the nominator (emissions rate) and the denominator (wind speed). Defaults to `None`. | `"kgh:mps"` |
| "wind_speed_col" | The name of the column in the `plume_file` plume emissions table that describes the wind speed. If None, it's assumed it won't be needed. Defaults to `None`. | `"HRRR windspeed mps"` |
| "wind_speed_unit" | The physical unit of the specified wind speed column, if given. Defaults to `None`. | `"mps"` |
| "cutoff_col" | The name of the column in the `plume_file` plume emissions table that holds a flag for whether or not the plume was cut by the field of view of the survey equipment. If None, the code assumes there is no such column. Defaults to `None`  | `"plume is cut off"` |
| "covered_productivity_dist_file" | A path to the file with an estimated distribution of productivity in the covered region, which will be used to re-weight the simulated data according to the "actual" productivity of the region (this process is called 'stratification' in the code). It is also used to define fractional loss (i.e. leaked methane divided by the volume of all methane produced). If not given, the code can't stratify the simulated sample, and won't be able to compute fractional volumetric loss as part of the outputs. Defaults to None. | `"/path/to/covered_productivity/estimate.csv"` |
| "covered_productivity_dist_col" | The name of the column in the table given by `covered_productivity_file` that holds the estimated per-site production in the covered region. If not given when the file is given, an error will be raised. Defaults to `None`. | `"productivity, mscf/d"` | 
| "covered_productivity_dist_unit" | The unit of `covered_productivity_col` in the table given by `covered_productivity_file` that holds the estimated per-site production in the covered region. If not given when the file is given, an error will be raised. Defaults to `None`. | `"mscf/d"` | 
| "num_wells_to_simulate" | This is supposed to reflect the total number of unique well sites covered in this aerial campaign. The code won't work if this isn't specified, but it's required to be derived from external analysis. | `1000` | 
| "well_visit_count" | This is supposed to reflect the total number of wells visited during the aerial campaign. The code won't work if this isn't specified, but it's required to be derived from external analysis. | `10000` |
| "wells_per_site" | This is supposed to reflect the average number of wells per well site in the covered aerial survey region. This gets used to derive confidence intervals based on experimental distributions. The code won't work if this isn't specified, but it's required to be derived from external analysis. | `3.14159` |
| "total_covered_ngprod_mcfd" | An estimate of the total natural gas production in the covered region, in mscf/day. | `100000`|
| "state_ghgi_file" | A path to the file with estimated state-level CO2eq emission for the state of interest (or best proxy). Should have years as columns, and a "Methane" row. The values are expected to be in mass of CO2eq/yr. | `"/path/to/my/statelevel_GHGI20XX_HI.csv"`|
| "ghgi_co2eq_unit" | The physical unit of emissions prescribed in `state_ghgi_file`. | `"MMT/yr"`|
| "enverus_state_production_file" | | `"/path/to/enverus/state_prod_mcfngperyear.csv"`|
| "enverus_natnl_production_file" | | `"/path/to/enverus/natnl_monthly_gas_oil_prod.csv"`|
| "enverus_prod_unit" | The unit of natural gas production for values in `enverus_state_production_file` and national gas production in `enverus_natnl_production_file`. | `"mscf/yr"` |
| "ghgi_ch4emissions_ngprod_file" | The GHGI table (usually from appendix/supplementary tables) of "CH4 Emissions from Natural Gas Systems", which has national CH4 emissions from different parts of the natural gas production process. The code will apply fixed rules to pull out the tabular content from the file, assuming it is in it's original "human readable" format. | `"/path/to/GHGI 2022 Table 3-69.csv"`|
| "ghgi_ch4emissions_ngprod_uncertainty_file" | The GHGI table (usually from appendix/supplementary tables) of "Approach 2 Quantitative Uncertainty Estiamtes for CH4 and Non-combustion CO2 Emissions from Natural Gas Systems", which describes the percentage 95% confidence bounds on national estimates of emissions from natural gas systems. The code will apply fixed rules to pull out the tabular content from the file, assuming it is in it's original "human readable" format, and try to only collect the confidence interval percentages.  | `"/path/to/GHGI 2022 Table 3-74.csv"`|
| "ghgi_ch4emissions_petprod_file" | The GHGI table (usually from appendix/supplementary tables) of "Ch4 Emissions from Petroleum Systems", which has national CH4 emissions from different parts of the oil production process. The code will apply fixed rules to pull out the tabular content from the file, assuming it is in it's original "human readable" format. | `"/path/to/GHGI 2022 Table 3-43.csv"`|
| "ghgi_ch4emissions_unit" | The physical unit of emissions in each of `ghgi_ch4emissions_ngprod_file` and `ghgi_ch4emissions_petprod_file`| `"kt/yr"` | 
| "year" | The year in the GHGI (and enverus production data) that you'd like to get data from. | `2019` |
| "state" | The state abbreviation in the enverus production data you'd like to use. | `"NM"` |
| "frac_aerial_midstream_emissions" | The estimated fraction of GHGI-estimated midstream emissions that are aerially detectable. | `0.123` |
| "random_seed" | The seed to give to `numpy.random.seed`, which is the source of randomness introduced in the algorithm. If `None`, numpy will do a default time-based seeding that will be very difficult to reproduce. Defaults to `None`. | `None`, `1234` |
| "gas_composition" | The fractional molar composition of natural gas. Molecules are denoted by carbon content (e.g. `"C1"` is methane ). Used in the translation of natural gas to CH4 in several places, as well as fractional energy loss. "C1" (methane) should always be included. Fractions do not have to add to 1, under the assumption that some small fraction of gas may not really contribute to energy content. | `{"C1":.6,"C2":.3,"C3":.05,"NC4":.01,"IC4":.01}` |
| "midstream_transition_point" | A prescribed transition point (in kg/h) to apply in the combined midstream emissions distribution, if applicable. The code won't try to find any transition point in this case if not given. | `40` |
| "stratify_sim_sample" | Whether or not the simulated emissions should be stratified to better reflect the true production estimated in this region (per the `covered_productivity_file`). Defaults to True. | `True` |
| "n_mc_samples" | The number of monte-carlo iterations to do. In each monte-carlo iteration, the (perhaps stratified) simulated emissions are sampled, and the aerial emissions are sampled and noised as well. The resulting distributions are then combined. All monte-carlo iterations are in the end part of the quantified results. Defaults to 100. | `1000` |
| "prod_transition_point" | A prescribed transition point to apply in the combined production emissions distribution, if applicable. If no such known transition point exists, supplying `None` will indicate to the code to find it by itself. Defaults to None. | `37.1` or `None` |
| "partial_detection_correction" | Whether or not to apply a partial detection correction to sampled aerial emissions, reflecting the fact that some observed emissions are unlikely to be picked up, and having observed them likely means there is more in the overall region to model that would otherwise not be accounted for. Defaults to True. | `True` |
| "simulate_error" | Whether or not to apply the prescribed `noise_fn` to sampled and corrected aerial emissions in order to help simulate error. Defaults to `True` | `True` |
| "handle_negative" | The name of a function in `roams.aerial.assumptions` (currently only "normal") that can take an array of values (will be sampled and noised aerial emissions) and do something with below-zero values. Defaults to `"zero_out"`. | `"zero_out"` |
| "PoD_fn" | The name of a function in `roams.aerial.partial_detection` (currently "linear" or "bin") that can take an array of wind-normalized emissions values, and return a probability of detection for each value. The result of this function will be fed into the equation to determine the multiplier for corresponding sampled emissions values:    `(1/PoD -1)`, where `PoD` is the outcome of the named function. As such, this should not return any 0 values. Defaults to `"bin"`. | `"bin"` |
| "correction_fn" | The name of a function in `roams.aerial.assumptions` (currently only "power_correction") that can take raw sampled aerial emissions data (equal to [wind normalized emissions]*[wind speed]), and apply a deterministic correction to account for macroscopic average measurement bias. Defaults to "power_correction". | `"power_correction"` |
| "noise_fn" | The name of a function in `roams.aerial.assumptions` (currently only "normal") that can take a numpy array, and return a properly noised version of it. Defaults to `"normal"`. | `"normal"` |
| "foldername" | A folder name into which given outputs will be saved under "run_results" (=roams.conf.RESULT_DIR). If `None`, will use a timestamp. Defaults to `None`. | `"my_special_run"` |
| "save_mean_dist" | Whether or not to save a "mean" distribution of all the components of the estimated production distributions (i.e. aerial, partial detection, simulated). Defaults to `True`. | `True`|
| "loglevel" | The log level to apply to analysis happening within the ROAMSModel and submodules that it calls on. If `None`, will end up using logging.INFO. Defaults to `None`. | `20` (= `logging.WARNING`)|