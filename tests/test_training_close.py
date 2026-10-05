import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from eco2ai.emission_track import Tracker


class Part:
    def __init__(self, samples, method="tdp", name="device", available=False):
        self.samples = list(samples)
        self.calls = 0
        self.is_gpu_available = available
        self.closed = False
        self._method = method
        self._name = name

    def calculate_consumption(self):
        value = self.samples[min(self.calls, len(self.samples) - 1)]
        self.calls += 1
        return value

    def name(self):
        return self._name

    def cpu_num(self):
        return 1

    def gpu_num(self):
        return 1

    def tdp(self):
        return 45

    def power_method_label(self):
        return "method:" + self._method

    def close(self):
        self.closed = True


class TrainingCloseTests(unittest.TestCase):
    def setUp(self):
        self._output = tempfile.TemporaryDirectory()
        self._home = tempfile.TemporaryDirectory()
        config = os.path.join(self._home.name, "config.txt")
        self._config = patch("eco2ai.utils.user_config_path", return_value=config)
        self._config.start()

    def tearDown(self):
        self._config.stop()
        self._output.cleanup()
        self._home.cleanup()

    def _tracker(self, name, **kwargs):
        path = os.path.join(self._output.name, name)
        options = dict(
            project_name="train",
            experiment_description="epochs",
            file_name=path,
            measure_period=3600,
            ignore_warnings=True,
            alpha_2_code="WORLD",
        )
        options.update(kwargs)
        return Tracker(**options)

    def _install(self, tracker, cpu, gpu, ram):
        patches = [
            patch("eco2ai.emission_track.CPU", return_value=cpu),
            patch("eco2ai.emission_track.GPU", return_value=gpu),
            patch("eco2ai.emission_track.RAM", return_value=ram),
        ]
        for item in patches:
            item.start()
        self.addCleanup(lambda: [item.stop() for item in patches])

    def test_stop_training_writes_the_open_epoch(self):
        cpu = Part([0.0, 0.001, 0.004], method="rapl", name="CPU")
        gpu = Part([0.0], available=False)
        ram = Part([0.0])
        tracker = self._tracker("open.csv")
        self._install(tracker, cpu, gpu, ram)
        tracker.start_training(start_epoch=1)
        tracker.new_epoch({"loss": 0.5})
        tracker.stop_training()
        frame = pd.read_csv(tracker.file_name, keep_default_na=False)
        self.assertEqual(len(frame), 2)
        self.assertIn("loss: 0.5", frame.iloc[0]["epoch"])
        self.assertAlmostEqual(float(frame.iloc[0]["power_consumption(kWh)"]), 0.001, delta=1e-12)
        self.assertEqual(frame.iloc[1]["epoch"], "epoch: 2")
        self.assertAlmostEqual(float(frame.iloc[1]["power_consumption(kWh)"]), 0.004, delta=1e-12)
        self.assertTrue(gpu.closed)
        self.assertEqual(tracker._mode, "shut down")

    def test_stop_training_without_new_epoch_writes_one_row(self):
        cpu = Part([0.0, 0.002], method="tdp", name="CPU")
        gpu = Part([0.0], available=False)
        ram = Part([0.0])
        tracker = self._tracker("once.csv")
        self._install(tracker, cpu, gpu, ram)
        tracker.start_training()
        tracker.stop_training()
        frame = pd.read_csv(tracker.file_name, keep_default_na=False)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["epoch"], "epoch: 1")
        self.assertAlmostEqual(float(frame.iloc[0]["power_consumption(kWh)"]), 0.002, delta=1e-12)

    def test_zero_tail_after_new_epoch_is_not_appended(self):
        cpu = Part([0.004, 0.004, 0.004, 0.0], method="rapl", name="CPU")
        gpu = Part([0.0], available=False)
        ram = Part([0.0])
        tracker = self._tracker("tail.csv")
        self._install(tracker, cpu, gpu, ram)
        tracker.start_training(start_epoch=1)
        tracker.new_epoch({"batch": 8})
        tracker.new_epoch({"batch": 16})
        tracker.stop()
        frame = pd.read_csv(tracker.file_name, keep_default_na=False)
        self.assertEqual(len(frame), 2)
        self.assertAlmostEqual(float(frame.iloc[0]["power_consumption(kWh)"]), 0.004, delta=1e-12)
        self.assertAlmostEqual(float(frame.iloc[1]["power_consumption(kWh)"]), 0.004, delta=1e-12)

    def test_run_stop_writes_once_and_second_stop_returns(self):
        cpu = Part([0.0, 0.001], method="tdp", name="CPU")
        gpu = Part([0.0], available=False)
        ram = Part([0.0])
        previous = os.getcwd()
        os.chdir(self._output.name)
        try:
            tracker = Tracker(
                project_name="train",
                experiment_description="epochs",
                file_name="run.csv",
                encode_file="encoded_run.csv",
                measure_period=3600,
                ignore_warnings=True,
                alpha_2_code="WORLD",
            )
            self._install(tracker, cpu, gpu, ram)
            tracker.start()
            try:
                tracker.stop()
                tracker.stop()
            finally:
                if tracker._scheduler.running:
                    tracker._scheduler.shutdown(wait=False)
            frame = pd.read_csv("run.csv", keep_default_na=False)
            encoded_frame = pd.read_csv("encoded_run.csv", keep_default_na=False)
        finally:
            os.chdir(previous)
        self.assertEqual(len(frame), 1)
        self.assertEqual(len(encoded_frame), 1)
        fresh = self._tracker("fresh.csv")
        with self.assertRaises(Exception):
            fresh.stop()


if __name__ == "__main__":
    unittest.main()
