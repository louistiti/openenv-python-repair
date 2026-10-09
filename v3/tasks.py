"""Original seeded multi-module repair tasks; references never enter candidate execution."""
import copy
import csv
import io
import random
from dataclasses import dataclass
from fractions import Fraction
from hard_tasks import HARD_SPECS, allocation_ref, expression_ref, hard_cases

FAMILIES = ('ledger', 'capacity', 'workflow', 'incident', 'sensor', 'reconcile', 'allocation', 'expression')
TASK_IDS = tuple(f'{f}-{level}' for f in FAMILIES for level in (1, 2, 3))

@dataclass
class Task:
    task_id: str
    seed: int
    prompt: str
    starter: dict
    solution: dict
    visible: list
    hidden: list
    mutations: list

def ledger_ref(events, fee):
    lots, pnl, missing = {}, 0, 0
    for e in events:
        key = (e['account'], e['asset'])
        queue = lots.setdefault(key, [])
        if e['side'] == 'buy':
            queue.extend([e['price']] * e['qty'])
        else:
            amount = min(e['qty'], len(queue))
            pnl += sum(e['price'] - p - fee for p in queue[:amount])
            del queue[:amount]
            missing += e['qty'] - amount
    return {'pnl': pnl, 'unfilled': missing, 'positions': [
        [a, s, len(q), sum(q)] for (a, s), q in sorted(lots.items()) if q]}

def capacity_ref(bookings, limit):
    # Independent interval scan, not the submitted endpoint sweep.
    boundaries = sorted({x for a, b, weight in bookings for x in (a, b) if a < b and weight > 0})
    segments, peak, area = [], 0, 0
    for a, b in zip(boundaries, boundaries[1:]):
        load = sum(w for s, e, w in bookings if s <= a < e and w > 0)
        peak = max(peak, load)
        area += max(0, load - limit) * (b - a)
        if load > limit:
            if segments and segments[-1][1] == a:
                segments[-1][1] = b
            else:
                segments.append([a, b])
    return {'peak': peak, 'overload': segments, 'excess_area': area}

def workflow_ref(jobs):
    lookup = {j['id']: j for j in jobs}
    finish, visiting = {}, set()
    def visit(name):
        if name not in lookup or name in visiting:
            raise ValueError('invalid dependencies')
        if name not in finish:
            visiting.add(name)
            j = lookup[name]
            finish[name] = j['duration'] + max([j['release']] + [visit(d) for d in j['deps']])
            visiting.remove(name)
        return finish[name]
    try:
        for j in jobs:
            visit(j['id'])
        return {'status': 'ok', 'finish': [[n, finish[n]] for n in sorted(finish)],
                'late': sorted(j['id'] for j in jobs if finish[j['id']] > j['deadline'])}
    except ValueError:
        return {'status': 'invalid', 'finish': [], 'late': []}

def incident_ref(events, window, threshold):
    ordered = sorted(enumerate(events), key=lambda x: (x[1]['time'], x[0]))
    history, seen, alerts = {}, set(), []
    for _, e in ordered:
        if e['id'] in seen:
            continue
        seen.add(e['id'])
        key = (e['user'], e['ip'])
        if e['outcome'] == 'success':
            history.pop(key, None)
            continue
        prior = [t for t in history.get(key, []) if e['time'] - window <= t]
        history[key] = prior + [e['time']]
        if len(prior) < threshold <= len(prior) + 1:
            alerts.append([e['user'], e['ip'], e['time']])
    return alerts

