"""Python Repair Lab v3: generated multi-file debugging, OpenEnv pinned SDK."""
import json
from typing import Literal
from uuid import uuid4

from openenv.core.env_server.http_server import create_app
from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import Action, Observation, State
from pydantic import Field

from tasks import TASK_IDS, make_task
from execution import grade, validate

MAX_STEPS = 30

class RepairAction(Action):
    operation: Literal['read','write','test','submit'] = Field(description='read returns a workspace file; write replaces one module; test runs visible examples; submit grades hidden cases and ends.')
    path: str = Field(default='',max_length=80,description='Observed flat Python filename for read/write. No paths, new files or changes to settings.py.')
    code: str = Field(default='',max_length=16000,description='Full replacement module for write. Allowed: local imports, csv.DictReader/reader, io.StringIO, fractions.Fraction and ordinary builtins/methods. No private attributes, filesystem, network, process or dynamic execution.')

class RepairObservation(Observation):
    task_id: str = ''
    message: str = ''
    files: dict[str,str] = Field(default_factory=dict)
    steps_left: int = MAX_STEPS

class RepairEnvironment(Environment):
    SUPPORTS_CONCURRENT_SESSIONS = True

    def __init__(self):
        self._state = State(episode_id=str(uuid4()),step_count=0)
        self.task = None
        self.files = {}
        self.ended = False
        self.last_reward = 0.0

    @property
    def state(self):
        return self._state

    def reset(self, seed=None, task_id=None, **kwargs):
        seed = 0 if seed is None else seed
        if task_id is None:
            task_id = TASK_IDS[seed % len(TASK_IDS)]
        self.task = make_task(task_id,seed)
        self.files = dict(self.task.starter)
        self.ended = False
        self.last_reward = 0.0
        self._state = State(episode_id=str(uuid4()),step_count=0)
        return RepairObservation(task_id=task_id,message=self.task.prompt+'\nPublic examples: '+json.dumps(self.task.visible),files=dict(self.files),reward=0.0,done=False)

    def step(self,action,**kwargs):
        if self.task is None:
            self.reset()
        if self.ended:
            return RepairObservation(task_id=self.task.task_id,message='Episode ended.',done=True,reward=self.last_reward,steps_left=0)
        self._state.step_count += 1
        message, files = '', {}
        if action.operation == 'read':
            if action.path in self.files:
                files[action.path] = self.files[action.path]
                message = 'File contents.'
            else:
                message = 'Unknown file.'
        elif action.operation == 'write':
            if action.path not in self.files or action.path=='settings.py':
                message = 'Unknown or read-only file. Source unchanged.'
            else:
                candidate = dict(self.files, **{action.path:action.code})
                try:
                    validate(candidate)
                    self.files = candidate
                    message = 'Module replaced. Use test or submit.'
                except (SyntaxError,ValueError,RecursionError) as error:
                    message = 'Rejected; source unchanged: '+str(error)[:180]
        elif action.operation == 'test':
            message = json.dumps(grade(self.files,self.task.visible,feedback=True))
        self.ended = action.operation=='submit' or self._state.step_count>=MAX_STEPS
        if self.ended:
            result = grade(self.files,self.task.hidden)
            self.last_reward = result['reward']
            message = json.dumps(result)
        return RepairObservation(task_id=self.task.task_id,message=message,files=files,done=self.ended,reward=self.last_reward if self.ended else 0.0,steps_left=max(0,MAX_STEPS-self._state.step_count))

app = create_app(RepairEnvironment,RepairAction,RepairObservation,env_name='python_repair_lab_v3',max_concurrent_envs=5)
