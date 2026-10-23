"""Focused tests for the production project autosave callbacks.

PySide6 is replaced with small signal and timer shims so these tests can run
without starting a desktop session. The autosave callbacks, dirty-state methods,
GenericWorker, and TaskRunnerController are loaded from their production source.
Only UI, filesystem paths, and the project writer are controlled collaborators.
"""

from __future__ import annotations

import ast
import logging
import os
import sys
import tempfile
import unittest
from collections import deque
from pathlib import Path
from types import ModuleType, SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


class _BoundSignal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, *args):
        for callback in self.callbacks:
            callback(*args)


class _Signal:
    def __init__(self, *_args):
        pass

    def __set_name__(self, _owner, name):
        self.name = name

    def __get__(self, instance, _owner=None):
        if instance is None:
            return self
        return instance.__dict__.setdefault(self.name, _BoundSignal())


class _Timer:
    events = deque()

    @classmethod
    def singleShot(cls, *_args):
        cls.events.append(_args[-1])

    @classmethod
    def drain(cls):
        while cls.events:
            cls.events.popleft()()

    @classmethod
    def reset(cls):
        cls.events.clear()


class _RecordingThreadPool:
    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)


class _RecordingTimer:
    def __init__(self):
        self.start_count = 0

    def start(self):
        self.start_count += 1


class _TrackedWorkers(list):
    def __init__(self):
        super().__init__()
        self.remove_count = 0

    def remove(self, worker):
        self.remove_count += 1
        super().remove(worker)


def _install_qt_shims():
    qtcore = ModuleType("PySide6.QtCore")
    qtcore.QRunnable = type("QRunnable", (), {})
    qtcore.QObject = object
    qtcore.Signal = _Signal
    qtcore.QTimer = _Timer
    qtcore.QCoreApplication = type(
        "QCoreApplication",
        (),
        {"translate": staticmethod(lambda _context, text: text)},
    )

    pyside = ModuleType("PySide6")
    pyside.__path__ = []
    pyside.QtCore = qtcore
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtCore"] = qtcore
    return qtcore


def _load_production_class(source_path, class_name, method_names, globals_dict):
    tree = ast.parse(source_path.read_text(encoding="utf-8-sig"))
    original_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    methods = [
        node
        for node in original_class.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name in method_names
    ]
    selected_class = ast.ClassDef(
        name=class_name,
        bases=[],
        keywords=[],
        body=methods,
        decorator_list=[],
    )
    module = ast.fix_missing_locations(ast.Module(body=[selected_class], type_ignores=[]))
    exec(compile(module, str(source_path), "exec"), globals_dict)
    return globals_dict[class_name]


_QTCORE = _install_qt_shims()

_worker_namespace = {}
_worker_path = ROOT / "app/thread_worker.py"
exec(
    compile(_worker_path.read_text(encoding="utf-8-sig"), str(_worker_path), "exec"),
    _worker_namespace,
)
GenericWorker = _worker_namespace["GenericWorker"]
_thread_worker_module = ModuleType("app.thread_worker")
_thread_worker_module.GenericWorker = GenericWorker
sys.modules["app.thread_worker"] = _thread_worker_module

_task_runner_namespace = {}
_task_runner_path = ROOT / "app/controllers/task_runner.py"
exec(
    compile(
        _task_runner_path.read_text(encoding="utf-8-sig"),
        str(_task_runner_path),
        "exec",
    ),
    _task_runner_namespace,
)
TaskRunnerController = _task_runner_namespace["TaskRunnerController"]


class _MessageSink:
    def __init__(self):
        self.errors = []

    def error(self, **kwargs):
        self.errors.append(kwargs)


