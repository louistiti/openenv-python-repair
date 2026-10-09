"""Untrained-Qwen difficulty probe, not a training run or Arena score.

Runs four stochastic rollouts for each task/seed group. Exact single JSON actions,
no JSON-constrained decoding, no thinking, no extraction of fenced code. Local
Ollama quantization and token accounting differ from Arena: label results as a
proxy only. The harness must not recommend submission from reference replays.
"""
import argparse
import json
import math
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import ValidationError
from server import MAX_STEPS, RepairAction, RepairEnvironment
from tasks import TASK_IDS


def decode(raw):
    def nonfinite(value):
        raise ValueError('nonfinite JSON')
    result=json.loads(raw,parse_constant=nonfinite)
    if not isinstance(result,dict):
        raise ValueError('reply must be one JSON object')
    if set(result)=={'action'} and isinstance(result['action'],dict):
        result=result['action']
    if set(result)=={'finish'} and result['finish'] is True:
        return RepairAction(operation='submit')
    return RepairAction.model_validate(result)


def episode(task_id,seed,generate,completion_budget=4096,context_budget=8192):
    env=RepairEnvironment()
    observation=env.reset(task_id=task_id,seed=seed)
    system='Reply with exactly one JSON object and nothing else. It must match the action schema, or be {"finish":true} to end. Thinking is disabled. Action schema: '+json.dumps(RepairAction.model_json_schema())
    messages=[{'role':'system','content':system},{'role':'user','content':observation.model_dump_json()}]
    model_tokens=0
    observation_estimate=0
    reason='max_actions'
    replies=[]
    for turn in range(MAX_STEPS):
        if model_tokens+observation_estimate>=completion_budget:
            reason='approx_completion_budget'
            break
        response=generate(messages,min(1600,completion_budget-model_tokens-observation_estimate))
        raw=response['message']['content']
        model_tokens+=response.get('eval_count',0)
        replies.append({'text':raw,'tokens':response.get('eval_count',0),'done_reason':response.get('done_reason')})
        # Ollama's own prompt counter is used when present. No guessed tokenizer equivalence.
        if response.get('prompt_eval_count',0)>context_budget:
            reason='context_budget'
            break
        messages.append({'role':'assistant','content':raw})
        try:
            action=decode(raw)
        except (ValueError,ValidationError,TypeError):
            reason='invalid_action'
            break
        observation=env.step(action)
        if observation.done:
            reason='terminal'
            break
        text=observation.model_dump_json()
        # Explicit approximation for post-reset observation tokens; report it in provenance.
        observation_estimate+=math.ceil(len(text.encode())/3)
        messages.append({'role':'user','content':text})
    if not observation.done:
        observation=env.step(RepairAction(operation='submit'))
    return {'task_id':task_id,'seed':seed,'reward':observation.reward,'done':observation.done,
            'steps':env.state.step_count,'termination':reason,'model_tokens':model_tokens,
            'observation_tokens_estimated':observation_estimate,'replies':replies}


class Ollama:
    def __init__(self,base,model,temperature,random_seed):
        parsed=urllib.parse.urlparse(base)
        if parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1','::1'} or parsed.username or parsed.password or parsed.query:
            raise ValueError('This harness is local-only; remote inference requires separate authorization')
        self.base=base.rstrip('/')
        self.model=model
        self.temperature=temperature
        self.random_seed=random_seed

    def request(self,path,payload=None):
        data=None if payload is None else json.dumps(payload).encode()
        request=urllib.request.Request(self.base+path,data=data,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=600) as response:
            return json.load(response)

    def info(self):
        version=self.request('/api/version')
        model=self.request('/api/show',{'model':self.model})
        return {'runtime':version,'model':self.model,'details':model.get('details'),
                'model_info':model.get('model_info'),'template':model.get('template')}

    def generate(self,messages,budget):
        self.random_seed+=1
        return self.request('/api/chat',{'model':self.model,'stream':False,'think':False,
            'messages':messages,'options':{'temperature':self.temperature,'seed':self.random_seed,
                                         'num_predict':budget,'num_ctx':8192},'keep_alive':'10m'})


def summarize(rows):
    groups={}
    for row in rows:
        groups.setdefault((row['task_id'],row['seed']),[]).append(row['reward'])
    result=[]
    for (task_id,seed),rewards in groups.items():
        result.append({'task_id':task_id,'seed':seed,'rewards':rewards,
            'variance':statistics.pvariance(rewards),'mixed_rewards':len(set(rewards))>1})
    return {'episodes':len(rows),'groups':result,'groups_with_mixed_rewards':sum(g['mixed_rewards'] for g in result),
        'perfect_episodes':sum(r['reward']==1 for r in rows),'invalid_actions':sum(r['termination']=='invalid_action' for r in rows),
        'mean_reward':statistics.mean(r['reward'] for r in rows) if rows else None,
        'proves_learning_gain':False,'arena_score':None}


def run_probes(model, task_ids, seed, repeats, temperature, output):
    info=model.info() # Fail before creating a result if no real model is available.
    rows=[]
    runtime_errors=[]
    started=time.time()
    initial_sampling_seed=model.random_seed
    for task_id in task_ids:
        for repeat in range(repeats):
            try:
                row=episode(task_id,seed,model.generate)
            except (urllib.error.URLError, TimeoutError) as error:
                detail={'task_id':task_id,'seed':seed,'repeat':repeat,
                        'type':type(error).__name__,'error':str(error)}
                if isinstance(error,urllib.error.HTTPError):
                    detail['status']=error.code
                    detail['body']=error.read(65536).decode(errors='replace')
                runtime_errors.append(detail)
                print(json.dumps({'runtime_error':detail}),flush=True)
            else:
                row['repeat']=repeat
                rows.append(row)
                print(json.dumps({k:row[k] for k in ('task_id','seed','repeat','reward','steps','termination')}),flush=True)
            report={'kind':'quantized_local_proxy','model':info,'temperature':temperature,
                'thinking':False,'json_constrained_decoding':False,
                'observation_token_accounting':'UTF-8 bytes/3 estimate, not Arena tokenizer',
                'completion_budget':4096,'context_budget':8192,'per_reply_token_cap':1600,
                'initial_sampling_seed':initial_sampling_seed,
                'requested_episodes':len(task_ids)*repeats,'runtime_errors':runtime_errors,
                'wall_seconds':time.time()-started,'summary':summarize(rows),'episodes':rows}
            Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:11434')
    parser.add_argument('--model',default='qwen3.8:27b')
    parser.add_argument('--tasks',nargs='+',choices=TASK_IDS,default=['allocation-3','expression-3','incident-3'])
    parser.add_argument('--seed',type=int,default=5000)
    parser.add_argument('--repeats',type=int,default=4)
    parser.add_argument('--temperature',type=float,default=1.0)
    parser.add_argument('--output',default='qwen-calibration.json')
    args=parser.parse_args()
    if args.repeats<2:
        parser.error('at least two repeats required for reward spread')
    model=Ollama(args.base,args.model,args.temperature,9000)
    run_probes(model,args.tasks,args.seed,args.repeats,args.temperature,args.output)
