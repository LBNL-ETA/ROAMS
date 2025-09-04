# Use Cases
[Back to README](/README.md)

This part of the docs is intended to describe different ways to use the codebase and change behavior locally for your own purposes. As such it's intended to be dynamic, and change as researchers find new ways to make use of it.

Currently, the only known use case is to run a ROAMS model for the purpose of replication or validation. But there are several imagined use cases too, which may help researchers adopt the code to their own purposes.

* [Running a ROAMS Model with an input file](#running-the-roams-model-with-an-input-file) (the known use case)
* [Running a ROAMS Model](#running-the-roams-model) (the known use case)
* [Using a custom ROAMS Model](#using-a-custom-roams-model)
* [Adding or altering input behavior](#adding-inputs-changing-behavior)
* [Making new or altered outputs](#making-new-or-altered-outputs)

## Running the ROAMS Model with an input file
[Back to the top](#use-cases)

As shown in the README, the simplest use case is to run an instance of the `ROAMSModel` with an input file:

```python3
from roams.model import ROAMSModel

if __name__=="__main__":
    m = ROAMSModel("path/to/my/input.json")
    m.perform_analysis()
```

This will execute the ROAMS methodology with the given input specification, and so corresponds to the estimation of emissions in only one survey region.

## Running the ROAMS Model with a dictionary
[Back to the top](#use-cases)

It's also possible to pass a dictionary as input to the `ROAMSModel`. This can be helpful if values have to dynamically in code. It's also helpful because you can define new functions for the `ROAMSModel` to use at distinct parts of the methodology.

```python3
from roams.model import ROAMSModel

# You could dynamically compute input quantities
production_value = compute_production_value()

# You can define custom functions that aren't contained in the codebase
# E.g. a difference application of noise to sampled & adjusted aerial emissions
def uniform_noise(emissions_array):
    noise = np.random.uniform(0,2,emissions_array.shape)
    return emissions_array * noise

# dictionary of inputs
my_input = {
    ...
    "noise_fn": uniform_noise,
    ...
    "total_covered_ngprod_mcfd" : production_value,
}

if __name__=="__main__":
    m = ROAMSModel(my_input) # You can pass this dictionary instead of an input file
    m.perform_analysis()
```

## Using a custom ROAMS Model
[Back to the top](#use-cases)

The `ROAMSModel` implements a very specific methodology for sampling and combining distributions. It's totally possible a different researcher may want to modify only one or two elements of this behavior, and keep the rest. The suggested approach is to take advantage of inheritability, and avoid at all costs copying & pasting significant parts of the original code (though this may be unavoidable in some cases).

For example, suppose a researcher has simulated well emissions data they've carefully tailored to the wells in this region. They don't want it to be sampled, they just want it to be used as-is in each monte-carlo iteration. They will choose to alter how the simulated sample is generated in a new child class of `ROAMSModel` (note this wouldn't remove randomness completely, see [how production emissions distributions are combined](/docs/methodology.md#combining-production-distributions)). They can define a new class that differs only in the method that creates the simulated sample. All of the rest of the logical execution will remain the same.

```python3
from roams.model import ROAMSModel 

class FixedSimROAMSModel(ROAMSModel):
  
  # Define a new `make_simulated_sample` method that overwrites parent method behavior
  def make_simulated_sample(self) -> np.ndarray:
      
      # Make sure simulated results are the right length
      if len(self.cfg.prodSimResults.simulated_emissions)!=self.cfg.num_wells_to_simulate:
          raise IndexError(f"Simulated Emissions should have length {self.cfg.num_wells_to_simulate}")
      
      # Instead of sampling with replacement, repeat the given emissions values
      fixed_sample = np.tile(
          self.cfg.prodSimResults.simulated_emissions,
          (self.cfg.n_mc_samples,1)
      ).T
      
      # Sort it
      fixed_sample.sort(axis=0)
      
      # Return this sample
      return fixed_sample


if __name__=="__main__":
  r = FixedSimROAMSModel("the/input/file.json")
  r.perform_analysis()
```

Similarly, you can call `super().<methodname>()` from within a method to try to modify the result of normal execution after-the fact, or slightly alter the context before normal execution. This is a desirable pattern because as the `ROAMSModel` updates, the custom class will also implicitly adopt updated behavior too.

If you've created a modification you believe to be substantially valuable as an option for other researchers, or perhaps is even preferable to the existing methodology, you are encouraged to follow the [contribution guidelines](/README.md#contributing) to bring your changes into the main code branch for everyone to more easily use.

## Adding inputs, changing behavior
[Back to the top](#use-cases)

Data formats and standards are expected to change over time as the ROAMS codebase is used for different projects. As such, it's expected that the input classes and/or input file will have to be modified to accommodate this new information.

### Input File Additions

You can trivially add information to the input file without altering the code. Unrecognized {key : value} pairs in the input file will be saved as attributes like every other pair, but will result in a warning. For example:

```python3
from roams.model import ROAMSModel

# A class that adds a value specified in the input to the simulated sample, that is neither required nor has default behavior
class MySpecialROAMSModel(ROAMSModel):

    def make_simulated_sample(self):
        sample = super().make_simulated_sample()
        sample += self.cfg.my_special_value
        return sample

if __name__=="__main__":
    my_input = {
        ... # regular content of an input dictionary
        "my_special_value" : 10, # Will end up adding 10 everywhere to the otherwise normally-sampled simulated data
    }

    r = MySpecialROAMSModel(my_input) # <- will log a warning because it suspects "my_special_value" won't be used
    r.perform_analysis()
```

### Input File Parsing Behavior

Just like the `ROAMSModel` itself, the `ROAMSConfig` (and each individual input class) is intended to be inheritable for users who need to get around or modify input parsing behavior for their work. Because the `ROAMSConfig` is passed as a keyword argument to the `ROAMSModel` for use in parsing a given input file, you can switch it out for your own class however you'd like. For example:

```python3
from roams.model import ROAMSModel
from roams.input import ROAMSConfig, _DEFAULT_CONFIGS

new_defaults = _DEFAULT_CONFIGS.copy()
new_defaults["my_special_value"] = 10 # Add a new default for my new input

# A ROAMSConfig class that will use the updated defaults
class myROAMSConfig(ROAMSConfig):
    def __init__(self,*args,_def = new_defaults,**kwargs)

if __name__=="__main__":
    
    # Direct the ROAMSModel to use your altered input class (although the it won't use this new assigned default)
    # Unless your input file has "my_special_value", it should log that it was missing and it used the default.
    r = ROAMSModel("path/to/input.json",parser=myROAMSConfig) 
    r.perform_analysis()
```

Part of the `__init__` of `ROAMSConfig` are a collection of keyword arguments (e.g. `surveyClass = AerialSurveyData`) with defaults pointing to each data input class. With the same kind of inheritance pattern, you can define new input classes, pass them to an inherited `ROAMSConfig`, and give the result to a `ROAMSModel` during instantiation. The hope is that this will remove fundamental blockers for users to be able to use wildly different sets of data, or perhaps completely ignore irrelevant parts of the `ROAMSModel`.

If you've created an input modification you believe to be substantially valuable as an option for other researchers, or perhaps is even preferable to the existing methodology, you are encouraged to follow the [contribution guidelines](/README.md#contributing) to bring your changes into the main code branch for everyone to more easily use.

## Making new or altered outputs
[Back to the top](#use-cases)

Through inheritance you can also adapt the output behavior. 

```python3
import pandas as pd
from matplotlib import pyplot as plt

from roams.model import ROAMSModel

class MoreOutputROAMSModel(ROAMSModel):
    
    # This will create all the normal tables by calling `super()...` , but add another table to table_outputs that will appear as "My Table.csv" when saved
    def make_tabular_outputs(self):
        super().make_tabular_outputs()
        
        # The index of the tables will not be saved.
        self.table_outputs["My Table"] = pd.DataFrame({"A":[1,2,3]})

    # This will replace the parent plotting behavior, and instead make a meaningless plot saved as "made up plot.svg"
    def gen_plots(self):
        plt.plot([1,2,3],[4,5,6])
        plt.ylabel("Values (unit)")
        plt.grid(True)
        plt.savefig(os.path.join(self.outfolder, "made up plot.svg"))

if __name__=="__main__":
    r = MoreOutputROAMSModel("path/to/input.json")
    r.perform_analysis()
```

If you've created an output modification you believe to be substantially valuable as an option for other researchers, or perhaps is even preferable to the existing methodology, you are encouraged to follow the [contribution guidelines](/README.md#contributing) to bring your changes into the main code branch for everyone to more easily use.