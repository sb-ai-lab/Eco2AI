import os
import tempfile
import unittest
from unittest.mock import patch

from eco2ai.emission_track import Tracker
from eco2ai.utils import get_params, set_params


class ConfigWriteTests(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._config = os.path.join(self._home.name, "config.txt")
        self._patch = patch("eco2ai.utils.user_config_path", return_value=self._config)
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._home.cleanup()

    def test_tracker_construction_does_not_write_defaults(self):
        Tracker(
            project_name="scratch",
            experiment_description="once",
            file_name="scratch.csv",
            measure_period=1,
            ignore_warnings=True,
            alpha_2_code="WORLD",
        )
        self.assertFalse(os.path.isfile(self._config))
        later = Tracker(file_name="real.csv", ignore_warnings=True, alpha_2_code="WORLD")
        self.assertNotEqual(later.project_name, "scratch")
        self.assertEqual(later._measure_period, 10)
        self.assertEqual(later.file_name, "real.csv")

    def test_set_params_is_what_the_next_tracker_reads(self):
        set_params(project_name="Malevich", file_name="emission.csv", measure_period=10)
        self.assertTrue(os.path.isfile(self._config))
        Tracker(project_name="scratch", file_name="scratch.csv", measure_period=1, ignore_warnings=True, alpha_2_code="WORLD")
        self.assertEqual(get_params()["project_name"], "Malevich")
        self.assertEqual(get_params()["measure_period"], 10)
        following = Tracker(ignore_warnings=True, alpha_2_code="WORLD")
        self.assertEqual(following.project_name, "Malevich")
        set_params(project_name="Kandinsky")
        after = Tracker(ignore_warnings=True, alpha_2_code="WORLD")
        self.assertEqual(after.project_name, "Kandinsky")


if __name__ == "__main__":
    unittest.main()
