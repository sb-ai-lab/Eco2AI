import os
import subprocess

import psutil

FROM_MW_TO_KWH = 1000 * 1000 * 3600
WATTS_TO_KWH = 1000 * 3600


class Sample:
    """One accelerator reading for the scheduler interval."""

    def __init__(self, kwh, method, used):
        self.kwh = float(kwh)
        self.method = method
        self.used = used


def watts_times_seconds_kwh(watts, seconds):
    if watts <= 0 or seconds <= 0:
        return 0.0
    return watts * seconds / WATTS_TO_KWH


def process_tree_pids():
    proc = psutil.Process(os.getpid())
    pids = {proc.pid}
    try:
        for child in proc.children(recursive=True):
            pids.add(child.pid)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass
    return pids


def pids_include_us(pids):
    """
    True when this process tree is in pids.
    False when pids was read and this process is absent.
    None when the tool could not list process ids.
    """
    if pids is None:
        return None
    return bool(process_tree_pids().intersection(pids))


def run_command(argv, runner=None, timeout=8):
    """Run a driver CLI. runner is a test stand-in that receives the argv list."""
    if runner is not None:
        return runner(list(argv))
    try:
        completed = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.stdout and completed.stdout.strip():
        return completed.stdout
    return None


def decode_gpu_name(name):
    """Return a device name as text."""
    if isinstance(name, bytes):
        return name.decode("UTF-8", "replace")
    return str(name)
