import json
import os
import tempfile
import unittest
from unittest.mock import patch

from eco2ai.utils import define_carbon_index


class CarbonOfflineTests(unittest.TestCase):
    def setUp(self):
        self._home = tempfile.TemporaryDirectory()
        self._config = os.path.join(self._home.name, "config.txt")
        self._patch = patch("eco2ai.utils.user_config_path", return_value=self._config)
        self._patch.start()
        self._env = patch.dict(os.environ, {}, clear=False)
        self._env.start()
        os.environ.pop("ECO2AI_ALPHA2", None)

    def tearDown(self):
        self._env.stop()
        self._patch.stop()
        self._home.cleanup()

    def test_env_skips_the_network(self):
        os.environ["ECO2AI_ALPHA2"] = "CH"
        with patch("eco2ai.utils.requests.get") as request:
            value, label = define_carbon_index()
        request.assert_not_called()
        self.assertEqual(label, "CH")
        self.assertAlmostEqual(float(value), 39.220, delta=1e-9)

    def test_failed_request_uses_the_cache(self):
        cache = os.path.join(self._home.name, "location.json")
        with open(cache, "w", encoding="utf-8") as handle:
            json.dump({"country": "CH", "region": "Ticino"}, handle)
        with patch("eco2ai.utils.requests.get", side_effect=OSError("offline")):
            value, label = define_carbon_index()
        self.assertEqual(label, "CH/Ticino")
        self.assertAlmostEqual(float(value), 39.220, delta=1e-9)

    def test_offline_without_cache_uses_the_world_row(self):
        with patch("eco2ai.utils.requests.get", side_effect=OSError("offline")):
            with self.assertWarns(UserWarning):
                value, label = define_carbon_index()
        self.assertEqual(label, "WORLD")
        self.assertAlmostEqual(float(value), 458.490, delta=1e-9)

    def test_explicit_code_skips_network_and_cache(self):
        cache = os.path.join(self._home.name, "location.json")
        with open(cache, "w", encoding="utf-8") as handle:
            json.dump({"country": "CH", "region": "Ticino"}, handle)
        with patch("eco2ai.utils.requests.get") as request:
            value, label = define_carbon_index(alpha_2_code="DE")
        request.assert_not_called()
        self.assertEqual(label, "DE")
        self.assertGreater(float(value), 0)

    def test_successful_lookup_is_cached(self):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"country": "CH", "region": "Ticino"}

        with patch("eco2ai.utils.requests.get", return_value=Response()) as request:
            define_carbon_index()
        request.assert_called_once()
        self.assertIn("timeout", request.call_args.kwargs)
        cache = os.path.join(self._home.name, "location.json")
        with open(cache, encoding="utf-8") as handle:
            saved = json.load(handle)
        self.assertEqual(saved["country"], "CH")
        self.assertEqual(saved["region"], "Ticino")


if __name__ == "__main__":
    unittest.main()
