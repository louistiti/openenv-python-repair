import copy
import json

import pytest
from fastapi.testclient import TestClient
from execution import RUNNER, equal, grade, validate
from server import MAX_STEPS, RepairAction, RepairEnvironment, app
from tasks import TASK_IDS, make_task

@pytest.mark.parametrize('task_id',TASK_IDS)
def test_reference_floor_and_partial(task_id):
    for seed in range(3):
        task=make_task(task_id,seed)
        assert grade(task.solution,task.hidden)['reward']==1, (task_id,seed)
        floor=grade(task.starter,task.hidden)
        assert floor['reward']<1, (task_id,seed,floor)
        assert 0<=floor['reward']<=1
        if len(task.mutations)>1:
            fixed=dict(task.starter)
            fixed[task.mutations[0]]=task.solution[task.mutations[0]]
            result=grade(fixed,task.hidden)
            assert result['reward']<1

@pytest.mark.parametrize('task_id',TASK_IDS)
def test_seeded_generation_and_terminal(task_id):
    a,b=make_task(task_id,21),make_task(task_id,22)
    assert a==make_task(task_id,21)
    assert a.hidden!=b.hidden
    assert len(a.starter)==5
    assert len(a.mutations)==int(task_id[-1])
    assert all(c not in a.hidden for c in a.visible[-1:])
    env=RepairEnvironment()
    initial=env.reset(task_id=task_id,seed=21)
    assert initial.files==a.starter and not initial.done and initial.reward==0
    assert 'mutations' not in initial.model_dump()
    for path in a.mutations:
        assert env.step(RepairAction(operation='write',path=path,code=a.solution[path])).reward==0
    observation=env.step(RepairAction(operation='test'))
    assert not observation.done
    assert json.loads(observation.message)['reward']==1
    result=env.step(RepairAction(operation='submit'))
    assert result.done and result.reward==1
    assert 'failures' not in json.loads(result.message)
    steps=env.state.step_count
    assert env.step(RepairAction(operation='submit')).reward==1
    assert env.state.step_count==steps

@pytest.mark.parametrize('source',[
    'import os\ndef solve(*args): return os.environ',
    'from io import FileIO\ndef solve(*args): return list(FileIO("/app/tasks.py"))',
    'import io\ndef solve(*args): return list(io.FileIO("/app/tasks.py"))',
    'def solve(*args): return (1).__class__',
    'def solve(*args): return globals()',
    'def solve(*args): return eval("1")',
    'def solve(*args): return __builtins__',
    'def solve(*args): return open("/etc/passwd")',
    'def solve(*args):\n    g=(i for i in [1])\n    return g.gi_frame.f_globals',
    'from fractions import sys\ndef solve(*args): return sys.path',
    'def solve(*args): return float("nan")',
    'def solve(*args):\n    while True: pass',
    'def solve(*args): return "x" * 1000000',
    'not python!!!',
])
def test_attack_and_resource_floor(source):
    task=make_task('capacity-3',8)
    files=dict(task.solution,**{'main.py':source})
    assert grade(files,task.hidden)['reward']==0

def test_parent_owned_verifier_and_type_equality():
    assert 'expected' not in RUNNER and 'reward' not in RUNNER
    assert not equal(True,1)
    assert not equal({'x':True},{'x':1})
    assert not equal(float('inf'),1)
    assert equal([1.0,{'x':2}],[1,{'x':2}])
    assert not equal({'extra':0,'x':1},{'x':1})
    task=make_task('capacity-3',3)
    files=dict(task.solution,**{'main.py':'def solve(bookings):\n    bookings.clear()\n    return {"peak":0,"overload":[],"excess_area":0}\n'})
    assert grade(files,task.hidden)['reward']<1


def test_session_isolation_read_rejection_and_budget():
    a,b=RepairEnvironment(),RepairEnvironment()
    initial=a.reset(task_id='sensor-3',seed=4)
    b.reset(task_id='sensor-3',seed=4)
    task=make_task('sensor-3',4)
    a.step(RepairAction(operation='write',path=task.mutations[0],code=task.solution[task.mutations[0]]))
    assert a.files!=b.files
    snapshot=copy.deepcopy(a.files)
    for path,code in [('settings.py','FEE=0'),('../main.py','def solve(*args):return 1'),('main.py','invalid syntax!')]:
        result=a.step(RepairAction(operation='write',path=path,code=code))
        assert a.files==snapshot
    read=a.step(RepairAction(operation='read',path='main.py'))
    assert read.files=={'main.py':a.files['main.py']}
    assert not a.step(RepairAction(operation='read',path='../../etc/passwd')).files
    assert a.reset(task_id='sensor-3',seed=4).files==initial.files
    for _ in range(MAX_STEPS):
        result=b.step(RepairAction(operation='read',path='main.py'))
    assert result.done and result.steps_left==0 and 0<=result.reward<1
    assert b.state.step_count==MAX_STEPS
    with pytest.raises(ValueError): a.reset(task_id='missing')


def test_http_and_websocket_contract():
    with TestClient(app) as client:
        assert client.get('/health').status_code==200
        schema=client.get('/schema').json()
        assert schema['action']['properties']['operation']['enum']==['read','write','test','submit']
        assert client.post('/reset',json={'task_id':'capacity-3','seed':8}).status_code==200
        assert client.post('/step',json={'action':{'operation':'invalid'}}).status_code==422
        with client.websocket_connect('/ws') as a,client.websocket_connect('/ws') as b:
            for sock in (a,b):
                sock.send_json({'type':'reset','data':{'task_id':'capacity-3','seed':8}})
                result=sock.receive_json()
                assert result['type']=='observation', result
            task=make_task('capacity-3',8)
            for path in task.mutations:
                a.send_json({'type':'step','data':{'operation':'write','path':path,'code':task.solution[path]}})
                assert a.receive_json()['type']=='observation'
            a.send_json({'type':'step','data':{'operation':'submit'}})
            assert a.receive_json()['data']['reward']==1
            b.send_json({'type':'step','data':{'operation':'submit'}})
            assert b.receive_json()['data']['reward']<1


def test_imported_unchanged_functions_still_resolve():
    task=make_task('reconcile-3',7)
    assert grade(task.solution,task.visible,feedback=True)['reward']==1
    # Modules load afresh per grade, not from previous candidate solutions.
    assert grade(task.starter,task.visible)['reward']<1
