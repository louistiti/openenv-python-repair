"""V2: 12 families x 4 repair patterns x 25 reproducible case sets.

The published 1,200 rows are episodes, not 1,200 unrelated algorithms.
Arena trains on 50 explicitly listed representatives, not every dataset row.
"""
import copy
import json
import random
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETS = 25
MUTATIONS = {
    'merge-intervals': [
        ('touching-boundary', 'a <= out[-1][1]', 'a < out[-1][1]'),
        ('nested-endpoint', 'max(b, out[-1][1])', 'min(b, out[-1][1])'),
        ('unsorted-input', 'for a,b in sorted(intervals):', 'for a,b in intervals:')],
    'moving-sums': [
        ('zero-window', 'k <= 0', 'k < 0'),
        ('window-width', 'values[i:i+k]', 'values[i:i+k-1]'),
        ('missing-first-window', 'range(len(values)-k+1)', 'range(1,len(values)-k+1)')],
    'weighted-mean': [
        ('unweighted-numerator', 'x*w', 'x'),
        ('wrong-denominator', 'total = sum(weights)', 'total = len(weights)'),
        ('zero-weight-result', 'if total else None', 'if total else 0')],
    'stable-unique': [
        ('reverse-traversal', 'for x in values:', 'for x in reversed(values):'),
        ('reverse-output', 'out.append(x)', 'out.insert(0,x)'),
        ('wrong-seen-value', 'seen.add(x)', 'seen.add(-x)')],
    'run-length': [
        ('inverted-grouping', 'out[-1][0] == c', 'out[-1][0] != c'),
        ('double-increment', 'out[-1][1] += 1', 'out[-1][1] += 2'),
        ('zero-initial-count', 'out.append([c,1])', 'out.append([c,0])')],
    'luhn': [
        ('wrong-parity', 'if i%2:', 'if not i%2:'),
        ('wrong-reduction', 'v -= 9', 'v -= 8'),
        ('wrong-modulus', 'total%10', 'total%9')],
    'edit-distance': [
        ('row-boundary', 'nxt = [i]', 'nxt = [0]'),
        ('inverted-substitution', '(x != y)', '(x == y)'),
        ('diagonal-index', 'row[j-1]+', 'row[j]+')],
    'meeting-rooms': [
        ('tie-order', 'sorted(events)', 'sorted(events,key=lambda item:(item[0],-item[1]))'),
        ('peak-tracking', 'best = max(best,active)', 'best = min(best,active)'),
        ('end-event-sign', 'events.append([b,-1])', 'events.append([b,1])')],
    'nearest-percentile': [
        ('floor-not-ceiling', '+99', '+0'),
        ('rank-index', '[rank-1]', '[rank-2]'),
        ('descending-order', 'sorted(values)', 'sorted(values,reverse=True)')],
    'fifo-inventory': [
        ('zero-lot-retention', 'if q-used:', 'if q >= used:'),
        ('over-consumption', 'used = min(q,demand)', 'used = max(q,demand)'),
        ('unit-cost-not-quantity', 'cost += used*p', 'cost += p')],
    'csv-row': [
        ('quoted-comma', "elif c == ',' and not quoted:", "elif c == ',':"),
        ('escaped-quote', "field += '\"'", "field += '\"\"'"),
        ('lost-final-field', '    out.append(field)\n    return out', '    if field: out.append(field)\n    return out')],
    'shortest-path': [
        ('farthest-first', 'n = min(candidates', 'n = max(candidates'),
        ('lost-path-prefix', 'd = dist[n]+w', 'd = w'),
        ('missing-relaxation', 'if nxt not in dist or d < dist[nxt]:', 'if nxt not in dist:')],
}


def extra_inputs(family, rng):
    """Distinct boundary instances, including failures absent from random pools."""
    out = []
    for i in range(20):
        a = rng.randrange(-40, 40)
        n = rng.randrange(3, 13)
        if family == 'merge-intervals':
            out.extend([[[[a+3,a+8],[a,a+3]]], [[[a,a+8],[a+1,a+2]]]])
        elif family == 'moving-sums':
            v = [rng.randrange(-30,31) for _ in range(n)]
            out.extend([[v,0], [v,1], [v,2]])
        elif family == 'weighted-mean':
            out.extend([[[a,a+7],[0,0]], [[a,a+7],[1,5]]])
        elif family == 'stable-unique':
            out.append([[a+2,a,a+2,a+1,a]])
        elif family == 'run-length':
            out.append([rng.choice('ab猫')*(i+2)+rng.choice('cd狗')*(i+1)])
        elif family == 'luhn':
            prefix = str(rng.randrange(10**5,10**8))
            total = 0
            for j,c in enumerate(reversed(prefix+'0')):
                digit = int(c)
                if j%2:
                    digit *= 2
                    if digit > 9: digit -= 9
                total += digit
            check = (-total)%10
            out.extend([[prefix+str(check)], [prefix+str((check+1)%10)]])
        elif family == 'edit-distance':
            text = ''.join(rng.choice('abc猫') for _ in range(n))
            out.extend([[text,''], [text,text], [text,text[::-1]]])
        elif family == 'meeting-rooms':
            out.extend([[[[a,a+2],[a+2,a+4]]], [[[a,a+8],[a+1,a+3],[a+2,a+7]]]])
        elif family == 'nearest-percentile':
            vals = list(range(a,a+2*n+1))
            rng.shuffle(vals)
            out.extend([[vals,33], [vals,50], [vals,99]])
        elif family == 'fifo-inventory':
            p = rng.randrange(1,500)
            out.extend([[[[0,p],[n,p+1]],0], [[[n,p],[n+1,p+2]],n-1]])
        elif family == 'csv-row':
            out.extend([[f'x{i},'], [f'"x{i},y",z'], [f'"x{i}""y",z']])
        elif family == 'shortest-path':
            # First-discovered route is not cheapest; later relaxation matters.
            prefix = rng.randrange(1,500)+i
            out.append([{'a':[['b',prefix+n],['c',prefix]],'c':[['b',1],['d',prefix+n+7]],'b':[['d',2]],'d':[]},'a','d'])
    return out


