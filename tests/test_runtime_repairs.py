"""Regression coverage for the queue, export, and macOS build entry points.

Queue and export orchestration are loaded from their production source. Tiny
Qt signal/timer shims make callback order deterministic without starting a
desktop event loop. Export tests use a small renderer but the production
save_and_make_worker and ZIP packager, so they inspect the actual staged pages
and archive entries.
"""

from __future__ import annotations

import ast
import logging
import os
import re
import shutil
import sys
import subprocess
import tempfile
import threading
import unittest
import zipfile
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


class _ThreadPool:
    def __init__(self):
        self.workers = []

    def start(self, worker):
        self.workers.append(worker)


def _load_queue_classes():
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

    worker_path = ROOT / "app/thread_worker.py"
    worker_namespace = {}
    exec(
        compile(worker_path.read_text(encoding="utf-8-sig"), str(worker_path), "exec"),
        worker_namespace,
    )
    worker_module = ModuleType("app.thread_worker")
    worker_module.GenericWorker = worker_namespace["GenericWorker"]
    sys.modules["app.thread_worker"] = worker_module

    runner_path = ROOT / "app/controllers/task_runner.py"
    queue_logger = logging.getLogger("comic-translate.queue-tests")
    queue_logger.addHandler(logging.NullHandler())
    queue_logger.propagate = False
    runner_namespace = {"__name__": queue_logger.name}
    exec(
        compile(runner_path.read_text(encoding="utf-8-sig"), str(runner_path), "exec"),
        runner_namespace,
    )
    return worker_namespace["GenericWorker"], runner_namespace["TaskRunnerController"]


GenericWorker, TaskRunnerController = _load_queue_classes()


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
        if isinstance(node, ast.FunctionDef) and node.name in method_names
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


class _Renderer:
    def __init__(self, image):
        self.image = image

    def apply_patches(self, _patches):
        pass

    def add_state_to_image(self, _state):
        pass

    def save_image(self, path):
        Path(path).write_bytes(self.image.encode("utf-8"))


def _load_export_methods():
    project_path = ROOT / "app/controllers/projects.py"
    project_class = _load_production_class(
        project_path,
        "ProjectController",
        {"_build_export_page_name", "save_and_make_worker"},
        {
            "ImageSaveRenderer": _Renderer,
            "logger": logging.getLogger("comic-translate.export-tests"),
            "make": _load_zip_packager(),
            "os": os,
            "re": re,
            "shutil": shutil,
            "tempfile": tempfile,
        },
    )
    return project_class


def _load_zip_packager():
    archive_path = ROOT / "modules/utils/archives.py"
    tree = ast.parse(archive_path.read_text(encoding="utf-8-sig"))
    selected = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"natural_sort_key", "is_image_file", "make_cbz", "make"}
    }
    module = ast.fix_missing_locations(
        ast.Module(
            body=[
                selected[name]
                for name in ("natural_sort_key", "is_image_file", "make_cbz", "make")
            ],
            type_ignores=[],
        )
    )
    namespace = {
        "_IMAGE_EXTENSIONS": (".jpg", ".jpeg", ".png", ".bmp", ".webp", ".avif"),
        "os": os,
        "re": re,
        "zipfile": zipfile,
    }
    exec(compile(module, str(archive_path), "exec"), namespace)
    return namespace["make"]


ProjectController = _load_export_methods()


