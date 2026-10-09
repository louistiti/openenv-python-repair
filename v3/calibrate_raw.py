"""Official-template local proxy without Ollama's chat/tool-output parser.

Raw model text is never cleaned up or constrained to JSON. The environment and
budgets remain those of calibrate.py. Quantized weights are still not Arena.
"""
import argparse
import hashlib
import json
import urllib.request

from jinja2.sandbox import ImmutableSandboxedEnvironment

from calibrate import Ollama, run_probes
from tasks import TASK_IDS

TEMPLATE_URL='https://huggingface.co/Qwen/Qwen3.8-27B/raw/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0/tokenizer_config.json'
TEMPLATE_SHA256='c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041'


def load_template():
    # Public source, no token, profile credential or implicit HF auth.
    with urllib.request.urlopen(TEMPLATE_URL,timeout=30) as response:
        template=json.load(response)['chat_template']
    if hashlib.sha256(template.encode()).hexdigest()!=TEMPLATE_SHA256:
        raise ValueError('Official template hash changed')
    return template


def renderer(template):
    env=ImmutableSandboxedEnvironment(trim_blocks=True,lstrip_blocks=True)
    def fail(message):
        raise ValueError(message)
    env.globals['raise_exception']=fail
    return env.from_string(template)


class RawOllama(Ollama):
    def __init__(self,base,model,temperature,random_seed,template):
        super().__init__(base,model,temperature,random_seed)
        self.template=template
        self.render=renderer(template)

    def info(self):
        result=super().info()
        result['inference_api']='/api/generate raw=true'
        result['official_template_url']=TEMPLATE_URL
        result['official_template_sha256']=hashlib.sha256(self.template.encode()).hexdigest()
        result['enable_thinking']=False
        return result

    def generate(self,messages,budget):
        self.random_seed+=1
        prompt=self.render.render(messages=messages,tools=None,
                                  enable_thinking=False,add_generation_prompt=True)
        result=self.request('/api/generate',{'model':self.model,'raw':True,
            'prompt':prompt,'stream':False,'think':False,
            'options':{'temperature':self.temperature,'seed':self.random_seed,
                       'num_predict':budget,'num_ctx':8192},'keep_alive':'10m'})
        # Preserve every generated character, including XML, fences and prose.
        result['message']={'role':'assistant','content':result['response']}
        return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--base',default='http://127.0.0.1:11434')
    parser.add_argument('--model',default='qwen3.8:27b')
    parser.add_argument('--tasks',nargs='+',choices=TASK_IDS,
                        default=['allocation-3','expression-3','incident-3'])
    parser.add_argument('--seed',type=int,default=5001)
    parser.add_argument('--repeats',type=int,default=4)
    parser.add_argument('--temperature',type=float,default=1.0)
    parser.add_argument('--output',default='qwen-raw-calibration.json')
    args=parser.parse_args()
    if args.repeats<2:
        parser.error('at least two repeats required for reward spread')
    model=RawOllama(args.base,args.model,args.temperature,9000,load_template())
    run_probes(model,args.tasks,args.seed,args.repeats,args.temperature,args.output)
