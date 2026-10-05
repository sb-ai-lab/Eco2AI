import importlib
import os
import sys
import tempfile
import types
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


class Metric:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


class Trainer:
    def __init__(self, metrics):
        self.callback_metrics = metrics


def _fake_lightning():
    callbacks = types.ModuleType("lightning.pytorch.callbacks")

    class Callback:
        pass

    callbacks.Callback = Callback
    pytorch = types.ModuleType("lightning.pytorch")
    pytorch.callbacks = callbacks
    lightning = types.ModuleType("lightning")
    lightning.pytorch = pytorch
    return {
        "lightning": lightning,
        "lightning.pytorch": pytorch,
        "lightning.pytorch.callbacks": callbacks,
    }


class LightningCallbackTests(unittest.TestCase):
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
            project_name="Malevich",
            experiment_description="fit",
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

    def test_callback_receives_the_written_row(self):
        rows = []
        cpu = Part([0.0, 0.001], method="tdp", name="CPU")
        gpu = Part([0.0], available=False)
        ram = Part([0.0])
        tracker = self._tracker("fit.csv", callback=rows.append)
        self._install(tracker, cpu, gpu, ram)
        tracker.start()
        try:
            tracker.stop()
        finally:
            if tracker._scheduler.running:
                tracker._scheduler.shutdown(wait=False)
        frame = pd.read_csv(tracker.file_name, keep_default_na=False)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(frame), 1)
        self.assertEqual(list(rows[0].keys()), list(frame.columns))
        self.assertEqual(rows[0]["project_name"], "Malevich")
        self.assertAlmostEqual(float(rows[0]["power_consumption(kWh)"]), 0.001, delta=1e-12)

    def test_callback_must_be_callable(self):
        with self.assertRaises(TypeError):
            self._tracker("bad.csv", callback="rows")

    def test_import_eco2ai_does_not_load_lightning(self):
        import eco2ai

        with open(eco2ai.__file__, encoding="utf-8") as handle:
            source = handle.read()
        self.assertNotIn("lightning", source)

    def test_missing_lightning_explains_how_to_install(self):
        saved_lightning = {name: sys.modules.get(name) for name in _fake_lightning()}
        saved_module = sys.modules.pop("eco2ai.lightning", None)
        real_import = __import__

        def guarded(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "lightning" or name.startswith("lightning."):
                raise ImportError("blocked")
            return real_import(name, globals, locals, fromlist, level)

        try:
            for name in saved_lightning:
                sys.modules.pop(name, None)
            with patch("builtins.__import__", guarded):
                with self.assertRaises(ImportError) as caught:
                    importlib.import_module("eco2ai.lightning")
            self.assertIn("pip install lightning", str(caught.exception))
        finally:
            sys.modules.pop("eco2ai.lightning", None)
            for name, module in saved_lightning.items():
                if module is not None:
                    sys.modules[name] = module
                else:
                    sys.modules.pop(name, None)
            if saved_module is not None:
                sys.modules["eco2ai.lightning"] = saved_module

    def test_fit_writes_one_row_per_epoch_and_drops_a_zero_tail(self):
        sys.modules.pop("eco2ai.lightning", None)
        with patch.dict(sys.modules, _fake_lightning(), clear=False):
            lightning = importlib.import_module("eco2ai.lightning")
        rows = []
        cpu = Part([0.0, 0.001, 0.002, 0.0], method="tdp", name="CPU")
        gpu = Part([0.0], available=False)
        ram = Part([0.0])
        callback = lightning.Eco2AICallback(
            project_name="Malevich",
            experiment_description="fit",
            file_name=os.path.join(self._output.name, "epochs.csv"),
            measure_period=3600,
            ignore_warnings=True,
            alpha_2_code="WORLD",
            callback=rows.append,
        )
        self._install(callback.tracker, cpu, gpu, ram)
        trainer = Trainer({"loss": Metric(0.5)})
        callback.on_fit_start(trainer, None)
        callback.on_train_epoch_end(trainer, None)
        trainer.callback_metrics = {"loss": Metric(0.2)}
        callback.on_train_epoch_end(trainer, None)
        callback.on_fit_end(trainer, None)
        frame = pd.read_csv(callback.tracker.file_name, keep_default_na=False)
        self.assertEqual(len(frame), 2)
        self.assertEqual(len(rows), 2)
        self.assertIn("loss: 0.5", frame.iloc[0]["epoch"])
        self.assertIn("loss: 0.2", frame.iloc[1]["epoch"])
        self.assertEqual(frame.iloc[1]["epoch"], "epoch: 2, loss: 0.2, ")
        self.assertAlmostEqual(float(frame.iloc[0]["power_consumption(kWh)"]), 0.001, delta=1e-12)
        self.assertAlmostEqual(float(frame.iloc[1]["power_consumption(kWh)"]), 0.002, delta=1e-12)
        self.assertEqual(callback.tracker._mode, "shut down")


if __name__ == "__main__":
    unittest.main()