class TaskRunnerTests(unittest.TestCase):
    def setUp(self):
        _Timer.reset()
        self.pool = _ThreadPool()
        self.main = SimpleNamespace(
            threadpool=self.pool,
            current_worker=None,
            _batch_active=False,
            _batch_cancel_requested=False,
        )
        self.runner = TaskRunnerController(self.main)
        self.started = []
        self.finished = []

    def _job(self, name, fail=False):
        def run():
            self.started.append(name)
            if fail:
                raise RuntimeError(name)
            return name

        return run

    def _run_worker(self, index=-1):
        self.pool.workers[index].run()
        _Timer.drain()

    def test_failed_job_advances_one_at_a_time(self):
        self.runner.run_threaded(
            self._job("A", fail=True),
            error_callback=lambda _error: self.finished.append("A:error"),
            finished_callback=lambda: self.finished.append("A:finished"),
        )
        self.runner.run_threaded(self._job("B"), finished_callback=lambda: self.finished.append("B"))
        self.runner.run_threaded(self._job("C"), finished_callback=lambda: self.finished.append("C"))
        self.assertEqual(len(self.pool.workers), 1)

        self._run_worker(0)
        self.assertEqual(len(self.pool.workers), 2)
        self.assertEqual(self.started, ["A"])
        self.assertEqual(self.finished, ["A:error", "A:finished"])

        self._run_worker(1)
        self.assertEqual(len(self.pool.workers), 3)
        self.assertEqual(self.started, ["A", "B"])
        self._run_worker(2)
        self.assertEqual(self.started, ["A", "B", "C"])
        self.assertEqual(self.finished, ["A:error", "A:finished", "B", "C"])
        self.assertFalse(self.runner.is_processing_queue)

    def test_success_path_and_later_enqueue_run_once(self):
        for name in ("A", "B", "C"):
            self.runner.run_threaded(self._job(name))
        self._run_worker(0)
        self.assertEqual(len(self.pool.workers), 2)
        self._run_worker(1)
        self.assertEqual(len(self.pool.workers), 3)
        self._run_worker(2)
        self.assertFalse(self.runner.is_processing_queue)

        self.runner.run_threaded(self._job("D"))
        self.assertEqual(len(self.pool.workers), 4)
        self._run_worker(3)
        self.assertEqual(self.started, ["A", "B", "C", "D"])

    def test_failure_drains_queue_and_later_enqueue_starts_once(self):
        self.runner.run_threaded(self._job("A"))
        self.runner.run_threaded(self._job("B", fail=True))
        self._run_worker(0)
        self.assertEqual(len(self.pool.workers), 2)
        self._run_worker(1)
        self.assertFalse(self.runner.is_processing_queue)

        self.runner.run_threaded(self._job("C"))
        self.assertEqual(len(self.pool.workers), 3)
        self._run_worker(2)
        self.assertEqual(self.started, ["A", "B", "C"])

    def test_duplicate_finished_signal_advances_only_once(self):
        self.runner.run_threaded(self._job("A"))
        self.runner.run_threaded(self._job("B"))
        worker = self.pool.workers[0]

        worker.run()
        worker.signals.finished.emit()
        _Timer.drain()

        self.assertEqual(len(self.pool.workers), 2)
        self.assertEqual(self.started, ["A"])
        self._run_worker(1)
        self.assertEqual(self.started, ["A", "B"])

    def test_callback_exceptions_do_not_duplicate_or_strand_queue(self):
        def broken_callback(*_args):
            raise RuntimeError("callback failed")

        self.runner.run_threaded(
            self._job("A", fail=True),
            error_callback=broken_callback,
            finished_callback=broken_callback,
        )
        self.runner.run_threaded(self._job("B"))
        self.runner.run_threaded(self._job("C"))

        self._run_worker(0)

        self.assertEqual(len(self.pool.workers), 2)
        self.assertEqual(self.started, ["A"])
        self._run_worker(1)
        self.assertEqual(len(self.pool.workers), 3)
        self._run_worker(2)
        self.assertEqual(self.started, ["A", "B", "C"])

    def test_result_callback_exception_does_not_block_queue(self):
        def broken_result(_result):
            raise RuntimeError("result callback failed")

        self.runner.run_threaded(self._job("A"), result_callback=broken_result)
        self.runner.run_threaded(self._job("B"))

        self._run_worker(0)

        self.assertEqual(len(self.pool.workers), 2)
        self.assertEqual(self.started, ["A"])
        self._run_worker(1)
        self.assertEqual(self.started, ["A", "B"])

    def test_cancel_and_clear_keep_new_work_behind_active_worker(self):
        self.runner.run_threaded(self._job("A"))
        self.runner.run_threaded(self._job("discarded"))
        active = self.pool.workers[0]
        entered = threading.Event()
        release = threading.Event()

        def blocking_job():
            self.started.append("A")
            entered.set()
            release.wait(timeout=2)

        active.fn = blocking_job
        self.addCleanup(release.set)
        worker_thread = threading.Thread(target=active.run)
        worker_thread.start()
        self.assertTrue(entered.wait(timeout=1))

        self.runner.cancel_current_task()
        self.assertTrue(self.runner.is_processing_queue)
        self.runner.run_threaded(self._job("C"))
        self.assertEqual(len(self.pool.workers), 1)

        # cancel() does not stop the active callable; it only suppresses results.
        release.set()
        worker_thread.join(timeout=2)
        self.assertFalse(worker_thread.is_alive())
        self.assertEqual(self.started, ["A"])
        self.assertTrue(self.runner.is_processing_queue)
        _Timer.drain()
        self.assertEqual(len(self.pool.workers), 2)
        self._run_worker(1)

        self.assertEqual(self.started, ["A", "C"])
        self.assertFalse(self.runner.is_processing_queue)

    def test_clear_queue_keeps_new_work_behind_active_worker(self):
        self.runner.run_threaded(self._job("A"))
        self.runner.run_threaded(self._job("discarded"))
        active = self.pool.workers[0]

        self.runner.clear_operation_queue()
        self.runner.run_threaded(self._job("C"))
        self.assertTrue(self.runner.is_processing_queue)
        self.assertEqual(len(self.pool.workers), 1)

        self._run_worker(0)
        self.assertEqual(len(self.pool.workers), 2)
        self._run_worker(1)
        self.assertEqual(self.started, ["A", "C"])
        self.assertFalse(self.runner.is_processing_queue)

    def test_immediate_worker_remains_outside_queue_order(self):
        self.runner.run_threaded(self._job("queued-A"))
        self.runner.run_threaded(self._job("queued-B"))
        self.assertIsNone(self.runner.run_threaded_immediate(self._job("immediate")))
        self.assertEqual(len(self.pool.workers), 2)

        self._run_worker(1)
        self.assertEqual(self.started, ["immediate"])
        self._run_worker(0)
        self.assertEqual(self.started, ["immediate", "queued-A"])
        self.assertEqual(len(self.pool.workers), 3)
        self._run_worker(2)
        self.assertEqual(self.started, ["immediate", "queued-A", "queued-B"])


