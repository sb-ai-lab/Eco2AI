import ctypes
import warnings
from ctypes import (
    POINTER,
    byref,
    c_char_p,
    c_int,
    c_uint,
    c_ulonglong,
    c_void_p,
    create_string_buffer,
)

from eco2ai.tools.gpu.base import (
    FROM_MW_TO_KWH,
    Sample,
    decode_gpu_name,
    pids_include_us,
    run_command,
    watts_times_seconds_kwh,
)

NVML_SUCCESS = 0
NVML_ERROR_NOT_SUPPORTED = 3
NVML_ERROR_ALREADY_INITIALIZED = 5
NVML_ERROR_NOT_FOUND = 6
NVML_ERROR_INSUFFICIENT_SIZE = 7
NVML_TEMPERATURE_GPU = 0


class MemoryInfo:
    def __init__(self, total, free, used):
        self.total = total
        self.free = free
        self.used = used


class NvmlError(Exception):
    pass


class NvmlUnsupported(NvmlError):
    pass


class _ProcessV1(ctypes.Structure):
    _fields_ = [
        ("pid", c_uint),
        ("usedGpuMemory", c_ulonglong),
    ]


class _ProcessV2(ctypes.Structure):
    _fields_ = [
        ("pid", c_uint),
        ("usedGpuMemory", c_ulonglong),
        ("gpuInstanceId", c_uint),
        ("computeInstanceId", c_uint),
    ]


class _ProcessV3(ctypes.Structure):
    _fields_ = [
        ("pid", c_uint),
        ("usedGpuMemory", c_ulonglong),
        ("gpuInstanceId", c_uint),
        ("computeInstanceId", c_uint),
        ("usedGpuCcProtectedMemory", c_ulonglong),
    ]


class _Memory(ctypes.Structure):
    _fields_ = [
        ("total", c_ulonglong),
        ("free", c_ulonglong),
        ("used", c_ulonglong),
    ]


def _library_names():
    if os_name_is_windows():
        return ("nvml.dll",)
    return ("libnvidia-ml.so.1", "libnvidia-ml.so")


def os_name_is_windows():
    import os
    return os.name == "nt"


def load_nvml_library():
    """Load the NVIDIA driver library when this machine has one. Never imports pynvml."""
    for name in _library_names():
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        wrapper = CtypesNvml(lib)
        try:
            wrapper.open()
        except (NvmlError, OSError, AttributeError):
            continue
        return wrapper
    return None


