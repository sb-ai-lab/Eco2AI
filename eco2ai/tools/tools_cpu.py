from cpuinfo import get_cpu_info
import psutil
import time
import subprocess
import re
import os
import pandas as pd
import numpy as np
import warnings
import platform
from eco2ai.resource_path import resource_filename


CONSTANT_CONSUMPTION = 100.1
FROM_WATTs_TO_kWATTh = 1000*3600
FROM_uJOULES_TO_kWATTh = 1000 * 1000 * 3600 * 1000
RAPL_ROOT = "/sys/class/powercap/intel-rapl"
NUM_CALCULATION = 200
CPU_TABLE_NAME = resource_filename('eco2ai', 'data/cpu_names.csv')
FAMILY_PATTERN = (
    "(Core Ultra)|(Ryzen Threadripper)|(Ryzen AI)|(Ryzen)|(EPYC)|(Athlon)|"
    "(Xeon Gold)|(Xeon Bronze)|(Xeon Silver)|(Xeon Platinum)|(Xeon)|"
    "(Core)|(Celeron)|(Atom)|(Pentium)|(Snapdragon)"
)

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
    def __init__(self, cpu_processes="current", ignore_warnings=False, rapl_root=None):
        """
            This class method initializes CPU object.
            Creates fields of class object. All the fields are private variables

            Parameters
            ----------
            cpu_processes: str
                if cpu_processes == "current", then calculates CPU utilization percent only for the current running process
                if cpu_processes == "all", then calculates full CPU utilization percent(sum of all running processes)
            ignore_warnings: bool
                If True, warnings are not shown. If False, warnings are shown.

            Returns
            -------
            CPU: CPU
                Object of class CPU with specified parameters

        """
        self._ignore_warnings = ignore_warnings
        self._cpu_processes = cpu_processes
        self._cpu_dict = get_cpu_info()
        self._name = self._cpu_dict["brand_raw"]
        self._tdp = find_tdp_value(self._name, CPU_TABLE_NAME, ignore_warnings=self._ignore_warnings)
        self._consumption = 0
        self._cpu_num = number_of_cpu(self._ignore_warnings)
        self._start = time.time()
        self._operating_system = platform.system()
        self._power_method = "tdp"
        self._rapl_root = RAPL_ROOT if rapl_root is None else rapl_root
        self._last_rapl_uj = None
        self._last_process_cpu_seconds = None
        self._last_system_cpu_seconds = None


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

    def power_method_label(self):
        """
            Label of the method used by the latest calculate_consumption call.
            Before that call the label is method:tdp.
            After a sample it is method:rapl or method:tdp.
        """
        return f"method:{self._power_method}"

    def set_consumption_zero(self):
        """
            This class method sets CPU consumption to zero.

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
            This class method returns CPU power consumption amount.

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
            taking into account only python processes. 
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
        os_dict = {
            'Linux': get_cpu_percent_linux,
            'Windows': get_cpu_percent_windows,
            'Darwin': get_cpu_percent_mac_os
        }
        cpu_percent = os_dict[self._operating_system](self._cpu_processes)
        return cpu_percent

    def calculate_consumption(self):
        """
            CPU energy for the interval since the previous sample.
            Intel RAPL package energy is used when the counters can be read.
            Otherwise the estimate is TDP times utilization, socket count, and duration.
            The first successful RAPL read is a baseline and adds nothing.
            
            Parameters
            ----------
            No parameters
            
            Returns
            -------
            consumption: float
                CPU energy of this sample, in kWh
        
        """
        rapl_kwh = self._rapl_delta_kwh()
        if rapl_kwh is not None:
            self._power_method = "rapl"
            if rapl_kwh < 0:
                rapl_kwh = 0
            self._consumption += rapl_kwh
            return rapl_kwh
        self._power_method = "tdp"
        time_period = time.time() - self._start
        self._start = time.time()
        consumption = self._tdp * self.get_cpu_percent() * self._cpu_num * time_period / FROM_WATTs_TO_kWATTh
        if consumption < 0:
            consumption = 0
        self._consumption += consumption
        return consumption

    def _rapl_delta_kwh(self):
        """
            Package energy since the previous sample, in kWh.
            None when RAPL cannot be read.
            The first successful read is a baseline and returns 0.
            When cpu_processes is "current", later samples are scaled
            by this process tree's share of system CPU time.
        """
        try:
            current = read_rapl_package_energy_uj(self._rapl_root)
        except (OSError, ValueError):
            return None
        previous = self._last_rapl_uj
        self._last_rapl_uj = current
        if previous is None:
            if self._cpu_processes == "current":
                self._last_process_cpu_seconds = process_tree_cpu_seconds()
                self._last_system_cpu_seconds = system_cpu_seconds()
            return 0.0
        delta = current - previous
        if delta < 0:
            return 0.0
        kwh = delta / FROM_uJOULES_TO_kWATTh
        if self._cpu_processes == "current":
            kwh *= self._cpu_time_share()
        return kwh

    def _cpu_time_share(self):
        process_seconds = process_tree_cpu_seconds()
        system_seconds = system_cpu_seconds()
        previous_process = self._last_process_cpu_seconds
        previous_system = self._last_system_cpu_seconds
        self._last_process_cpu_seconds = process_seconds
        self._last_system_cpu_seconds = system_seconds
        if previous_process is None or previous_system is None:
            return 0.0
        return cpu_time_share(process_seconds - previous_process, system_seconds - previous_system)

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


def number_of_cpu(ignore_warnings=True):
    """
        This function returns the number of CPU sockets (physical CPU processors).
        On macOS a positive hw.packages value is that socket count.
        If the package count is missing or not positive, hw.physicalcpu
        (physical cores) is used.
        If the count cannot be read, the number of CPU devices is set to 1.
        
        Parameters
        ----------
        ignore_warnings: bool
            If True, warnings are not shown. If False, warnings are shown.
            The default is True.
        
        Returns
        -------
        cpu_num: int
            Socket count, or physical cores on macOS when the package count is missing

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
            if not ignore_warnings:
                warnings.warn(
                    message="\nYou probably should have installed 'util-linux' to determine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                    category=NoNeededLibrary
                    )
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
            # Use regex for multi-digit CPU numbers
            match = re.findall(r'- (\d+)\.', processor_string)
            cpu_num = int(match[0]) if match else 1
        except:
            if not ignore_warnings:
                warnings.warn(
                    message="\nIt's impossible to determine cpu number correctly\nFor now, number of cpu devices is set to 1\n\n", 
                    category=NoNeededLibrary
                    )
            cpu_num = 1
    elif operating_system == "Darwin":
        cpu_num = 0
        try:
            """
            Physical CPU packages from hw.packages.
            A positive count is kept.
            A failed probe, or a count that is not positive, is not a socket count.
            The physical-core fallback below is used in both of those cases.
            """
            out = subprocess.check_output(
                ["sysctl", "-n", "hw.packages"], text=True
            ).strip()
            cpu_num = int(out)
        except (subprocess.CalledProcessError, ValueError, OSError):
            cpu_num = 0

        if cpu_num <= 0:
            try:
                """
                Fallback: physical cores from hw.physicalcpu.
                This is used only when the package count is missing or not positive.
                """
                out = subprocess.check_output(
                    ["sysctl", "-n", "hw.physicalcpu"], text=True
                ).strip()
                cpu_num = int(out)
            except (subprocess.CalledProcessError, ValueError, OSError):
                cpu_num = 0
            if cpu_num <= 0:
                if not ignore_warnings:
                    warnings.warn(
                        message="Unable to determine the number of CPU sockets on Darwin; defaulting to 1",
                        category=UserWarning,
                    )
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
    cpu_name = re.sub(r'(\(R\))|(®)|(™)|(\(TM\))|(@.*)|(\S*GHz\S*)|(\[.*\])|( \d+-Cores?)|(\(.*\))', '', cpu_name)

    # dropping all the waste words:
    array = re.split(" ", cpu_name)
    for i in array[::-1]:
        if ("CPU" in i) or ("Processor" in i) or (i == ''):
            array.remove(i)
    cpu_name = " ".join(array)
    patterns = get_patterns(cpu_name)
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
    patterns = re.findall(r"(\S*\d+\S*)", cpu_name)
    for i in re.findall(FAMILY_PATTERN, cpu_name):
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
def find_tdp_value(cpu_name, f_table_name, constant_value=CONSTANT_CONSUMPTION, ignore_warnings=True):
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

        ignore_warnings: bool
            If True, warnings are not shown. If False, warnings are shown.
            The default is True.
        
        Returns
        -------
        CPU TDP: float
            TDP of user CPU device

    """
    f_table = pd.read_csv(f_table_name)
    cpu_name_mod, patterns = transform_cpu_name(cpu_name)
    rows = f_table[["Model", "TDP"]].values
    suitable_elements = rows[rows[:, 0] == cpu_name_mod]
    if suitable_elements.shape[0] > 0:
        return find_max_tdp(suitable_elements)
    tokens = sku_tokens(cpu_name_mod)
    if len(tokens) == 0:
        if not ignore_warnings:
            warnings.warn(
                message="\n\nYour CPU device is not found in our database\nCPU TDP is set to constant value 100\n",
                category=NoCPUinTableWarning
                )
        return constant_value
    families = [pattern for pattern in patterns if not re.search(r"\d", pattern)]
    matches = []
    for element in rows:
        row_tokens = set(sku_tokens(str(element[0])))
        if not all(token in row_tokens for token in tokens):
            continue
        if families:
            row_families = [pattern for pattern in get_patterns(str(element[0])) if not re.search(r"\d", pattern)]
            if not set(families).issubset(row_families):
                continue
        matches.append(element)
    if len(matches) == 0:
        if not ignore_warnings:
            warnings.warn(
                message="\n\nYour CPU device is not found in our database\nCPU TDP is set to constant value 100\n",
                category=NoCPUinTableWarning
                )
        return constant_value
    return find_max_tdp(matches)

def sku_tokens(cpu_name):
    """
        Distinctive model tokens such as 285K or 9995WX.
        Short series numbers and family words are not included.
    """
    tokens = []
    for token in re.findall(r"[A-Za-z0-9]+", str(cpu_name)):
        if not re.search(r"\d", token):
            continue
        if re.fullmatch(r"\d{1,2}", token):
            continue
        tokens.append(token.lower())
    return tokens


def read_rapl_package_energy_uj(root):
    """
        Sum energy_uj for top-level RAPL package domains.
        DRAM and other child domains are not included.
    """
    if not root or not os.path.isdir(root):
        raise OSError("RAPL root is not available")
    total = 0
    found = False
    for entry in os.listdir(root):
        domain = os.path.join(root, entry)
        name_path = os.path.join(domain, "name")
        energy_path = os.path.join(domain, "energy_uj")
        if not os.path.isdir(domain) or not os.path.isfile(name_path):
            continue
        with open(name_path, "r", encoding="utf-8") as handle:
            name = handle.read().strip()
        if not name.startswith("package"):
            continue
        with open(energy_path, "r", encoding="utf-8") as handle:
            total += int(handle.read().strip())
        found = True
    if not found:
        raise OSError("No RAPL package energy file")
    return total


def cpu_time_share(process_delta, system_delta):
    """
        Fraction of system CPU time, including idle, used by a process tree.
    """
    if system_delta <= 0 or process_delta <= 0:
        return 0.0
    return min(1.0, process_delta / system_delta)


def utilization_from_cpu_percent(cpu_percent, cpu_count):
    """
        Convert a psutil-style CPU percent into a fraction of machine capacity.
    """
    if not cpu_count:
        return 0.0
    fraction = float(cpu_percent) / (float(cpu_count) * 100.0)
    if fraction < 0:
        return 0.0
    return fraction


# psutil stores the cpu_percent baseline on the Process object.
# A new Process(pid) returns 0 on every first cpu_percent() call, so the
# same object has to be reused for the sample that covers the run.
_CPU_PERCENT_PROCESSES = {}


def _reuse_cpu_percent_process(proc):
    pid = getattr(proc, "pid", None)
    if not isinstance(pid, int):
        return proc
    cached = _CPU_PERCENT_PROCESSES.get(pid)
    if cached is None:
        _CPU_PERCENT_PROCESSES[pid] = proc
        return proc
    try:
        if cached.is_running():
            return cached
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    _CPU_PERCENT_PROCESSES[pid] = proc
    return proc


def _iter_process_tree(pid=None):
    proc = _reuse_cpu_percent_process(psutil.Process(os.getpid() if pid is None else pid))
    yield proc
    try:
        children = proc.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return
    for child in children:
        yield _reuse_cpu_percent_process(child)


def process_tree_cpu_seconds(pid=None):
    total = 0.0
    for proc in _iter_process_tree(pid):
        try:
            times = proc.cpu_times()
            total += float(times.user) + float(times.system)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return total


def system_cpu_seconds():
    return float(sum(psutil.cpu_times()))


def process_tree_cpu_percent(pid=None):
    total = 0.0
    for proc in _iter_process_tree(pid):
        try:
            value = proc.cpu_percent(interval=None)
            if value is not None:
                total += float(value)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return total


def get_cpu_percent_mac_os(cpu_processes="current"):
    """
        This function calculates CPU utilization on MacOS.
        
        Parameters
        ----------
        cpu_processes: str
            if cpu_processes == "current", then calculates CPU utilization percent only for the current running process
            if cpu_processes == "all", then calculates full CPU utilization percent(sum of all running processes)
        
        Returns
        -------
        cpu_percent: float
            CPU utilization fraction. 'cpu_percent' is in [0, 1]. 

    """
    if cpu_processes == "current":
        return utilization_from_cpu_percent(process_tree_cpu_percent(), psutil.cpu_count() or 1)
    elif cpu_processes == "all":
        strings = os.popen('top -stats "command,cpu,pgrp" -l 2| grep -E "(CPU usage:)"').read().split("\n")
        strings.pop()
        strings = strings[-1].split()
        cpu_percent = float(strings[2][:-1]) + float(strings[4][:-1])
    return cpu_percent / 100


def get_cpu_percent_linux(cpu_processes="current"):
    """
        This function calculates CPU utilization on Linux.
        
        Parameters
        ----------
        cpu_processes: str
            if cpu_processes == "current", then calculates CPU utilization percent only for the current running process
            if cpu_processes == "all", then calculates full CPU utilization percent(sum of all running processes)
        
        Returns
        -------
        cpu_percent: float
            CPU utilization fraction. 'cpu_percent' is in [0, 1]. 

    """
    if cpu_processes == "current":
        return utilization_from_cpu_percent(process_tree_cpu_percent(), psutil.cpu_count() or 1)
    elif cpu_processes == "all":
        # execute the top command with the grep command to filter the output
        output = subprocess.run(["top", "-b", "-n1"], capture_output=True, text=True)
    else: 
        raise ValueError(f"'cpu_processes' parameter can be only 'current' or 'all', now it is '{cpu_processes}'")
    cpu_num = psutil.cpu_count()
    # check if the output is empty
    if not output.stdout:
        return 0
    else:
        # split the output into lines
        lines = output.stdout.split('\n')
        # display(lines)
        # variable to store the sum of all process CPU usage
        sum_cpu = 0
        # flag to check if we are at the processes section
        process_section = False
        # iterate through the lines
        for line in lines:
            # check if we are at the processes section
            if 'PID' in line:
                process_section = True
            elif process_section:
                # check if we reached the end of the processes section
                if not line:
                    break
                # split the line into words
                words = line.split()
                # check if the line contains a process
                if len(words) > 0:
                    # the CPU usage percentage is the 8th word
                    sum_cpu += float(words[8].replace(',','.'))
    return sum_cpu / (cpu_num * 100)


def get_cpu_percent_windows(cpu_processes="current"):
    """
        This function calculates CPU utilization on Windows.
        
        Parameters
        ----------
        cpu_processes: str
            if cpu_processes == "current", then calculates CPU utilization percent only for the current running process
            if cpu_processes == "all", then calculates full CPU utilization percent(sum of all running processes)
        
        Returns
        -------
        cpu_percent: float
            CPU utilization fraction. 'cpu_percent' is in [0, 1]. 

    """
    if cpu_processes == "current":
        return utilization_from_cpu_percent(process_tree_cpu_percent(), psutil.cpu_count() or 1)
    elif cpu_processes == "all":
        cpu_percent = psutil.cpu_percent()/100
    else:
        raise ValueError(f"'cpu_processes' parameter can be only 'current' or 'all', now it is '{cpu_processes}'")
    return cpu_percent