def build():
    tasks, solutions = [], {}
    patterns = {}
    for cohort in range(SETS):
        seed = 20261008 + 7919*cohort
        base = runpy.run_path(str(ROOT/'generate_tasks.py'),
                             init_globals={'CURRICULUM_SEED':seed}, run_name='base_curriculum')
        for original in base['tasks']:
            family = original['task_id']
            gold = base['solutions'][family]
            scope = {}
            exec(gold, scope)
            cases = copy.deepcopy(original['cases'])
            for args in extra_inputs(family, random.Random(seed+sum(map(ord,family)))):
                cases.append({'args':args,'expected':scope['solve'](*copy.deepcopy(args))})
            # Never inflate case counts with duplicated input instances.
            unique = {json.dumps(c['args'],ensure_ascii=False,sort_keys=True):c for c in cases}
            cases = list(unique.values())
            starters = [('baseline', original['starter'])]
            for label, before, after in MUTATIONS[family]:
                assert gold.count(before)==1, (family,label,before)
                starters.append((label,gold.replace(before,after)))
            patterns[family] = [name for name,_ in starters]
            for bug, (label, starter) in enumerate(starters):
                task_id = family if cohort==0 and bug==0 else f'{family}-b{bug}-s{cohort:02}'
                # Examples change with the cohort; this is visible training variation.
                chosen = random.Random(seed+bug).sample(cases, min(3,len(cases)))
                examples = [{'args':c['args'],'expected':c['expected']} for c in chosen]
                prompt = original['prompt']+'\nExamples (JSON args and expected result): '+json.dumps(examples,ensure_ascii=False)
                tasks.append({'task_id':task_id,'family':family,'bug_pattern':label,
                              'case_seed':seed,'prompt':prompt,'starter':starter,'cases':cases})
                solutions[task_id] = gold
    assert len(tasks)==1200 and len({t['task_id'] for t in tasks})==1200
    # All 48 patterns, distributed across cohorts, plus two further boundary-heavy episodes.
    representatives = []
    families = list(patterns)
    for index,family in enumerate(families):
        for bug in range(4):
            cohort = (index*2+bug*5)%SETS
            representatives.append(family if cohort==0 and bug==0 else f'{family}-b{bug}-s{cohort:02}')
    representatives += ['csv-row-b2-s24','shortest-path-b3-s24']
    assert len(set(representatives))==50
    selected = set(representatives)
    (ROOT/'tasks.json').write_text(json.dumps(tasks,ensure_ascii=False,separators=(',',':'))+'\n')
    (ROOT/'solutions.json').write_text(json.dumps(solutions,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'tasks.jsonl').write_text(''.join(json.dumps({**t,'split':'train'},ensure_ascii=False,separators=(',',':'))+'\n' for t in tasks))
    manifest = {'version':2,'families':patterns,'case_sets_per_pattern':SETS,'rows':len(tasks),
                'distinct_bug_patterns':48,'cases_total':sum(len(t['cases']) for t in tasks),
                'arena_task_ids':representatives,'arena_task_count':50,
                'note':'Only the 50 listed representatives train in Arena; the remaining rows are reproducible public episodes.'}
    (ROOT/'curriculum.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Retain full canonical row data for download; use stable primitive columns in Arrow.
    viewer=[]
    for task in tasks:
        row={k:task[k] for k in ('task_id','family','bug_pattern','case_seed','prompt','starter')}
        row.update(split='train',arena_selected=task['task_id'] in selected,num_cases=len(task['cases']),
                   cases_json=json.dumps(task['cases'],ensure_ascii=False,separators=(',',':')))
        assert json.loads(row['cases_json'])==task['cases']
        viewer.append(row)
    (ROOT/'viewer_train.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in viewer))
    print(json.dumps({k:v for k,v in manifest.items() if k!='families'},indent=2))


if __name__=='__main__':
    build()