class CtypesNvml:
    """The NVML calls eco2ai uses, bound to the driver library."""

    def __init__(self, lib):
        self._lib = lib
        self._open = False
        self._handles = []

    def open(self):
        init = self._symbol("nvmlInit_v2") or self._symbol("nvmlInit")
        if init is None:
            raise NvmlError("nvmlInit is missing")
        init.argtypes = []
        init.restype = c_int
        rc = init()
        if rc not in (NVML_SUCCESS, NVML_ERROR_ALREADY_INITIALIZED):
            raise NvmlError("nvmlInit returned %s" % rc)
        self._open = True
        count = self._count()
        self._handles = [self._handle(index) for index in range(count)]

    def close(self):
        if not self._open:
            return
        shutdown = self._symbol("nvmlShutdown")
        if shutdown is not None:
            shutdown.argtypes = []
            shutdown.restype = c_int
            shutdown()
        self._open = False
        self._handles = []

    def device_count(self):
        return len(self._handles)

    def device_name(self, index):
        fn = self._symbol("nvmlDeviceGetName")
        fn.argtypes = [c_void_p, c_char_p, c_uint]
        fn.restype = c_int
        buffer = create_string_buffer(256)
        self._check(fn(self._handles[index], buffer, 256))
        return decode_gpu_name(buffer.value)

    def power_mw(self, index):
        return self._uint("nvmlDeviceGetPowerUsage", index)

    def energy_mj(self, index):
        fn = self._symbol("nvmlDeviceGetTotalEnergyConsumption")
        if fn is None:
            raise NvmlUnsupported("energy counter is missing")
        fn.argtypes = [c_void_p, POINTER(c_ulonglong)]
        fn.restype = c_int
        value = c_ulonglong()
        rc = fn(self._handles[index], byref(value))
        if rc == NVML_ERROR_NOT_SUPPORTED:
            raise NvmlUnsupported("energy counter is not supported")
        self._check(rc)
        return int(value.value)

    def memory(self, index):
        fn = self._symbol("nvmlDeviceGetMemoryInfo")
        fn.argtypes = [c_void_p, POINTER(_Memory)]
        fn.restype = c_int
        info = _Memory()
        self._check(fn(self._handles[index], byref(info)))
        return MemoryInfo(int(info.total), int(info.free), int(info.used))

    def temperature(self, index):
        fn = self._symbol("nvmlDeviceGetTemperature")
        fn.argtypes = [c_void_p, c_int, POINTER(c_uint)]
        fn.restype = c_int
        value = c_uint()
        self._check(fn(self._handles[index], NVML_TEMPERATURE_GPU, byref(value)))
        return int(value.value)

    def power_limit_mw(self, index):
        return self._uint("nvmlDeviceGetEnforcedPowerLimit", index)

    def client_pids(self, index):
        """
        Process ids with a compute or graphics context.
        None when every query is unsupported.
        """
        found = []
        for prefix, layouts in (
            (
                "nvmlDeviceGetComputeRunningProcesses",
                (("v3", _ProcessV3), ("v2", _ProcessV2), ("", _ProcessV1)),
            ),
            (
                "nvmlDeviceGetGraphicsRunningProcesses",
                (("v3", _ProcessV3), ("v2", _ProcessV2), ("", _ProcessV1)),
            ),
        ):
            pids = self._running_pids(prefix, layouts, index)
            if pids is not None:
                found.append(pids)
        if not found:
            return None
        merged = set()
        for pids in found:
            merged.update(pids)
        return merged

    def _running_pids(self, prefix, layouts, index):
        for suffix, struct in layouts:
            name = prefix if not suffix else "%s_%s" % (prefix, suffix)
            fn = self._symbol(name)
            if fn is None:
                continue
            fn.argtypes = [c_void_p, POINTER(c_uint), POINTER(struct)]
            fn.restype = c_int
            count = c_uint(0)
            rc = fn(self._handles[index], byref(count), None)
            if rc == NVML_SUCCESS:
                return set()
            if rc in (NVML_ERROR_NOT_FOUND, NVML_ERROR_NOT_SUPPORTED):
                continue
            if rc != NVML_ERROR_INSUFFICIENT_SIZE:
                continue
            if count.value == 0:
                return set()
            infos = (struct * count.value)()
            rc = fn(self._handles[index], byref(count), infos)
            if rc in (NVML_ERROR_NOT_FOUND, NVML_ERROR_NOT_SUPPORTED):
                continue
            if rc != NVML_SUCCESS:
                continue
            pids = {int(infos[i].pid) for i in range(count.value)}
            valid = {pid for pid in pids if 0 < pid < 0xFFFFFFFF}
            if pids and not valid:
                return None
            return valid
        return None

    def _uint(self, name, index):
        fn = self._symbol(name)
        fn.argtypes = [c_void_p, POINTER(c_uint)]
        fn.restype = c_int
        value = c_uint()
        self._check(fn(self._handles[index], byref(value)))
        return int(value.value)

    def _count(self):
        fn = self._symbol("nvmlDeviceGetCount_v2") or self._symbol("nvmlDeviceGetCount")
        fn.argtypes = [POINTER(c_uint)]
        fn.restype = c_int
        count = c_uint()
        self._check(fn(byref(count)))
        return int(count.value)

    def _handle(self, index):
        fn = self._symbol("nvmlDeviceGetHandleByIndex_v2") or self._symbol("nvmlDeviceGetHandleByIndex")
        fn.argtypes = [c_uint, POINTER(c_void_p)]
        fn.restype = c_int
        handle = c_void_p()
        self._check(fn(index, byref(handle)))
        return handle

    def _symbol(self, name):
        fn = getattr(self._lib, name, None)
        if fn is None:
            return None
        return fn

    def _check(self, rc):
        if rc != NVML_SUCCESS:
            raise NvmlError("NVML returned %s" % rc)


