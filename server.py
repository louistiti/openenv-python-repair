"""Python Repair Lab: isolated bounded function execution and deterministic rewards."""
import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Literal
from uuid import uuid4

from openenv.core.env_server.http_server import create_app
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field

TASKS = {t['task_id']: t for t in json.loads(Path(__file__).with_name('tasks.json').read_text())}
MAX_STEPS = 12
METHODS = {'append','extend','pop','insert','remove','sort','reverse','count','index','get','keys','values','items','setdefault','add','discard','union','intersection','difference','split','join','strip','lstrip','rstrip','replace','startswith','endswith','lower','upper','isdigit','isalpha','isalnum','copy'}

class RepairAction(Action):
    operation: Literal['write','test','submit'] = Field(description='write replaces solve source; test gives case feedback; submit ends with a correctness reward.')
    code: str = Field(default='',max_length=16000,description='Full Python source defining solve. Used only for write. No imports, I/O, or private attributes; ordinary builtins and container/string methods are available.')

class RepairObservation(Observation):
    task_id: str = ''
    message: str = ''
    source: str = ''
    steps_left: int = MAX_STEPS

# This subprocess is a defense-in-depth execution boundary, not a general Python sandbox.
# Restrict language before exec; container sandbox is the outer isolation boundary.
RUNNER = r'''
import builtins, json, math, resource, sys
resource.setrlimit(resource.RLIMIT_CPU,(2,2))
if sys.platform != 'darwin': resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
resource.setrlimit(resource.RLIMIT_FSIZE,(0,0))
resource.setrlimit(resource.RLIMIT_NOFILE,(16,16))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
payload=json.load(sys.stdin)
allowed='abs all any bool dict enumerate filter float int isinstance len list map max min pow range reversed round set sorted str sum tuple zip'.split()
g={'__builtins__':{name:getattr(builtins,name) for name in allowed}}
def equal(a,b):
    if isinstance(a,bool) or isinstance(b,bool): return type(a) is type(b) and a==b
    if isinstance(a,(int,float)) and isinstance(b,(int,float)): return math.isfinite(a) and math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-9)
    if isinstance(a,list) and isinstance(b,list): return len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return type(a) is type(b) and a==b
passed=0
failures=[]
try:
    exec(payload['code'],g,g)
    f=g['solve']
    for case in payload['cases']:
        args=case['args']
        original=json.dumps(args,ensure_ascii=False,sort_keys=True)
        try:
            actual=json.loads(json.dumps(f(*args),allow_nan=False))
            ok=equal(actual,case['expected']) and original==json.dumps(args,ensure_ascii=False,sort_keys=True)
            if ok: passed+=1
            elif len(failures)<3: failures.append({'args':json.loads(original),'expected':case['expected'],'actual':str(actual)[:250]})
        except BaseException as e:
            if len(failures)<3: failures.append({'error':type(e).__name__})
    print(json.dumps({'passed':passed,'total':len(payload['cases']),'failures':failures},ensure_ascii=False))
except BaseException as e:
    print(json.dumps({'passed':0,'total':len(payload['cases']),'error':type(e).__name__}))
'''

def validate_source(code):
    tree = ast.parse(code)
    if not any(isinstance(n,ast.FunctionDef) and n.name=='solve' for n in tree.body):
        raise ValueError('Define a function named solve.')
    for node in ast.walk(tree):
        if isinstance(node,(ast.Import,ast.ImportFrom,ast.ClassDef,ast.AsyncFunctionDef,ast.Await,ast.With,ast.AsyncWith,ast.Global,ast.Nonlocal,ast.Try,ast.Raise,ast.Delete)):
            raise ValueError('Imports, classes, I/O and exceptional control flow are not available.')
        if isinstance(node,ast.Attribute) and node.attr not in METHODS:
            raise ValueError('Only ordinary container/string methods are available.')
        if isinstance(node,ast.Name) and node.id.startswith('_'):
            raise ValueError('Private names are not available.')
        if isinstance(node,ast.arg) and node.arg.startswith('_'):
            raise ValueError('Private parameters are not available.')
        if isinstance(node,ast.FunctionDef) and (node.name.startswith('_') or node.decorator_list):
            raise ValueError('Private or decorated functions are not available.')
    return tree

def grade(code,task):
    try:
        validate_source(code)
        result = subprocess.run([sys.executable,'-I','-S','-c',RUNNER],input=json.dumps({'code':code,'cases':task['cases']}),text=True,capture_output=True,timeout=3,env={'PATH':'/usr/bin:/bin'},cwd='/tmp')
        if result.returncode:
            return {'passed':0,'total':len(task['cases']),'error':'Execution failed or exceeded resource limit.'}
        return json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        return {'passed':0,'total':len(task['cases']),'error':'Execution timed out.'}
    except (ValueError,SyntaxError,RecursionError) as error:
        return {'passed':0,'total':len(task['cases']),'error':str(error)[:300]}

class RepairEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()),step_count=0)
        self.task = None
        self.code = ''
        self.ended = False
        self.last_reward = 0.0

    @property
    def state(self):
        return self._state

    def reset(self,seed=None,task_id=None,**kwargs):
        if task_id is None:
            task_id = list(TASKS)[(seed or 0)%len(TASKS)]
        if task_id not in TASKS: raise ValueError('Unknown task_id.')
        self.task = TASKS[task_id]
        self.code = self.task['starter']
        self.ended = False
        self.last_reward = 0.0
        self._state = State(episode_id=str(uuid4()),step_count=0)
        return RepairObservation(task_id=task_id,message=self.task['prompt']+'\nRepair solve using write, inspect with test, end with submit. Max 12 steps. No imports or I/O; ordinary Python builtins and container/string methods are available. Inputs must not be mutated.',source=self.code,reward=0.0,done=False)

    def step(self,action,**kwargs):
        if self.task is None: self.reset()
        if self.ended:
            return RepairObservation(task_id=self.task['task_id'],message='Episode ended. Reset to start another.',done=True,reward=self.last_reward,steps_left=0)
        self._state.step_count += 1
        result = None
        message = ''
        if action.operation == 'write':
            self.code = action.code
            try:
                validate_source(self.code)
                message = 'Source replaced. Use test for feedback or submit to finish.'
            except (SyntaxError,ValueError) as error:
                message = 'Invalid source: '+str(error)[:300]
        else:
            result = grade(self.code,self.task)
            message = json.dumps(result,ensure_ascii=False)
        self.ended = action.operation=='submit' or self._state.step_count>=MAX_STEPS
        if self.ended:
            result = result or grade(self.code,self.task)
            self.last_reward = result['passed']/result['total']
            message = json.dumps(result,ensure_ascii=False)
        return RepairObservation(task_id=self.task['task_id'],message=message,done=self.ended,reward=self.last_reward if self.ended else 0.0,steps_left=max(0,MAX_STEPS-self._state.step_count))

app = create_app(RepairEnvironment,RepairAction,RepairObservation,env_name='python_repair_lab',max_concurrent_envs=5)
