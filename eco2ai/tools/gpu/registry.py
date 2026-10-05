import warnings

from eco2ai.tools.gpu.amd import try_open_amd
from eco2ai.tools.gpu.detect import eligible_vendors, probe_devices, rapl_package_present
from eco2ai.tools.gpu.google import try_open_google
from eco2ai.tools.gpu.huawei import try_open_huawei
from eco2ai.tools.gpu.intel import try_open_intel
from eco2ai.tools.gpu.nvidia import try_open_nvidia

MISSING = {
    "nvidia": "NVIDIA device found. Power tracking needs the NVIDIA driver library, an already installed pynvml, or nvidia-smi.",
    "amd": "AMD device found. Power tracking needs rocm-smi or amd-smi from the AMD driver.",
    "intel": "Intel discrete GPU found. Power tracking needs xpu-smi from the Intel driver.",
    "huawei": "Ascend device found. Power tracking needs npu-smi from the CANN driver.",
    "google": "TPU found. The chip type was missing from tpu-info or is not in the estimate table.",
}


def open_backends(
    devices=None,
    rapl_present=None,
    rapl_root=None,
    runner=None,
    nvml_library=None,
    probe_kwargs=None,
):
    """
    Open one backend per eligible vendor.
    nvml_library=False skips the NVIDIA driver library and uses nvidia-smi.
    runner(argv) supplies driver CLI text in tests.
    """
    if devices is None:
        devices = probe_devices(**(probe_kwargs or {}))
    if rapl_present is None:
        if rapl_root is None:
            rapl_present = rapl_package_present()
        else:
            rapl_present = rapl_package_present(rapl_root)
    chosen = eligible_vendors(devices, rapl_present)
    backends = []
    notes = []
    if "nvidia" in chosen:
        backend = try_open_nvidia(runner=runner, library=nvml_library)
        _keep(backends, notes, "nvidia", backend)
    if "amd" in chosen:
        _keep(backends, notes, "amd", try_open_amd(runner=runner))
    if "intel" in chosen:
        _keep(
            backends,
            notes,
            "intel",
            try_open_intel(chosen["intel"], runner=runner, rapl_present=bool(rapl_present)),
        )
    if "huawei" in chosen:
        _keep(backends, notes, "huawei", try_open_huawei(runner=runner))
    if "google" in chosen:
        _keep(backends, notes, "google", try_open_google(runner=runner))
    return backends, notes


def _keep(backends, notes, vendor, backend):
    if backend is None:
        notes.append(MISSING[vendor])
        return
    if backend is False:
        return
    backends.append(backend)


def warn_missing(notes, ignore_warnings, category):
    if ignore_warnings:
        return
    for note in notes:
        warnings.warn(message=note, category=category)
