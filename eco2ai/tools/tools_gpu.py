import pynvml
import time
import warnings

FROM_mWATTS_TO_kWATTH = 1000*1000*3600

class NoGPUWarning(Warning):
    pass

class GPU():
    """
        This class is interface for tracking gpu consumption.
        All methods are done here on the assumption that all gpu devices are of equal model.
        The GPU class is not intended for separate usage, outside the Tracker class

    """
    def __init__(self,):
        """
            This class method initializes GPU object.
            Creates fields of class object. All the fields are private variables

            Parameters
            ----------
            No parameters

            Returns
            -------
            GPU: GPU
                Object of class GPU

        """
        self._consumption = 0
        self.is_gpu_available = is_gpu_available()
        if not self.is_gpu_available:
            warnings.warn(message="\n\nThere is no any available GPU devices or your GPU is not supported by Nvidia library!\nThe tracker will consider CPU usage only\n",
                          category=NoGPUWarning)
        if self.is_gpu_available:
            self._start = time.time()
    
    def calculate_consumption(self):
        """
            This class method calculates GPU power consumption.
            
            Parameters
            ----------
            No parameters
            
            Returns
            -------
            consumption: float
                CPU power consumption
        """
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
        """
            This class method returns GPU power consupmtion amount.

            Parameters
            ----------
            No parameters

            Returns
            -------
            self._consumption: float
                CPU power consumption

        """
        if not self.is_gpu_available:
            return 0
        return self._consumption
    
    def gpu_memory(self):
        """
            This class method returns GPU Memory used. Pynvml library is used.

            Parameters
            ----------
            No parameters

            Returns
            -------
            gpus_memory: list
                list of GPU Memory used per every GPU

        """
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_memory = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            gpus_memory.append(pynvml.nvmlDeviceGetMemoryInfo(handle))
        pynvml.nvmlShutdown()
        return gpus_memory

    def gpu_temperature(self):
        """
            This class method returns GPU temperature. Pynvml library is used.

            Parameters
            ----------
            No parameters

            Returns
            -------
            gpus_temps: list
                list of GPU temperature per every GPU

        """
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_temps = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            gpus_temps.append(pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU))
        pynvml.nvmlShutdown()
        return gpus_temps

    def gpu_power(self):
        """
            This class method returns GPU power consumption. Pynvml library is used.

            Parameters
            ----------
            No parameters

            Returns
            -------
            gpus_powers: list
                list of GPU power consumption per every GPU

        """
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_powers = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            gpus_powers.append(pynvml.nvmlDeviceGetPowerUsage(handle))
        pynvml.nvmlShutdown()
        return gpus_powers

    def gpu_power_limit(self):
        """
            This class method returns GPU power limits. Pynvml library is used.

            Parameters
            ----------
            No parameters

            Returns
            -------
            gpus_limits: list
                list of GPU power limits per every GPU

        """
        if not self.is_gpu_available:
            return None
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_limits = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            gpus_limits.append(pynvml.nvmlDeviceGetEnforcedPowerLimit(handle))
        pynvml.nvmlShutdown()
        return gpus_limits
    
    def name(self,):
        """
            This class method returns GPU name if there are any GPU visible
            or it returns empty string. All the GPU devices are intended to be of the same model
            Pynvml library is used.

            Parameters
            ----------
            No parameters

            Returns
            -------
            gpus_name: string
                string with GPU name. 

        """
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
        """
            This class method returns number of visible GPU devices.
            Pynvml library is used.

            Parameters
            ----------
            No parameters

            Returns
            -------
            deviceCount: int
                Number of visible GPU devices. 

        """
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
    """
        This function checks if there are any available GPU devices
        All the GPU devices are intended to be of the same model
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        gpu_availability: bool
            If there are any visible GPU devices, 
            then gpu_availability = True, else gpu_availability = False

    """
    try:
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_powers = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            gpus_powers.append(pynvml.nvmlDeviceGetPowerUsage(handle))
        pynvml.nvmlShutdown()
        return True
    except pynvml.NVMLError:
        return False

def all_available_gpu():
    """
        This function prints all seeable GPU devices
        All the GPU devices are intended to be of the same model
        
        Parameters
        ----------
        No parameters
        
        Returns
        -------
        No returns

    """
    try:
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        gpus_name = []
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            pynvml.nvmlDeviceGetPowerUsage(handle)
            gpus_name.append(pynvml.nvmlDeviceGetName(handle))
        string = f"""Seeable gpu device(s):
        {gpus_name[0].decode("UTF-8")}: {deviceCount} device(s)"""
        print(string)
        pynvml.nvmlShutdown()
    except:
        print("There is no any available gpu device(s)")