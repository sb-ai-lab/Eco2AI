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
    '''
    This class is interface for tracking cpu consumption.
    All methods are done here on the assumption that all cpu devices are of equal model.
    The CPU class is not intended for separate usage, outside the Tracker class
    '''
    def __init__(self, measure_period=0.5):
        self._cpu_dict = get_cpu_info()
        self._measure_period = measure_period
        self._name = self._cpu_dict["brand_raw"]
        self._tdp = find_tdp_value(self._name, CPU_TABLE_NAME)
        self._consumption = 0
        self._cpu_num = number_of_cpu()
        self._start = time.time()

    def tdp(self):
        return self._tdp

    def set_consumption_zero(self):
        self._consumption = 0

    def get_consumption(self):
        self.calculate_consumption()
        return self._consumption

    def get_cpu_percent(self):
        tmp_array = psutil.cpu_percent(interval=self._measure_period, percpu=True)
        percent = sum(tmp_array) / len(tmp_array)
        return percent

    def calculate_consumption(self):
        time_period = time.time() - self._start
        self._start = time.time()
        consumption = self._tdp * self.get_cpu_percent() / 100 * self._cpu_num * time_period / FROM_WATTs_TO_kWATTh
        if consumption < 0:
            consumption = 0
        self._consumption += consumption
        return consumption

    def name(self,):
        return self._name

    def cpu_num(self,):
        return self._cpu_num

def all_available_cpu():
    '''
    Prints all seeable cpu devices
    All the devices should be of the same model
    '''
    try:
        cpu_dict = get_cpu_info()
        string = f"""Seeable cpu device(s):
        {cpu_dict["brand_raw"]}: {number_of_cpu()} device(s)"""
        print(string)
    except:
        print("There is no any available cpu device(s)")


def number_of_cpu():
    '''
    Returns number of cpu sockets(physical cpu processors)
    If the body of the function runs with error, number of available cpu devices will be set to 1
    '''
    operating_system = platform.system()
    result = None

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
            result = min(int(dictionary["Socket(s)"]), int(dictionary["NUMA node(s)"]))
        except:
            warnings.warn(message="\nYou probably should have installed 'util-linux' to deretmine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                          category=NoNeededLibrary)
            result = 1
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
            result = int(re.findall('- (\d)\.', processor_string)[0])
        except:
            warnings.warn(message="\nIt's impossible to deretmine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                          category=NoNeededLibrary)
            result = 1
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
            result = int(re.findall('(\d)', processor_string)[0])
        except:
            warnings.warn(message="\nIt's impossible to deretmine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                          category=NoNeededLibrary)
            result = 1
    else: 
        result = 1
    return result


def transform_cpu_name(f_string):
    '''
    Drops all the waste tokens, and words from a cpu name
    Finds patterns. Patterns include processor's family and 
    some certain specifications like 9400F in Intel Core i5-9400F
    Returns modified cpu name with patterns
    '''
    # dropping all the waste tokens and patterns:
    f_string = re.sub('(\(R\))|(®)|(™)|(\(TM\))|(@.*)|(\S*GHz\S*)|(\[.*\])|( \d-Core)|(\(.*\))', '', f_string)

    # dropping all the waste words:
    array = re.split(" ", f_string)
    for i in array[::-1]:
        if ("CPU" in i) or ("Processor" in i) or (i == ''):
            array.remove(i)
    f_string = " ".join(array)
    patterns = re.findall("(\S*\d+\S*)", f_string)
    for i in re.findall("(Ryzen Threadripper)|(Ryzen)|(EPYC)|(Athlon)|(Xeon Gold)|(Xeon Bronze)|(Xeon Silver)|(Xeon Platinum)|(Xeon)|(Core)|(Celeron)|(Atom)|(Pentium)", f_string):
        patterns += i
    patterns = list(set(patterns))
    if '' in patterns:
        patterns.remove('')
    return f_string, patterns


def find_max_tdp(elements):
    '''
    Takes cpu names as input
    Returns cpu with maximum TDP value
    '''
    # finds and returns element with maximum TDP
    if len(elements) == 1:
        return float(elements[0][1])

    max_value = 0
    for index in range(len(elements)):
        if float(elements[index][1]) > max_value:
            max_value = float(elements[index][1])
    return max_value

def get_patterns(cpu_name):
    """
    Finds patterns. Patterns include processor's family and 
    some certain specifications like 9400F in Intel Core i5-9400F
    Returns modified cpu name with patterns
    """
    array = re.findall("(\S*\d+\S*)", cpu_name)
    for i in re.findall("(Ryzen Threadripper)|(Ryzen)|(EPYC)|(Athlon)|(Xeon Gold)|(Xeon Bronze)|(Xeon Silver)|(Xeon Platinum)|(Xeon)|(Core)|(Celeron)|(Atom)|(Pentium)",
                        cpu_name):
        array += i
    array = list(set(array))
    if '' in array:
        array.remove('')
    return array

# searching cpu name in cpu table
def find_tdp_value(f_string, f_table_name, constant_value=CONSTANT_CONSUMPTION):
    '''
    Takes cpu names as input
    Returns cpu TDP
    '''
    # firstly, we try to find transformed cpu name in the cpu table:
    f_table = pd.read_csv(f_table_name)
    f_string, patterns = transform_cpu_name(f_string)
    f_table = f_table[["Model", "TDP"]].values
    suitable_elements = f_table[f_table[:, 0] == f_string]
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