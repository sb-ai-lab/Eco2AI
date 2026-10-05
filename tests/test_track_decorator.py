import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from eco2ai.emission_track import Tracker, track


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


class TrackDecoratorTests(unittest.TestCase):
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

    def test_exception_propagates_and_one_row_is_written(self):
        path = os.path.join(self._output.name, "oom.csv")

        @track(project_name="Malevich", file_name=path, alpha_2_code="WORLD", ignore_warnings=True, measure_period=3600)
        def train():
            raise RuntimeError("oom")

        with self.assertRaises(RuntimeError) as caught:
            train()
        self.assertEqual(str(caught.exception), "oom")
        frame = pd.read_csv(path, keep_default_na=False)
        self.assertEqual(len(frame), 1)
        self.assertEqual(frame.iloc[0]["project_name"], "Malevich")

    def test_decorator_keywords_are_not_passed_to_the_function(self):
        path = os.path.join(self._output.name, "run.csv")
        seen = {}

        @track(project_name="Malevich", file_name=path, alpha_2_code="WORLD", ignore_warnings=True, measure_period=3600)
        def train(model, epochs):
            seen["args"] = (model, epochs)
            return epochs

        self.assertEqual(train("net", 2), 2)
        self.assertEqual(seen["args"], ("net", 2))
        frame = pd.read_csv(path, keep_default_na=False)
        self.assertEqual(frame.iloc[0]["project_name"], "Malevich")

    def test_bare_decorator_uses_a_tracker(self):
        class Response:
            content = b'{"country": "CH", "region": "Ticino"}'

        @track
        def work():
            return "ok"

        with patch("eco2ai.utils.requests.get", return_value=Response()):
            self.assertEqual(work(), "ok")


if __name__ == "__main__":
    unittest.main()
