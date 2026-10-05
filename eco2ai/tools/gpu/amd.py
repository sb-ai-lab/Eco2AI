import json

from eco2ai.tools.gpu.base import Sample, pids_include_us, run_command, watts_times_seconds_kwh

UJ_PER_KWH = 1000 * 1000 * 1000 * 3600

AMD_POWER_COMMANDS = (
    ["rocm-smi", "--showpower", "--json"],
    ["amd-smi", "metric", "--power", "--json"],
)
AMD_PID_COMMANDS = (
    ["rocm-smi", "--showpids"],
    ["amd-smi", "process"],
)


def _number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text or text.upper() in ("N/A", "[N/A]"):
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def _as_watts(value, label):
    text = label.lower()
    if "uw" in text or "microwatt" in text or value >= 1000000:
        return value / 1000000.0
    if "(mw)" in text or text.endswith(" mw"):
        return value / 1000.0
    return value


def _as_uj(value, label):
    text = label.lower()
    if "uj" in text or "microjoule" in text:
        return value
    if value >= 1000000:
        return value
    return None


def _is_power_key(label):
    text = label.lower()
    if "power" not in text:
        return False
    if any(skip in text for skip in ("limit", "cap", "max")):
        return False
    return True


def _collect(obj, name, powers, energies):
    if isinstance(obj, dict):
        power = None
        energy = None
        for key, value in obj.items():
            number = _number(value)
            label = str(key)
            if number is None:
                continue
            if _is_power_key(label):
                power = _as_watts(number, label)
            elif "energy" in label.lower():
                parsed = _as_uj(number, label)
                if parsed is not None:
                    energy = parsed
        if power is not None or energy is not None:
            powers.append((name or "AMD GPU", power))
            energies.append(energy)
            return
        for key, value in obj.items():
            child = name
            lowered = str(key).lower()
            if lowered.startswith("card") or lowered.startswith("gpu"):
                child = str(key)
            _collect(value, child, powers, energies)
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            _collect(item, name or "AMD GPU %s" % index, powers, energies)


def parse_amd_sample(text):
    """
    Names, watts, and optional cumulative microjoules.
    Watts entry is None when that device only reported energy.
    """
    if not text:
        return [], [], []
    try:
        payload = json.loads(text)
    except ValueError:
        payload = None
    names = []
    watts = []
    energies = []
    if payload is not None:
        found_power = []
        found_energy = []
        _collect(payload, "", found_power, found_energy)
        for name, power in found_power:
            names.append(name)
            watts.append(power)
        energies = found_energy
        if any(item is not None for item in watts) or any(item is not None for item in energies):
            return names, watts, energies
    labeled = []
    for line in text.splitlines():
        if "power" not in line.lower():
            continue
        number = None
        for token in line.replace(":", " ").split():
            try:
                number = float(token)
            except ValueError:
                continue
        if number is not None:
            labeled.append(number)
    if not labeled:
        return [], [], []
    return ["AMD GPU"], labeled, []


def parse_amd_pids(text):
    if text is None:
        return None
    pids = set()
    for line in text.splitlines():
        lowered = line.lower()
        if "pid" not in lowered and not line.strip().isdigit():
            continue
        for token in line.replace(":", " ").replace(",", " ").split():
            if token.lower() == "pid":
                continue
            try:
                pids.add(int(token))
            except ValueError:
                continue
    return pids


class AmdBackend:
    vendor = "amd"
    default_method = "amd_power"

    def __init__(self, names, runner):
        self._names = list(names) or ["AMD GPU"]
        self._runner = runner
        self._last_energies = None
        self._method = "amd_power"

    def close(self):
        return None

    def device_count(self):
        return len(self._names)

    def device_name(self):
        return self._names[0]

    def sample(self, duration):
        text = _first_output(AMD_POWER_COMMANDS, self._runner)
        names, watts, energies = parse_amd_sample(text)
        if names:
            self._names = names
        use_energy = bool(energies) and all(item is not None for item in energies)
        if use_energy:
            self._method = "amd_energy"
            kwh = self._energy_delta_kwh(energies)
        else:
            self._method = "amd_power"
            total_watts = sum(item for item in watts if item is not None)
            kwh = watts_times_seconds_kwh(total_watts, duration)
        used = pids_include_us(parse_amd_pids(_first_output(AMD_PID_COMMANDS, self._runner)))
        if used is False:
            return Sample(0.0, "amd_not_used", False)
        return Sample(kwh, self._method, used)

    def power(self):
        text = _first_output(AMD_POWER_COMMANDS, self._runner)
        _names, watts, _energies = parse_amd_sample(text)
        if not watts or any(item is None for item in watts):
            return None
        return [int(item * 1000) for item in watts]

    def memory(self):
        return None

    def temperature(self):
        return None

    def power_limit(self):
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
                total += delta / UJ_PER_KWH
        return total


def _first_output(commands, runner):
    for argv in commands:
        text = run_command(argv, runner)
        if text:
            return text
    return None


def try_open_amd(runner=None):
    text = _first_output(AMD_POWER_COMMANDS, runner)
    names, watts, energies = parse_amd_sample(text)
    if not names:
        return None
    if not any(item is not None for item in watts) and not any(item is not None for item in energies):
        return None
    return AmdBackend(names, runner)
