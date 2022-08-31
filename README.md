<img src=https://github.com/sb-ai-lab/Eco2AI/blob/main/images/photo_2022-06-14_13-02-37.jpg />


![PyPI Downloads](https://img.shields.io/pypi/dm/eco2ai?color=brightgreen&label=PyPI%20downloads&logo=pypi&logoColor=yellow)
[![PyPI all Downloads](https://img.shields.io/badge/All%20PyPI%20downloads-look%20in%20Colab-brightgreen)](https://colab.research.google.com/drive/1BQu8ju01zYXrfW61x3oBn0wnSoUxP6kc?usp=sharing)


[![PyPI - Downloads](https://img.shields.io/badge/%20PyPI%20-link%20for%20download-brightgreen)](https://pypi.org/project/eco2ai/)
![PyPI - Downloads](https://img.shields.io/pypi/v/eco2ai?color=bright-green&label=PyPI&logo=pypi&logoColor=yellow)
[![DOI](https://img.shields.io/badge/DOI-eco2AI%20article-brightgreen)](https://arxiv.org/abs/2208.00406)
[![telegram support](https://img.shields.io/twitter/url?label=eco2ai%20support&logo=telegram&style=social&url=https%3A%2F%2Ft.me%2F%2BjsaoAgioprQ4Zjk6)](https://t.me/eco2ai)

# Eco2AI

+ [About Eco2AI :clipboard:](#1)
+ [Installation :wrench:](#2)
+ [Use examples :computer:](#3)
+ [Important note :blue_book:](#4)
+ [Citing](#5)
+ [Feedback :envelope:](#6)





## About Eco2AI :clipboard: <a name="1"></a> 
The Eco2AI is a python library for CO<sub>2</sub> emission tracking. It monitors energy consumption of CPU & GPU devices and estimates equivalent carbon emissions taking into account the regional emission coefficient. 
The Eco2AI is applicable to all python scripts and all you need is to add the couple of strings to your code. All emissions data and information about your devices are recorded in a local file. 

Every single run of Tracker() accompanies by a session description added to the log file, including the following elements:
                              

+ project_name
+ experiment_description
+ start_time
+ duration(s)
+ power_consumption(kWTh)
+ CO<sub>2</sub>_emissions(kg)
+ CPU_name
+ GPU_name
+ OS
+ country

##  Installation <a name="2"></a> 
To install the eco2ai library, run the following command:

```
pip install eco2ai
```

## Use examples <a name="3"></a> 

Example usage eco2ai [![Open In Collab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1GQ5pI01iv7GJB-A9v9g7QX2yij3n_wNB?usp=sharing)

Example usage eco2ai [![Open In Collab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1GQ5pI01iv7GJB-A9v9g7QX2yij3n_wNB?usp=sharing)

The eco2ai interface is quite simple. Here is the simplest usage example:

```python

import eco2ai

tracker = eco2ai.Tracker(project_name="YourProjectName", experiment_description="training the <your model> model")

tracker.start()

<your gpu &(or) cpu calculations>

tracker.stop()
```

The eco2ai also supports decorators. As soon as the decorated function is executed, the information about the emissions will be written to the emission.csv file:

```python
from eco2ai import track

@track
def train_func(model, dataset, optimizer, epochs):
    ...

train_func(your_model, your_dataset, your_optimizer, your_epochs)
```

For your convenience, every time you instantiate the Tracker object with your custom parameters, these settings will be saved until the library is deleted. Each new tracker will be created with your custom settings (if you create a tracker with new parameters, they will be saved instead of the old ones). For example:

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
# now, it's equivalent to:
# tracker = eco2ai.Tracker(
#     project_name="YourProjectName", 
#     experiment_description="training the <your model> model",
#     file_name="emission.csv"
# )
tracker.start()
<your gpu &(or) cpu calculations>
tracker.stop()

```

You can also set parameters using the set_params() function, as in the example below:

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
## Important note <a name="4"></a> 

If for some reasons it is not possible to define country, then emission coefficient is set to 436.529kg/MWh, which is global average.
[Global Electricity Review](https://ember-climate.org/insights/research/global-electricity-review-2022/#supporting-material-downloads)

For proper calculation of gpu and cpu power consumption, you should create a "Tracker" before any gpu or CPU usage.

Create a new “Tracker” for every new calculation.

# Citing Eco2AI
[![DOI](https://img.shields.io/badge/DOI-eco2AI%20article-brightgreen)](https://arxiv.org/abs/2208.00406)

The Eco2AI is licensed under a [Apache licence 2.0](https://www.apache.org/licenses/LICENSE-2.0).

Please consider citing the following paper in any research manuscript using the Eco2AI library:

```
@article{eco2ai_lib,
    author = {Semen Budennyy*, Vladimir Lazarev, Nikita Zakharenko, Alexey Korovin, Olga Plosskaya, Denis Dimitrov, Vladimir Arkhipkin, Ivan Barsola, Ilya Egorov, Aleksandra Kosterina, Leonid Zhukov
    
},
    title = {eco2AI: open-source library for carbon emission tracking of machine learning models},
    year = {2022},
    journal={arXiv preprint arXiv:2208.00406},
}
```


## Feedback :envelope:<a name="6"></a> 

If you have any problems working with our tracker, please make comments on [document](https://docs.google.com/spreadsheets/d/1927TwoFaW7R_IFC6-4xKG_sjlPUaYCX9vLqzrOsASB4/edit#gid=0)

## In collaboration with
[<img src="https://github.com/sb-ai-lab/Eco2AI/blob/main/images/AIRI%20-%20Full%20logo%20(2).png" width="200"/>](https://airi.net/)
