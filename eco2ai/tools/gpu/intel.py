from eco2ai.tools.gpu.base import Sample, run_command, watts_times_seconds_kwh
from eco2ai.tools.gpu.detect import is_integrated_name


def parse_intel_discovery(text):
    """Device index and name pairs from xpu-smi discovery."""
    if not text:
        return []
    devices = []
    current_index = None
    for line in text.splitlines():
        if "Device ID" in line and "Device Name" not in line:
            continue
        if "Device Name:" in line:
            name = line.split("Device Name:", 1)[1].strip(" |")
            index = current_index if current_index is not None else len(devices)
            devices.append((index, name))
            current_index = None
            continue
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        if len(cells) >= 2 and cells[0].isdigit():
            current_index = int(cells[0])
            if "Device Name:" in cells[1]:
                name = cells[1].split("Device Name:", 1)[1].strip()
                devices.append((current_index, name))
                current_index = None
    return devices


def parse_labeled_watts(text):
    if not text:
        return None
    lines = text.splitlines()
    header = None
    for line in lines:
        if "power" not in line.lower():
            continue
        if ":" in line:
            tail = line.split(":")[-1].strip().split()
            if tail:
                try:
                    return float(tail[0].strip(","))
                except ValueError:
                    pass
        header = [cell.strip() for cell in line.split(",")]
    if header is None:
        return None
    power_index = None
    for index, cell in enumerate(header):
        if "power" in cell.lower():
            power_index = index
            break
    if power_index is None:
        return None
    for line in lines:
        cells = [cell.strip() for cell in line.split(",")]
        if len(cells) <= power_index or cells == header:
            continue
        try:
            return float(cells[power_index])
        except ValueError:
            continue
    return None


class IntelBackend:
    vendor = "intel"
    default_method = "intel_power"

    def __init__(self, devices, runner):
        self._devices = list(devices)
        self._runner = runner

    def close(self):
        return None

    def device_count(self):
        return len(self._devices)

    def device_name(self):
        if not self._devices:
            return ""
        return self._devices[0][1]

    def sample(self, duration):
        total = 0.0
        found = False
        for index, _name in self._devices:
            text = run_command(
                ["xpu-smi", "dump", "-d", str(index), "-m", "1", "-n", "1"],
                self._runner,
            )
            watts = parse_labeled_watts(text)
            if watts is None:
                continue
            found = True
            total += watts
        if not found:
            return Sample(0.0, "intel_power", None)
        return Sample(watts_times_seconds_kwh(total, duration), "intel_power", None)

    def power(self):
        values = []
        for index, _name in self._devices:
            text = run_command(
                ["xpu-smi", "dump", "-d", str(index), "-m", "1", "-n", "1"],
                self._runner,
            )
            watts = parse_labeled_watts(text)
            if watts is None:
                return None
            values.append(int(watts * 1000))
        return values

    def memory(self):
        return None

    def temperature(self):
        return None

    def power_limit(self):
        return None


def _discrete_devices(devices, rapl_present):
    chosen = []
    for index, name in devices:
        integrated = is_integrated_name("intel", name)
        if rapl_present and integrated is not False:
            continue
        chosen.append((index, name))
    return chosen


def try_open_intel(group=None, runner=None, rapl_present=False):
    discovery = run_command(["xpu-smi", "discovery"], runner)
    devices = parse_intel_discovery(discovery)
    if not devices and group:
        devices = [
            (index, device.name)
            for index, device in enumerate(group)
            if device.name
        ]
    if devices and not _discrete_devices(devices, rapl_present):
        return False
    devices = _discrete_devices(devices, rapl_present)
    if not devices:
        return None
    readable = []
    for index, name in devices:
        text = run_command(["xpu-smi", "dump", "-d", str(index), "-m", "1", "-n", "1"], runner)
        if parse_labeled_watts(text) is None:
            continue
        readable.append((index, name))
    if not readable:
        return None
    return IntelBackend(readable, runner)
