from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot

from .logging_config import get_logger


logger = get_logger("worker")


class WorkerSignals(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    finished = pyqtSignal()
    progress = pyqtSignal(int, str)


class Worker(QRunnable):
    def __init__(
        self,
        function: Callable[..., Any],
        *args: Any,
        provide_progress: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.provide_progress = provide_progress
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self) -> None:
        try:
            kwargs = dict(self.kwargs)
            if self.provide_progress:
                kwargs["progress_callback"] = self.signals.progress.emit
            result = self.function(*self.args, **kwargs)
        except Exception as exc:  # Qt iş parçacığı sınırında kullanıcıya aktarılır.
            logger.exception("Background task failed: %s", self.function.__name__)
            self.signals.failed.emit(str(exc))
        else:
            self.signals.succeeded.emit(result)
        finally:
            self.signals.finished.emit()