class ExportTests(unittest.TestCase):
    def _controller(self, paths):
        controller = ProjectController()
        controller.main = SimpleNamespace(
            file_handler=SimpleNamespace(should_pre_materialize=lambda _paths: False),
            image_files=list(paths),
            image_patches={},
            webtoon_mode=False,
            load_image=lambda path: path,
        )
        return controller

    def test_export_keeps_sanitization_collisions_as_ordered_archive_pages(self):
        paths = [
            "/input/a b.png",
            "/input/a+b.png",
            "/left/duplicate.jpg",
            "/right/duplicate.jpg",
            "/input/Case.PNG",
            "/input/case.png",
            "/input/東京.png",
            "/input/日本語.png",
        ]
        controller = self._controller(paths)
        viewer_states = {path: {"viewer_state": {}} for path in paths}

        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "translated.cbz"
            controller.save_and_make_worker(
                [{"page_indices": list(range(len(paths))), "output_path": str(archive_path)}],
                viewer_states,
            )

            expected_names = [
                "0001_a_b.png",
                "0002_a_b.png",
                "0003_duplicate.jpg",
                "0004_duplicate.jpg",
                "0005_Case.png",
                "0006_case.png",
                "0007_page.png",
                "0008_page.png",
            ]
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), expected_names)
                self.assertEqual(
                    [archive.read(name).decode("utf-8") for name in expected_names],
                    paths,
                )

        self.assertEqual(controller.main.image_files, paths)

    def test_each_export_group_gets_ordered_unique_entries(self):
        paths = [
            "/one/a b.png",
            "/one/a+b.png",
            "/two/c d.png",
            "/two/c+d.png",
        ]
        controller = self._controller(paths)
        viewer_states = {path: {"viewer_state": {}} for path in paths}

        with tempfile.TemporaryDirectory() as directory:
            first_archive = Path(directory) / "first.cbz"
            second_archive = Path(directory) / "second.cbz"
            controller.save_and_make_worker(
                [
                    {"page_indices": [0, 1], "output_path": str(first_archive)},
                    {"page_indices": [2, 3], "output_path": str(second_archive)},
                ],
                viewer_states,
            )

            for archive_path, expected_names, expected_payloads in (
                (
                    first_archive,
                    ["0001_a_b.png", "0002_a_b.png"],
                    paths[:2],
                ),
                (
                    second_archive,
                    ["0001_c_d.png", "0002_c_d.png"],
                    paths[2:],
                ),
            ):
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertEqual(archive.namelist(), expected_names)
                    self.assertEqual(
                        [archive.read(name).decode("utf-8") for name in archive.namelist()],
                        expected_payloads,
                    )

    def test_export_number_width_handles_pages_above_four_digits(self):
        self.assertEqual(
            ProjectController._build_export_page_name(10000, "/input/page.png", 5),
            "10000_page.png",
        )


