import warnings

from eco2ai.tools.gpu.base import decode_gpu_name
from eco2ai.tools.gpu.detect import probe_devices

__all__ = [
    "GPU",
    "NoGPUWarning",
    "all_available_gpu",
    "decode_gpu_name",
    "is_gpu_available",
]
from eco2ai.tools.gpu.registry import open_backends, warn_missing

class NoGPUWarning(Warning):
    pass


class GPU:
    """
    Interface for tracking accelerator energy.
    NVIDIA, AMD, Intel, Huawei Ascend, and Google TPU backends are opened
    only for hardware visible on this machine. Driver tools that are already
    installed supply the readings. No vendor Python package is imported.

    The public methods keep the Tracker contract. NVIDIA samples are still
    labeled method:nvml_energy, method:nvml_power, or method:nvml_not_used.
    """

    def __init__(self, ignore_warnings=False, backends=None):
        """
        Parameters
        ----------
        ignore_warnings: bool
            If True, warnings are not shown. If False, warnings are shown.
        backends: list or None
            Open backends. None probes this machine and opens the matching ones.
        """
        self._consumption = 0
        self._ignore_warnings = ignore_warnings
        self._power_methods = None
        self._notes = []
        if backends is None:
            self._backends, self._notes = open_backends()
        else:
            self._backends = list(backends)
        self.is_gpu_available = bool(self._backends)
        if not self.is_gpu_available and not self._ignore_warnings:
            if self._notes:
                warn_missing(self._notes, ignore_warnings=False, category=NoGPUWarning)
            else:
                warnings.warn(
                    message=(
                        "No supported accelerator was found, or its driver tool is missing.\n"
                        "The tracker will consider CPU and RAM usage only"
                    ),
                    category=NoGPUWarning,
                )
        elif self._notes and not self._ignore_warnings:
            warn_missing(self._notes, ignore_warnings=False, category=NoGPUWarning)
        if self.is_gpu_available:
            import time
            self._start = time.time()

    def calculate_consumption(self):
        """
        Accelerator energy since the previous sample, in kWh.
        A joule counter is used when a backend has one. Otherwise energy is
        power times the duration since the previous sample.
        Power drawn while this process is not running on the device is not
        included when the backend can list client process ids.
        A negative result is stored as zero.
        """
        if not self.is_gpu_available:
            return 0
        import time
        duration = time.time() - self._start
        self._start = time.time()
        total = 0.0
        methods = []
        for backend in self._backends:
            try:
                sample = backend.sample(duration)
            except Exception:
                continue
            kwh = sample.kwh
            if kwh < 0:
                kwh = 0.0
            total += kwh
            methods.append(sample.method)
        if total < 0:
            total = 0.0
        self._power_methods = methods
        self._consumption += total
        return total

    def get_consumption(self):
        """Return the summed accelerator energy for this run, in kWh."""
        if not self.is_gpu_available:
            return 0
        return self._consumption

    def power_method_label(self):
        """
        Label of the method used by the latest calculate_consumption call.
        Before that call the label is method:nvml_power when an NVIDIA
        backend is open. After a sample, labels from each backend are joined
        with +. NVIDIA labels stay nvml_energy, nvml_power, and nvml_not_used.
        """
        if not self._power_methods:
            for backend in self._backends:
                if getattr(backend, "vendor", "") == "nvidia":
                    return "method:nvml_power"
            if self._backends:
                return "method:%s" % self._backends[0].default_method
            return "method:nvml_power"
        return "method:" + "+".join(self._power_methods)

    def close(self):
        """Shut down every open backend."""
        for backend in self._backends:
            close = getattr(backend, "close", None)
            if close is None:
                continue
            try:
                close()
            except Exception:
                pass
        self._backends = []

    def name(self):
        """Joined device names, or an empty string when none are open."""
        names = []
        for backend in self._backends:
            try:
                label = backend.device_name()
            except Exception:
                label = ""
            if label:
                names.append(label)
        return ", ".join(names)

    def gpu_num(self):
        """Number of devices across open backends."""
        total = 0
        for backend in self._backends:
            try:
                total += int(backend.device_count())
            except Exception:
                continue
        return total

    def gpu_memory(self):
        return self._first("memory")

    def gpu_temperature(self):
        return self._first("temperature")

    def gpu_power(self):
        return self._first("power")

    def gpu_power_limit(self):
        return self._first("power_limit")

    def _first(self, method):
        if not self.is_gpu_available:
            return None
        for backend in self._backends:
            fn = getattr(backend, method, None)
            if fn is None:
                continue
            try:
                value = fn()
            except Exception:
                continue
            if value is not None:
                return value
        return None


def is_gpu_available():
    """True when at least one accelerator backend can open on this machine."""
    backends, _notes = open_backends()
    available = bool(backends)
    for backend in backends:
        close = getattr(backend, "close", None)
        if close is None:
            continue
        try:
            close()
        except Exception:
            pass
    return available


def all_available_gpu():
    """Print accelerators visible to the operating-system probe."""
    try:
        devices = probe_devices()
    except Exception:
        devices = []
    if not devices:
        print("There is no any available gpu device(s)")
        return
    lines = []
    for device in devices:
        label = device.name or device.vendor
        lines.append("        %s (%s)" % (label, device.vendor))
    print("Seeable gpu device(s):\n" + "\n".join(lines))
