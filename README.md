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

## Structure


## Input file format

The code is capable of of reading a JSON input file, which holds a nested dictionary structure. Here is an illustrative (and nonfunctional) input file, with text to help describe what each entry is and how it's treated. When reading JSON files, `null` will become `None` in python, and the booleans `true/false` become `True/False`. **NOTE** that comments aren't allowed in a JSON file - this is just documentation, not an example input file.

```json
{
        # Simulated production data
        "sim_em_file" :     The file path to a file holding the simulated production emissions to sample from, and optionally the simulated production for each simulated well
        "sim_em_col" :      The name of the column in `em_file` that holds the estimates of emissions from a well in the covered study region. This is required for the ROAMSModel to operate. E.g. "Emissions kgh"
        "sim_em_unit" :     The units of the emissions rate described in `em_col`. This is required for the ROAMSModel to opearate. E.g. "kgh"
        "sim_prod_col" :    The name of the column in `em_file` that holds the estimates of production from a well in the covered study region. If not specified, the code will later break if this ends up  being required for stratification or any other analysis. Defaults to None.
        "sim_prod_unit" :   The units of production described in `production_col`. E.g. "mscf/day". Defaults to None.

        # Aerial Survey input specification        
        "plume_file" :      The file path to the reported plume-level emissions. It's required that each plume record can be matched to each recorded source in the `source_file` by some source identifier.
        "source_file" :     The file path to the covered sources. Should share a column identifier with `plume_file`, and should also contain a descriptor of the asset that best represents the source.
        "source_id_name" :  The column name in both `plume_file` and `source_file` that holds the unique source identifiers. The code will use the values in this column in order to link the tables together. The code will raise an error if not specified. Defaults to None.
        "asset_col" :       The name of the column in the source table that describes the type of infrastructure producing the corresponding plumes. This, together with `asset_type`, is used to segregate the aerial survey data. Defaults to None.
        "prod_asset_type" : A tuple of production asset types under the `asset_col` column to include in the estimation of aerial emissions.
        "midstream_asset_type" : A tuple of midstream asset types under the `asset_col` column to include in the estimation of aerial emissions.
        "coverage_count" :  The name of the column in the `source_file` source table that holds the number of times the given piece of infrastructure was viewed (whether or not emissions were observed).
        "aerial_em_col" :   The name of the column in the `plume_file` plume emissions table that describes the emissions rate. If None, you MUST be specifying wind-normalized emissions rate and wind-speed to be able to infer this. Defaults to None.
        "aerial_em_unit" :  The physical unit of emissions rate, if the corresponding column in the plume file (`emm_col`) has been specified. E.g. "kgh". Defaults to None.
        "wind_norm_col" :   The name of the column in the `plume_file` plume emissions table that describes the wind-normalized emissions rate. If None, you MUST be specifying emissions and wind-speed to be  able to infer this. Defaults to None.
        "wind_norm_unit" :  The physical unit of wind-normalized emissions, if specified. Use a ":" to differentiate between the nominator (emissions rate) and the denominator (wind speed). E.g. "kgh:mps". Defaults to None.
        "wind_speed_col" :  The name of the column in the `plume_file` plume emissions table that describes the wind speed. If None, it's assumed it won't be needed. Defaults to None.
        "wind_speed_unit" : The physical unit of the specified wind speed column, if given. E.g. "mps". Defaults to None.
        "cutoff_col" :      The name of the column in the `plume_file` plume emissions table that holds a flag for whether or not the plume was cut by the field of view of the survey equipment. If None, the code assumes there is none. Defaults to None.

        # Covered productivity input specification
        "covered_productivity_file" :   A path to the file with an estimated distribution of productivity in the covered region, which will be used to re-weight the simulated data according to the "actual" productivity of the region (this process is called 'stratification' in the code). It is also used to define fractional loss (i.e. leaked methane divided by the volume of all methane produced). If not given, the code can't stratify the simulated sample, and won't be able to compute fractional volumetric loss as part of the outputs. Defaults to None.
        "covered_productivity_col" :    The name of the column in the table given by `covered_productivity_file` that holds the estimated per-site production in the covered region. If not given when the file is given, an error will be raised. Defaults to None.
        "covered_productivity_unit" :   The unit of `covered_productivity_col` in the table given by `covered_productivity_file` that holds the estimated per-site production in the covered region. If not given when the file is given, an error will be raised. Defaults to None.
        "num_wells_to_simulate" :       This is supposed to reflect the total number of unique well sites covered in this aerial campaign. The code won't work if this isn't specified, but it's required to be derived from external analysis. Defaults to None.
        "well_visit_count" :    This is supposed to reflect the total number of wells visited during the aerial campaign. The code won't work if this isn't specified, but it's required to be derived from external analysis. Defaults to None.
        "wells_per_site" :      This is supposed to reflect the average number of wells per well site in the covered aerial survey region. This gets used to derive confidence intervals based on experimental distributions. The code won't work if this isn't specified, but it's required to be derived from external analysis. Defaults to None.
        "frac_production_ch4" : The fraction of produced natural gas (reported in covered productivity) that is CH4. Used in the definition of fractional loss when that's being calculated. Defaults to roams.constants.ALVAREZ_ET_AL_CH4_FRAC.
    
        # Algorithmic inputs for the ROAMS model to care about
        "midstream_transition_point" :  A prescribed transition point to apply in the combined midstream emissions distribution, if applicable. The code won't try to find any transition point in this case if not given.
        "stratify_sim_sample" :         Whether or not the simulated emissions should be stratified to better reflect the true production estimated in this region (per the `covered_productivity_file`). Defaults to True.
        "n_mc_samples" :                The number of monte-carlo iterations to do. In each monte-carlo iteration, the (perhaps stratified) simulated emissions are sampled, and the aerial emissions are sampled and noised as well. The resulting distributions are then combined. All monte-carlo iterations are in the end part of the quantified results.Defaults to 100.
        "prod_transition_point" :       A prescribed transition point to apply in the combined production emissions distribution, if applicable. If no such known transition point exists, supplying `None` will indicate to the code to find it by itself. Defaults to None.
        "partial_detection_correction" :Whether or not to apply a partial detection correction to sampled aerial emissions, reflecting the fact that some observed emissions are unlikely to be picked up, and having observed them likely means there is more in the overall region to model that would otherwise not be accounted for. Defaults to True.
        "simulate_error" :              Whether or not to apply `self.noise_fn` to sampled and corrected aerial emissions in order to help simulate error.
        "handle_negative" :             The name of a function in `roams.aerial.assumptions` that can take an array of values (will be sampled and noised aerial data) and do something with below-zero values. Defaults to "zero_out".
        "PoD_fn" :                      The name of a function in `roams.aerial.partial_detection` ("linear" or "bin") that can take an array of wind-normalized emissions values, and return a probability of detection for each value. The result of this function will be fed into the equation to determine the multiplier for corresponding sampled emissions values:    (1/PoD -1), where `PoD` is the outcome of the named function. As such, this should not return any 0 values. Defaults to bin.
        "correction_fn" :               The name of a function in `roams.aerial.assumptions` that can take raw sampled aerial emissions data (equal to [wind normalized emissions]*[wind speed]), and apply a deterministic correction to account for macroscopic average measurement bias. Defaults to "power_correction".
        "noise_fn" :                    The name of a function in `roams.aerial.assumptions` that can take a numpy array, and return a properly noised version of it. Defaults to "normal".
        
        # Output specification
        "foldername" :      A folder name into which given outputs will be saved under "run_results" (=roams.conf.RESULT_DIR). If None, will use a timestamp. Defaults to None.
        "save_mean_dist" :  Whether or not to save a "mean" distribution of all the components of the estimated production distributions (i.e. aerial, partial detection, simulated). Defaults to True.
        "loglevel" :        The log level to apply to analysis happening within the ROAMSModel and submodules that it calls on. If None, will end up using logging.INFO. Defaults to None.
}
```