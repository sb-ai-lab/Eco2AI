import os
import time
import platform
import pandas as pd
import requests
import numpy as np
import warnings
from re import sub
import json
from pkg_resources import resource_stream
import sys
from apscheduler.schedulers.background import BackgroundScheduler

from eco2ai.tools.tools_gpu import *
from eco2ai.tools.tools_cpu import *

FROM_mWATTS_TO_kWATTH = 1000*1000*3600
FROM_kWATTH_TO_MWATTH = 1000


def set_params(**params):
    """
    Sets default Tracker attributes values:
    project_name = ...
    experiment_description = ...
    file_name = ...
    """
    dictionary = dict()
    filename = resource_stream('eco2ai', 'data/config.txt').name
    for param in params:
        dictionary[param] = params[param]
    # print(dictionary)
    if "project_name" not in dictionary:
        dictionary["project_name"] = "default project name"
    if "experiment_description" not in dictionary:
        dictionary["experiment_description"] = "default experiment description"
    if "file_name" not in dictionary:
        dictionary["file_name"] = "emission.csv"
    with open(filename, 'w') as json_file:
        json_file.write(json.dumps(dictionary))
    return dictionary


def get_params():
    """
    Returns default Tracker attributes values:
    project_name = ...
    experiment_description = ...
    file_name = ...
    """
    filename = resource_stream('eco2ai', 'data/config.txt').name
    if not os.path.isfile(filename):
        with open(filename, "w"):
            pass
    with open(filename, "r") as json_file:
        if os.path.getsize(filename):
            dictionary = json.loads(json_file.read())
        else:
            dictionary = {
                "project_name": "Deafult project name",
                "experiment_description": "no experiment description",
                "file_name": "emission.csv"
                }
    return dictionary


def define_carbon_index(
    emission_level=None, 
    alpha_2_code=None
):
    carbon_index_table_name = resource_stream('eco2ai', 'data/carbon_index.csv').name
    if alpha_2_code is None:
        ip_dict = eval(requests.get("https://ipinfo.io/").content.decode('ascii'))
        country = ip_dict['country']
        region = ip_dict['region']
    else:
        country = alpha_2_code
        region = None
    if emission_level is not None:
        print((emission_level, f'({country}/{region})') if region is not None else (emission_level, f'({country})'))
        return (emission_level, f'({country}/{region})') if region is not None else (emission_level, f'({country})')
    data = pd.read_csv(carbon_index_table_name)
    result = data[data['alpha_2_code'] == country]
    if result.shape[0] < 1:
        result = data[data['country'] == 'World']
    if result.shape[0] > 1:
        if data[data['region'] == region].shape[0] > 0:
            result = data[data['region'] == region]
        else: 
            result = result[result['region'] == 'Whole country']
    result = result.values[0][-1]
    return (result, f'({country}/{region})') if region is not None else (result, f'({country})')