class MacPackagingTests(unittest.TestCase):
    def test_workflow_build_files_exist_and_match_expected_artifact(self):
        workflow = (ROOT / ".github/workflows/build-macos-dmg.yml").read_text(encoding="utf-8")
        spec_match = re.search(r"run:\s*pyinstaller\s+([^\s]+)", workflow)
        script_match = re.search(r"(?m)^\s*chmod \+x ([^\s]+)$", workflow)
        artifact_match = re.search(r'(?m)^\s*path:\s*"([^"]+)"', workflow)
        self.assertIsNotNone(spec_match)
        self.assertIsNotNone(script_match)
        self.assertIsNotNone(artifact_match)

        spec_path = ROOT / spec_match.group(1)
        script_path = ROOT / script_match.group(1)
        self.assertTrue(spec_path.is_file(), f"missing workflow input: {spec_path.name}")
        self.assertTrue(script_path.is_file(), f"missing workflow input: {script_path.name}")
        self.assertEqual(artifact_match.group(1), "dist/Comic Translate.dmg")

        spec_text = spec_path.read_text(encoding="utf-8")
        ast.parse(spec_text, filename=str(spec_path))
        self.assertIn("comic.py", spec_text)
        self.assertIn('hiddenimports=["controller"]', spec_text)
        self.assertIn("resources", spec_text)
        self.assertIn("icon.icns", spec_text)
        self.assertIn('name=f"{app_name}.app"', spec_text)
        for bundled_resource in (
            "resources/icons/icon.icns",
            "resources/icons/splash.png",
            "resources/static/main.qss",
            "resources/translations/compiled/ct_zh-CN.qm",
        ):
            self.assertTrue((ROOT / bundled_resource).is_file(), bundled_resource)

        script_text = script_path.read_text(encoding="utf-8")
        self.assertIn("create-dmg", script_text)
        self.assertIn('APP_BUNDLE="dist/${APP_NAME}.app"', script_text)
        self.assertIn('OUTPUT_DMG="dist/${APP_NAME}.dmg"', script_text)

    def _bash_executable(self):
        if os.name == "nt":
            program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
            candidates = (
                program_files / "Git/bin/bash.exe",
                Path("C:/Program Files (x86)/Git/bin/bash.exe"),
            )
            return next((str(path) for path in candidates if path.is_file()), None)
        return shutil.which("bash")

    def _bash_path(self, bash, path):
        path = str(path)
        if os.name != "nt":
            return path
        converted = subprocess.run(
            [bash, "-c", 'cygpath -u "$1"', "bash", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return converted.stdout.strip()

    def test_dmg_source_folder_contains_complete_bundle_and_is_cleaned(self):
        bash = self._bash_executable()
        if not bash:
            self.skipTest("Bash is required to run the DMG packaging fixture")

        with tempfile.TemporaryDirectory() as directory:
            fixture_root = Path(directory)
            app_contents = fixture_root / "dist" / "Comic Translate.app" / "Contents"
            (app_contents / "MacOS").mkdir(parents=True)
            (app_contents / "Info.plist").write_text("fixture app bundle", encoding="utf-8")
            (fixture_root / "resources" / "icons").mkdir(parents=True)
            (fixture_root / "resources" / "icons" / "icon.icns").write_bytes(b"fixture icon")

            capture_args = fixture_root / "captured-args.txt"
            capture_source = fixture_root / "captured-source.txt"
            capture_info = fixture_root / "captured-info.plist"
            harness = fixture_root / "dmg-fixture.sh"
            harness.write_text(
                r'''#!/usr/bin/env bash
set -euo pipefail

ditto() {
    cp -R "$1" "$2"
}

create-dmg() {
    local output_path=""
    local source_folder=""
    local previous=""
    local icon_name=""
    for arg in "$@"; do
        if [[ "$previous" == "--icon" ]]; then
            icon_name="$arg"
        fi
        output_path="$source_folder"
        source_folder="$arg"
        previous="$arg"
    done

    [[ -d "$source_folder/Comic Translate.app/Contents" ]]
    [[ ! -d "$source_folder/Contents" ]]
    [[ -d "$source_folder/$icon_name/Contents" ]]
    [[ -f "$source_folder/$icon_name/Contents/Info.plist" ]]
    printf '%s\n' "$@" > "$CAPTURE_ARGS"
    printf '%s\n' "$source_folder" > "$CAPTURE_SOURCE"
    cp "$source_folder/$icon_name/Contents/Info.plist" "$CAPTURE_INFO"
    if [[ "${FAIL_CREATE_DMG:-0}" == "1" ]]; then
        return 53
    fi
    : > "$output_path"
}

source "$1"
''',
                encoding="utf-8",
            )

            env = os.environ.copy()
            env["CAPTURE_ARGS"] = self._bash_path(bash, capture_args)
            env["CAPTURE_SOURCE"] = self._bash_path(bash, capture_source)
            env["CAPTURE_INFO"] = self._bash_path(bash, capture_info)
            completed = subprocess.run(
                [
                    bash,
                    self._bash_path(bash, harness),
                    self._bash_path(bash, ROOT / "builddmg.sh"),
                ],
                cwd=fixture_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )

            self.assertEqual(
                completed.returncode,
                0,
                f"DMG fixture failed: {completed.stdout}\n{completed.stderr}",
            )
            args = capture_args.read_text(encoding="utf-8").splitlines()
            source_folder = Path(capture_source.read_text(encoding="utf-8").strip())
            if not source_folder.is_absolute():
                source_folder = fixture_root / source_folder
            icon_index = args.index("--icon")

            self.assertEqual(args[-2], "dist/Comic Translate.dmg")
            self.assertEqual(args[-1], capture_source.read_text(encoding="utf-8").strip())
            self.assertEqual(args[icon_index + 1], "Comic Translate.app")
            self.assertEqual(capture_info.read_text(encoding="utf-8"), "fixture app bundle")
            self.assertTrue((fixture_root / "dist" / "Comic Translate.dmg").is_file())
            self.assertFalse(source_folder.exists(), "temporary DMG source folder was not cleaned")

            env["FAIL_CREATE_DMG"] = "1"
            failed = subprocess.run(
                [
                    bash,
                    self._bash_path(bash, harness),
                    self._bash_path(bash, ROOT / "builddmg.sh"),
                ],
                cwd=fixture_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertNotEqual(failed.returncode, 0)
            failed_source = Path(capture_source.read_text(encoding="utf-8").strip())
            if not failed_source.is_absolute():
                failed_source = fixture_root / failed_source
            self.assertFalse(
                failed_source.exists(), "failed DMG build left its temporary source folder"
            )


if __name__ == "__main__":
    unittest.main()
