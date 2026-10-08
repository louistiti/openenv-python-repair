import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from server import MAX_STEPS, TASKS, RepairAction, RepairEnvironment, app, grade

SOLUTIONS = json.loads(Path('solutions.json').read_text())

@pytest.mark.parametrize('task_id', list(TASKS))
def test_oracle_and_buggy_floor(task_id):
    task = TASKS[task_id]
    oracle = grade(SOLUTIONS[task_id],task)
    assert oracle['passed'] == oracle['total'], (task_id,oracle)
    floor = grade(task['starter'],task)
    assert floor['passed'] < floor['total'], (task_id,floor)
    env = RepairEnvironment()
    initial = env.reset(task_id=task_id,seed=3)
    assert initial.task_id == task_id and not initial.done
    assert env.step(RepairAction(operation='write',code=SOLUTIONS[task_id])).reward == 0
    assert not env.step(RepairAction(operation='test')).done
    terminal = env.step(RepairAction(operation='submit'))
    assert terminal.done and terminal.reward == 1
    assert env.step(RepairAction(operation='test')).reward == 1
    assert env.state.step_count == 3

@pytest.mark.parametrize('code', [
    'import os\ndef solve(*args): return 0',
    'def solve(*args): return (1).__class__',
    'def solve(*args): return open("/app/tasks.json").read()',
    'def solve(*args): return __builtins__',
    'not python!!!',
    'def solve(*args):\n    while True: pass',
    'def solve(*args): return float("nan")',
])
def test_invalid_untrusted_source(code):
    result = grade(code,TASKS['merge-intervals'])
    assert result['passed'] == 0

def test_reset_isolation_and_budget():
    a,b = RepairEnvironment(),RepairEnvironment()
    ia,ib = a.reset(task_id='moving-sums'),b.reset(task_id='moving-sums')
    assert ia.source == ib.source
    a.step(RepairAction(operation='write',code=SOLUTIONS['moving-sums']))
    assert a.code != b.code
    assert a.reset(task_id='moving-sums').source == ia.source
    assert a.state.step_count == 0
    for _ in range(MAX_STEPS): result = b.step(RepairAction(operation='test'))
    assert result.done and 0 <= result.reward <= 1
    assert a.reset(seed=8).source == a.reset(seed=8).source
    with pytest.raises(ValueError): a.reset(task_id='missing')

def test_http_contract():
    # Pinned OpenEnv HTTP routes are stateless. Stateful episodes use /ws.
    with TestClient(app) as client:
        assert client.get('/health').status_code == 200
        schema = client.get('/schema')
        assert schema.status_code == 200
        assert schema.json()['action']['properties']['operation']['enum'] == ['write','test','submit']
        for task_id in TASKS:
            response = client.post('/reset',json={'task_id':task_id,'seed':7})
            assert response.status_code == 200, response.text
            assert response.json()['observation']['task_id'] == task_id
        response = client.post('/step',json={'action':{'operation':'submit'}})
        assert response.status_code == 200, response.text
        assert response.json()['done'] is True
        assert 0 <= response.json()['reward'] <= 1
        assert client.get('/state').status_code == 200
        assert client.post('/step',json={'action':{'operation':'invalid'}}).status_code == 422

def test_websocket_sessions():
    with TestClient(app) as client:
        with client.websocket_connect('/ws') as a, client.websocket_connect('/ws') as b:
            for sock in (a,b):
                sock.send_json({'type':'reset','data':{'task_id':'moving-sums'}})
                response = sock.receive_json()
                assert response['type'] == 'observation', response
            a.send_json({'type':'step','data':{'operation':'write','code':SOLUTIONS['moving-sums']}})
            assert a.receive_json()['type'] == 'observation'
            a.send_json({'type':'step','data':{'operation':'submit'}})
            assert a.receive_json()['data']['reward'] == 1
            b.send_json({'type':'step','data':{'operation':'submit'}})
            assert b.receive_json()['data']['reward'] < 1
