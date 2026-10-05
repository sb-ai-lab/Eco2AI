"""
Lightning callback for a training fit.

Importing this module loads Lightning. It is not imported by ``import eco2ai``.
"""

try:
    from lightning.pytorch.callbacks import Callback
except ImportError as error:
    raise ImportError(
        "Eco2AICallback needs Lightning. Install it with: pip install lightning"
    ) from error

from eco2ai.emission_track import Tracker


def _metric_value(value):
    item = getattr(value, "item", None)
    if not callable(item):
        return value
    try:
        return item()
    except Exception:
        return value


class Eco2AICallback(Callback):
    """
    Record one emission row per training epoch.

    Fit start calls ``start_training``. Each training-epoch end calls
    ``new_epoch`` with the trainer's logged metrics. Fit end calls ``stop``.
    """

    def __init__(self, tracker=None, **tracker_kwargs):
        super().__init__()
        self.tracker = tracker if tracker is not None else Tracker(**tracker_kwargs)

    def on_fit_start(self, trainer, pl_module):
        self.tracker.start_training()

    def on_train_epoch_end(self, trainer, pl_module):
        metrics = getattr(trainer, "callback_metrics", None) or {}
        self.tracker.new_epoch({key: _metric_value(value) for key, value in dict(metrics).items()})

    def on_fit_end(self, trainer, pl_module):
        self.tracker.stop()