class Tracker:
    """
    This class calculates CO2 emissions during cpu or gpu calculations 
    In order to calculate gpu & cpu power consumption correctly you should create the 'Tracker' before any gpu or cpu usage
    For every new calculation create a new “Tracker.”

    ----------------------------------------------------------------------
    Use example:

    import eco2ai.Tracker
    tracker = eco2ai.Tracker()

    tracker.start()

    *your gpu calculations*
    
    tracker.stop()
    ----------------------------------------------------------------------
    """
    def __init__(self,
                 project_name=None,
                 experiment_description=None,
                 file_name=None,
                 measure_period=10,
                 emission_level=None,
                 alpha_2_code=None,
                 ):
        warnings.warn(
    message="""
    If you use a VPN, you may have problems with identifying your country by IP.
    It is recommended to disable VPN or
    manually install the ISO-Alpha-2 code of your country during initialization of the Tracker() class.
    You can find the ISO-Alpha-2 code of your country here: https://www.iban.com/country-codes
    """
)
        self._params_dict = get_params()
        self.project_name = project_name if project_name is not None else self._params_dict["project_name"]
        self.experiment_description = experiment_description if experiment_description is not None else self._params_dict["experiment_description"]
        self.file_name = file_name if file_name is not None else self._params_dict["file_name"]
        self.get_set_params(self.project_name, self.experiment_description, self.file_name)
        if (type(measure_period) == int or type(measure_period) == float) and measure_period <= 0:
            raise ValueError("measure_period should be positive number")
        self._measure_period = measure_period
        self._emission_level, self._country = define_carbon_index(emission_level, alpha_2_code)
        self._scheduler = BackgroundScheduler(job_defaults={'max_instances': 4}, misfire_grace_time=None)
        self._start_time = None
        self._cpu = None
        self._gpu = None
        self._consumption = 0
        self._os = platform.system()
        if self._os == "Darwin":
            self._os = "MacOS"
        # self._mode == "first_time" means that CO2 emissions is written to .csv file first time
        # self._mode == "runtime" means that CO2 emissions is written to file periodically during runtime 
        # self._mode == "shut down" means that CO2 tracker is stopped
        self._mode = "first_time"
    
    
    def get_set_params(self, project_name, experiment_description, file_name):
        dictionary = dict()
        if project_name is not None:
            dictionary["project_name"] = project_name
        else: 
            dictionary["project_name"] = "default project name"
        if experiment_description is not None:
            dictionary["experiment_description"] = experiment_description
        else:
            dictionary["experiment_description"] = "default experiment description"
        if file_name is not None:
            dictionary["file_name"] = file_name
        else:
            dictionary["file_name"] = "emission.csv"
        set_params(**dictionary)


    def consumption(self):
        return self._consumption
    

    def emission_level(self):
        return self._emission_level
    

    def measure_period(self):
        return self._measure_period


    def _write_to_csv(self):
        # if user used older versions, it may be needed to upgrade his .csv file
        # but after all, such verification should be deleted
        # self.check_for_older_versions()
        duration = time.time() - self._start_time
        emissions = self._consumption * self._emission_level / FROM_kWATTH_TO_MWATTH
        if not os.path.isfile(self.file_name):
            with open(self.file_name, 'w') as file:
                file.write("project_name,experiment_description(model type etc.),start_time,duration(s),power_consumption(kWTh),CO2_emissions(kg),CPU_name,GPU_name,OS,region/country\n")
                file.write(f"\"{self.project_name}\",\"{self.experiment_description}\",{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._start_time))},{duration},{self._consumption},{emissions},\"{self._cpu.name()}/{self._cpu.cpu_num()} device(s), TDP:{self._cpu.tdp()}\",{self._gpu.name()} {self._gpu.gpu_num()} device(s),{self._os},{self._country}\n")
        else:
            with open(self.file_name, "a") as file:
                file.write(f"\"{self.project_name}\",\"{self.experiment_description}\",{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self._start_time))},{duration},{self._consumption},{emissions},\"{self._cpu.name()}/{self._cpu.cpu_num()} device(s), TDP:{self._cpu.tdp()}\",{self._gpu.name()} {self._gpu.gpu_num()} device(s),{self._os},{self._country}\n")
        if self._mode == "runtime":
            self._merge_CO2_emissions()
        self._mode = "runtime"


    # merges 2 CO2 emissions calculations together
    def _merge_CO2_emissions(self,):
        # it should be eliminated in future versions. 
        try:
            dataframe = pd.read_csv(self.file_name)
        except:
            dataframe = pd.read_csv(self.file_name, sep='\t')
        columns, values = dataframe.columns, dataframe.values
        row = values[-2]
        row[3:6] += values[-1][3:6]
        values = np.concatenate((values[:-2], row.reshape(1, -1)))
        pd.DataFrame(values, columns=columns).to_csv(self.file_name, index=False)


    def _func_for_sched(self):
        cpu_consumption = self._cpu.calculate_consumption()
        if self._gpu.is_gpu_available:
            gpu_consumption = self._gpu.calculate_consumption()
        else:
            gpu_consumption = 0
        self._consumption += cpu_consumption
        self._consumption += gpu_consumption
        self._write_to_csv()
        self._consumption = 0
        self._start_time = time.time()
        if self._mode == "shut down":
            self._scheduler.remove_job("job")
            self._scheduler.shutdown()


    def start(self):
        if self._start_time is not None:
            try:
                self._scheduler.remove_job("job")
                self._scheduler.shutdown()
            except:
                pass
        self._cpu = CPU()
        self._gpu = GPU()
        self._start_time = time.time()
        self._scheduler.add_job(self._func_for_sched, "interval", seconds=self._measure_period, id="job")
        self._scheduler.start()
        # print(self._cpu.name())
        # print(self._gpu.name())


    def stop(self, ):
        if self._start_time is None:
            raise Exception("Need to first start the tracker by running tracker.start()")
        self._scheduler.remove_job("job")
        self._scheduler.shutdown()

        self._func_for_sched() 
        self._write_to_csv()
        self._mode = "shut down"


def available_devices():
    '''
    Prints number of all available and seeable cpu & gpu devices
    '''
    all_available_cpu()
    all_available_gpu()
    # need to add RAM


def track(func):
    """
    decorator, that modifies function by creating Tracker object and 
    running Tracker.start() in the function beginning and 
    running Tracker.stop() in the end of function
    """
    def inner(*args):
        tracker = Tracker()
        tracker.start()
        # print(args)
        try:
            returned = func(*args)
        except Exception:
            tracker.stop()
            del tracker
            raise Exception
        tracker.stop()
        del tracker
        return returned
    return inner


class FileDoesNotExists(Exception):
    pass


class NotNeededExtension(Exception):
    pass


def calculate_money(
    kwh_price,
    filename='emisison.csv',
    project_name='all',
    experiment_description=None
):
    if not os.path.exists(filename):
        raise FileDoesNotExists(f'File \'{filename}\' does not exist')
    if not filename.endswith('.csv'):
        raise NotNeededExtension('File need to be with extension \'.csv\'')
    df = pd.read_csv(filename)
    if project_name != 'all':
        df = df[df['project_name'] == project_name]
    if experiment_description is not None:
        df = df[df['experiment_description(model type etc.)'] == experiment_description]
    if df.shape[0] == 0:
        warnings.warn(
            '''
            There is no any projects with your specified project_name and experiment_description arguments
            '''
        )
        
    consumption = df['power_consumption(kWTh)'].values
    consumption = consumption.sum()
    
    return consumption * kwh_price