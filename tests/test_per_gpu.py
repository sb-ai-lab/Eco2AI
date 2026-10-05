import os
import unittest

from eco2ai.tools.gpu.nvidia import NvidiaBackend
from eco2ai.tools.tools_gpu import GPU

ONE_WH_MJ = 3_600_000


class TwoDevices:
    """NVML stand-in with a separate client set on each device."""

    def __init__(self):
        self.energies = [0, 0]
        self.powers = [0, 0]
        self.clients = [set(), set()]
        self.fail_pids = False

    def device_count(self):
        return 2

    def device_name(self, index):
        return b"NVIDIA A100"

    def energy_mj(self, index):
        return self.energies[index]

    def power_mw(self, index):
        return self.powers[index]

    def client_pids(self, index):
        if self.fail_pids:
            return None
        return set(self.clients[index])

    def close(self):
        return None


def open_gpu(library):
    return GPU(ignore_warnings=True, backends=[NvidiaBackend(library)])


class PerGpuTests(unittest.TestCase):
    def test_only_the_device_this_process_uses_is_counted(self):
        library = TwoDevices()
        library.clients = [{os.getpid()}, set()]
        gpu = open_gpu(library)
        gpu.calculate_consumption()
        library.energies = [ONE_WH_MJ, ONE_WH_MJ]
        self.assertAlmostEqual(gpu.calculate_consumption(), 0.001, delta=1e-12)
        self.assertEqual(gpu.power_method_label(), "method:nvml_energy")
        self.assertEqual(gpu.gpu_num(), 2)

    def test_no_context_records_zero(self):
        library = TwoDevices()
        gpu = open_gpu(library)
        gpu.calculate_consumption()
        library.energies = [ONE_WH_MJ, ONE_WH_MJ]
        self.assertEqual(gpu.calculate_consumption(), 0.0)
        self.assertEqual(gpu.power_method_label(), "method:nvml_not_used")

    def test_power_fallback_skips_the_unused_device(self):
        library = TwoDevices()
        library.clients = [{os.getpid()}, set()]
        library.powers = [1000, 1000]

        def no_energy(index):
            raise RuntimeError("no energy")

        library.energy_mj = no_energy
        sample = NvidiaBackend(library).sample(3600)
        self.assertEqual(sample.method, "nvml_power")
        self.assertAlmostEqual(sample.kwh, 0.001, delta=1e-12)

    def test_unknown_process_list_keeps_every_device(self):
        library = TwoDevices()
        library.fail_pids = True
        gpu = open_gpu(library)
        gpu.calculate_consumption()
        library.energies = [ONE_WH_MJ, ONE_WH_MJ]
        self.assertAlmostEqual(gpu.calculate_consumption(), 0.002, delta=1e-12)


if __name__ == "__main__":
    unittest.main()
