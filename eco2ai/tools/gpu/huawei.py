import re

from eco2ai.tools.gpu.base import Sample, run_command, watts_times_seconds_kwh

_POWER_LINE = re.compile(
    r"Power(?:\s*Dissipation)?\s*(?:\(W\))?\s*:\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE,
)


def parse_ascend_watts(text):
    if not text:
        return None
    match = _POWER_LINE.search(text)
    if match is None:
        return None
    return float(match.group(1))


class HuaweiBackend:
    vendor = "huawei"
    default_method = "ascend_power"

    def __init__(self, count, runner):
        self._count = count
        self._runner = runner

    def close(self):
        return None

    def device_count(self):
        return self._count

    def device_name(self):
        if self._count == 1:
            return "Ascend"
        return "Ascend"

    def sample(self, duration):
        total = 0.0
        found = 0
        for index in range(self._count):
            text = run_command(["npu-smi", "info", "-t", "power", "-i", str(index)], self._runner)
            watts = parse_ascend_watts(text)
            if watts is None:
                break
            total += watts
            found += 1
        if found == 0:
            return Sample(0.0, "ascend_power", None)
        self._count = found
        return Sample(watts_times_seconds_kwh(total, duration), "ascend_power", None)

    def power(self):
        values = []
        for index in range(self._count):
            text = run_command(["npu-smi", "info", "-t", "power", "-i", str(index)], self._runner)
            watts = parse_ascend_watts(text)
            if watts is None:
                break
            values.append(int(watts * 1000))
        return values or None

    def memory(self):
        return None

    def temperature(self):
        return None

    def power_limit(self):
        return None


def try_open_huawei(runner=None):
    count = 0
    for index in range(8):
        text = run_command(["npu-smi", "info", "-t", "power", "-i", str(index)], runner)
        if parse_ascend_watts(text) is None:
            break
        count += 1
    if count == 0:
        return None
    return HuaweiBackend(count, runner)
