import pytest

from calibrate import decode
from calibrate_raw import RawOllama, renderer


MOCK_TEMPLATE='{{ messages[0].content }}:{{ enable_thinking }}:{{ add_generation_prompt }}'


def test_raw_output_is_not_cleaned_or_json_constrained(monkeypatch):
    model=RawOllama('http://localhost:11434','explicit-test-mock',1.0,3,MOCK_TEMPLATE)
    raw='<tool_call>not a JSON action</tool_call>'
    def request(path,payload):
        assert path=='/api/generate' and payload['raw'] is True
        assert payload['think'] is False and payload['prompt']=='spec:False:True'
        assert 'format' not in payload and payload['options']['num_predict']==100
        return {'response':raw,'eval_count':10}
    monkeypatch.setattr(model,'request',request)
    reply=model.generate([{'role':'system','content':'spec'}],100)
    assert reply['message']['content']==raw and reply['eval_count']==10
    with pytest.raises(ValueError): decode(reply['message']['content'])


def test_raw_adapter_keeps_local_only_restriction():
    with pytest.raises(ValueError):
        RawOllama('https://remote.example','explicit-test-mock',1,3,MOCK_TEMPLATE)


def test_template_errors_are_not_suppressed():
    with pytest.raises(ValueError,match='bad input'):
        renderer("{{ raise_exception('bad input') }}").render()
