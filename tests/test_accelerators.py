import json
import os
import sys
import tempfile
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from eco2ai.tools.gpu.amd import parse_amd_sample, try_open_amd
from eco2ai.tools.gpu.base import FROM_MW_TO_KWH, WATTS_TO_KWH
from eco2ai.tools.gpu.detect import (
    Device,
    eligible_vendors,
    probe_devices,
    rapl_package_present,
)
from eco2ai.tools.gpu.google import TPU_CHIP_WATTS, try_open_google
from eco2ai.tools.gpu.huawei import try_open_huawei
from eco2ai.tools.gpu.nvidia import (
    NvidiaBackend,
    NvidiaSmiBackend,
    parse_nvidia_smi_power,
    try_open_nvidia,
)
from eco2ai.tools.gpu.registry import open_backends
from eco2ai.tools.tools_gpu import GPU, NoGPUWarning, decode_gpu_name


def _no_cli(name):
    return None


def _missing(_path):
    return False


class _FakePynvml:
    def __init__(self):
        self.energy = 0
        self.shut_down = False
        self.NVML_TEMPERATURE_GPU = 0

    def nvmlInit(self):
        return None

    def nvmlShutdown(self):
        self.shut_down = True

    def nvmlDeviceGetCount(self):
        return 1

    def nvmlDeviceGetHandleByIndex(self, index):
        return index

    def nvmlDeviceGetName(self, handle):
        return b"Old Driver GPU"

    def nvmlDeviceGetPowerUsage(self, handle):
        return 5000

    def nvmlDeviceGetTotalEnergyConsumption(self, handle):
        return self.energy

    def nvmlDeviceGetMemoryInfo(self, handle):
        return None

    def nvmlDeviceGetTemperature(self, handle, sensor):
        return 30

    def nvmlDeviceGetEnforcedPowerLimit(self, handle):
        return 100000

    def nvmlDeviceGetComputeRunningProcesses(self, handle):
        class Info:
            pid = os.getpid()

        return [Info()]


class FakeNvml:
    def __init__(self):
        self.energy = [1000]
        self.pids = {os.getpid()}
        self.power_values = [10000]
        self.closed = False
        self.fail_energy = False

    def device_count(self):
        return 1

    def device_name(self, index):
        return b"Test GPU"

    def energy_mj(self, index):
        if self.fail_energy:
            raise RuntimeError("no energy")
        return self.energy[index]

    def power_mw(self, index):
        return self.power_values[index]

    def client_pids(self, index):
        if self.pids is None:
            return None
        return set(self.pids)

    def memory(self, index):
        return None

    def temperature(self, index):
        return 41

    def power_limit_mw(self, index):
        return 75000

    def close(self):
        self.closed = True


