"""Bounded restricted Python execution. Parent owns all expected answers and rewards.

Not a general sandbox. AST/builtin restrictions and a subprocess are defense in
 depth; the container is the outer isolation boundary. Hidden tests, references
 and grading state are never sent to the candidate interpreter.
"""
import ast
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

STDLIB = {'csv', 'io', 'fractions'}
EXPORTS = {'csv': {'DictReader', 'reader'}, 'io': {'StringIO'}, 'fractions': {'Fraction'}}
METHODS = set('append extend pop insert remove clear sort reverse count index get keys values items setdefault add discard union intersection difference split splitlines join strip lstrip rstrip replace startswith endswith lower upper casefold isdigit isalpha isalnum isspace copy fromkeys numerator denominator limit_denominator'.split()) | set().union(*EXPORTS.values())
MAX_SOURCE = 48000
RUNNER = r'''
import builtins, contextlib, importlib, io, json, resource, sys, types
resource.setrlimit(resource.RLIMIT_CPU, (2,2))
if sys.platform != 'darwin':
    resource.setrlimit(resource.RLIMIT_AS,(256*1024*1024,256*1024*1024))
resource.setrlimit(resource.RLIMIT_FSIZE,(1048576,1048576))
resource.setrlimit(resource.RLIMIT_NOFILE,(16,16))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
payload=json.load(sys.stdin)
sources={p[:-3]:c for p,c in payload['files'].items()}
allowed={n:getattr(builtins,n) for n in 'abs all any bool dict enumerate filter float int isinstance len list map max min pow range reversed round set sorted str sum tuple zip Exception ValueError TypeError'.split()}
cache={}
loading=set()
def load(name,globals=None,locals=None,fromlist=(),level=0):
    if level or '.' in name:
        raise ImportError('only absolute top-level imports')
    if name in ('csv','io','fractions'):
        names={'csv':['DictReader','reader'],'io':['StringIO'],'fractions':['Fraction']}[name]
        safe=types.ModuleType(name)
        original=importlib.import_module(name)
        for n in names:
            setattr(safe,n,getattr(original,n))
        return safe
    if name not in sources:
        raise ImportError(name)
    if name in loading:
        raise ImportError('circular local import')
    if name not in cache:
        loading.add(name)
        module=types.ModuleType(name)
        module.__dict__['__builtins__']=dict(allowed, __import__=load)
        exec(sources[name],module.__dict__,module.__dict__)
        cache[name]=module
        loading.remove(name)
    return cache[name]
results=[]
try:
    with contextlib.redirect_stdout(io.StringIO()):
        solve=load('main').solve
        for args in payload['args']:
            original=json.dumps(args,sort_keys=True,allow_nan=False)
            try:
                output=solve(*args)
                encoded=json.dumps(output,allow_nan=False)
                if len(encoded)>20000:
                    raise ValueError('output too large')
                results.append({'output':json.loads(encoded),'mutated':original!=json.dumps(args,sort_keys=True,allow_nan=False)})
            except BaseException as e:
                results.append({'error':type(e).__name__})
except BaseException as e:
    results=[{'error':type(e).__name__} for args in payload['args']]
print(json.dumps(results,allow_nan=False))
'''