def sensor_ref(readings, calibrations, threshold):
    converted = {}
    for r in readings:
        if r['valid']:
            gain, offset = calibrations[r['sensor']]
            converted[(r['sensor'], r['time'])] = gain * r['value'] + offset
    groups = {}
    for (_, time), value in converted.items():
        groups.setdefault(time, []).append(value)
    result = []
    for time, values in sorted(groups.items()):
        ordered = sorted(values)
        n = len(ordered)
        mid = Fraction(ordered[n // 2]) if n % 2 else Fraction(ordered[n//2-1] + ordered[n//2], 2)
        result.append([time, float(mid), mid > threshold])
    return result

def reconcile_ref(left, right):
    totals = [{}, {}]
    for side, text in enumerate((left, right)):
        for row in csv.DictReader(io.StringIO(text)):
            key = row['key'].strip().casefold()
            value = Fraction(row['amount'])
            if row['kind'] == 'credit':
                value = -value
            totals[side][key] = totals[side].get(key, Fraction(0)) + value
    return [[key, str(totals[0].get(key, Fraction(0)) - totals[1].get(key, Fraction(0)))]
            for key in sorted(totals[0].keys() | totals[1].keys())
            if totals[0].get(key, Fraction(0)) != totals[1].get(key, Fraction(0))]

REFERENCES = dict(zip(FAMILIES, (ledger_ref, capacity_ref, workflow_ref, incident_ref, sensor_ref, reconcile_ref)))

# Each defect is in a distinct module and has a targeted verifier group.
SPECS = {
'ledger': (
    'solve(events): FIFO accounting in input order. Each event has account, asset, side (buy/sell), qty (positive integer), price (integer cents). Separate lots by (account,asset). Sell only available units, do not create shorts. Deduct FEE cents per filled sold unit. Return pnl, unfilled (total requested units lacking stock), and sorted nonempty positions [account,asset,qty,cost_basis]. Do not mutate input.',
    {
        'identity.py': "def key(e):\n    return (e['account'], e['asset'])\n",
        'lots.py': "def consume(queue, qty):\n    used = min(qty, sum(n for n, p in queue))\n    remaining, cost = used, 0\n    while remaining:\n        n, p = queue[0]\n        take = min(n, remaining)\n        cost += take * p\n        remaining -= take\n        if take == n:\n            queue.pop(0)\n        else:\n            queue[0] = (n - take, p)\n    return used, cost\n",
        'charges.py': "from settings import FEE\ndef profit(qty, price, cost):\n    return qty * (price - FEE) - cost\n",
        'main.py': "from identity import key\nfrom lots import consume\nfrom charges import profit\ndef solve(events):\n    lots, pnl, unfilled = {}, 0, 0\n    for e in events:\n        k = key(e)\n        q = lots.setdefault(k, [])\n        if e['side'] == 'buy':\n            q.append((e['qty'], e['price']))\n        else:\n            used, cost = consume(q, e['qty'])\n            pnl += profit(used, e['price'], cost)\n            unfilled += e['qty'] - used\n    return {'pnl': pnl, 'unfilled': unfilled, 'positions': [[a, s, sum(n for n, p in q), sum(n*p for n,p in q)] for (a,s),q in sorted(lots.items()) if q]}\n",
    }, [('identity.py', "(e['account'], e['asset'])", "(e['asset'], e['asset'])"),
        ('lots.py', 'queue[0]', 'queue[-1]'),
        ('charges.py', 'qty * (price - FEE) - cost', 'qty * price - FEE - cost')]),
'capacity': (
    'solve(bookings): each [start,end,weight] is a half-open integer-time weighted reservation. Ignore zero-length and nonpositive-weight entries. Return peak load, merged maximal overload intervals where load > LIMIT, and integral of max(load-LIMIT,0) over time as excess_area. Touching overload intervals must merge. Input unchanged.',
    {
        'events.py': "def endpoints(bookings):\n    delta = {}\n    for a,b,w in bookings:\n        if a < b and w > 0:\n            delta[a] = delta.get(a, 0) + w\n            delta[b] = delta.get(b, 0) - w\n    return sorted(delta.items())\n",
        'rules.py': "from settings import LIMIT\ndef overloaded(load):\n    return load > LIMIT\ndef excess(load):\n    return max(0, load - LIMIT)\n",
        'merge.py': "def append_span(spans, a, b):\n    if spans and spans[-1][1] == a:\n        spans[-1][1] = b\n    else:\n        spans.append([a,b])\n",
        'main.py': "from events import endpoints\nfrom rules import overloaded, excess\nfrom merge import append_span\ndef solve(bookings):\n    points = endpoints(bookings)\n    load, peak, area, spans = 0, 0, 0, []\n    for i in range(len(points)-1):\n        a,delta = points[i]\n        b = points[i+1][0]\n        load += delta\n        peak = max(peak, load)\n        area += excess(load) * (b-a)\n        if overloaded(load):\n            append_span(spans, a, b)\n    return {'peak': peak, 'overload': spans, 'excess_area': area}\n",
    }, [('events.py', 'delta.get(b, 0) - w', 'delta.get(b, 0) + w'),
        ('rules.py', 'load > LIMIT', 'load >= LIMIT'),
        ('merge.py', 'spans[-1][1] == a', 'spans[-1][1] > a')]),
'workflow': (
    'solve(jobs): jobs have unique id, duration>=0, release>=0, deadline, deps (job IDs). Unlimited parallel workers. Start each job at max(release, predecessor finish times), then add duration. Return status=ok, sorted finish pairs and IDs with finish strictly greater than deadline as late. Missing dependencies or any cycle make the whole graph invalid: status=invalid, finish=[], late=[]. Jobs are arbitrarily ordered; do not mutate them.',
    {
        'graph.py': "def ready(job, pending, finished):\n    return all(d in finished for d in job['deps'])\n",
        'timing.py': "def end_time(job, finished):\n    return max([job['release']] + [finished[d] for d in job['deps']]) + job['duration']\n",
        'report.py': "def report(jobs, finished):\n    return {'status': 'ok', 'finish': [[n,finished[n]] for n in sorted(finished)], 'late': sorted(j['id'] for j in jobs if finished[j['id']] > j['deadline'])}\n",
        'main.py': "from graph import ready\nfrom timing import end_time\nfrom report import report\ndef solve(jobs):\n    pending = {j['id']:j for j in jobs}\n    finished = {}\n    while pending:\n        progress = False\n        for name,job in list(pending.items()):\n            if ready(job, pending, finished):\n                finished[name] = end_time(job, finished)\n                del pending[name]\n                progress = True\n        if not progress:\n            return {'status':'invalid','finish':[],'late':[]}\n    return report(jobs, finished)\n",
    }, [('graph.py', "all(d in finished for d in job['deps'])", "all(d not in pending for d in job['deps'])"),
        ('timing.py', "max([job['release']] + [finished[d] for d in job['deps']])", "job['release'] + sum(finished[d] for d in job['deps'])"),
        ('report.py', "> j['deadline']", ">= j['deadline']")]),
'incident': (
    'solve(events): process events by (time, original index), preserving ties. Global event id deduplication keeps the first in that sorted order. Group failures by (user,ip). At each failure retain times in inclusive [time-WINDOW,time]. Alert [user,ip,time] only on a crossing from fewer than THRESHOLD failures to at least THRESHOLD. A success clears that pair only. Return alerts in processing order, without mutating events.',
    {
        'order.py': "def ordered(events):\n    return sorted(enumerate(events), key=lambda x: (x[1]['time'], x[0]))\n",
        'window.py': "from settings import WINDOW\ndef trim(times, now):\n    return [t for t in times if t >= now - WINDOW]\n",
        'resetter.py': "def reset(history, key):\n    history.pop(key, None)\n",
        'main.py': "from settings import THRESHOLD\nfrom order import ordered\nfrom window import trim\nfrom resetter import reset\ndef solve(events):\n    history, seen, alerts = {}, set(), []\n    for idx,e in ordered(events):\n        if e['id'] in seen:\n            continue\n        seen.add(e['id'])\n        k = (e['user'],e['ip'])\n        if e['outcome'] == 'success':\n            reset(history,k)\n        else:\n            prior = trim(history.get(k,[]),e['time'])\n            history[k] = prior + [e['time']]\n            if len(prior) < THRESHOLD <= len(prior)+1:\n                alerts.append([e['user'],e['ip'],e['time']])\n    return alerts\n",
    }, [('order.py', "(x[1]['time'], x[0])", "(x[1]['time'], -x[0])"),
        ('window.py', 't >= now - WINDOW', 't > now - WINDOW'),
        ('resetter.py', 'history.pop(key, None)', 'history.clear()')]),
'sensor': (
    'solve(readings): readings have sensor, time, value (integer), valid (bool). Ignore invalid readings; for duplicate (sensor,time), keep the last valid occurrence in input order. Convert each retained value with CALIBRATIONS[sensor]=[gain,offset] as gain*value+offset BEFORE aggregation. Return sorted [time,median,alarm] rows; even-count median averages the middle two; alarm is median strictly > THRESHOLD. Inputs unchanged.',
    {
        'dedup.py': "def latest(readings):\n    kept = {}\n    for r in readings:\n        if r['valid']:\n            kept[(r['sensor'],r['time'])] = r\n    return list(kept.values())\n",
        'convert.py': "from settings import CALIBRATIONS\ndef convert(r):\n    gain,offset = CALIBRATIONS[r['sensor']]\n    return gain*r['value']+offset\n",
        'stats.py': "def median(values):\n    v = sorted(values)\n    n = len(v)\n    return v[n//2] if n%2 else (v[n//2-1]+v[n//2])/2\n",
        'main.py': "from settings import THRESHOLD\nfrom dedup import latest\nfrom convert import convert\nfrom stats import median\ndef solve(readings):\n    groups = {}\n    for r in latest(readings):\n        groups.setdefault(r['time'],[]).append(convert(r))\n    return [[t, median(v), median(v)>THRESHOLD] for t,v in sorted(groups.items())]\n",
    }, [('dedup.py', "kept[(r['sensor'],r['time'])] = r", "kept.setdefault((r['sensor'],r['time']), r)"),
        ('convert.py', "gain*r['value']+offset", "gain*(r['value']+offset)"),
        ('stats.py', '(v[n//2-1]+v[n//2])/2', 'v[n//2]')]),
'reconcile': (
    'solve(left,right): two CSV strings with header key,amount,kind. CSV quoting follows Python csv rules. Normalize keys using strip().casefold(). Amount is a finite decimal string, kind is debit or credit; credits negate the amount. Sum duplicates separately in each file using exact arithmetic. Return sorted [key,delta] for nonzero left-minus-right differences. delta MUST be canonical Fraction string (integer if denominator=1, otherwise numerator/denominator), not decimal or float.',
    {
        'parse.py': "import csv\nimport io\ndef rows(text):\n    return list(csv.DictReader(io.StringIO(text)))\n",
        'keys.py': "def key(row):\n    return row['key'].strip().casefold()\n",
        'amounts.py': "from fractions import Fraction\ndef amount(row):\n    value = Fraction(row['amount'])\n    return -value if row['kind']=='credit' else value\n",
        'main.py': "from fractions import Fraction\nfrom parse import rows\nfrom keys import key\nfrom amounts import amount\ndef totals(text):\n    out = {}\n    for row in rows(text):\n        k = key(row)\n        out[k] = out.get(k,Fraction(0)) + amount(row)\n    return out\ndef solve(left,right):\n    a,b = totals(left),totals(right)\n    return [[k,str(a.get(k,Fraction(0))-b.get(k,Fraction(0)))] for k in sorted(set(a)|set(b)) if a.get(k,Fraction(0))!=b.get(k,Fraction(0))]\n",
    }, [('parse.py', 'list(csv.DictReader(io.StringIO(text)))', "[dict(zip(['key','amount','kind'],line.split(','))) for line in text.splitlines()[1:]]"),
        ('keys.py', ".strip().casefold()", ".strip().lower()"),
        ('amounts.py', "-value if row['kind']=='credit' else value", 'value')]),
}

def csv_text(rows):
    f = io.StringIO()
    w = csv.writer(f)
    w.writerow(['key','amount','kind'])
    w.writerows(rows)
    return f.getvalue()

def cases(family, rng, config):
    """Targeted edge groups plus compositional random tests; no private benchmark data."""
    out = []
    def add(group, *args):
        out.append({'group': group, 'args': list(args)})
    if family == 'ledger':
        def event(a, s, side, n, p):
            return dict(account=a,asset=s,side=side,qty=n,price=p)
        add('empty', [])
        add('identity', [event('a','x','buy',3,100),event('b','x','sell',2,150)])
        add('fifo', [event('a','x','buy',2,10),event('a','x','buy',3,30),event('a','x','sell',3,45)])
        add('fee', [event('a','x','buy',4,7),event('a','x','sell',4,12)])
        add('shortfall', [event('a','x','buy',1,10),event('a','x','sell',5,30)])
        for i in range(30):
            add('random', [event(rng.choice('abc'),rng.choice('xyz'),rng.choice(['buy','sell']),rng.randint(1,6),rng.randint(1,250)) for _ in range(rng.randint(4,30))])
    elif family == 'capacity':
        limit = config['LIMIT']
        add('empty', [])
        add('half_open', [[0,4,limit],[4,7,limit]])
        add('strict', [[0,5,limit]])
        add('merge', [[0,3,limit+1],[3,6,limit+2]])
        add('ignore', [[0,0,99],[1,5,0],[2,8,-3]])
        for i in range(30):
            values=[]
            for j in range(rng.randint(2,15)):
                a = rng.randint(-5,15)
                values.append([a,a+rng.randint(0,10),rng.randint(-1,limit+4)])
            add('random', values)
    elif family == 'workflow':
        def job(n, deps, duration=2, release=0, deadline=10):
            return dict(id=n,deps=deps,duration=duration,release=release,deadline=deadline)
        add('empty', [])
        add('missing', [job('a',['absent'])])
        add('cycle', [job('a',['b']),job('b',['a'])])
        add('join', [job('c',['a','b'],3,4),job('b',[],5,2),job('a',[],2,1)])
        add('deadline', [job('a',[],5,0,5)])
        for i in range(30):
            rows=[]
            for j in range(rng.randint(3,12)):
                rows.append(job(f'n{j}',[f'n{k}' for k in range(j) if rng.random()<.35],rng.randint(0,6),rng.randint(0,9),rng.randint(2,25)))
            if i%7==0:
                rows[0]['deps'] = [rows[-1]['id']]
                rows[-1]['deps'].append(rows[0]['id'])
            rng.shuffle(rows)
            add('random', rows)
    elif family == 'incident':
        window, threshold = config['WINDOW'], config['THRESHOLD']
        def event(i,t,u='u',ip='ip',outcome='failure'):
            return dict(id=str(i),time=t,user=u,ip=ip,outcome=outcome)
        add('empty', [])
        add('boundary', [event(i,0 if i==0 else window) for i in range(threshold)])
        add('ties', [event('s',0,outcome='success')]+[event(i,0) for i in range(threshold)]+[event(f'later{i}',1) for i in range(threshold)])
        add('reset_scope', [event(i,0,'a') for i in range(threshold-1)]+[event('s',1,'b',outcome='success'),event('last',2,'a')])
        add('dedup', [event('dup',0)]*threshold)
        for i in range(30):
            rows=[event(j,rng.randint(0,window*3),rng.choice('ab'),rng.choice(['ip1','ip2']),rng.choice(['failure']*5+['success'])) for j in range(45)]
            rows.extend(copy.deepcopy(rows[:5]))
            rng.shuffle(rows)
            add('random', rows)
    elif family == 'sensor':
        names=list(config['CALIBRATIONS'])
        def reading(s,t,v,valid=True):
            return dict(sensor=s,time=t,value=v,valid=valid)
        add('empty', [])
        add('dedup', [reading(names[0],1,0),reading(names[0],1,9),reading(names[0],1,100,False)])
        add('convert', [reading(names[1],2,3)])
        add('median', [reading(names[0],3,0),reading(names[1],3,10)])
        add('invalid', [reading(names[0],4,5,False)])
        for i in range(30):
            add('random', [reading(rng.choice(names),rng.randint(0,6),rng.randint(-10,20),rng.random()>.2) for _ in range(25)])
    else:
        add('empty', csv_text([]),csv_text([]))
        add('quoting',csv_text([('a,b','1.25','debit'),('a\nline','2','debit')]),csv_text([]))
        add('unicode',csv_text([(' Straße ','3','debit')]),csv_text([('STRASSE','3','debit')]))
        add('sign',csv_text([('x','0.1','credit'),('x','0.2','debit')]),csv_text([('x','0.1','debit')]))
        add('exact',csv_text([('x','0.1','debit'),('x','0.2','debit')]),csv_text([('x','0.3','debit')]))
        keys = [' Alpha ','ALPHA','beta','Straße','STRASSE','a,b','a\nline','"quote"']
        for i in range(30):
            pair=[]
            for side in range(2):
                pair.append(csv_text([(rng.choice(keys),f'{rng.randint(-1000,1000)/100:.2f}',rng.choice(['debit','credit'])) for _ in range(rng.randint(1,20))]))
            add('random',*pair)
    return out

def make_task(task_id, seed=0):
    if task_id not in TASK_IDS:
        raise ValueError('Unknown task_id')
    family, level_text = task_id.rsplit('-',1)
    level = int(level_text)
    rng = random.Random(f'v3/{task_id}/{seed}')
    config = {'FEE':rng.randint(1,7), 'LIMIT':rng.randint(2,8), 'WINDOW':rng.randint(5,20),
              'THRESHOLD':rng.randint(2,4), 'CALIBRATIONS':{'s0':[1,0],'s1':[rng.randint(2,4),rng.randint(1,5)],'s2':[-1,3]}}
    instruction, modules, defects = (HARD_SPECS if family in HARD_SPECS else SPECS)[family]
    solution = dict(modules)
    # Rotating subsets avoid a fixed easy starter for the lower levels.
    chosen = rng.sample(defects,level)
    starter = dict(solution)
    for path, before, after in chosen:
        assert before in starter[path], (family,path,before)
        starter[path] = starter[path].replace(before,after)
    settings = '\n'.join(f'{k} = {v!r}' for k,v in config.items())+'\n'
    starter['settings.py'] = solution['settings.py'] = settings
    all_cases = hard_cases(family,rng) if family in HARD_SPECS else cases(family,rng,config)
    if family=='ledger': extra=[config['FEE']]
    elif family=='capacity': extra=[config['LIMIT']]
    elif family=='incident': extra=[config['WINDOW'],config['THRESHOLD']]
    elif family=='sensor': extra=[config['CALIBRATIONS'],config['THRESHOLD']]
    else: extra=[]
    for c in all_cases:
        reference = {'allocation':allocation_ref,'expression':expression_ref}.get(family) or REFERENCES[family]
        c['expected'] = reference(*copy.deepcopy(c['args']),*extra)
    visible = [copy.deepcopy(all_cases[i]) for i in (0,1,len(all_cases)-1)]
    # Disjoint random held-outs; edge groups may share semantic shapes, not random payloads.
    hidden = all_cases[:-1]
    prompt = instruction + '\nRuntime constants are in settings.py. There are multiple modules; main.solve is the entry point. Repair any necessary files. Imports may use these local modules or csv, io, fractions. No filesystem/network/process access. Use read/write/test/submit; test exposes only public examples; submit runs hidden checks. Maximum 30 actions. Fresh data and defect combinations depend on reset seed.'
    return Task(task_id,seed,prompt,starter,solution,visible,hidden,[p for p,_,_ in chosen])
