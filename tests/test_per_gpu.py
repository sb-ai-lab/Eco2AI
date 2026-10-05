import os
import unittest
from unittest.mock import patch

from eco2ai.tools.tools_gpu import GPU

ONE_WH_MJ = 3_600_000


class FakeNvml:
    def __init__(self):
        self.energies = [0, 0]
        self.powers = [0, 0]
        self.count = 2
        self.names = [b"NVIDIA A100", b"NVIDIA A100"]
        self.clients = [set(), set()]

    def nvmlInit(self):
        return None

    def nvmlShutdown(self):
        return None

    def nvmlDeviceGetCount(self):
        return self.count

    def nvmlDeviceGetHandleByIndex(self, index):
        return index

    def nvmlDeviceGetTotalEnergyConsumption(self, handle):
        return self.energies[handle]

    def nvmlDeviceGetPowerUsage(self, handle):
        return self.powers[handle]

    def nvmlDeviceGetName(self, handle):
        return self.names[handle]

    def nvmlDeviceGetComputeRunningProcesses(self, handle):
        return [type("Info", (), {"pid": pid})() for pid in self.clients[handle]]

    def nvmlDeviceGetGraphicsRunningProcesses(self, handle):
        return []


def open_gpu(fake):
    names = (
        "nvmlInit",
        "nvmlShutdown",
        "nvmlDeviceGetCount",
        "nvmlDeviceGetHandleByIndex",
        "nvmlDeviceGetTotalEnergyConsumption",
        "nvmlDeviceGetPowerUsage",
        "nvmlDeviceGetName",
        "nvmlDeviceGetComputeRunningProcesses",
        "nvmlDeviceGetGraphicsRunningProcesses",
    )
    started = []
    with patch("eco2ai.tools.tools_gpu.is_gpu_available", return_value=True):
        gpu = GPU(ignore_warnings=True)
    for name in names:
        item = patch("eco2ai.tools.tools_gpu.pynvml." + name, getattr(fake, name))
        item.start()
        started.append(item)
    return gpu, started


class PerGpuTests(unittest.TestCase):
    def test_only_the_device_this_process_uses_is_counted(self):
        fake = FakeNvml()
        gpu, started = open_gpu(fake)
        try:
            fake.clients = [{os.getpid()}, set()]
            gpu.calculate_consumption()
            fake.energies = [ONE_WH_MJ, ONE_WH_MJ]
            self.assertAlmostEqual(gpu.calculate_consumption(), 0.001, delta=1e-12)
            self.assertEqual(gpu.power_method_label(), "method:nvml_energy")
            self.assertEqual(gpu.gpu_num(), 2)
        finally:
            for item in started:
                item.stop()

    def test_no_context_records_zero(self):
        fake = FakeNvml()
        gpu, started = open_gpu(fake)
        try:
            gpu.calculate_consumption()
            fake.energies = [ONE_WH_MJ, ONE_WH_MJ]
            self.assertEqual(gpu.calculate_consumption(), 0.0)
            self.assertEqual(gpu.power_method_label(), "method:nvml_not_used")
        finally:
            for item in started:
                item.stop()

    def test_unknown_process_list_keeps_every_device(self):
        fake = FakeNvml()
        gpu, started = open_gpu(fake)
        query = patch(
            "eco2ai.tools.tools_gpu.GPU._used_device_indexes",
            return_value=None,
        )
        query.start()
        try:
            gpu.calculate_consumption()
            fake.energies = [ONE_WH_MJ, ONE_WH_MJ]
            self.assertAlmostEqual(gpu.calculate_consumption(), 0.002, delta=1e-12)
        finally:
            query.stop()
            for item in started:
                item.stop()


if __name__ == "__main__":
    unittest.main()
