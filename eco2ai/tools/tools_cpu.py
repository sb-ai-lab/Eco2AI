from cpuinfo import get_cpu_info
import psutil
import time
import re
import os
import pandas as pd
import numpy as np
import warnings
import platform
from pkg_resources import resource_stream


CONSTANT_CONSUMPTION = 100.1
FROM_WATTs_TO_kWATTh = 1000*3600
NUM_CALCULATION = 200
CPU_TABLE_NAME = resource_stream('eco2ai', 'data/cpu_names.csv').name

class NoCPUinTableWarning(Warning):
    pass

class NoNeededLibrary(Warning):
    pass

class CPU():
    """
        This class is the interface for tracking CPU power consumption.
        All methods are done here on the assumption that all cpu devices are of equal model.
        The CPU class is not intended for separate usage, outside the Tracker class

    """
    def __init__(self, measure_period=10):
        """
            This class method initializes CPU object.
            Creates fields of class object. All the fields are private variables

            Parameters
            ----------
            measure_period: float
                Period of power consumption measurements in seconds.
                The more period the more time between measurements
                The default is 10

            Returns
            -------
            CPU: CPU
                Object of class CPU with specified parameters

        """
        self._cpu_dict = get_cpu_info()
        self._measure_period = measure_period
        self._name = self._cpu_dict["brand_raw"]
        self._tdp = find_tdp_value(self._name, CPU_TABLE_NAME)
        self._consumption = 0
        self._cpu_num = number_of_cpu()
        self._start = time.time()

    def tdp(self):
        """
            This class method returns TDP value of process.

            Parameters
            ----------
            No parameters

            Returns
            -------
            self._tdp : float
                TDP value of the CPU

        """
        return self._tdp

    def set_consumption_zero(self):
        """
            This class method sets CPU consumtion to zero.

            Parameters
            ----------
            No parameters

            Returns
            -------
            No returns

        """
        self._consumption = 0

    def get_consumption(self):
        """
            This class method returns CPU power consupmtion amount.

            Parameters
            ----------
            No parameters

            Returns
            -------
            self._consumption: float
                CPU power consumption

        """
        self.calculate_consumption()
        return self._consumption

    def get_cpu_percent(self,):
        """
            This class method calculates CPU utilization
            taking into acount only python processes. 
            Method of calculating CPU utilization depends on operating system: 
            Windows, MacOS or Linux are only supported operating systems

            Parameters
            ----------
            No parameters
            
            Returns
            -------
            cpu_percent: float
                cpu utilization fraction. 'cpu_percent' in [0, 1]. 
                The current cpu utilization from python processes
        
        """
        operating_system = platform.system()
        os_dict = {
            'Linux': get_cpu_percent_linux,
            'Windows': get_cpu_percent_windows,
            'Darwin': get_cpu_percent_mac_os
        }
        cpu_percent = os_dict[operating_system]()
        return cpu_percent

    def calculate_consumption(self):
        """
            This class method calculates CPU power consumption.
            
            Parameters
            ----------
            No parameters
            
            Returns
            -------
            consumption: float
                CPU power consumption
        
        """
        time_period = time.time() - self._start
        self._start = time.time()
        consumption = self._tdp * self.get_cpu_percent() * self._cpu_num * time_period / FROM_WATTs_TO_kWATTh
        if consumption < 0:
            consumption = 0
        self._consumption += consumption
        return consumption

    def name(self,):
        return self._name

    def cpu_num(self,):
        return self._cpu_num
    

def all_available_cpu():
    """
        This function prints all seeable CPU devices
        All the CPU devices are intended to be of the same model
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        No returns

    """
    try:
        cpu_dict = get_cpu_info()
        string = f"""Seeable cpu device(s):
        {cpu_dict["brand_raw"]}: {number_of_cpu()} device(s)"""
        print(string)
    except:
        print("There is no any available cpu device(s)")