class AcceleratorTests(unittest.TestCase):
    def test_import_does_not_load_pynvml(self):
        sys.modules.pop("pynvml", None)
        import eco2ai.tools.tools_gpu as tools_gpu
        import eco2ai.tools.gpu.nvidia as nvidia

        self.assertNotIn("pynvml", sys.modules)
        with open(tools_gpu.__file__, "r", encoding="utf-8") as handle:
            self.assertNotIn("pynvml", handle.read())
        with open(nvidia.__file__, "r", encoding="utf-8") as handle:
            source = handle.read()
        for line in source.splitlines():
            if "import pynvml" in line or "from pynvml" in line:
                self.assertNotEqual(line, line.lstrip())
        setup_path = os.path.join(ROOT, "setup.py")
        project_path = os.path.join(ROOT, "pyproject.toml")
        with open(setup_path, "r", encoding="utf-8") as handle:
            self.assertNotIn("pynvml", handle.read())
        with open(project_path, "r", encoding="utf-8") as handle:
            self.assertNotIn("pynvml", handle.read())

    def test_installed_pynvml_is_used_only_after_ctypes_fails(self):
        module = _FakePynvml()
        calls = {"smi": 0}

        def runner(argv):
            calls["smi"] += 1
            return "Should Not Run, 10\n"

        backend = try_open_nvidia(runner=runner, library=False, pynvml_module=module)
        self.assertIsInstance(backend, NvidiaBackend)
        self.assertEqual(backend.device_name(), "Old Driver GPU")
        self.assertEqual(calls["smi"], 0)
        self.assertEqual(backend.sample(10).kwh, 0.0)
        module.energy = FROM_MW_TO_KWH
        sample = backend.sample(10)
        self.assertAlmostEqual(sample.kwh, 1.0)
        self.assertEqual(sample.method, "nvml_energy")
        backend.close()
        self.assertTrue(module.shut_down)

        def smi_runner(argv):
            if "power.draw" in " ".join(argv):
                return "Board GPU, 12.0\n"
            return None

        fallback = try_open_nvidia(runner=smi_runner, library=False, pynvml_module=False)
        self.assertIsInstance(fallback, NvidiaSmiBackend)

    def test_decode_gpu_name_accepts_bytes(self):
        self.assertEqual(decode_gpu_name(b"NVIDIA"), "NVIDIA")

    def test_sysfs_probe_keeps_display_and_drops_bridge(self):
        with tempfile.TemporaryDirectory() as root:
            self._pci(root, "0000_01_00.0", "0x10de", "0x030000", "NVIDIA GeForce GTX 1650")
            self._pci(root, "0000_00_02.0", "0x8086", "0x030000", "Intel(R) UHD Graphics")
            self._pci(root, "0000_00_1c.0", "0x8086", "0x060000", "Host bridge")
            devices = probe_devices(
                sysfs_root=root,
                platform_name="posix",
                which=_no_cli,
                exists=_missing,
                environ={},
            )
        vendors = [(device.vendor, device.integrated, device.name) for device in devices]
        self.assertIn(("nvidia", False, "NVIDIA GeForce GTX 1650"), vendors)
        self.assertIn(("intel", True, "Intel(R) UHD Graphics"), vendors)
        self.assertEqual(len(devices), 2)

    def test_windows_pnp_rows(self):
        devices = probe_devices(
            sysfs_root=os.path.join(tempfile.gettempdir(), "eco2ai-no-sysfs"),
            platform_name="nt",
            windows_rows=[("NVIDIA GeForce GTX 1650", r"PCI\VEN_10DE&DEV_1F99")],
            which=_no_cli,
            exists=_missing,
            environ={},
        )
        self.assertEqual(devices[0].vendor, "nvidia")
        self.assertFalse(devices[0].integrated)

    def test_intel_igpu_skipped_when_rapl_package_exists(self):
        with tempfile.TemporaryDirectory() as root:
            domain = os.path.join(root, "intel-rapl-0")
            os.makedirs(domain)
            with open(os.path.join(domain, "name"), "w", encoding="utf-8") as handle:
                handle.write("package-0\n")
            with open(os.path.join(domain, "energy_uj"), "w", encoding="utf-8") as handle:
                handle.write("10\n")
            self.assertTrue(rapl_package_present(root))
        igpu = Device("intel", "Intel(R) UHD Graphics", True)
        arc = Device("intel", "Intel(R) Arc(TM) A770", False)
        self.assertNotIn("intel", eligible_vendors([igpu], rapl_present=True))
        self.assertIn("intel", eligible_vendors([igpu, arc], rapl_present=True))
        self.assertIn("intel", eligible_vendors([igpu], rapl_present=False))

        def runner(argv):
            if argv[:2] == ["xpu-smi", "discovery"]:
                return "| 0 | Device Name: Intel(R) UHD Graphics |\n"
            return "GPU Power (W): 15\n"

        backends, notes = open_backends(
            devices=[igpu],
            rapl_present=True,
            runner=runner,
            nvml_library=False,
        )
        self.assertEqual(backends, [])
        self.assertEqual(notes, [])

    def test_nvidia_energy_counter_and_not_used(self):
        library = FakeNvml()
        backend = NvidiaBackend(library)
        gpu = GPU(ignore_warnings=True, backends=[backend])
        self.assertEqual(gpu.power_method_label(), "method:nvml_power")
        self.assertEqual(gpu.calculate_consumption(), 0.0)
        self.assertEqual(gpu.power_method_label(), "method:nvml_energy")
        self.assertEqual(gpu.name(), "Test GPU")
        self.assertEqual(gpu.gpu_temperature(), [41])

        library.energy = [1000 + FROM_MW_TO_KWH]
        self.assertAlmostEqual(gpu.calculate_consumption(), 1.0)
        self.assertAlmostEqual(gpu.get_consumption(), 1.0)

        library.pids = set()
        library.energy = [1000 + 2 * FROM_MW_TO_KWH]
        self.assertEqual(gpu.calculate_consumption(), 0.0)
        self.assertIn("nvml_not_used", gpu.power_method_label())
        gpu.close()
        self.assertTrue(library.closed)

    def test_nvidia_power_fallback_and_smi(self):
        library = FakeNvml()
        library.fail_energy = True
        backend = NvidiaBackend(library)
        backend._count = 1
        sample = backend.sample(10)
        expected = 10000 / FROM_MW_TO_KWH * 10
        self.assertAlmostEqual(sample.kwh, expected)
        self.assertEqual(sample.method, "nvml_power")

        def runner(argv):
            command = " ".join(argv)
            if "power.draw" in command:
                return "Board GPU, 36.0\n"
            if "compute-apps" in command:
                return "999999\n"
            return None

        smi = NvidiaSmiBackend(parse_nvidia_smi_power("Board GPU, 36.0\n"), runner)
        sample = smi.sample(10)
        self.assertEqual(sample.method, "nvml_not_used")
        self.assertEqual(sample.kwh, 0.0)
        sample = NvidiaSmiBackend([("Board GPU", 36.0)], lambda argv: None).sample(10)
        self.assertAlmostEqual(sample.kwh, 36.0 * 10 / WATTS_TO_KWH)
        self.assertEqual(sample.method, "nvml_power")

    def test_amd_power_integration(self):
        payload = json.dumps({"card0": {"Average Graphics Package Power (W)": "36.0"}})

        def runner(argv):
            if argv[:2] == ["rocm-smi", "--showpower"]:
                return payload
            return None

        backend = try_open_amd(runner)
        self.assertIsNotNone(backend)
        sample = backend.sample(10)
        self.assertEqual(sample.method, "amd_power")
        self.assertAlmostEqual(sample.kwh, 36.0 * 10 / WATTS_TO_KWH)
        names, watts, _energies = parse_amd_sample(payload)
        self.assertEqual(names, ["card0"])
        self.assertEqual(watts, [36.0])

    def test_amd_energy_counter(self):
        first = json.dumps({"card0": {"Energy (uJ)": 0}})
        second = json.dumps({"card0": {"Energy (uJ)": 3600000000000}})
        calls = {"n": 0}

        def runner(argv):
            if argv[:2] == ["rocm-smi", "--showpower"]:
                calls["n"] += 1
                if calls["n"] < 3:
                    return first
                return second
            return None

        backend = try_open_amd(runner)
        self.assertEqual(backend.sample(10).kwh, 0.0)
        sample = backend.sample(10)
        self.assertEqual(sample.method, "amd_energy")
        self.assertAlmostEqual(sample.kwh, 1.0)

    def test_ascend_power(self):
        def runner(argv):
            if argv[:1] == ["npu-smi"] and argv[-1] == "0":
                return "NPU ID : 0\nPower (W) : 72.5\n"
            return None

        backend = try_open_huawei(runner)
        self.assertEqual(backend.device_count(), 1)
        sample = backend.sample(10)
        self.assertEqual(sample.method, "ascend_power")
        self.assertAlmostEqual(sample.kwh, 72.5 * 10 / WATTS_TO_KWH)

    def test_tpu_estimate_and_unknown_chip(self):
        def known(argv):
            if argv == ["tpu-info"]:
                return "Chip type: TPU v4\nDuty cycle: 50%\n"
            return None

        backend = try_open_google(known)
        self.assertEqual(backend.device_name(), "TPU v4")
        sample = backend.sample(10)
        self.assertEqual(sample.method, "tpu_tdp_duty")
        expected = TPU_CHIP_WATTS["v4"] * 0.5 * 10 / WATTS_TO_KWH
        self.assertAlmostEqual(sample.kwh, expected)

        def unknown(argv):
            if argv == ["tpu-info"]:
                return "Chip type: TPU v9z\nDuty cycle: 80%\n"
            return None

        backends, notes = open_backends(
            devices=[Device("google", "TPU", False)],
            rapl_present=False,
            runner=unknown,
            nvml_library=False,
        )
        self.assertEqual(backends, [])
        self.assertEqual(notes, [])

    def test_intel_arc_is_measured_when_rapl_exists(self):
        def runner(argv):
            if argv[:2] == ["xpu-smi", "discovery"]:
                return "| 0 | Device Name: Intel(R) Arc(TM) A770 |\n"
            if argv[:2] == ["xpu-smi", "dump"]:
                return "GPU Power (W): 40\n"
            return None

        backends, _notes = open_backends(
            devices=[Device("intel", "", None)],
            rapl_present=True,
            runner=runner,
            nvml_library=False,
        )
        self.assertEqual(len(backends), 1)
        sample = backends[0].sample(10)
        self.assertEqual(sample.method, "intel_power")
        self.assertAlmostEqual(sample.kwh, 40 * 10 / WATTS_TO_KWH)

    def test_joined_method_label(self):
        nvidia = NvidiaBackend(FakeNvml())
        amd_payload = json.dumps({"card0": {"Average Graphics Package Power (W)": "10"}})

        def runner(argv):
            if argv[:2] == ["rocm-smi", "--showpower"]:
                return amd_payload
            return None

        amd = try_open_amd(runner)
        gpu = GPU(ignore_warnings=True, backends=[nvidia, amd])
        gpu.calculate_consumption()
        self.assertEqual(gpu.power_method_label(), "method:nvml_energy+amd_power")
        self.assertEqual(gpu.gpu_num(), 2)

    def test_missing_accelerator_warns(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            GPU(ignore_warnings=False, backends=[])
        self.assertTrue(any(item.category is NoGPUWarning for item in caught))

    def _pci(self, root, address, vendor, class_id, name):
        folder = os.path.join(root, address)
        os.makedirs(folder)
        for filename, contents in (
            ("vendor", vendor),
            ("class", class_id),
            ("name", name),
        ):
            with open(os.path.join(folder, filename), "w", encoding="utf-8") as handle:
                handle.write(contents + "\n")


if __name__ == "__main__":
    unittest.main()
