

<img src=https://github.com/sb-ai-lab/Eco2AI/blob/main/images/photo_2022-06-14_13-02-37.jpg />


![PyPI - Downloads](https://img.shields.io/pypi/dm/eco2ai?color=brightgreen&label=PyPI%20downloads&logo=pypi&logoColor=yellow)
[![PyPI - Downloads](https://img.shields.io/badge/%20PyPI%20-link%20for%20download-brightgreen)](https://pypi.org/project/eco2ai/)
![PyPI - Downloads](https://img.shields.io/pypi/v/eco2ai?color=bright-green&label=PyPI&logo=pypi&logoColor=yellow)

# Eco2AI
Eco2AI is a python library for CO2 emission tracking. It monitors energy consumption of CPU and GPU, then estimates equivalent carbon emissions. 
Eco2AI is applicable to all python scripts, all you need is to add couple strings to your code.  All emission data and your devices info are logged into local file.  

Every single run of Tracker() accompanies with session description added into logging file including the following items:

+ project_name
+ experiment_description
+ start_time
+ duration(s)
+ power_consumption(kWTh)
+ CO2_emissions(kg)
+ CPU_name
+ GPU_name
+ OS
+ country

##  Installation
To install eco2ai library run next command:

```
pip install eco2ai
```

## Use examples

eco2ai's interface is quite simple. Here is a the most straightforward usage example:
```python

import eco2ai

tracker = eco2ai.Tracker(project_name="YourProjectName", experiment_description="training the <your model> model")

tracker.start()

<your gpu &(or) cpu calculations>

tracker.stop()
```

eco2ai also supports decorators. Once decorated function executed, emissions info will be written to the file. See example below:
```python
from eco2ai import track

@track
def train_func(model, dataset, optimizer, epochs):
    ...

train_func(your_model, your_dataset, your_optimizer, your_epochs)
```


For your convenience every time you initilize a Tracker object with your custom parameters, this settings will be saved until library is uninstalled, and then every new tracker will be created with your custom settings(if you will create new tracker with new parameters, then they will be saved instead of old ones). For example:

```python

import eco2ai

tracker = eco2ai.Tracker(
    project_name="YourProjectName", 
    experiment_description="training <your model> model",
    file_name="emission.csv"
    )

tracker.start()
<your gpu &(or) cpu calculations>
tracker.stop()

...

# now, we want to create a new tracker for new calculations
tracker = eco2ai.Tracker()
# now, it's equivelent to:
# tracker = eco2ai.Tracker(
#     project_name="YourProjectName", 
#     experiment_description="training the <your model> model",
#     file_name="emission.csv"
# )
tracker.start()
<your gpu &(or) cpu calculations>
tracker.stop()

```

You can also set parameters using set_params() function, like in the example below:

```python
from eco2ai import set_params, Tracker

set_params(
    project_name="My_default_project_name",
    experiment_description="We trained...",
    file_name="my_emission_file.csv"
)

tracker = Tracker()
# now, it's equivelent to:
# tracker = Tracker(
#     project_name="My_default_project_name",
#     experiment_description="We trained...",
#     file_name="my_emission_file.csv"
# )
tracker.start()
<your code>
tracker.stop()
```



<!-- There is [sber_emission_tracker_guide.ipynb](https://github.com/vladimir-laz/AIRIEmisisonTracker/blob/704ff88468f6ad403d69a63738888e1a3c41f59b/guide/sber_emission_tracker_guide.ipynb)  - useful jupyter notebook with more examples and notes. We highly recommend to check it out beforehand. -->
## Important note

According to climate transparency report for each kilowatt hour of electricity generated in Russia in 2020, an average of 310 g of CO2 was emitted. This constant is used in CO2 estimation by default.

In order to calculate gpu & cpu power consumption correctly you should create the 'Tracker' before any gpu or cpu usage

For every new calculation create a new “Tracker.”

# Feedback
If you had some problems while working with our tracker, please, give us a feedback comments in [document](https://docs.google.com/spreadsheets/d/1927TwoFaW7R_IFC6-4xKG_sjlPUaYCX9vLqzrOsASB4/edit#gid=0)
