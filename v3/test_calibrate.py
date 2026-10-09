import json

import pytest
from calibrate import Ollama, decode, episode, summarize, run_probes
from tasks import make_task


def test_strict_json_actions_and_wrapper():
    assert decode('{"operation":"test"}').operation=='test'
    assert decode('{"finish":true}').operation=='submit'
    assert decode('{"action":{"operation":"submit"}}').operation=='submit'
    for raw in ['```json\n{"operation":"test"}\n```','hello','[]','{}','{"operation":"unknown"}','{"finish":1}','{"finish":1,"extra":0}']:
        with pytest.raises(ValueError): decode(raw)


def test_mock_transport_oracle_episode():
    task=make_task('allocation-3',5000)
    actions=[{'operation':'write','path':p,'code':task.solution[p]} for p in task.mutations]+[{'operation':'submit'}]
    def generate(messages,budget):
        assert 'hidden' not in messages[1]['content'] or 'hidden checks' in messages[1]['content']
        return {'message':{'content':json.dumps(actions.pop(0))},'eval_count':50,'prompt_eval_count':1000}
    result=episode(task.task_id,5000,generate)
    assert result['reward']==1 and result['termination']=='terminal'
    assert result['steps']==4 and result['model_tokens']==200


def test_invalid_reply_still_grades_current_workspace():
    def generate(messages,budget):
        return {'message':{'content':'not JSON'},'eval_count':3}
    result=episode('expression-3',3,generate)
    assert result['done'] and result['reward']<1
    assert result['termination']=='invalid_action'


def test_summary_never_claims_training_improvement():
    rows=[{'task_id':'allocation-3','seed':7,'reward':r,'termination':'terminal'} for r in (0,1,0.5,0.5)]
    report=summarize(rows)
    assert report['groups_with_mixed_rewards']==1
    assert report['groups'][0]['variance']==0.125
    assert report['proves_learning_gain'] is False and report['arena_score'] is None


def test_runtime_failures_are_not_rewards(tmp_path, monkeypatch):
    import io
    import urllib.error
    import calibrate
    class MockModel:
        random_seed=9000
        def info(self): return {'model':'explicit-unit-test-mock'}
        def generate(self, messages, budget): raise AssertionError('mocked episode should be used')
    attempts=iter([urllib.error.HTTPError('http://localhost',500,'failure',{},io.BytesIO(b'backend failure')),
                   {'task_id':'incident-3','seed':7,'reward':1.0,'done':True,'steps':4,'termination':'terminal'}])
    def fake_episode(*args):
        value=next(attempts)
        if isinstance(value,Exception): raise value
        return value
    monkeypatch.setattr(calibrate,'episode',fake_episode)
    report=run_probes(MockModel(),['incident-3'],7,2,1.0,tmp_path/'report.json')
    assert report['requested_episodes']==2 and report['summary']['episodes']==1
    assert report['summary']['mean_reward']==1 and len(report['runtime_errors'])==1
    assert report['runtime_errors'][0]['body']=='backend failure'
    assert report['per_reply_token_cap']==1600
    assert json.loads((tmp_path/'report.json').read_text())==report


def test_all_runtime_failures_have_no_mean_reward(tmp_path, monkeypatch):
    import urllib.error
    import calibrate
    class MockModel:
        random_seed=9000
        def info(self): return {'model':'explicit-unit-test-mock'}
        def generate(self, messages, budget): raise AssertionError('mocked episode should be used')
    def fake_episode(*args): raise urllib.error.URLError('local inference unavailable')
    monkeypatch.setattr(calibrate,'episode',fake_episode)
    report=run_probes(MockModel(),['incident-3'],7,2,1.0,tmp_path/'report.json')
    assert report['summary']['episodes']==0 and report['summary']['mean_reward'] is None
    assert len(report['runtime_errors'])==2 and not report['episodes']


def test_paid_or_credentialled_endpoints_refused():
    for url in ['https://api.example.com','http://user:secret@localhost:11434','http://localhost:11434?token=secret']:
        with pytest.raises(ValueError): Ollama(url,'qwen3.8:27b',1,1)
