"""Read-only source-level reproductions; no Qt/models or project edits required."""
from pathlib import Path
import ast
import logging
import os
import re
import shutil
import sys
import tempfile
import types
from collections import deque

root = Path('/workspace/repos/comic-translate')

# Execute the real worker and task runner with deterministic Qt signal/timer shims.
class BoundSignal:
    def __init__(self): self.callbacks = []
    def connect(self, callback): self.callbacks.append(callback)
    def emit(self, *args):
        for callback in self.callbacks: callback(*args)
class Signal:
    def __init__(self, *args): self.name = None
    def __set_name__(self, owner, name): self.name = name
    def __get__(self, instance, owner=None):
        if instance is None: return self
        return instance.__dict__.setdefault('_signal_' + self.name, BoundSignal())
class QObject: pass
class QRunnable: pass
class Timer:
    events = deque()
    @classmethod
    def singleShot(cls, *args): cls.events.append(args[-1])
    @classmethod
    def drain(cls):
        while cls.events: cls.events.popleft()()
qtcore = types.ModuleType('PySide6.QtCore')
qtcore.QRunnable, qtcore.Signal, qtcore.QObject = QRunnable, Signal, QObject
qtcore.QCoreApplication, qtcore.QTimer = object, Timer
pyside = types.ModuleType('PySide6')
pyside.QtCore = qtcore
sys.modules['PySide6'] = pyside
sys.modules['PySide6.QtCore'] = qtcore
worker_module = types.ModuleType('app.thread_worker')
exec(compile((root / 'app/thread_worker.py').read_text(), 'app/thread_worker.py', 'exec'), worker_module.__dict__)
sys.modules['app.thread_worker'] = worker_module
runner_namespace = {}
exec(compile((root / 'app/controllers/task_runner.py').read_text(), 'app/controllers/task_runner.py', 'exec'), runner_namespace)
workers = []
main = types.SimpleNamespace(threadpool=types.SimpleNamespace(start=workers.append), current_worker=None)
runner = runner_namespace['TaskRunnerController'](main)
def fails(): raise RuntimeError('controlled failure')
runner.run_threaded(fails)
runner.run_threaded(lambda: 'B')
runner.run_threaded(lambda: 'C')
assert len(workers) == 1
workers[0].run()
Timer.drain()
assert len(workers) == 3, len(workers)
print('QUEUE REPRO: a failed first job starts B and C before either finishes; active pending workers =', len(workers) - 1)

# Execute only the production export methods with a tiny renderer to inspect output files.
tree = ast.parse((root / 'app/controllers/projects.py').read_text(encoding='utf-8-sig'))
original_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ProjectController')
methods = [n for n in original_class.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in {'_build_export_page_name', 'save_and_make_worker'}]
klass = ast.ClassDef(name='ProjectController', bases=[], keywords=[], body=methods, decorator_list=[])
unit = ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[]))
captured = {}
class Renderer:
    def __init__(self, image): self.image = image
    def apply_patches(self, patches): pass
    def add_state_to_image(self, state): pass
    def save_image(self, path): Path(path).write_text(self.image)
def make(directory, output):
    captured.update({p.name: p.read_text() for p in Path(directory).iterdir()})
namespace = dict(os=os, re=re, tempfile=tempfile, shutil=shutil, logger=logging.getLogger('repro'), ImageSaveRenderer=Renderer, make=make)
exec(compile(unit, 'app/controllers/projects.py [export methods]', 'exec'), namespace)
controller = namespace['ProjectController']()
paths = ['/input/a b.png', '/input/a?b.png']
controller.main = types.SimpleNamespace(
    file_handler=types.SimpleNamespace(should_pre_materialize=lambda _: False),
    image_files=paths, webtoon_mode=False, image_patches={}, load_image=lambda path: path,
)
with tempfile.TemporaryDirectory() as directory:
    controller.save_and_make_worker([{'page_indices': [0, 1], 'output_path': str(Path(directory) / 'export.zip')}], {p: {'viewer_state': {}} for p in paths})
assert captured == {'a_b.png': '/input/a?b.png'}, captured
print('EXPORT REPRO: two distinct input pages produce only', captured)

missing = [p for p in ['ct-mac.spec', 'builddmg.sh'] if not (root / p).exists()]
assert len(missing) == 2
print('BUILD REPRO: checked-in macOS workflow references missing files:', ', '.join(missing))

count = 0
for path in root.rglob('*.py'):
    if '.git' in path.parts: continue
    compile(path.read_bytes(), str(path), 'exec')
    count += 1
print('SYNTAX: compiled', count, 'Python files without writing bytecode')

# Exercise autosave's actual error and finish closures; GenericWorker emits both on failure.
methods = [n for n in original_class.body if isinstance(n, ast.FunctionDef) and n.name == 'autosave_project']
klass = ast.ClassDef(name='ProjectController', bases=[], keywords=[], body=methods, decorator_list=[])
unit = ast.fix_missing_locations(ast.Module(body=[klass], type_ignores=[]))
namespace = dict(logger=logging.getLogger('repro'))
exec(compile(unit, 'app/controllers/projects.py [autosave method]', 'exec'), namespace)
autosave = namespace['ProjectController']()
autosave._autosave_save_pending = False
autosave._autosave_retrigger_requested = False
autosave.save_current_state = lambda: None
autosave._ensure_autosave_project_file_if_needed = lambda: None
autosave.save_project = lambda _: None
calls = []
autosave.clear_recovery_checkpoint = lambda: calls.append('recovery deleted')
autosave.add_recent_project = lambda _: None
autosave._refresh_home_screen = lambda: None
autosave._realtime_autosave_timer = types.SimpleNamespace(start=lambda: calls.append('retry scheduled'))
callbacks = {}
def capture_save(callback, result, error, finished, target): callbacks.update(error=error, finished=finished)
main = types.SimpleNamespace(image_files=['page.png'], _batch_active=False,
    text_ctrl=types.SimpleNamespace(_commit_pending_text_command=lambda: None),
    has_unsaved_changes=lambda: 'marked clean' not in calls,
    settings_page=types.SimpleNamespace(get_export_settings=lambda: {'project_autosave_enabled': True}),
    project_file='/project.ctpr', _dirty_revision=7, set_project_clean=lambda: calls.append('marked clean'),
    run_threaded=capture_save)
autosave.main = main
autosave.autosave_project()
callbacks['error']((OSError, OSError('controlled disk full'), ''))
callbacks['finished']()
assert calls == ['recovery deleted', 'marked clean'], calls
print('AUTOSAVE REPRO: failed save causes', calls, '; no retry scheduled')
