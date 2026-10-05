import re

from eco2ai.tools.gpu.base import Sample, run_command, watts_times_seconds_kwh

# Full-duty chip power for method tpu_tdp_duty. These are estimates, not a
# measured joule counter. A chip type that is not listed does not open.
TPU_CHIP_WATTS = {
    "v4": 200.0,
    "v5e": 170.0,
    "v5p": 450.0,
    "v6e": 200.0,
}

_CHIP = re.compile(r"tpu\s*v(\d+[a-z]*)", re.IGNORECASE)
_DUTY = re.compile(r"duty(?:\s*cycle)?\s*[:=]?\s*([0-9]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE)


def parse_tpu_info(text):
    """Return (chip_key, duty_fraction) or (None, None)."""
    if not text:
        return None, None
    chip = _CHIP.search(text)
    duty = _DUTY.search(text)
    if chip is None or duty is None:
        return None, None
    return "v" + chip.group(1).lower(), float(duty.group(1)) / 100.0


class GoogleBackend:
    vendor = "google"
    default_method = "tpu_tdp_duty"

    def __init__(self, chip, watts, duty, runner):
        self._chip = chip
        self._watts = watts
        self._duty = duty
        self._runner = runner

    def close(self):
        return None

    def device_count(self):
        return 1

    def device_name(self):
        return "TPU %s" % self._chip

    def sample(self, duration):
        text = run_command(["tpu-info"], self._runner)
        chip, duty = parse_tpu_info(text)
        if chip == self._chip and duty is not None:
            self._duty = duty
        kwh = watts_times_seconds_kwh(self._watts * self._duty, duration)
        return Sample(kwh, "tpu_tdp_duty", None)

    def memory(self):
        return None

    def temperature(self):
        return None

    def power(self):
        return [int(self._watts * self._duty * 1000)]

    def power_limit(self):
        return [int(self._watts * 1000)]


def try_open_google(runner=None):
    text = run_command(["tpu-info"], runner)
    if not text:
        return None
    chip, duty = parse_tpu_info(text)
    if chip not in TPU_CHIP_WATTS or duty is None:
        return False
    return GoogleBackend(chip, TPU_CHIP_WATTS[chip], duty, runner)
