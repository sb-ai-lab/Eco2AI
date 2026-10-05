import os
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from eco2ai import __version__
from eco2ai.emission_track import Tracker


class Part:
    def __init__(self, method="tdp", available=False):
        self.is_gpu_available = available
        self._method = method
        self.closed = False

    def calculate_consumption(self):
        return 0.001 if self.is_gpu_available or self._method == "tdp" else 0.0

    def name(self):
        return "device"

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


class ProvenanceTests(unittest.TestCase):
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

    def _run(self, name, **kwargs):
        path = os.path.join(self._output.name, name)
        cpu = Part(method="tdp")
        gpu = Part(method="nvml_energy", available=True)
        ram = Part(method="ram")
        tracker = Tracker(
            project_name="paper",
            file_name=path,
            measure_period=3600,
            ignore_warnings=True,
            **kwargs,
        )
        patches = [
            patch("eco2ai.emission_track.CPU", return_value=cpu),
            patch("eco2ai.emission_track.GPU", return_value=gpu),
            patch("eco2ai.emission_track.RAM", return_value=ram),
        ]
        for item in patches:
            item.start()
        try:
            tracker.start()
            tracker.stop()
        finally:
            for item in patches:
                item.stop()
            if tracker._scheduler.running:
                tracker._scheduler.shutdown(wait=False)
        return pd.read_csv(path, keep_default_na=False).iloc[0]

    def test_country_region_and_user_factor_columns(self):
        swiss = self._run("ch.csv", alpha_2_code="CH")
        self.assertEqual(swiss["eco2ai_version"], __version__)
        self.assertEqual(swiss["cpu_power_method"], "tdp")
        self.assertEqual(swiss["gpu_power_method"], "nvml_energy")
        self.assertEqual(str(swiss["carbon_year"]), "2025")
        self.assertEqual(swiss["carbon_source"], "ember")
        self.assertEqual(swiss["carbon_basis"], "CO2")
        self.assertIn("method:tdp", swiss["CPU_name"])

        california = self._run("ca.csv", alpha_2_code="US", region="California")
        self.assertEqual(str(california["carbon_year"]), "2023")
        self.assertEqual(california["carbon_source"], "egrid2023")
        self.assertEqual(california["carbon_basis"], "CO2")

        wales = self._run("nsw.csv", alpha_2_code="AU", region="New South Wales")
        self.assertEqual(str(wales["carbon_year"]), "2025")
        self.assertEqual(wales["carbon_source"], "nga2025")
        self.assertEqual(wales["carbon_basis"], "CO2e")

        moscow = self._run("msk.csv", alpha_2_code="RU", region="Moscow")
        self.assertEqual(str(moscow["carbon_year"]), "2021")
        self.assertEqual(moscow["carbon_source"], "russia")
        self.assertEqual(moscow["carbon_basis"], "CO2")

        custom = self._run("custom.csv", emission_level=12.5, alpha_2_code="DE")
        self.assertEqual(custom["carbon_year"], "N/A")
        self.assertEqual(custom["carbon_source"], "user")
        self.assertEqual(custom["carbon_basis"], "user")

    def test_older_rows_gain_na_in_new_columns(self):
        path = os.path.join(self._output.name, "old.csv")
        pd.DataFrame([{"id": "old", "project_name": "old", "power_consumption(kWh)": "1"}]).to_csv(path, index=False)
        cpu = Part()
        gpu = Part(available=False)
        ram = Part(method="ram")
        tracker = Tracker(
            project_name="new",
            file_name=path,
            measure_period=3600,
            ignore_warnings=True,
            alpha_2_code="CH",
        )
        patches = [
            patch("eco2ai.emission_track.CPU", return_value=cpu),
            patch("eco2ai.emission_track.GPU", return_value=gpu),
            patch("eco2ai.emission_track.RAM", return_value=ram),
        ]
        for item in patches:
            item.start()
        try:
            tracker.start()
            tracker.stop()
        finally:
            for item in patches:
                item.stop()
            if tracker._scheduler.running:
                tracker._scheduler.shutdown(wait=False)
        frame = pd.read_csv(path, keep_default_na=False)
        self.assertEqual(frame.loc[0, "carbon_year"], "N/A")
        self.assertEqual(frame.loc[1, "carbon_source"], "ember")
        self.assertEqual(frame.loc[0, "project_name"], "old")


if __name__ == "__main__":
    unittest.main()