def number_of_cpu():
    """
        This function returns number of CPU sockets(physical CPU processors)
        If the body of the function runs with error, number of available cpu devices will be set to 1
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        cpu_num: int
            Number of CPU sockets(physical CPU processors)

    """
    operating_system = platform.system()
    cpu_num = None

    if operating_system == "Linux":
        try:
            # running terminal command, getting output
            string = os.popen("lscpu")
            output = string.read()
            output
            # dictionary creation
            dictionary = dict()
            for i in output.split('\n'):
                tmp = i.split(':')
                if len(tmp) == 2:
                    dictionary[tmp[0]] = tmp[1]
            cpu_num = min(int(dictionary["Socket(s)"]), int(dictionary["NUMA node(s)"]))
        except:
            warnings.warn(message="\nYou probably should have installed 'util-linux' to deretmine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                          category=NoNeededLibrary)
            cpu_num = 1
    elif operating_system == "Windows":
        try:
            # running cmd command, getting output
            string = os.popen("systeminfo")
            output = string.read()
            output
            # dictionary creation
            dictionary = dict()
            for i in output.split('\n'):
                tmp = i.split(':')
                if len(tmp) == 2:
                    dictionary[tmp[0]] = tmp[1]
            processor_string = 'something'
            if 'Processor(s)' in dictionary:
                processor_string = dictionary['Processor(s)']
            if 'Џа®жҐбб®а(л)' in dictionary:
                processor_string = dictionary['Џа®жҐбб®а(л)']
            if 'Процессор(ы)' in dictionary:
                processor_string = dictionary['Процессор(ы)']
            cpu_num = int(re.findall('- (\d)\.', processor_string)[0])
        except:
            warnings.warn(message="\nIt's impossible to deretmine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                          category=NoNeededLibrary)
            cpu_num = 1
    elif operating_system == "Darwin":
        try:
            # running terminal command, getting output
            string = os.popen("sysctl -a| sort | grep cpu")
            output = string.read()
            output
            # dictionary creation
            dictionary = dict()
            for i in output.split('\n'):
                tmp = i.split(':')
                if len(tmp) == 2:
                    dictionary[tmp[0]] = tmp[1]
            processor_string = 'something'
            if 'hw.cpu64bit_capable' in dictionary:
                processor_string = dictionary['hw.cpu64bit_capable']
            else:
                pass
            cpu_num = int(re.findall('(\d)', processor_string)[0])
        except:
            warnings.warn(message="\nIt's impossible to deretmine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                          category=NoNeededLibrary)
            cpu_num = 1
    else: 
        cpu_num = 1
    return cpu_num


def transform_cpu_name(cpu_name):
    """
        This function drops all the waste tokens, and words from a cpu name
        It finds patterns. Patterns include processor's family and 
        some certain specifications like 9400F in Intel Core i5-9400F
        
        Parameters
        ----------
        cpu_name: str
            A string, containing CPU name, taken from psutil library
        
        Returns
        -------
        cpu_name: str
            Modified CPU name, containing patterns only
        patterns: list of str
            Array with all the patterns

    """
    # dropping all the waste tokens and patterns:
    cpu_name = re.sub('(\(R\))|(®)|(™)|(\(TM\))|(@.*)|(\S*GHz\S*)|(\[.*\])|( \d-Core)|(\(.*\))', '', cpu_name)

    # dropping all the waste words:
    array = re.split(" ", cpu_name)
    for i in array[::-1]:
        if ("CPU" in i) or ("Processor" in i) or (i == ''):
            array.remove(i)
    cpu_name = " ".join(array)
    patterns = re.findall("(\S*\d+\S*)", cpu_name)
    for i in re.findall(
        "(Ryzen Threadripper)|(Ryzen)|(EPYC)|(Athlon)|(Xeon Gold)|(Xeon Bronze)|(Xeon Silver)|(Xeon Platinum)|(Xeon)|(Core)|(Celeron)|(Atom)|(Pentium)", 
        cpu_name
        ):
        patterns += i
    patterns = list(set(patterns))
    if '' in patterns:
        patterns.remove('')
    return cpu_name, patterns


def get_patterns(cpu_name):
    """
        This function finds patterns. Patterns include processor's family and 
        some certain specifications like 9400F in Intel Core i5-9400F
        Returns modified cpu name with patterns
        
        Parameters
        ----------
        cpu_name: str
            A string, containing CPU name, taken from psutil library
        
        Returns
        -------
        patterns: list of strings
            Array with all the patterns

    """
    patterns = re.findall("(\S*\d+\S*)", cpu_name)
    for i in re.findall(
        "(Ryzen Threadripper)|(Ryzen)|(EPYC)|(Athlon)|(Xeon Gold)|(Xeon Bronze)|(Xeon Silver)|(Xeon Platinum)|(Xeon)|(Core)|(Celeron)|(Atom)|(Pentium)",
        cpu_name
        ):
        patterns += i
    patterns = list(set(patterns))
    if '' in patterns:
        patterns.remove('')
    return patterns


def find_max_tdp(elements):
    """
        This function finds and returns element with maximum TDP
        
        Parameters
        ----------
        elements: list
            Array of arrays of two strings. 
            Where the first one is CPU name and the second one is CPU TDP
        
        Returns
        -------
        max_value: float
            The maximum TDP value

    """
    # finds and returns element with maximum TDP
    if len(elements) == 1:
        return float(elements[0][1])

    max_value = 0
    for index in range(len(elements)):
        if float(elements[index][1]) > max_value:
            max_value = float(elements[index][1])
    return max_value


# searching cpu name in cpu table
def find_tdp_value(cpu_name, f_table_name, constant_value=CONSTANT_CONSUMPTION):
    """
        This function finds and returns TDP of user CPU device.
        
        Parameters
        ----------
        cpu_name: str
            Name of user CPU device, taken from psutil library

        f_table_name: str
            A file name of CPU TDP values Database

        constant_value: constant_value
            The value, that is assigned to CPU TDP if 
            user CPU device is not found in CPU TDP database
            The default is CONSTANT_CONSUMPTION(a global value, initialized in the beginning of the file)
        
        Returns
        -------
        CPU TDP: float
            TDP of user CPU device

    """
    # firstly, we try to find transformed cpu name in the cpu table:
    f_table = pd.read_csv(f_table_name)
    cpu_name, patterns = transform_cpu_name(cpu_name)
    f_table = f_table[["Model", "TDP"]].values
    suitable_elements = f_table[f_table[:, 0] == cpu_name]
    if suitable_elements.shape[0] > 0:
        # if there are more than one suitable elements, return one with maximum TDP value
        return find_max_tdp(suitable_elements)
    # secondly, if needed element isn't found in the table,
    # then we try to find patterns in cpu names and return suitable values:
    # if there is no any patterns in cpu name, we simply return constant consumption value
    if len(patterns) == 0:
        warnings.warn(message="\n\nYour CPU device is not found in our database\nCPU TDP is set to constant value 100\n", 
                      category=NoCPUinTableWarning)
        return constant_value
    # appending to array all suitable for at least one of the patterns elements
    suitable_elements = []
    for element in f_table:
        flag = 0
        tmp_patterns = get_patterns(element[0])
        for pattern in patterns:
            if pattern in tmp_patterns:
                flag += 1
        if flag:
            # suitable_elements.append(element)
            suitable_elements.append((element, flag))

    # if there is only one suitable element, we return this element.
    # If there is no suitable elements, we return constant value
    # If there are more than one element, we check existence of elements suitable for all the patterns simultaneously.
    # If there are such elements(one or more), we return the value with maximum TDP among them.
    # If there is no, we return the value with maximum TDP among all the suitable elements
    if len(suitable_elements) == 0:
        warnings.warn(message="\n\nYour CPU device is not found in our database\nCPU TDP is set to constant value 100\n", 
                      category=NoCPUinTableWarning)
        return CONSTANT_CONSUMPTION
    elif len(suitable_elements) == 1:
        return float(suitable_elements[0][0][1])
    else:
        suitable_elements.sort(key=lambda x: x[1], reverse=True)
        max_coincidence = suitable_elements[0][1]

        tmp_elements = []
        for element in suitable_elements:
            if element[1] == max_coincidence:
                tmp_elements.append(element[0])
        return find_max_tdp(tmp_elements)



def get_cpu_percent_mac_os():
    """
        This function calculates CPU utlization on MacOS.
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        cpu_percent: float
            CPU utilization fraction. 'cpu_percent' in [0, 1]. 

    """
    cpu_num = psutil.cpu_count()
    current_pid = os.getpid()
    cpu_percent = 0
    strings = os.popen('top -stats "command,cpu,pgrp" -l 2| grep -E "(python)|(%CPU)"').read().split('\n')
    strings.pop()
    strings = strings[int(len(strings) / 2) + 1:]
    for index in range(len(strings)):
        if int(strings[index].split()[-1]) == current_pid:
            cpu_percent = float(strings[index].split()[1])
    return cpu_percent / cpu_num / 100


def get_cpu_percent_linux():
    """
        This function calculates CPU utlization on Linux.
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        cpu_percent: float
            CPU utilization fraction. 'cpu_percent' in [0, 1]. 

    """
    cpu_num = psutil.cpu_count()
    current_pid = os.getpid()
    strings = os.popen('top -b -n 1 | grep -E -w -i "python.*|jupyter.*|COMMAND"').read().split('\n')
    strings.pop()
    index_cpu = strings[0].split().index('%CPU')
    for index, string in enumerate(strings[1:]):
        if int(string.split()[0]) == current_pid:
            cpu_percent = float(string.split()[index_cpu].replace(',', '.'))
            break
    return cpu_percent / cpu_num / 100


def get_cpu_percent_windows():
    """
        This function calculates CPU utlization on Windows.
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        cpu_percent: float
            CPU utilization fraction. 'cpu_percent' in [0, 1]. 

    """
    current_pid = os.getpid()
    cpu_percent = 0
    list_of_all_processes = []
    #Iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            pinfo = proc.as_dict(attrs=['name', 'cpu_percent', 'pid'])
           # Check if process pid equals the current one.
            if pinfo['cpu_percent'] is not None:
                list_of_all_processes.append(pinfo['cpu_percent'])
                if pinfo['pid'] == current_pid:
                    # print(pinfo)
                    cpu_percent = pinfo['cpu_percent']
        except (psutil.NoSuchProcess, psutil.AccessDenied , psutil.ZombieProcess) :
            pass
    sum_all = sum(list_of_all_processes)
    if sum_all != 0:
        return cpu_percent / sum_all
    else:
        return 0