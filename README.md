<img src=https://github.com/sb-ai-lab/Eco2AI/blob/main/images/photo_2022-06-14_13-02-37.jpg />


![PyPI Downloads](https://img.shields.io/pypi/dm/eco2ai?color=brightgreen&label=PyPI%20downloads&logo=pypi&logoColor=yellow)
[![PyPI all Downloads](https://img.shields.io/badge/All%20PyPI%20downloads-look%20in%20Colab-brightgreen)](https://colab.research.google.com/drive/1UoSHPRUHbg5B1U2x8p_ACo21X9N6n1im?authuser=1)


[![PyPI - Downloads](https://img.shields.io/badge/%20PyPI%20-link%20for%20download-brightgreen)](https://pypi.org/project/eco2ai/)
![PyPI - Downloads](https://img.shields.io/pypi/v/eco2ai?color=bright-green&label=PyPI&logo=pypi&logoColor=yellow)
[![DOI](https://img.shields.io/badge/DOI-eco2AI%20article-brightgreen)](https://link.springer.com/article/10.1134/S1064562422060230)
[![telegram support](https://img.shields.io/twitter/url?label=eco2ai%20support&logo=telegram&style=social&url=https%3A%2F%2Ft.me%2F%2BjsaoAgioprQ4Zjk6)](https://t.me/eco2ai)

# Eco2AI

+ [About Eco2AI :clipboard:](#1)
+ [Installation :wrench:](#2)
+ [Use examples :computer:](#3)
+ [Important note :blue_book:](#4)
+ [Citing](#5)
+ [Feedback :envelope:](#6) 





## About Eco2AI :clipboard: <a name="1"></a> 

<img src=https://github.com/sb-ai-lab/Eco2AI/blob/main/images/eco2ai_logo_cut.jpg />

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
To install the eco2AI library, run the following command:

```
pip install eco2ai
```

## Use examples <a name="3"></a> 

Example usage eco2AI [![Open In Collab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1hn0DQiKHeyXwvOOR3UEXaGsD6DqVm6b7?authuser=1)
You can also find eco2AI tutorial on youtube [![utube](https://img.shields.io/youtube/views/-fegQpA2gPg?label=eco2AI&style=social)](https://www.youtube.com/watch?v=-fegQpA2gPg&ab_channel=AIRIInstitute)

The eco2AI interface is quite simple. Here is the simplest usage example:

```python

import eco2ai

tracker = eco2ai.Tracker(project_name="YourProjectName", experiment_description="training the <your model> model")

tracker.start()

<your gpu &(or) cpu calculations>

tracker.stop()
```

The eco2AI also supports decorators. As soon as the decorated function is executed, the information about the emissions will be written to the emission.csv file:

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

# Usage of Eco2AI

An example of using the library is given in the [publication](https://arxiv.org/abs/2208.00406). It the paper we presented experiments of tracking equivalent CO<sub>2</sub> emissions using eco2AI while training [ruDALL-E](https://github.com/sberbank-ai/ru-dalle) models with with 1.3 billion ([Malevich](https://habr.com/ru/company/sberbank/blog/589673/), ruDALL-E XL 1.3B) and 12 billion parameters ([Kandinsky](https://github.com/sberbank-ai/ru-dalle), ruDALL-E XL 12B). These are [multimodal](https://arxiv.org/abs/2202.10435) pre-trained transformers that learn the conditional distribution of images with by some string of text capable of generating arbitrary images from a russian text prompt that describes the desired result.
Properly accounted carbon emissions and power consumption Malevich and Kandinsky fine-tuning Malevich and Kandinsky on the [Emojis dataset](https://arxiv.org/abs/2112.02448) is given in the table below.
   
   | **Model** | **Train time** | **Power, kWh** | **CO<sub>2</sub>, kg** | **GPU** | **CPU** | **Batch Size** |
   |:----------|:-------------:|:------:| :-----: |:-----:|:------:|:------:|
   | **Malevich**| 4h 19m | 1.37 | **0.33** | A100 Graphics, 1 | AMD EPYC 7742 64-Core | 4 |
   | **Kandinsky** | 9h 45m | 24.50 | **5.89** | A100 Graphics, 8 | AMD EPYC 7742 64-Core | 12 |

Also we presented results for training of Malevich with optimized variation of [GELU](https://arxiv.org/abs/1606.08415) activation function. Training of the Malevich with the [8-bit version of GELU](https://arxiv.org/abs/2110.02861) allows us to spent about 10\% less energy and, consequently, produce less equivalent CO<sub>2</sub> emissions.

# Citing Eco2AI
[![DOI](https://img.shields.io/badge/DOI-eco2AI%20article-brightgreen)](https://link.springer.com/article/10.1134/S1064562422060230)

The Eco2AI is licensed under a [Apache licence 2.0](https://www.apache.org/licenses/LICENSE-2.0).

Please consider citing the following paper in any research manuscript using the Eco2AI library:

```
@article{eco2AI,
title={eco2AI: Carbon Emissions Tracking of Machine Learning Models as the First Step Towards Sustainable AI},
url={https://doi.org/10.1134/S1064562422060230}, DOI={10.1134/S1064562422060230},
journal={Doklady Mathematics},
author={Budennyy, S. A. and Lazarev, V. D. and Zakharenko, N. N. and Korovin, A. N. and Plosskaya, O. A. and Dimitrov, D. V. and Akhripkin, V. S. and Pavlov, I. V. and Oseledets, I. V. and Barsola, I. S. and Egorov, I. V. and Kosterina, A. A. and Zhukov, L. E.}, year={2023}, month=jan, language={en}}
```

## In collaboration with
[<img src="https://github.com/sb-ai-lab/Eco2AI/blob/main/images/AIRI%20-%20Full%20logo%20(2).png" width="200"/>](https://airi.net/)
