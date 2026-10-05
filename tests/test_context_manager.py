import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from eco2ai.emission_track import Tracker


class Part:
    def __init__(self):
        self.is_gpu_available = False
        self.closed = False

    def calculate_consumption(self):
        return 0.001

    def name(self):
        return "CPU"

    def cpu_num(self):
        return 1

    def gpu_num(self):
        return 0

    def tdp(self):
        return 45

    def power_method_label(self):
        return "method:tdp"

    def close(self):
        self.closed = True


class ContextManagerTests(unittest.TestCase):
    def setUp(self):
        self._output = tempfile.TemporaryDirectory()
        self._home = tempfile.TemporaryDirectory()
        config = os.path.join(self._home.name, "config.txt")
        self._config = patch("eco2ai.utils.user_config_path", return_value=config)
        self._config.start()
        self._devices = [
            patch("eco2ai.emission_track.CPU", return_value=Part()),
            patch("eco2ai.emission_track.GPU", return_value=Part()),
            patch("eco2ai.emission_track.RAM", return_value=Part()),
        ]
        for item in self._devices:
            item.start()

    def tearDown(self):
        for item in self._devices:
            item.stop()
        self._config.stop()
        self._output.cleanup()
        self._home.cleanup()

    def test_with_block_writes_one_row(self):
        path = os.path.join(self._output.name, "run.csv")
        with Tracker(
            project_name="run",
            file_name=path,
            alpha_2_code="WORLD",
            ignore_warnings=True,
            measure_period=3600,
        ) as tracker:
            self.assertIsNotNone(tracker._start_time)
        frame = pd.read_csv(path, keep_default_na=False)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["project_name"], "run")
        self.assertEqual(tracker._mode, "shut down")

    def test_exception_is_written_and_propagates(self):
        path = os.path.join(self._output.name, "oom.csv")
        with self.assertRaises(RuntimeError) as caught:
            with Tracker(
                project_name="run",
                file_name=path,
                alpha_2_code="WORLD",
                ignore_warnings=True,
                measure_period=3600,
            ):
                raise RuntimeError("oom")
        self.assertEqual(str(caught.exception), "oom")
        frame = pd.read_csv(path, keep_default_na=False)
        self.assertEqual(len(frame), 1)


if __name__ == "__main__":
    unittest.main()
