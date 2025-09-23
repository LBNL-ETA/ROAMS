# ROAMS

This repository holds python code intended to implement the logic behind the **R**egional **O**il and gas **A**erial **M**ethane **S**ynthesis (ROAMS) model. 

This method was established by Evan Sherwin et al in [this paper](https://doi.org/10.1038/s41586-024-07117-5) for the aerial surveys described there.

The goal of this model is to holistically estimate a CH<sub>4</sub> emissions size distribution of gas & oil infrastructure in a specific region. It is especially valuable because it can combine distributions that separately cover small- and large-size CH<sub>4</sub> emissions events.

To read more about the model or underlying methodology, read the [methodology docs](/docs/methodology.md). To learn more about the details of the implementation, you can look at the [implementation docs](/docs/implementation.md). If you're having trouble using the code for your own work, you can read through example [use cases](docs/use%20cases.md).

## Table of Contents

* [Installation](#installation)
* [Usage](#usage)
* [Scripts](#scripts)
* [Tests and Validation](#tests-and-validation)
* [Contributing](#contributing)
* [Input File Format](#input-file-format)

## Installation
[go to top](#roams)

I suggest you install this package from a local clone of this repository. 

1. Clone this repository locally
2. Create a new python environment, e.g. `python -m venv /path/to/envs/roamsmodeling`
3. Activate the new python environment, e.g. `source /path/to/envs/roamsmodeling/bin/activate` (on unix) or `C:\path\to\envs\roamsmodeling\Scripts\Activate.bat` (windows)
4. Navigate to the root of the cloned repository in your terminal or command prompt
5. Run `pip install .` to install the content of the repo as a package in your environment
6. (Optional) you can verify the validity of your installation by running `python -m unittest`, which will run prescribed tests in the repository.

## Usage
[go to top](#roams)

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

## Scripts
[go to top](#roams)

Scripts that make use of the code are in the `scripts/` folder. There is currently only one: `run_roams_model.py`.

### run_roams_model

This script allows users to run the `ROAMSModel` on an input file, and so only takes one required argument: the path to the input file. You can run the model on an input file as follows from your terminal, with the right python environment activated:

```shell
> python scripts/run_roams_model.py "path/to/your/input/file.json"
```

You can direct the code to log at the debug level to the console with the `--debug` flag (it will always be logged at debug level to the log file):

```shell
> python scripts/run_roams_model.py "path/to/your/input/file.json" --debug
```

## Tests and Validation
[go to top](#roams)

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

## Contributing
[go to top](#roams)

The ROAMS Model is intended to change over time in order to fix bugs, update assumptions, and add new features. In whichever case, please follow these steps:

1. Make an issue on the repository
    * The issue can be a venue for discussion of implementation, opinions to add or remove, and identification of any concerns.
    * Detail what you would like to do, and why it's important. Who is affected by this bug or feature? If a bug, how do you reproduce it? If a feature, how would you use it? Be thoughtful and communicate your thoughts. This helps a lot to document decision making about the model.
2. Develop on a new branch
    * In general its a good idea to use the issue discussion as a guide, where appropriate, to inform development closely. 
    * It's suggested that you name your branch using the issue number and basic description (e.g. `10_fix_aerial_input_bug`) (It's OK to address closely related issues on the same branch, too)
    * For ease of merging, make sure you branch from the latest version of main unless you have a good reason to do otherwise
3. Prepare for Pull Request
    * Increment the version number in `roams.__init__`, which serves as the code version and should be 1-to-1 with version tags. Use basic [semantic versioning](https://semver.org/) practice to choose to increment major, minor, and patch versions.
    * If you haven't added or altered any existing unit tests, consider whether or not you should. E.g. is your new feature being tested? Did you remove something that results in a tautological test?
    * Make sure all the unit tests pass
    * Update the [changelog](/docs/changelog.md) to describe what has been changed, added, and/or fixed. Make sure newer versions are at the top of the document, and is included in the version list as well.
    * **Update any and all documentation affected by your changes**. Docstrings should obviously be updated, but perhaps also the README and/or docs.
4. Create a Pull Request
    * Describe what issue this branch is addressing and basically how.
    * Choose a reviewer with time to review, and enough expertise to know what your changes are about
    * You can bring up any unexpected small problems that arose or choices you had to make, and ask for input about whether something else should be done
5. (Reviewer) Review Pull Request
    * In a new environment, make sure all the tests pass
    * Review the changes and make sure you can confirm the issue has been addressed.
    * Review the changes and think about existing users: is there any new requirement this places on them? If they were to update their code and use the same input file, would it work?
    * Review the changes and think about existing use cases: does this introduce any serious impediment to known code workflows?
    * Are there any additional tests that should probably be added? Are there any that should be removed or altered?
    * Are there warnings that can be avoided?
    * **Make sure the documentation has been updated as appropriate**. Check the README and docs content. Even small updates are worth making if it keeps the documentation up-to-date.
    * It's OK to decline a pull request if it's no longer really needed, if a much better approach was found, or if it doesn't really meet the issue. The approach can be reworked in the issue discussion, the branch can be redeveloped, and 
6. Merge branch
    * If everything is OK, the reviewer approves the PR and merges the branch
    * [Tag](https://git-scm.com/book/en/v2/Git-Basics-Tagging) the merge commit on the main branch, with a message to simply describe the change. The version tag should correspond to the new `__version__` in `roams/__init__.py`.
    * Communicate to stakeholders that changes have been made (e.g. the bug has been fixed, the desired feature now exists...).


## Input file format
[go to top](#roams)

The code is capable of of reading a JSON input file, which holds a simple flat dictionary structure. Here's a table that describes the keys of this flat dictionary input structure. Note that when reading JSON files, `null` will become `None` in python, and the booleans `true/false` become `True/False`. The defaults listed here are the Python defaults.

You can find an example input embodied in the small [validation exercise](/roams/tests/validation/deterministic_validation.py), which is a runnable script (and part of unit test cases) that will produce example outputs in `run_results/` from example inputs. The input dictionary defined within the file may be useful as a guide for you getting your input file off the ground. **NOTE** that the data is not realistic, and also that it specifically uses a child class of the `ROAMSModel` that implements deterministic behavior. That is to say, outside of providing example input formatting, this should NOT be used as a guide for your project.

| Field | Usage | Default (if applicable) | Example |
|---|---|---|---|
| "sim_em_file" | The file path to a file holding the simulated production emissions to sample from, and optionally the simulated production for each simulated well | | `"/path/to/my/sim/results.csv"` |
| "sim_em_col" | The name of the column in `sim_em_file` that holds the estimates of emissions from a well in the covered study region. This is required for the ROAMSModel to operate. | | `"emissions kgh"` |
| "sim_em_unit" | The units of the emissions rate described in `sim_em_col`. This is required for the ROAMSModel to opearate. | | `"kgh"`, `"kg/h"` |
| "sim_prod_col" | The name of the column in `sim_em_file` that holds the estimates of production from a well in the covered study region. If not specified, the code will later break if this ends up  being required for stratification |  `None` | `"well production mscf/site/day"` |
| "sim_prod_unit" | The units of production described in `sim_prod_col`, if provided. |  `None` | `"mscf/day"`  |
| "plume_file" | The file path to the reported plume-level emissions. It's required that each plume record can be matched to each recorded source in the `source_file` by some source identifier. | | `"/path/to/my/plume/observations.csv"` |
| "source_file" | The file path to the covered sources. Should share a column identifier with `plume_file`, and should also contain a descriptor of the asset that best represents the source. | | `"/path/to/my/source/descriptions.csv"` |
| "source_id_name" | The column name in both `plume_file` and `source_file` that holds the unique source identifiers. The code will use the values in this column in order to link the tables together. The code will raise an error if not specified. | | `"source_id"` |
| "asset_col" | The name of the column in the source table that describes the type of infrastructure producing the corresponding plumes. This, together with `asset_type`, is used to segregate the aerial survey data. | | `"asset_type"` |
| "asset_groups" | A dictionary of `{asset group name : list of included assets}` to use when splitting up the aerial data. The `ROAMSModel` requires that this has at least "production" and "midstream", whose asset types should not intersect. Remaining asset groups will have their aerially measured emissions characterized with the same sampling and adjustment procedure.| | `{"production":["Well site"],"midstream":["Pipeline"]}` |
| "coverage_count" | The name of the column in the `source_file` source table that holds the number of times the given piece of infrastructure was viewed (whether or not emissions were observed).  | | `"coverage count"` |
| "aerial_em_col" | The name of the column in the `plume_file` plume emissions table that describes the (not wind-normalized) emissions rate. If None, you MUST be specifying wind-normalized emissions rate and wind-speed to be able to infer this |  `None` | `"plume emissions kgh"` |
| "aerial_em_unit" | The physical unit of emissions rate, if the corresponding column in the plume file (`emm_col`) has been specified |  `None` | `"kgh"` |
| "wind_norm_col" | The name of the column in the `plume_file` plume emissions table that describes the wind-normalized emissions rate. If None, you MUST be specifying emissions and wind-speed to be  able to infer this. | `None` | `"wind-normalized emissions - kgh/mps"` |
| "wind_norm_unit" | The physical unit of wind-normalized emissions, if specified. Use a ":" to differentiate between the nominator (emissions rate) and the denominator (wind speed) |  `None` | `"kgh:mps"` |
| "wind_speed_col" | The name of the column in the `plume_file` plume emissions table that describes the wind speed. If None, it's assumed it won't be needed |  `None` | `"HRRR windspeed mps"` |
| "wind_speed_unit" | The physical unit of the specified wind speed column, if given |  `None` | `"mps"` |
| "cutoff_col" | The name of the column in the `plume_file` plume emissions table that holds a flag for whether or not the plume was cut by the field of view of the survey equipment. If None, the code assumes there is no such column. | `None`  | `"plume is cut off"` |
| "covered_productivity_dist_file" | A path to the file with an estimated distribution of well-level productivity in the covered region, which will be used to re-weight the simulated data according to the "actual" productivity of the region (this process is called 'stratification' in the code). It is expected for this to represent uniform quantiles of well-level productivity, at a granularity of 0.1% at least (i.e. productivity of 0.1 percentile well, productivity of 0.2 percentile well, etc.), if not smaller grain. This will be roughly translated into well-site-level productivity by multiplying each value by `"wells_per_site"`. If not given, the code can't stratify the simulated sample. | `None` | `"/path/to/covered_productivity/estimate.csv"` |
| "covered_productivity_dist_col" | The name of the column in the table given by `covered_productivity_file` that holds the estimated per-site production in the covered region. If not given when the file is given, an error will be raised. | `None` | `"productivity, mscf/d"` | 
| "covered_productivity_dist_unit" | The unit of `covered_productivity_col` in the table given by `covered_productivity_file` that holds the estimated per-site production in the covered region. If not given when the file is given, an error will be raised |  `None` | `"mscf/d"` | 
| "num_wells_to_simulate" | This is supposed to reflect the total number of unique well sites covered in this aerial campaign. The code won't work if this isn't specified, but it's required to be derived from external analysis. | | `1000` | 
| "well_visit_count" | This is supposed to reflect the total number of wells visited during the aerial campaign. The code won't work if this isn't specified, but it's required to be derived from external analysis. | | `10000` |
| "wells_per_site" | This is supposed to reflect the average number of wells per well site in the covered aerial survey region. This gets used to derive confidence intervals based on experimental distributions. The code won't work if this isn't specified, but it's required to be derived from external analysis. | | `3.14159` |
| "total_covered_ngprod_mcfd" | An estimate of the total natural gas production in the covered region, in mscf/day. | | `100000`|
| "state_ghgi_file" | A path to the file with estimated state-level CO2eq emission for the state of interest (or best proxy). Should have years as columns, and a "Methane" row. The values are expected to be in mass of CO2eq/yr. | | `"/path/to/my/statelevel_GHGI20XX_HI.csv"`|
| "ghgi_co2eq_unit" | The physical unit of emissions prescribed in `state_ghgi_file`. | | `"MMT/yr"`|
| "production_state_est_file" | The path to a table of annual state-level natural gas production, with rows containing state abbreviations (one of which should be your given `"state"` input), and columns headed by years (one of which should be your `"year"` input). | | `"/path/to/your/state_prod_mcfngperyear.csv"`|
| "production_natnl_est_file" | The path to a long-form table of national monthly production data, with an "production month" column containing a "\<day of week\>, \<month\> 1, YYYY" date format, and at least a "Gas" column. The code will only care about the last four characters (year) of the date column. The units of the "Gas" column are given by `"production_est_unit"`. | | `"/path/to/your/natnl_monthly_gas_oil_prod.csv"`|
| "production_est_unit" | The unit of natural gas production for values in `production_state_est_file` and national gas production in `production_natnl_est_file`. | | `"mscf/yr"` |
| "ghgi_ch4emissions_ngprod_file" | The GHGI table (usually from appendix/supplementary tables) of "CH4 Emissions from Natural Gas Systems", which has national CH<sub>4</sub> emissions from different parts of the natural gas production process. The code will apply fixed rules to pull out the tabular content from the file, assuming it is in it's original "human readable" format. | | `"/path/to/GHGI 2022 Table 3-69.csv"`|
| "ghgi_ch4emissions_ngprod_uncertainty_file" | The GHGI table (usually from appendix/supplementary tables) of "Approach 2 Quantitative Uncertainty Estiamtes for CH4 and Non-combustion CO2 Emissions from Natural Gas Systems", which describes the percentage 95% confidence bounds on national estimates of emissions from natural gas systems. The code will apply fixed rules to pull out the tabular content from the file, assuming it is in it's original "human readable" format, and try to only collect the confidence interval percentages.  | | `"/path/to/GHGI 2022 Table 3-74.csv"`|
| "ghgi_ch4emissions_petprod_file" | The GHGI table (usually from appendix/supplementary tables) of "Ch4 Emissions from Petroleum Systems", which has national CH<sub>4</sub> emissions from different parts of the oil production process. The code will apply fixed rules to pull out the tabular content from the file, assuming it is in it's original "human readable" format. | | `"/path/to/GHGI 2022 Table 3-43.csv"`|
| "ghgi_ch4emissions_unit" | The physical unit of emissions in each of `ghgi_ch4emissions_ngprod_file` and `ghgi_ch4emissions_petprod_file`| | `"kt/yr"` | 
| "year" | The year in the GHGI (and production estimate data) that you'd like to get data from. | | `2019` |
| "state" | The state abbreviation in the `"production_state_est_file"` production data you'd like to use. This state abbreviation will also be used, where relevant, to look up GHGI emissions estimates for the state that's most representative of your study region. | | `"NM"` |
| "frac_aerial_midstream_emissions" | The estimated fraction of GHGI-estimated midstream emissions that are above the minimum detection level. | | `0.123` |
| "random_seed" | The seed to give to `numpy.random.seed`, which is the source of randomness introduced in the algorithm. If `None`, numpy will do a default time-based seeding that will be very difficult to reproduce |  `None` | `1234` |
| "gas_composition" | The fractional molar composition of natural gas. Molecules are denoted by carbon content (e.g. `"C1"` is methane ). Used in the translation of natural gas to CH<sub>4</sub> in several places, as well as fractional energy loss. "C1" (methane) should always be included. Fractions do not have to add to 1, under the assumption that some small fraction of gas may not really contribute to energy content. | | `{"C1":.6,"C2":.3,"C3":.05,"NC4":.01,"IC4":.01}` |
| "midstream_transition_point" | A prescribed transition point (in kg/h) to apply in the combined midstream emissions distribution, if applicable. The code won't try to find any transition point in this case if not given. | | `40` |
| "stratify_sim_sample" | Whether or not the simulated emissions should be stratified to better reflect the true production estimated in this region (per the `covered_productivity_file`). See the [methodology docs](/docs/methodology.md#stratified-sampling) for a description of this process. |  `True` | `True` |
| "n_mc_samples" | The number of monte-carlo iterations to do. In each monte-carlo iteration, the (perhaps stratified) simulated emissions are sampled, and the aerial emissions are sampled and noised as well. The resulting distributions are then combined. All monte-carlo iterations are in the end part of the quantified results |  `100` | `1000` |
| "prod_transition_point" | A prescribed transition point to apply in the combined production emissions distribution, if applicable. If no such known transition point exists, supplying `None` will indicate to the code to find it by itself. Should be in units `roams.constants.COMMON_EMISSIONS_UNITS` |  `None` | `None` |
| "handle_negative" | The name of a function in `roams.aerial.assumptions` (currently only "zero_out") that can take an array of values (will be sampled and noised aerial emissions) and do something with below-zero values. |  `"zero_out"` | `"zero_out"` |
| "partial_detection_correction" | Whether or not to apply a partial detection correction to sampled aerial emissions, reflecting the fact that some observed emissions are unlikely to be picked up, and having observed them likely means there is more in the overall region to model that would otherwise not be accounted for | `True` | `True` |
| "PoD_fn" | The name of a function in `roams.aerial.partial_detection` (currently "linear" or "bin") that can take an array of wind-normalized emissions values, and return a probability of detection for each value. The result of this function will be fed into the equation to determine the multiplier for corresponding sampled emissions values: `(1/PoD -1)`, where `PoD` is the outcome of the named function. As such, this should not return any 0 values. |  `"bin"` | `"bin"` |
| "correction_fn" | Either `None` (no mean correction applied to aerial plume emissions), or a dictionary. If a dictionary, should include a `"name"` key whose value is the name of a method in the `roams.aerial.assumptions` module (currently only "power" and "linear") . Remaining key:value pairs in the dictionary will be passed as keyword arguments to that method at execution time. |  `None` | `{"name":"power","constant":4.08,"power":0.77}` |
| "simulate_error" | Whether or not to apply the prescribed `noise_fn` to sampled and corrected aerial emissions in order to help simulate error. | `True` | `True` |
| "noise_fn" | If `"simulate_error"` is `True`, the noise function to apply to sampled aerial data. Either `None` (in which case it will use a normal distribution with a mean of 1.00 and SD of 0.39 based on a distribution established in [Chen, Sherwin et al. (2022)](https://doi.org/10.1021/acs.est.1c06458)), or a dictionary. If a dictionary, should include a `"name"` key whose value is the name of a method in the `numpy.random` module. Remaining key:value pairs in the dictionary will be passed as keyword arguments to that method at execution time. The `size=` keyword argument is decided by the code based on the size of sampled aerial emissions - do not provide that argument. The noise will be generated by the method, and applied multiplicatively to the sample emissions. | `{"name":"normal","loc":1.0,"scale":0.39}` | `{"name":"normal","loc":1.0,"scale":1.0}` |
| "foldername" | A folder name into which given outputs will be saved under "run_results" (=roams.conf.RESULT_DIR). If `None`, will use a timestamp |  `None` | `"my_special_run"` |
| "save_mean_dist" | Whether or not to save a "mean" distribution of all the components of the estimated production distributions (i.e. aerial, partial detection, simulated) |  `True` | `True`|
| "loglevel" | The log level to apply to analysis happening within the ROAMSModel and submodules that it calls on. If `None`, will end up using `logging.INFO` |  `None` | `20` (= `logging.WARNING`)|