def validate(files):
    if 'main.py' not in files or sum(len(c) for c in files.values()) > MAX_SOURCE:
        raise ValueError('Missing main.py or workspace too large')
    locals_allowed = {p[:-3] for p in files}
    for path, code in files.items():
        if not path.endswith('.py') or not path[:-3].isidentifier() or path.startswith('_'):
            raise ValueError('Only flat public Python module names')
        tree = ast.parse(code)
        if path == 'main.py' and not any(isinstance(n,ast.FunctionDef) and n.name=='solve' for n in tree.body):
            raise ValueError('main.py must define solve')
        for n in ast.walk(tree):
            if isinstance(n,(ast.ClassDef,ast.AsyncFunctionDef,ast.Await,ast.With,ast.AsyncWith,ast.Global,ast.Nonlocal)):
                raise ValueError('Unsupported control construct')
            if isinstance(n,ast.Import):
                for a in n.names:
                    if a.name not in locals_allowed | STDLIB or (a.asname or a.name).startswith('_'):
                        raise ValueError('Import unavailable')
            if isinstance(n,ast.ImportFrom):
                if n.level or n.module not in locals_allowed | STDLIB or any(a.name.startswith('_') or (a.asname or '').startswith('_') or a.name=='*' or (n.module in STDLIB and a.name not in EXPORTS[n.module]) for a in n.names):
                    raise ValueError('Import unavailable')
            if isinstance(n,ast.Attribute) and n.attr not in METHODS:
                raise ValueError('Private attributes and I/O unavailable')
            if isinstance(n,ast.Name) and (n.id.startswith('_') or n.id in {'open','eval','exec','compile','globals','locals','vars','getattr','setattr','delattr','hasattr','type','input','print','breakpoint','help','dir','memoryview'}):
                raise ValueError('Private/dynamic names and I/O unavailable')
            if isinstance(n,(ast.FunctionDef,ast.arg)):
                name=n.name if isinstance(n,ast.FunctionDef) else n.arg
                if name.startswith('_') or (isinstance(n,ast.FunctionDef) and n.decorator_list):
                    raise ValueError('Private or decorated functions unavailable')
            if isinstance(n,ast.ExceptHandler) and n.name and n.name.startswith('_'):
                raise ValueError('Private exception alias unavailable')
    return True

def equal(actual, expected):
    if isinstance(actual,bool) or isinstance(expected,bool):
        return type(actual) is type(expected) and actual==expected
    if isinstance(actual,(int,float)) and isinstance(expected,(int,float)):
        return math.isfinite(actual) and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-10)
    if isinstance(actual,list) and isinstance(expected,list):
        return len(actual)==len(expected) and all(equal(a,b) for a,b in zip(actual,expected))
    if isinstance(actual,dict) and isinstance(expected,dict):
        return actual.keys()==expected.keys() and all(equal(actual[k],expected[k]) for k in expected)
    return type(actual) is type(expected) and actual==expected

def grade(files, cases, feedback=False):
    total=len(cases)
    outputs=[]
    error=None
    try:
        validate(files)
        # Bounded spool prevents untrusted output exhausting parent memory.
        with tempfile.TemporaryDirectory(prefix='repair-v3-') as work:
            output_path=Path(work)/'result'
            with output_path.open('w+') as out:
                process=subprocess.run([sys.executable,'-I','-S','-c',RUNNER],
                    input=json.dumps({'files':files,'args':[c['args'] for c in cases]}),
                    text=True,stdout=out,stderr=subprocess.DEVNULL,timeout=3,
                    cwd=work,env={'PATH':'/usr/bin:/bin'})
                out.seek(0)
                raw=out.read(1048577)
            if process.returncode or len(raw)>1048576:
                raise ValueError('execution/resource limit')
            outputs=json.loads(raw)
            if not isinstance(outputs,list) or len(outputs)!=total:
                raise ValueError('invalid result protocol')
    except (ValueError,SyntaxError,RecursionError,subprocess.TimeoutExpired) as e:
        error=type(e).__name__+': '+str(e)[:150]
    groups, failures, passed={},[],0
    for i,c in enumerate(cases):
        result=outputs[i] if i<len(outputs) else {'error':error or 'no output'}
        ok=isinstance(result,dict) and 'output' in result and not result.get('mutated') and equal(result['output'],c['expected'])
        passed+=int(ok)
        tally=groups.setdefault(c['group'],[0,0]); tally[0]+=int(ok); tally[1]+=1
        if feedback and not ok and len(failures)<3:
            failures.append({'args':c['args'],'expected':c['expected'],'actual':result})
    # Balance distinct behaviors instead of allowing random easy cases to swamp edge cases.
    reward=sum(a/b for a,b in groups.values())/len(groups) if groups else 0.0
    result={'passed':passed,'total':total,'reward':reward}
    if feedback:
        result['failures']=failures
    if error:
        result['error']=error
    return result
