from __future__ import annotations

from collections import deque
import logging
import traceback
from typing import TYPE_CHECKING, Callable

from PySide6 import QtCore
from PySide6.QtCore import QCoreApplication

from app.thread_worker import GenericWorker

if TYPE_CHECKING:
    from controller import ComicTranslate


logger = logging.getLogger(__name__)


class TaskRunnerController:
    def __init__(self, main: ComicTranslate):
        self.main = main
        self.operation_queue = deque()
        self.is_processing_queue = False

    def run_threaded(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        return self._queue_operation(
            callback,
            result_callback,
            error_callback,
            finished_callback,
            *args,
            **kwargs,
        )

    def _queue_operation(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        operation = {
            "callback": callback,
            "result_callback": result_callback,
            "error_callback": error_callback,
            "finished_callback": finished_callback,
            "args": args,
            "kwargs": kwargs,
        }

        self.operation_queue.append(operation)
        if not self.is_processing_queue:
            self._process_next_operation()

    def _process_next_operation(self):
        if not self.operation_queue:
            self.is_processing_queue = False
            return

        self.is_processing_queue = True
        operation = self.operation_queue.popleft()
        completion = {"scheduled": False}

        def schedule_next_operation():
            if completion["scheduled"]:
                return
            completion["scheduled"] = True
            QtCore.QTimer.singleShot(0, self.main, self._process_next_operation)

        def enhanced_finished_callback():
            try:
                self._invoke_callback(
                    operation["finished_callback"], callback_name="finished"
                )
            finally:
                schedule_next_operation()

        def enhanced_error_callback(error_tuple):
            self._invoke_callback(
                operation["error_callback"], error_tuple, callback_name="error"
            )

        def enhanced_result_callback(result):
            self._invoke_callback(
                operation["result_callback"], result, callback_name="result"
            )

        try:
            self._execute_single_operation(
                operation["callback"],
                enhanced_result_callback,
                enhanced_error_callback,
                enhanced_finished_callback,
                *operation["args"],
                **operation["kwargs"],
            )
        except Exception as error:
            logger.exception("Failed to start queued operation")
            self._invoke_callback(
                operation["error_callback"],
                (type(error), error, traceback.format_exc()),
                callback_name="error",
            )
            schedule_next_operation()

    @staticmethod
    def _invoke_callback(callback, *args, callback_name: str):
        """Log and suppress UI callback errors so worker cleanup can continue."""
        if not callback:
            return
        try:
            callback(*args)
        except Exception:
            logger.exception("Task %s callback raised an exception", callback_name)

    def _execute_single_operation(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        worker = GenericWorker(callback, *args, **kwargs)

        if result_callback:
            worker.signals.result.connect(
                lambda result: QtCore.QTimer.singleShot(
                    0,
                    self.main,
                    lambda: self._invoke_callback(
                        result_callback, result, callback_name="result"
                    ),
                )
            )
        if error_callback:
            worker.signals.error.connect(
                lambda error: QtCore.QTimer.singleShot(
                    0,
                    self.main,
                    lambda: self._invoke_callback(
                        error_callback, error, callback_name="error"
                    ),
                )
            )
        if finished_callback:
            worker.signals.finished.connect(
                lambda: QtCore.QTimer.singleShot(
                    0,
                    self.main,
                    lambda: self._invoke_callback(
                        finished_callback, callback_name="finished"
                    ),
                )
            )

        self.main.current_worker = worker
        self.main.threadpool.start(worker)

    def run_threaded_immediate(
        self,
        callback: Callable,
        result_callback: Callable = None,
        error_callback: Callable = None,
        finished_callback: Callable = None,
        *args,
        **kwargs,
    ):
        return self._execute_single_operation(
            callback,
            result_callback,
            error_callback,
            finished_callback,
            *args,
            **kwargs,
        )

    def clear_operation_queue(self):
        self.operation_queue.clear()

    def cancel_current_task(self):
        if self.main.current_worker:
            self.main.current_worker.cancel()

        if self.main._batch_active:
            self.main._batch_cancel_requested = True
            self.main.cancel_button.setEnabled(False)
            self.main.progress_bar.setFormat(
                QCoreApplication.translate("Messages", "Cancelling... %p%")
            )

        self.clear_operation_queue()

    def run_finish_only(
        self, finished_callback: Callable, error_callback: Callable = None
    ):
        def _noop():
            pass

        self._queue_operation(
            callback=_noop,
            result_callback=None,
            error_callback=error_callback,
            finished_callback=finished_callback,
        )