def parse_nvidia_smi_power(text):
    """Rows of (name, watts) from nvidia-smi csv power.draw."""
    rows = []
    if not text:
        return rows
    for line in text.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 2:
            continue
        power = parts[1]
        if power in ("", "[N/A]", "N/A", "[Not Supported]"):
            continue
        try:
            watts = float(power)
        except ValueError:
            continue
        rows.append((parts[0], watts))
    return rows


def parse_nvidia_smi_pids(text):
    if text is None:
        return None
    pids = set()
    for line in text.splitlines():
        cell = line.split(",")[0].strip()
        if not cell or cell.lower() == "pid":
            continue
        try:
            pids.add(int(cell))
        except ValueError:
            continue
    return pids


class NvidiaBackend:
    """
    In-process NVML through the driver library.
    The total-energy counter is preferred. Power times duration is the fallback.
    """

    vendor = "nvidia"
    default_method = "nvml_power"

    def __init__(self, library):
        self._library = library
        self._last_energies = None
        self._count = library.device_count()

    def close(self):
        close = getattr(self._library, "close", None)
        if close is not None:
            close()

    def device_count(self):
        return self._count

    def device_name(self):
        if self._count <= 0:
            return ""
        try:
            return decode_gpu_name(self._library.device_name(0))
        except Exception:
            return ""

    def sample(self, duration):
        try:
            energies = [self._library.energy_mj(index) for index in range(self._count)]
        except Exception:
            energies = None
        if energies is not None:
            method = "nvml_energy"
            kwh = self._energy_delta_kwh(energies)
        else:
            method = "nvml_power"
            kwh = 0.0
            for index in range(self._count):
                try:
                    milliwatts = self._library.power_mw(index)
                except Exception:
                    continue
                kwh += milliwatts / FROM_MW_TO_KWH * duration
        if kwh < 0:
            kwh = 0.0
        used = self._used()
        if used is False:
            return Sample(0.0, "nvml_not_used", False)
        return Sample(kwh, method, used)

    def memory(self):
        return self._map("memory")

    def temperature(self):
        return self._map("temperature")

    def power(self):
        return self._map("power_mw")

    def power_limit(self):
        return self._map("power_limit_mw")

    def _map(self, method):
        fn = getattr(self._library, method, None)
        if fn is None:
            return None
        values = []
        try:
            for index in range(self._count):
                values.append(fn(index))
        except Exception:
            return None
        return values

    def _used(self):
        fn = getattr(self._library, "client_pids", None)
        if fn is None:
            return None
        try:
            merged = set()
            answered = False
            for index in range(self._count):
                pids = fn(index)
                if pids is None:
                    continue
                answered = True
                merged.update(pids)
            if not answered:
                return None
            return pids_include_us(merged)
        except Exception:
            return None

    def _energy_delta_kwh(self, energies):
        previous = self._last_energies
        self._last_energies = list(energies)
        if previous is None or len(previous) != len(energies):
            return 0.0
        total = 0.0
        for prev, current in zip(previous, energies):
            delta = current - prev
            if delta > 0:
                total += delta / FROM_MW_TO_KWH
        return total


class NvidiaSmiBackend:
    """Power-only path. nvidia-smi does not expose the total-energy counter."""

    vendor = "nvidia"
    default_method = "nvml_power"

    def __init__(self, rows, runner):
        self._rows = list(rows)
        self._runner = runner

    def close(self):
        return None

    def device_count(self):
        return len(self._rows)

    def device_name(self):
        if not self._rows:
            return ""
        return self._rows[0][0]

    def sample(self, duration):
        text = run_command(
            ["nvidia-smi", "--query-gpu=name,power.draw", "--format=csv,noheader,nounits"],
            self._runner,
        )
        rows = parse_nvidia_smi_power(text)
        if rows:
            self._rows = rows
        watts = sum(watts for _name, watts in self._rows)
        kwh = watts_times_seconds_kwh(watts, duration)
        pids = parse_nvidia_smi_pids(
            run_command(
                ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                self._runner,
            )
        )
        used = pids_include_us(pids)
        if used is False:
            return Sample(0.0, "nvml_not_used", False)
        return Sample(kwh, "nvml_power", used)

    def power(self):
        return [int(watts * 1000) for _name, watts in self._rows]

    def memory(self):
        return None

    def temperature(self):
        return None

    def power_limit(self):
        return None


