# ROAMS Methodology
[Back to README](/README.md)

This part of the documentation describes the implemented methodology in a mostly code-agnostic way. The implementation of this methodology, and other decisions made around it, are described in the [implementation documentation](/docs/implementation.md)

## Table of Contents

* The [summary](#summary) provides a quick overview of the purpose and primary inputs to the methodology, as well as the primary outputs.
* The [aerial emissions](#aerial-emissions-quantification) section describes how aerial emissions observations are used to generate distributions
    * The [partial detection correction](#partial-detection-correction) section describes this accounting of unobserved emissions that are still above the minimum detectable level
* The [simulated emissions](#simulated-emissions-quantification) section describes how simulated emissions from production 
* The [combining production distributions](#combining-production-distributions)
* The [GHGI-based Emissions quantification](#ghgi-based-emissions-quantification)

## Summary
[go back to top](#roams-methodology)

The ROAMS model is intended to produce a size distribution of CH4 emissions from oil and gas infrastructure in a specific region of interest. With this information, it can try to characterize the emissions in the region (How much CH4 is emitted? From which infrastructure? What is the contribution of super-emitters?). In order to do this, it separately characterizes emissions from production and midstream infrastructure, and incorporates estimates for each within different emissions size regimes. While all emissions above "minimum detectable level" (MDL) are intended to be captured by aerial measurement, the "sub-MDL" (below minimum detectable level) emissions are estimated from different sources. The table below describes the sources of data used in this characterization.

| | **Production Infrastructure**  | **Midstream Infrastructure** |
| --- | ------------- | ------------- |
| **Emissions ≥ Minimum Detection Level** | Aerial Measurement   | Aerial Measurement |
| **Emissions < Minimum Detection Level** | Simulation | GHGI-based Estimate |

The ROAMS Methodology is executed in several discrete steps:

1. Generate N different samples of adjusted aerial measurements, each representing an emissions size distribution (See [aerial emissions quantification](#aerial-emissions-quantification))
    * For emissions from both production and midstream infrastructure, separately 
2. Generate N different samples of simulated sub-detection-level emissions from production infrastructure (See [simulated emissions quantification](#simulated-emissions-quantification))
3. For each of the N iterations, combine the sample of sub-MDL simulated production emissions with the sample of aerially measured production emissions (See [combining production distributions](#combining-production-distributions))
4. Compute an estimate of sub-MDL emissions from midstream infrastructure. (See [GHGI-based Emissions quantification](#ghgi-based-emissions-quantification))

As a result of these steps, the methodology has produced N CH4 emissions size distributions for all production infrastructure in the studied region. This can yield a distribution of (a) total estimated CH4 emissions, (b) estimated maximum site emissions, (c) estimated median site emissions, and more. In addition, one could average over all the N generated distributions in order to estimate an "average" emissions size distribution of production infrastructure in the area. It's also possible to attempt to characterize the fraction of emissions coming from sub-MDL versus aerially observed measurements. The component sampled emissions distributions of production infrastructure (aerial and sub-MDL simulated) may also be of use to users.

On the midstream infrastructure side, there are N CH4 emissions size distributions of aerially measured data, but no corresponding estimated distributions of sub-MDL emissions. The sub-MDL GHGI-based emissions estimate is just a single value with a confidence interval. As such, when trying to answer questions about midstream infrastructure, you can still try to answer questions about the total, and characterize the largest (i.e. aerially observed) emissions, but there is currently no way to try to answer questions about the distribution of all emissions.

## Aerial Emissions Quantification
[go back to top](#roams-methodology)

The aerially measured emissions serve as the basis for the distribution of emissions above the minimum detectable level.

The first step in the treatment of the aerial measurement data is to segregate it into the plume measurements coming from production and midstream infrastructure, separately. After that point, the treatment of each set of plume observations is identical. In the diagram below, the steps for the treatment of aerial data are outlined.

```mermaid
graph LR;
    A[Input Data] --> B(Source Plume Sample)
    B --> C(Bias Correction)
    C --> D(Noise Application)
    D --> E[Aerial Sample]
```

The first step is to generate a sample of N plumes from each observed source. For N times, the method will sample with replacement uniformly from all coverages of this source. For example:

> A source was flown over 3 times, and the plume observations are `[0 kgh (no observed plume), 50 kgh, 100kgh]`, the code is equally likely to sample 0 kgh, 50kgh, and 100kgh for this source.

When this sample is generated, the method will simultaneously keep track of the corresponding sampled wind-normalized emissions (e.g. `kgh CH4 observed/mps of wind`), which will be used in the [partial detection correction](#partial-detection-correction). 

The next step is to take all of the sampled emissions, and send them through a deterministic function intended to correct for known measurement bias. For example, in [Evan Sherwin et al](https://doi.org/10.1038/s41586-024-07117-5), sampled emissions were raised to a non-integer power and multiplied by a constant, in order to account for observed bias. This adjustment is not applied to the wind-normalized emissions values to which the original plume values correspond.

After applying this function to the sampled emissions, the resulting values are passed through a function that applies random noise. The ultimate purpose of this step in the process is to allow for a better characterization of uncertainty in the final estimates. Emissions values coming out of this process which are less than 0 should be dealt with - either by resampling, or setting to 0. This adjustment is not applied to the wind-normalized emissions values to which the original plume values correspond.

The result of all these steps is N distinct samples of adjusted and noised aerially observed emissions. Corresponding to each adjusted and noised value is an originally estimated wind-normalized emissions value.

After generating these samples, the methodology completes the quantification of aerially measured emissions by estimating a [partial detection correction](#partial-detection-correction)

### Partial Detection Correction

The *Partial Detection Correction* is an accounting of unobserved emissions that were likely to have existed at the time of aerial survey, but were not measured. This accounting is necessary because measurement equipment and methodology is imperfect, and in a certain regime of emission quantity, the measurement of emissions at all is a probabalistic event.

For example:

> Suppose that specific measurement equipment used during a survey has a 50% chance of being able to measure emissions of 10 kgh, all else being equal. If you had flown over 10,000 well sites, and 20 of them were observed to be emitting at 10 kgh, you would expect that in total there were probably about 40 total well sites emitting at that rate, and you just happened to be able to measure half of them (because you had a 50% chance). The *partial detection correction* is a record of the `(40 total sites @10kgh - 20 observed sites @10kgh ) * 10kgh = 200 kgh` that is unobserved but likely to exist in the 10,000 surveyed well sites. This total amount of emissions (`200 kgh`) is associated to the corresponding emissions size (`10kgh`) in the accounting of the region-wide emissions size distribution.

In practice, the partial detection correction is the result of taking a probability of detection (as a function of wind-normalized emissions, and perhaps additional information from each sampled plume), and using it to define an adjustment factor (=`[partial detection emissions]/[observed emissions]`) to apply to the corresponding adjusted-and-noised emissions value. In the example above, the probability of detection would be 50%, and the partial detection adjustment factor would be 1 (for each observed emission, there is 1 unobserved).

## Simulated Emissions Quantification
[go back to top](#roams-methodology)

The ROAMS methodology expects that the sub-MDL emissions of production infrastructure are estimated via simulation, for example via the BASE model ([described here](https://doi.org/10.1038/s41467-021-25017-4)).

The simulated emissions inputs are more or less just a long table of simulated emissions values, which may also contain simulated production values as well.

The first step of using the simulated emissions data is to tell whether or not you can reasonably believe that the values are representative of the surveyed production infrastructure. If so, you can move on to the next step. If not, you will need to re-sample the simulated emissions values so that the resulting distribution of simulated production better matches that of the covered region. The process used to meet this condition is called "stratified sampling", in which the simulated emissions associated to specific quantile bins of production are re-sampled according to their prevalence in the "actual" covered production distribution.

> Example: Simulated emissions are uniform over `[0 kgh,10 kgh]`, and corresponding production is uniform over `[1 mscf/d, 11 mscf/d]` (this is not realistic). Further, there's an exact correspondence between emissions and production, i.e. 0 kgh <-> 1 mscf/d, 1kgh <-> 2mscf/d, etc (this is definitely not realistic). At the same time, the covered production distribution shows there are only lower production wells - it suggests a uniform distribution over `[1 mscf/d, 5 mscf/d]`. As such, we will do "stratified sampling" of the simulated emissions by sampling uniformly with replacement from those producing in the range `[1 mscf/d, 5 mscf/d]`, and end up with a uniform distribution of simulated emissions in `[0 kgh, 4 kgh]`. The result of this sampling would be our "stratified sample".

In reality, the methodology avoids trying to typify the underlying distribution of covered production. Instead, if computes specific quantiles of the simulated production data, and finds the fraction of covered productivity in each of those bins. It then proportionally re-samples corresponding simulated emissions values in each of those production bins to better match the concentration of covered productivity.

The second step is far easier. You take the resulting simulated emissions values (which may or may not have been re-sampled, according to your case), and just sample them with replacement to produce N distinct distributions. Unlike the aerial observations, these values do not go through an adjustment process.

## GHGI-based Emissions Quantification
[go back to top](#roams-methodology)

The ROAMS methodology expects that the sub-MDL emissions of midstream infrastructure is a point estimate with a confidence interval. This value is supposed to represent the total amount of emissions coming from midstream infrastructure below the minimum-detectable-level.

This value is derived as `[Total CH4 production in covered region] * [min(state-level midstream emissions rate, national midstream emissions rate)] * [Fraction of midstream emissions that are below MDL]`

Both the `Total Ch4 production in covered region` and `Fraction of midstream emissions that are below MDL` have to be more or less explicitly provided as inputs. 

The `national midstream emissions rate` is just the ratio of `[total US CH4 emitted from midstream infrastructure] / [total CH4 produced in the US]`, as estimated per the GHGI and any reliable US production dataset of your choice.

The `state-level midstream emissions rate` is just the ratio of `[state midstream CH4 emissions] / [state CH4 produced]`. The denominator can be based on whatever production data you have access to, while the numerator is computed as `[state CH4 emissions] * [fraction of national CH4 emissions that come from midstream]`, where both values can come from available GHGI data.

## Combining Production Distributions
[go back to top](#roams-methodology)

By the end of the sampling procedure for both aerially measured and simulated production infrastructure, there are N distinct aerial distributions and simulated distributions. Each should be an estimate, for each well in the covered region, of an amount of emissions. By the nature of aerial observation, each of these N distributions of aerial samples will be mostly 0s, followed by a relatively small amount of large emissions values. Each of the N distributions of simulated emissions values will be a list of more homogenous and smaller emissions values.

For each of the N sub-MDL and aerial distributions, the method prescribes the same treatment. The first step is to find a [transition point](#transition-point), which is an emissions value above which the aerial distribution dominates, and below which the simulated distribution dominates. After doing this computation, the combination is easy:

1. Define the result, initially, as just a copy of the aerially sampled and adjusted values for this iteration
2. Get a list of all the simulated values below the transition point
3. Replace all values in the result (from 1.) that are below the transition point with a sample (with replacement) of values from (2.)
    * There is no defined behavior when the list of values from (2.) is smaller than the amount of infrastructure whose estimated emissions are below the transition point

### Transition Point

The goal of the transition point calculation is to produce an emissions value at which the aerial emissions distribution is larger than the simulated emissions distribution. The inputs to the transition point calculation are four separate lists:

* The simulated emissions values
    * These are the "x" values of the cumulative simulated emissions distribution plot
* The cumulative simulated emissions distribution (Amount of emissions from sources that emit at least X, where X is the simulated emissions from above)
    * These are the "y" values of the cumulative simulated emissions distribution plot
* The aerially sampled + adjusted emissions values
    * These are the "x" values of the cumulative aerial emissions distribution plot
* The cumulative aerial emissions distribution (Amount of emissions from sources that emit at least X, where X is the aerially sampled + adjusted emissions from above)
    * These are the "y" values of the cumulative aerial emissions distribution plot
    * This includes the partial detection accounting too, not just the sampled + adjusted emissions

The first step is to interpolate each cumulative distribution into the same `[5 kgh,1000 kgh]` range (interpolated at each integer emissions value). 

Next, we take a `diff()` of the cumulative distribution (redefine each value as `value - previous value`)

Then, we use a moving-average window to smooth the result. These numbers should reflect the total emissions coming from different parts of the emissions size distribution.

Lastly, we define the transition point as the least emissions value where the smoothed aerial diff() is greater than the smoothed simulated diff().

## Primary Outputs
[go back to top](#roams-methodology)

There are few concrete outputs of the ROAMS methodology, as different researchers/users may be interested in very different properties of all the resulting quantities.

But there are some outputs that are easy to derive and largely useful no matter what:

* Total estimated basin CH4 emissions = `[Total CH4 emissions of combined production distribution] + [Total midstream aerial CH4 emissions ≥ midstream transition point] + [Total estimated sub-MDL midstream CH4 emissions]`
* The fraction of basin CH4 emissions from each measurement source = `[Total CH4 emissions from estimate source] / [Total estimated basin CH4 emissions]`
* The fractional volumetric loss of CH4 in the basin = `[Total estimated basin CH4 emissions] / [Total produced CH4 in the basin]`
* The fractional energy loss of CH4 in the basin = `[Total embodied energy of basin CH4 emissions] / [Total embodied energy of all CH4 and oil produced in basin]`
    * This can be a useful alternative to volumetric loss, where for basins that almost entirely oil, the denominator of volumetric loss would be close to 0 - they report almost no NG produced.
* Average emissions size distributions and cumulative emissions distributions
    * When averaged over a collection of N sorted iterations, can provide a smooth estimate of the emissions distribution from individual sources, or a combined estimate.