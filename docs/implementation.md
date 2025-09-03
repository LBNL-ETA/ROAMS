# Implementation

The code in this codebase is an attempt to implement the [methodology](#/docs/methodology.md) described elsewhere.

## Table of Contents

* [Summary](#summary)
* [Input Layer](#input-layer-and-behavior)
* [Processing Layer](#processing-layer)
* [Output Layer](#output-layer)

## Summary

The ROAMS methodology is embodied by the `perform_analysis` method of the `roams.model.ROAMSModel` class. This method creates samples, emissions estimates, and the outputs thereof. This method only calls four other methods, one of which generates the outputs:

| Method Name | Method Purpose |
| --- | --- |
| `make_samples` | Create aerial and simulated emissions samples |
| `combine_prod_samples` | Combined the simulated and aerial production emissions distributions|
| `compute_simulated_midstream_emissions` | Estimate the sub-detection-level midstream emissions |
| `generate_and_write_outputs` | Create and save some outputs |

The methodology requires data from several distinct sources. In an effort to maintain strict separation between the task of specifying the inputs (e.g. what column in this table holds the information we need? What unit is it in? How do we convert it to be usable?) and using them within the prescribed methodology, a lot of the code focuses specifically on making sense of the inputs, and providing entrypoints to the actual computation code. As such, the task of specifying and parsing inputs is put into an [Input Layer](#input-layer-and-behavior), whose job is fundamentally to make sense of the inputs and provide the relevant information to the part of the code that does the computation.

Within this workflow, the `ROAMSModel` class calls an instance of `ROAMSConfig` to parse the content of an input file (or input dictionary), which uses several distinct classes to make sense of different data sources. After this parsing is done within the `__init__` of the `ROAMSModel` class, one can call `perform_analysis()`.

After having parsed the input the [processing layer](#processing-layer), embodied by most of the guts of `ROAMSModel`, actually does stuff with the input information to execute the ROAMS methodology. It is finally up to the [output layer](#output-layer) to do something with all the computed results.

## Input Layer and Behavior
[back to top](#implementation)

The "Input Layer" is intended to abstract the task of input specification away from the computational parts of the codebase. It is fundamentally embodied by the `roams.input.ROAMSConfig` class, which is instantiated with a JSON input file or python dictionary (see the [README](/README.md) for specification) within the `__init__()` method of `ROAMSModel`.

The `ROAMSConfig` class parses the content of the file (or dictionary) by asserting that required inputs exist and are of the right type, then by filling in default values for non-required inputs. It will log warnings if inputs are provided that are neither required nor optional -- they won't be used by the code.

After parsing through the input file in this manner, it will use the specification, now filled with defaults where appropriate, to instantiate distinct input classes designed to parse specific data. See details below for how each specific input class handles input data. These classes are: [AerialSurveyData](#aerial-data-input-class), [SimulatedProductionAssetData](#simulated-data-input-class), [CoveredProductionDistData](#covered-production-data-input-class), and [GHGIDataInput](#ghgi--production-data-input-class)

```mermaid
graph TD;
    Z[ROAMSModel]                   --> A[ROAMSConfig] : creates;
    A[ROAMSConfig]                  --> B[AerialSurveyData] : creates;
    A[ROAMSConfig]                  --> C[SimulatedProductionAssetData] : creates;
    A[ROAMSConfig]                  --> D[CoveredProductionDistData] : creates;
    A[ROAMSConfig]                  --> E[GHGIDataInput] : creates;
    A[ROAMSConfig]                  --> J(Gas Composition) : makes sense of;
    A[ROAMSConfig]                  --> K(Covered Production) : makes sense of;
    B[AerialSurveyData]             --> F(Aerial Data) : makes sense of;
    C[SimulatedProductionAssetData] --> G(Simulated Production Data) : makes sense of;
    D[CoveredProductionDistData]    --> H(Covered Production Data) : makes sense of;
    E[GHGIDataInput]                --> I(GHGI & Production Data) : makes sense of;
```

### Aerial Data Input Class 
The input class for parsing aerial survey input data is `roams.aerial.input.AerialSurveyData`. 

It's expected that the aerial data is provided in two parts: plume data and source data. While plume data holds the information about plume size (and what sources they're coming from), the source data classifies the source types and number of fly-overs. The column names, and units thereof where necessary, are always expected to be provided.

When first instantiated, the `AerialSurveyData` class will assert that the prescribed columns exist, and that there's sufficient information to collect or infer emissions and wind-normalized emissions (via the relation `emissions [mass/time] = wind-normalized emissions [mass/time / speed] * windspeed [speed]`, if necessary). It will also segregate the dataset into different `asset_group`s, which are subsets of the source and plume data corresponding to specific prescribed source asset types. The subsets of the input data corresponding to each asset group are used in providing data to the ROAMSModel class. While the `AerialSurveyData` class doesn't have an opinion about what asset groups are specified, the `ROAMSConfig` will require that "production" and "midstream" are given - the `ROAMSModel` will require those.

The class provides several properties as entry points to the `ROAMSModel` class:

* `plume_emissions`: a dictionary of `asset group : emissions array` pairs, where the key is a string matching the name of a prescribed asset group. The array of emissions values will be converted into `COMMON_EMISSIONS_UNITS`, and in the same order as they would appear in the input data, after filtering for this asset type.
* `plume_wind_norm`: a dictionary of `asset group : wind-normalized emissions array` pairs, where the key is a string matching the name of a prescribed asset group. The array of wind normalized emissions values will be converted into `COMMON_WIND_NORM_EM_UNITS`, and in the same order as they would appear in the input data, after filtering for this asset type.
* `plume_windspeed`: a dictionary of `asset group : wind speed array` pairs, where the key is a string matching the name of a prescribed asset group. The array of wind speed values will be converted into `COMMON_WIND_SPEED_UNITS`, and in the same order as they would appear in the input data, after filtering for this asset type.

For more detail on unit handling, see the [unit handling section](#unit-handling).

### Simulated Data Input Class 
The input class for parsing simulated production emissions data is `roams.simulated.input.SimulatedProductionAssetData`.

This class will expect the data to be provided with a table that at least has a column holding simulated emissions values. A user also has to specify the units of these physical emissions values. If stratified re-sampling is intended to be done, this data should also have a simulated production column (and corresponding specified unit).

The class provides several properties as entrypoints to the `ROAMSModel` class:

* `simulated_emissions` : A `numpy.ndarray` of simulated emissions values from the input table, converted into units of `COMMON_EMISSIONS_UNITS`. The order is the same as that in the original data.
* `simulated_production` : A `numpy.ndarray` of simulated production values from the input table, converted into units of `COMMON_PRODUCTION_UNITS`. The order is the same as that in the original data.

For more detail on unit handling, see the [unit handling section](#unit-handling).

### Covered Production Data Input Class 
The input class for parsing covered production data is `roams.production.input.CoveredProductionDistData`.

This class expects that the covered production distribution data is passed as a csv file with a single column, whose name and physical units are specified. It's intended that this is a long list of values that embodies a distribution reflective of per-well production in the study region. It also requires passing a `gas_composition`, which is used to convert between natural gas and CH4.

The class provides three main properties that serve as entrypoints for the `ROAMSModel` to access the underlying data:

* `ng_production_dist_volumetric`: A `np.ndarray` containing the rate of volumetric production of natural gas for this representative collection of wells, in `COMMON_PRODUCTION_UNITS`. Will be in the same order as the input data.
* `ch4_production_dist_volumetric`: A `np.ndarray` containing the rate of volumetric production of CH4 for this representative collection of wells, in `COMMON_PRODUCTION_UNITS`. It uses the gas composition to make this conversion. Will be in the same order as the input data.
* `ch4_production_dist_mass`: A `np.ndarray` containing the rate of mass production of CH4 for this representative collection of wells, in `COMMON_EMISSIONS_UNITS`. It uses the gas composition and a fixed density assumption to compute this quantity. It will be in the same order as the input data.

For more detail on unit handling, see the [unit handling section](#unit-handling).

### GHGI & Production Data Input Class
The input class for parsing GHGI & State/National production data is `roams.midstream_ghgi.input.GHGIDataInput`.

This class takes a lot of distinct tables as inputs. It requires state & national production data, as well as several different tables that typically appear in the GHGI appendices. Aside from that, the units of quantities within the tables have to be specified, and the data year to use, as well as the state to use in creating estimates, have to be specified. Lastly, it has to be told what fraction of midstream emissions are aerially observable.

This particular input class has very specific opinions about how the data are formatted. You should look at the dummy data to ensure that your inputs are in the same form if you're experiencing problems.

The class provides two main properties to serve as entrypoints for the `ROAMSModel` to access the underlying data:
* `total_midstream_ch4_loss_rate` : The total rate of CH4 loss, expressed as a dimensionless and unitless ratio of `[CH4 emitted from midstream infrastructure]/[Total CH4 produced]`. It is the lesser of a state-level and national-level estimate.
* `submdl_midstream_ch4_loss_rate` : A fraction of `total_midstream_ch4_loss_rate`, representing only the portion that is presumably not aerially observable.

For more detail on unit handling, see the [unit handling section](#unit-handling).

### Unit Handling
Each class in the input layer is responsible for furnishing quantities of interest to the `ROAMSModel` in known, constant units. The common units of computation to be used are in `roams.constants`. After having used values from the inputs to create and quantify new results, it is intended that it can be confident of the units of these quantities - specifically that they are in these common units.

The logic of converting units within the input layer is handled by `roams.utils.convert_units`, and in a few places `roams.utils.ch4_volume_to_mass` and `roams.utils.energycontent_mj_mcf`. These use fixed physical and conversion assumptions to convert between small sets of prescribed units. It is completely expected that the incorporation of novel units will break this code, even if fundamentally consistent with the rest of the analysis.

## Processing Layer
[back to top](#implementation)

```mermaid
graph LR;
    A[perform_analysis] --> B[make_samples]
    A[perform_analysis] --> C[combine_prod_samples]
    A[perform_analysis] --> D[compute_simulated_midstream_emissions]
```

## Output Layer
[back to top](#implementation)

```mermaid
graph LR;
    A[perform_analysis] --> B[generate_and_write_outputs]
```