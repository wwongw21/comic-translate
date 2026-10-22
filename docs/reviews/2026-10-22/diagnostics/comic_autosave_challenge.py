from pathlib import Path
from types import ModuleType, SimpleNamespace
from collections import deque
import ast, sys, logging, tempfile, os
ROOT=Path('/workspace/repos/comic-translate')
class Bound:
    def __init__(self): self.callbacks=[]
    def connect(self,f): self.callbacks.append(f)
    def emit(self,*a):
        for f in self.callbacks: f(*a)
class Signal:
    def __init__(self,*a): pass
    def __set_name__(self,owner,name): self.name=name
    def __get__(self,instance,owner=None):
        if instance is None: return self
        return instance.__dict__.setdefault(self.name,Bound())
class Timer:
    events=deque()
    @classmethod
    def singleShot(cls,*a): cls.events.append(a[-1])
    @classmethod
    def drain(cls):
        while cls.events: cls.events.popleft()()
qtcore=ModuleType('PySide6.QtCore'); qtcore.QRunnable=type('QRunnable',(),{}); qtcore.QObject=object
qtcore.Signal=Signal; qtcore.QTimer=Timer; qtcore.QCoreApplication=object
pyside=ModuleType('PySide6'); pyside.QtCore=qtcore
sys.modules['PySide6']=pyside; sys.modules['PySide6.QtCore']=qtcore
wm=ModuleType('app.thread_worker'); exec(compile((ROOT/'app/thread_worker.py').read_text(),'app/thread_worker.py','exec'),wm.__dict__)
sys.modules['app.thread_worker']=wm
rn={}; exec(compile((ROOT/'app/controllers/task_runner.py').read_text(),'task_runner.py','exec'),rn)
def extract(path,class_name,wanted,new_name,ns):
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name)
    out=ast.ClassDef(name=new_name,bases=[],keywords=[],body=[m for m in cls.body if isinstance(m,ast.FunctionDef) and m.name in wanted],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[out],type_ignores=[])),str(path),'exec'),ns)
    return ns[new_name]
Main=extract(ROOT/'controller.py','ComicTranslate',{'_any_undo_dirty','has_unsaved_changes','set_project_clean'},'Main',{})
Project=extract(ROOT/'app/controllers/projects.py','ProjectController',{'autosave_project','clear_recovery_checkpoint'},'Project',{'logger':logging.getLogger('challenge'),'os':os})
for target_kind,revision_changed in [('regular',False),('regular',True),('recovery',False)]:
    with tempfile.TemporaryDirectory(dir='/workspace/review') as d:
        recovery=Path(d)/'recovery.ctpr'; recovery.write_text('last successful checkpoint')
        m=Main(); m._manual_dirty=True; m.undo_stacks={}; m._dirty_revision=8
        m._update_window_modified=lambda:None
        m.image_files=['image.png']; m._batch_active=False
        m.text_ctrl=SimpleNamespace(_commit_pending_text_command=lambda:None)
        m.project_file=str(Path(d)/'regular.ctpr')
        m.settings_page=SimpleNamespace(get_export_settings=lambda:{'project_autosave_enabled':True})
        workers=[]; m.threadpool=SimpleNamespace(start=workers.append); m.current_worker=None
        runner=rn['TaskRunnerController'](m); m.run_threaded=runner.run_threaded
        p=Project(); p.main=m; p._autosave_save_pending=False; p._autosave_retrigger_requested=False
        p.save_current_state=lambda:None; p._ensure_autosave_project_file_if_needed=lambda:None
        p._recovery_project_path=lambda:str(recovery)
        p.add_recent_project=lambda _:None; p._refresh_home_screen=lambda:None
        retries=[]; p._realtime_autosave_timer=SimpleNamespace(start=lambda:retries.append(True))
        def failure(_): raise OSError(28,'No space left on device')
        p.save_project=failure
        p.autosave_project(prefer_project_file=target_kind=='regular')
        if revision_changed:m._dirty_revision+=1
        workers[0].run(); Timer.drain()
        result={'target':target_kind,'edited_during_save':revision_changed,'dirty':m.has_unsaved_changes(),'recovery_exists':recovery.exists(),'retry_started':bool(retries)}
        print(result)
        if target_kind=='regular' and not revision_changed:
            assert result==dict(target='regular',edited_during_save=False,dirty=False,recovery_exists=False,retry_started=False)
        elif target_kind=='regular':
            assert result['dirty'] and not result['recovery_exists'] and result['retry_started']
        else:
            assert result['dirty'] and result['recovery_exists']