class PynvmlLibrary:
    """
    The same readings as the ctypes binding, through a pynvml module that is
    already installed. eco2ai does not install that package.
    """

    def __init__(self, module):
        self._nvml = module
        self._open = False
        self._handles = []

    def open(self):
        self._nvml.nvmlInit()
        self._open = True
        count = self._nvml.nvmlDeviceGetCount()
        self._handles = [self._nvml.nvmlDeviceGetHandleByIndex(index) for index in range(count)]

    def close(self):
        if not self._open:
            return
        try:
            self._nvml.nvmlShutdown()
        except Exception:
            pass
        self._open = False
        self._handles = []

    def device_count(self):
        return len(self._handles)

    def device_name(self, index):
        return self._nvml.nvmlDeviceGetName(self._handles[index])

    def power_mw(self, index):
        return int(self._nvml.nvmlDeviceGetPowerUsage(self._handles[index]))

    def energy_mj(self, index):
        return int(self._nvml.nvmlDeviceGetTotalEnergyConsumption(self._handles[index]))

    def memory(self, index):
        return self._nvml.nvmlDeviceGetMemoryInfo(self._handles[index])

    def temperature(self, index):
        sensor = getattr(self._nvml, "NVML_TEMPERATURE_GPU", 0)
        return int(self._nvml.nvmlDeviceGetTemperature(self._handles[index], sensor))

    def power_limit_mw(self, index):
        return int(self._nvml.nvmlDeviceGetEnforcedPowerLimit(self._handles[index]))

    def client_pids(self, index):
        handle = self._handles[index]
        found = []
        for name in (
            "nvmlDeviceGetComputeRunningProcesses",
            "nvmlDeviceGetGraphicsRunningProcesses",
        ):
            getter = getattr(self._nvml, name, None)
            if getter is None:
                continue
            try:
                infos = getter(handle) or []
            except Exception as error:
                if _pynvml_unsupported(self._nvml, error):
                    continue
                return None
            pids = set()
            for info in infos:
                pid = getattr(info, "pid", info if isinstance(info, int) else None)
                if pid and int(pid) != 0xFFFFFFFF:
                    pids.add(int(pid))
            found.append(pids)
        if not found:
            return None
        merged = set()
        for pids in found:
            merged.update(pids)
        return merged


def _pynvml_unsupported(module, error):
    nvml_error = getattr(module, "NVMLError", ())
    if not isinstance(error, nvml_error):
        return False
    return getattr(error, "value", None) in (
        getattr(module, "NVML_ERROR_NOT_FOUND", None),
        getattr(module, "NVML_ERROR_NOT_SUPPORTED", None),
    )


def load_installed_pynvml():
    """
    Open NVML through pynvml when that module is already importable.
    A missing package is skipped. Nothing is installed.
    """
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            import pynvml
    except ImportError:
        return None
    library = PynvmlLibrary(pynvml)
    try:
        library.open()
    except Exception:
        library.close()
        return None
    return library


def _backend_from_library(library):
    if library in (None, False):
        return None
    try:
        if library.device_count() > 0:
            return NvidiaBackend(library)
    except Exception:
        pass
    close = getattr(library, "close", None)
    if close is not None:
        close()
    return None


def try_open_nvidia(runner=None, library=None, pynvml_module=None):
    """
    Prefer the driver library. If that does not open, use pynvml when it is
    already installed. nvidia-smi remains the power-only fallback.
    library=False skips ctypes. pynvml_module=False skips the installed package.
    """
    if library is None:
        library = load_nvml_library()
    backend = _backend_from_library(library)
    if backend is not None:
        return backend
    if pynvml_module is None:
        installed = load_installed_pynvml()
    elif pynvml_module is False:
        installed = None
    else:
        installed = PynvmlLibrary(pynvml_module)
        try:
            installed.open()
        except Exception:
            installed.close()
            installed = None
    backend = _backend_from_library(installed)
    if backend is not None:
        return backend
    text = run_command(
        ["nvidia-smi", "--query-gpu=name,power.draw", "--format=csv,noheader,nounits"],
        runner,
    )
    rows = parse_nvidia_smi_power(text)
    if not rows:
        return None
    return NvidiaSmiBackend(rows, runner)