class _Harness:
    def __init__(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        folder = Path(self.temp_dir.name)
        self.project_path = folder / "comic.ctpr"
        self.recovery_path = folder / "project_recovery.ctpr"
        self.recovery_path.write_text("last successful recovery", encoding="utf-8")
        self.write_outcomes = deque()
        self.save_targets = []
        self.recent_projects = []
        self.refresh_count = 0
        self.clean_count = 0
        self.errors = _MessageSink()

        self.main = _load_production_class(
            ROOT / "controller.py",
            "ComicTranslate",
            {"_any_undo_dirty", "has_unsaved_changes", "set_project_clean"},
            {},
        )()
        self.main._manual_dirty = True
        self.main._dirty_revision = 5
        self.main.undo_stacks = {}
        self.main._update_window_modified = lambda: None
        self.main.image_files = ["page.png"]
        self.main._batch_active = False
        self.main.project_file = str(self.project_path)
        self.main.text_ctrl = SimpleNamespace(_commit_pending_text_command=lambda: None)
        self.main.settings_page = SimpleNamespace(
            get_export_settings=lambda: {"project_autosave_enabled": True}
        )
        self.main.tr = lambda text: text
        self.main.threadpool = _RecordingThreadPool()
        original_set_clean = self.main.set_project_clean

        def count_set_clean():
            self.clean_count += 1
            original_set_clean()

        self.main.set_project_clean = count_set_clean

        runner = TaskRunnerController(self.main)
        self.main.run_threaded = runner.run_threaded

        self.project = _load_production_class(
            ROOT / "app/controllers/projects.py",
            "ProjectController",
            {
                "_show_autosave_failure",
                "_on_batch_page_done",
                "autosave_project",
                "clear_recovery_checkpoint",
            },
            {
                "GenericWorker": GenericWorker,
                "MMessage": self.errors,
                "QtCore": _QTCORE,
                "logger": logging.getLogger("comic-translate.autosave-tests"),
                "os": os,
            },
        )()
        self.project.main = self.main
        self.project._autosave_save_pending = False
        self.project._autosave_retrigger_requested = False
        self.project._active_save_workers = _TrackedWorkers()
        self.project._realtime_autosave_timer = _RecordingTimer()
        self.project._recovery_project_path = lambda: str(self.recovery_path)
        self.project._ensure_autosave_project_file_if_needed = lambda: None
        self.project.save_current_state = lambda: None
        self.project.add_recent_project = self.recent_projects.append
        self.project._refresh_home_screen = self._refresh
        self.project.save_project = self._save_project

    def _refresh(self):
        self.refresh_count += 1

    def _save_project(self, target):
        self.save_targets.append(target)
        outcome = self.write_outcomes.popleft() if self.write_outcomes else None
        if isinstance(outcome, BaseException):
            raise outcome
        Path(target).write_text("saved project", encoding="utf-8")

    def queue_outcome(self, outcome):
        self.write_outcomes.append(outcome)

    def run_worker(self, index=-1):
        _Timer.reset()
        worker = self.main.threadpool.workers[index]
        worker.run()
        _Timer.drain()
        return worker

    def close(self):
        self.temp_dir.cleanup()


class ProjectAutosaveTests(unittest.TestCase):
    def setUp(self):
        _Timer.reset()

    def make_harness(self):
        harness = _Harness()
        self.addCleanup(harness.close)
        return harness

    def test_worker_finished_stays_unconditional_after_error(self):
        worker = GenericWorker(lambda: (_ for _ in ()).throw(OSError("disk full")))
        calls = []
        worker.signals.error.connect(lambda _error: calls.append("error"))
        worker.signals.finished.connect(lambda: calls.append("finished"))

        worker.run()

        self.assertEqual(calls, ["error", "finished"])

    def test_regular_save_failures_keep_dirty_state_and_recovery(self):
        failures = (
            OSError(28, "No space left on device"),
            PermissionError("permission denied"),
            ValueError("serialization failed"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                harness = self.make_harness()
                harness.queue_outcome(failure)
                harness.project.autosave_project()
                worker = harness.main.threadpool.workers[0]

                worker.run()
                self.assertTrue(harness.project._autosave_save_pending)
                _Timer.drain()

                self.assertFalse(harness.project._autosave_save_pending)
                self.assertTrue(harness.main.has_unsaved_changes())
                self.assertTrue(harness.recovery_path.exists())
                self.assertEqual(harness.clean_count, 0)
                self.assertEqual(harness.recent_projects, [])
                self.assertEqual(harness.refresh_count, 0)
                self.assertEqual(harness.errors.errors[0]["parent"], harness.main)
                self.assertIn("still unsaved", harness.errors.errors[0]["text"])
                self.assertEqual(harness.project._realtime_autosave_timer.start_count, 0)

    def test_regular_success_cleans_once_and_clears_recovery(self):
        harness = self.make_harness()
        harness.project.autosave_project()
        harness.run_worker()

        self.assertEqual(harness.clean_count, 1)
        self.assertFalse(harness.main.has_unsaved_changes())
        self.assertFalse(harness.recovery_path.exists())
        self.assertEqual(harness.recent_projects, [str(harness.project_path)])
        self.assertEqual(harness.refresh_count, 1)
        self.assertFalse(harness.project._autosave_save_pending)

    def test_success_during_new_edit_keeps_new_revision_dirty_and_recovery(self):
        for path in ("regular", "batch"):
            with self.subTest(path=path):
                harness = self.make_harness()
                if path == "regular":
                    harness.project.autosave_project()
                else:
                    harness.project._on_batch_page_done("page.png")
                harness.main._dirty_revision += 1
                harness.run_worker()

                self.assertTrue(harness.main.has_unsaved_changes())
                self.assertEqual(harness.clean_count, 0)
                self.assertTrue(harness.recovery_path.exists())
                self.assertEqual(harness.recent_projects, [str(harness.project_path)])
                self.assertEqual(harness.refresh_count, 1)

    def test_regular_failed_save_can_retry_once_and_then_succeed(self):
        harness = self.make_harness()
        harness.queue_outcome(OSError(28, "disk full"))
        harness.project.autosave_project()
        harness.project.autosave_project()  # Coalesced while the first save is active.
        harness.run_worker(0)

        self.assertTrue(harness.main.has_unsaved_changes())
        self.assertTrue(harness.recovery_path.exists())
        self.assertEqual(harness.project._realtime_autosave_timer.start_count, 1)
        self.assertFalse(harness.project._autosave_save_pending)

        harness.project.autosave_project()
        harness.run_worker(1)

        self.assertFalse(harness.main.has_unsaved_changes())
        self.assertFalse(harness.recovery_path.exists())
        self.assertEqual(harness.clean_count, 1)
        self.assertEqual(len(harness.errors.errors), 1)
        self.assertEqual(harness.project._realtime_autosave_timer.start_count, 1)

    def test_batch_failures_release_reference_once_without_retry_loop(self):
        failures = (
            OSError(28, "No space left on device"),
            PermissionError("permission denied"),
            ValueError("serialization failed"),
        )
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                harness = self.make_harness()
                harness.queue_outcome(failure)
                harness.project._on_batch_page_done("page-a.png")
                harness.project._on_batch_page_done("page-b.png")
                worker = harness.main.threadpool.workers[0]

                worker.run()
                self.assertTrue(harness.project._autosave_save_pending)
                _Timer.drain()

                self.assertFalse(harness.project._autosave_save_pending)
                self.assertEqual(harness.project._active_save_workers.remove_count, 1)
                self.assertEqual(harness.project._active_save_workers, [])
                self.assertEqual(len(harness.main.threadpool.workers), 1)
                self.assertFalse(harness.project._autosave_retrigger_requested)
                self.assertTrue(harness.main.has_unsaved_changes())
                self.assertTrue(harness.recovery_path.exists())
                self.assertEqual(harness.clean_count, 0)
                self.assertEqual(harness.errors.errors[0]["parent"], harness.main)

    def test_batch_success_cleans_once_and_releases_reference(self):
        harness = self.make_harness()
        harness.project._on_batch_page_done("page-a.png")
        harness.run_worker()

        self.assertEqual(harness.project._active_save_workers.remove_count, 1)
        self.assertEqual(harness.project._active_save_workers, [])
        self.assertFalse(harness.project._autosave_save_pending)
        self.assertEqual(harness.clean_count, 1)
        self.assertFalse(harness.main.has_unsaved_changes())
        self.assertFalse(harness.recovery_path.exists())
        self.assertEqual(harness.recent_projects, [str(harness.project_path)])
        self.assertEqual(harness.refresh_count, 1)

    def test_batch_failure_is_retryable_on_later_page(self):
        harness = self.make_harness()
        harness.queue_outcome(OSError(28, "disk full"))
        harness.project._on_batch_page_done("page-a.png")
        harness.run_worker(0)

        self.assertEqual(len(harness.main.threadpool.workers), 1)
        self.assertTrue(harness.recovery_path.exists())
        self.assertTrue(harness.main.has_unsaved_changes())
        self.assertEqual(harness.project._active_save_workers.remove_count, 1)

        harness.project._on_batch_page_done("page-b.png")
        harness.run_worker(1)

        self.assertEqual(harness.project._active_save_workers.remove_count, 2)
        self.assertEqual(harness.project._active_save_workers, [])
        self.assertFalse(harness.main.has_unsaved_changes())
        self.assertFalse(harness.recovery_path.exists())
        self.assertEqual(harness.clean_count, 1)

    def test_recovery_only_success_keeps_existing_recovery_behavior(self):
        harness = self.make_harness()
        harness.project.autosave_project(prefer_project_file=False)
        harness.run_worker()

        self.assertTrue(harness.recovery_path.exists())
        self.assertTrue(harness.main.has_unsaved_changes())
        self.assertEqual(harness.clean_count, 0)
        self.assertEqual(harness.recent_projects, [])
        self.assertEqual(harness.refresh_count, 0)


if __name__ == "__main__":
    unittest.main()
