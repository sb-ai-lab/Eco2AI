import os
import time
import warnings

import psutil
import pynvml

FROM_mWATTS_TO_kWATTH = 1000 * 1000 * 3600


def _process_tree_pids():
    proc = psutil.Process(os.getpid())
    pids = {proc.pid}
    try:
        for child in proc.children(recursive=True):
            pids.add(child.pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return pids


def _gpu_client_pids(handle):
    """
    Process ids with a compute or graphics context on this GPU.
    A query that this device does not support is skipped.
    """
    pids = set()
    for name in (
        "nvmlDeviceGetComputeRunningProcesses",
        "nvmlDeviceGetGraphicsRunningProcesses",
    ):
        getter = getattr(pynvml, name, None)
        if getter is None:
            continue
        try:
            infos = getter(handle) or []
        except pynvml.NVMLError as error:
            if getattr(error, "value", None) in (
                getattr(pynvml, "NVML_ERROR_NOT_FOUND", None),
                getattr(pynvml, "NVML_ERROR_NOT_SUPPORTED", None),
            ):
                continue
            raise
        for info in infos:
            pid = getattr(info, "pid", info if isinstance(info, int) else None)
            if pid:
                pids.add(int(pid))
    return pids


def decode_gpu_name(name):
    """Return a GPU device name as text.

    pynvml 5.6+ returns bytes from nvmlDeviceGetName. nvidia-ml-py returns str.
    """
    if isinstance(name, bytes):
        return name.decode("UTF-8")
    return str(name)


class NoGPUWarning(Warning):
    pass


class GPU:
    """
    This class is interface for tracking gpu consumption.
    All methods are done here on the assumption that all gpu devices are of equal model.
    The GPU class is not intended for separate usage, outside the Tracker class

    """

    def __init__(self, ignore_warnings=False):
        """
        This class method initializes GPU object.
        Creates fields of class object. All the fields are private variables

        Parameters
        ----------
        ignore_warnings: bool
            If True, warnings are not shown. If False, warnings are shown.
            The default is False.

        Returns
        -------
        GPU: GPU
            Object of class GPU

        """
        self._consumption = 0
        self._ignore_warnings = ignore_warnings
        self._nvml_open = False
        self._last_energies = None
        self._power_method = None
        self.is_gpu_available = is_gpu_available()

        if not self.is_gpu_available and not self._ignore_warnings:
            warnings.warn(
                message="""There is no any available GPU devices or your GPU is not supported by Nvidia library!\nThe tracker will consider CPU usage only""",
                category=NoGPUWarning,
            )
        if self.is_gpu_available:
            self._start = time.time()

    def calculate_consumption(self): 
        """
        GPU energy since the previous sample.
        NVML total-energy counters are used when every device reports one.
        The first successful read is a baseline and adds nothing.
        If the energy counters cannot be read, energy is power times the
        duration since the previous sample.
        Power drawn while this process is not running on the GPU is not
        included. An idle card is not energy of a CPU-only calculation.
        A negative result is stored as zero.

        Parameters
        ----------
        No parameters

        Returns
        -------
        consumption: float
            GPU energy of this sample, in kWh
        """
        if not self.is_gpu_available:
            return 0
        duration = time.time() - self._start
        self._start = time.time()
        try:
            energies = self._read_total_energy()
        except Exception:
            energies = None
        if energies is not None:
            self._power_method = "nvml_energy"
            consumption = self._energy_delta_kwh(energies)
        else:
            self._power_method = "nvml_power"
            consumption = 0
            powers = self.gpu_power() or []
            for current_power in powers:
                consumption += current_power / FROM_mWATTS_TO_kWATTH * duration
        if consumption < 0:
            consumption = 0
        if self._process_uses_gpu() is False:
            consumption = 0.0
            self._power_method = "nvml_not_used"
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
            GPU power consumption

        """
        if not self.is_gpu_available:
            return 0
        return self._consumption

    def power_method_label(self):
        """
            Label of the method used by the latest calculate_consumption call.
            Before that call the label is method:nvml_power.
            After a sample it is method:nvml_energy, method:nvml_power,
            or method:nvml_not_used when this process is not running on the GPU.
        """
        if not self._power_method:
            return "method:nvml_power"
        return f"method:{self._power_method}"

    def close(self):
        """
            Shut down NVML once tracking stops.
        """
        if self._nvml_open:
            try:
                pynvml.nvmlShutdown()
            except Exception:
                pass
            self._nvml_open = False

    def _ensure_nvml(self):
        if not self._nvml_open:
            pynvml.nvmlInit()
            self._nvml_open = True

    def _handles(self):
        self._ensure_nvml()
        device_count = pynvml.nvmlDeviceGetCount()
        return [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(device_count)]

    def _read_total_energy(self):
        energies = []
        for handle in self._handles():
            energies.append(pynvml.nvmlDeviceGetTotalEnergyConsumption(handle))
        return energies

    def _process_uses_gpu(self):
        """
        Whether this process or one of its children has a GPU context.
        False means the card's power belongs to other programs.
        None means NVML could not answer, and the sample is kept.
        """
        if not any(
            hasattr(pynvml, name)
            for name in (
                "nvmlDeviceGetComputeRunningProcesses",
                "nvmlDeviceGetGraphicsRunningProcesses",
            )
        ):
            return None
        try:
            ours = _process_tree_pids()
            for handle in self._handles():
                if ours.intersection(_gpu_client_pids(handle)):
                    return True
            return False
        except Exception:
            return None

    def _energy_delta_kwh(self, energies):
        previous = self._last_energies
        self._last_energies = list(energies)
        if previous is None:
            return 0.0
        total = 0.0
        for prev, current in zip(previous, energies):
            delta = current - prev
            if delta > 0:
                total += delta / FROM_mWATTS_TO_kWATTH
        return total

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
        try:
            return [pynvml.nvmlDeviceGetMemoryInfo(handle) for handle in self._handles()]
        except Exception:
            return None

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
        try:
            return [
                pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                for handle in self._handles()
            ]
        except Exception:
            return None

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
        try:
            return [pynvml.nvmlDeviceGetPowerUsage(handle) for handle in self._handles()]
        except Exception:
            return None

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
        try:
            return [pynvml.nvmlDeviceGetEnforcedPowerLimit(handle) for handle in self._handles()]
        except Exception:
            return None

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
            names = []
            for handle in self._handles():
                pynvml.nvmlDeviceGetPowerUsage(handle)
                names.append(pynvml.nvmlDeviceGetName(handle))
            if not names:
                return ""
            return decode_gpu_name(names[0])
        except Exception:
            return ""

    def gpu_num(self) -> int:
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
            device_count = 0
            for handle in self._handles():
                pynvml.nvmlDeviceGetPowerUsage(handle)
                device_count += 1
            return device_count
        except Exception:
            return 0


def is_gpu_available() -> bool:
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
    except Exception:  # catch all exceptions for robustness
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
        if gpus_name:
            string = f"""Seeable gpu device(s):
        {decode_gpu_name(gpus_name[0])}: {deviceCount} device(s)"""
            print(string)
        else:
            print("There is no any available gpu device(s)")
        pynvml.nvmlShutdown()
    except Exception:
        print("There is no any available gpu device(s)")
