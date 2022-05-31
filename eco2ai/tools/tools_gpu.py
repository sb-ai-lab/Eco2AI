import pynvml
import time
import warnings

FROM_mWATTS_TO_kWATTH = 1000*1000*3600

class NoGPUWarning(Warning):
    pass

class GPU():
    '''
    This class is interface for tracking gpu consumption.
    All methods are done here on the assumption that all gpu devices are of equal model.
    The GPU class is not intended for separate usage, outside the Tracker class
    '''
    def __init__(self,):
        self._consumption = 0
        self.is_gpu_available = is_gpu_available()
        if not self.is_gpu_available:
            warnings.warn(message="\n\nThere is no any available GPU devices or your gpu is not supported by Nvidia library!\nThe thacker will consider CPU usage only\n",
                          category=NoGPUWarning)
        if self.is_gpu_available:
            self._start = time.time()
    
    def calculate_consumption(self):
        if not self.is_gpu_available:
            return 0
        duration = time.time() - self._start
        self._start = time.time()
        consumption = 0
        for current_power in self.gpu_power():
            consumption += current_power / FROM_mWATTS_TO_kWATTH * duration
        if consumption < 0:
            consumption = 0
        self._consumption += consumption
        return consumption
    
    def get_consumption(self):
        if not self.is_gpu_available:
            return 0
        return self._consumption
    
    def gpu_memory(self):
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_memory = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # print("memory:", pynvml.nvmlDeviceGetMemoryInfo(handle))
            gpus_memory.append(pynvml.nvmlDeviceGetMemoryInfo(handle))
        pynvml.nvmlShutdown()
        return gpus_memory

    def gpu_temperature(self):
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_temps = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # print("temperature:", pynvml.nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU))
            gpus_temps.append(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
        pynvml.nvmlShutdown()
        return gpus_temps

    def gpu_power(self):
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_powers = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # print("power:", pynvml.nvmlDeviceGetPowerUsage(handle))
            gpus_powers.append(pynvml.nvmlDeviceGetPowerUsage(handle))
        pynvml.nvmlShutdown()
        return gpus_powers

    def gpu_power_limit(self):
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_limits = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # print("power limit:", pynvml.nvmlDeviceGetEnforcedPowerLimit(handle))
            gpus_limits.append(pynvml.nvmlDeviceGetEnforcedPowerLimit(handle))
        pynvml.nvmlShutdown()
        return gpus_limits
    
    def name(self,):
        try:
            pynvml.nvmlInit()
            deviceCount = pynvml.nvmlDeviceGetCount()
            gpus_name = []
            for i in range(deviceCount):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                pynvml.nvmlDeviceGetPowerUsage(handle)
                gpus_name.append(pynvml.nvmlDeviceGetName(handle))
            pynvml.nvmlShutdown()
            return gpus_name[0].decode("UTF-8")
        except:
            return ""
    
    def gpu_num(self):
        try:
            pynvml.nvmlInit()
            deviceCount = pynvml.nvmlDeviceGetCount()
            for i in range(deviceCount):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                pynvml.nvmlDeviceGetPowerUsage(handle)
            pynvml.nvmlShutdown()
            return deviceCount
        except: 
            return 0


def is_gpu_available():
    '''
    Returns True if there are GPUs available.
    '''
    try:
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_powers = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            # print("power:", pynvml.nvmlDeviceGetPowerUsage(handle))
            gpus_powers.append(pynvml.nvmlDeviceGetPowerUsage(handle))
        pynvml.nvmlShutdown()
        return True
    except pynvml.NVMLError:
        return False

def all_available_gpu():
    '''
    Prints all seeable gpu devices
    All the devices should be of the same model
    '''
    try:
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_name = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            pynvml.nvmlDeviceGetPowerUsage(handle)
            # print("names:", pynvml.nvmlDeviceGetName(handle))
            gpus_name.append(pynvml.nvmlDeviceGetName(handle))
        string = f"""Seeable gpu device(s):
        {gpus_name[0].decode("UTF-8")}: {deviceCount} device(s)"""
        print(string)
        pynvml.nvmlShutdown()
    except:
        print("There is no any available gpu device(s)")