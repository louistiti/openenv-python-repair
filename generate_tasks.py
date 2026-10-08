"""Original, deterministic public curriculum. Gold functions are not shipped in the image."""
import csv
import io
import json
import math
import random
from pathlib import Path

rng = random.Random(20261008)
tasks = []
solutions = {}

def add(task_id, prompt, starter, solution, inputs):
    scope = {}
    exec(solution, scope)
    cases = [{"args": args, "expected": scope["solve"](*args)} for args in inputs]
    tasks.append({"task_id": task_id, "prompt": prompt, "starter": starter, "cases": cases})
    solutions[task_id] = solution

add("merge-intervals", "Implement solve(intervals). Merge closed intervals that overlap or touch, sort by start, and return lists [start,end]. Inputs may be unsorted; do not mutate them. Empty input returns [].", "def solve(intervals):\n    return sorted(intervals)\n", '''def solve(intervals):
    out = []
    for a,b in sorted(intervals):
        if out and a <= out[-1][1]:
            out[-1][1] = max(b, out[-1][1])
        else:
            out.append([a,b])
    return out
''', [[[]], [[[1,4],[2,3],[4,8]]]] + [[[[a,a+rng.randrange(8)] for a in [rng.randrange(-20,30) for _ in range(rng.randrange(1,16))]]] for _ in range(70)])

add("moving-sums", "Implement solve(values,k). Return sums of every contiguous window of length k. k<=0 or k>len(values) returns [].", "def solve(values,k):\n    return [sum(values[i:i+k]) for i in range(len(values)-k)]\n", '''def solve(values,k):
    if k <= 0 or k > len(values): return []
    return [sum(values[i:i+k]) for i in range(len(values)-k+1)]
''', [[[],1], [[1,2,3],2], [[5],1], [[1],0]] + [[[rng.randrange(-100,101) for _ in range(rng.randrange(20))],rng.randrange(-2,23)] for _ in range(80)])

add("weighted-mean", "Implement solve(values,weights). Inputs have equal length and nonnegative weights. Return weighted arithmetic mean; return None if total weight is zero (including empty inputs).", "def solve(values,weights):\n    return sum(values)/len(values) if values else None\n", '''def solve(values,weights):
    total = sum(weights)
    return sum(x*w for x,w in zip(values,weights))/total if total else None
''', [[[],[]], [[2,10],[0,1]], [[2],[0]]] + [[[rng.randrange(-50,51) for _ in range(n)], [rng.randrange(6) for _ in range(n)]] for n in [rng.randrange(1,20) for _ in range(80)]])

add("stable-unique", "Implement solve(values). Deduplicate integer values while preserving first occurrence order. Empty list stays empty.", "def solve(values):\n    return sorted(set(values))\n", '''def solve(values):
    seen = set()
    out = []
    for x in values:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
''', [[[]], [[3,1,3,2,1]]] + [[[rng.randrange(-10,11) for _ in range(rng.randrange(30))]] for _ in range(80)])

add("run-length", "Implement solve(text). Run-length encode consecutive Unicode characters as a list of [character,count] pairs. Empty text returns []. Nonadjacent occurrences remain separate.", "def solve(text):\n    return [[c,text.count(c)] for c in sorted(set(text))]\n", '''def solve(text):
    out = []
    for c in text:
        if out and out[-1][0] == c: out[-1][1] += 1
        else: out.append([c,1])
    return out
''', [[""], ["aabbaa"], ["猫猫🙂🙂猫"]] + [["".join(rng.choice("ab c猫🙂") for _ in range(rng.randrange(35)))] for _ in range(80)])

add("luhn", "Implement solve(text). Return whether a nonempty ASCII digit string satisfies the Luhn checksum: starting from right, double every second digit, subtract 9 if >9, and require total divisible by 10. Nondigits/empty input return False.", "def solve(text):\n    return bool(text) and text.isdigit() and sum(int(c) for c in text)%10 == 0\n", '''def solve(text):
    if not text or any(c not in '0123456789' for c in text): return False
    total = 0
    for i,c in enumerate(reversed(text)):
        v = int(c)
        if i%2:
            v *= 2
            if v > 9: v -= 9
        total += v
    return total%10 == 0
''', [[x] for x in ["", "0", "79927398713", "79927398714", "12x", " 0", "１２", "0000"]] + [["".join(rng.choice("0123456789") for _ in range(rng.randrange(1,20)))] for _ in range(140)])

add("edit-distance", "Implement solve(a,b). Return Levenshtein edit distance with unit-cost insertion, deletion, and substitution over Unicode characters.", "def solve(a,b):\n    return abs(len(a)-len(b))\n", '''def solve(a,b):
    row = list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt = [i]
        for j,y in enumerate(b,1):
            nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x != y)))
        row = nxt
    return row[-1]
''', [["",""], ["kitten","sitting"], ["猫","狗"]] + [["".join(rng.choice("abcd猫") for _ in range(rng.randrange(12))), "".join(rng.choice("abcd猫") for _ in range(rng.randrange(12)))] for _ in range(80)])

add("meeting-rooms", "Implement solve(intervals). Return minimum rooms for positive-length half-open meetings [start,end). A meeting ending at time t frees its room for one starting at t. Empty input returns 0.", "def solve(intervals):\n    return len(intervals)\n", '''def solve(intervals):
    events = []
    for a,b in intervals:
        events.append([a,1])
        events.append([b,-1])
    active = best = 0
    for t,d in sorted(events):
        active += d
        best = max(best,active)
    return best
''', [[[]], [[[0,1],[1,2]]], [[[0,5],[1,3],[2,4]]]] + [[[[a,a+rng.randrange(1,9)] for a in [rng.randrange(20) for _ in range(rng.randrange(20))]]] for _ in range(80)])

add("nearest-percentile", "Implement solve(values,p). Return nearest-rank percentile: sort ascending and take 1-based rank max(1,ceil(p/100*n)). p is integer 0..100. Empty input returns None.", "def solve(values,p):\n    return sorted(values)[int(p/100*len(values))] if values else None\n", '''def solve(values,p):
    if not values: return None
    rank = max(1,(p*len(values)+99)//100)
    return sorted(values)[rank-1]
''', [[[],50], [[1,2,3,4],100], [[1,2,3,4],50], [[4],0]] + [[[rng.randrange(-100,101) for _ in range(rng.randrange(1,30))],rng.randrange(101)] for _ in range(80)])

add("fifo-inventory", "Implement solve(lots,demand). lots are [quantity,unit_price_cents] in purchase order with nonnegative integers. Return [cost_cents,remaining_lots] after fulfilling demand FIFO, dropping zero-quantity lots. If inventory cannot cover demand, return None. Do not mutate input; demand>=0.", "def solve(lots,demand):\n    return [0,lots]\n", '''def solve(lots,demand):
    if sum(q for q,p in lots) < demand: return None
    remaining = []
    cost = 0
    for q,p in lots:
        used = min(q,demand)
        demand -= used
        cost += used*p
        if q-used: remaining.append([q-used,p])
    return [cost,remaining]
''', [[[],0], [[],1], [[[2,100],[3,200]],3], [[[0,50],[2,80]],0]] + [[[[rng.randrange(8),rng.randrange(1000)] for _ in range(rng.randrange(10))],rng.randrange(35)] for _ in range(80)])

add("csv-row", "Implement solve(row). Parse one valid CSV record into strings, comma delimiter, double-quote quoting, and doubled quotes inside quoted fields. No embedded newlines. Empty row means []. Do not trim spaces. Use no imports.", "def solve(row):\n    return row.split(',') if row else []\n", '''def solve(row):
    if not row: return []
    out = []
    field = ''
    quoted = False
    i = 0
    while i < len(row):
        c = row[i]
        if c == '"':
            if quoted and i+1 < len(row) and row[i+1] == '"':
                field += '"'
                i += 1
            else: quoted = not quoted
        elif c == ',' and not quoted:
            out.append(field)
            field = ''
        else: field += c
        i += 1
    out.append(field)
    return out
''', [[x] for x in ["", "a,b", '"a,b",c', '"a""b",,c', ',,', '""']] + [[(lambda s: (csv.writer(s,lineterminator="\n").writerow(["".join(rng.choice('ab ,"猫') for _ in range(rng.randrange(12))) for _ in range(rng.randrange(1,8))]),s.getvalue().rstrip("\n"))[1])(io.StringIO())] for _ in range(80)])

add("shortest-path", "Implement solve(graph,start,target). graph maps string nodes to lists of [neighbor,nonnegative_integer_weight] directed edges. Return shortest distance, or None if unreachable. start==target returns 0. Nodes without a key have no outgoing edges.", "def solve(graph,start,target):\n    return 0 if start == target else None\n", '''def solve(graph,start,target):
    dist = {start:0}
    visited = set()
    while True:
        candidates = [n for n in dist if n not in visited]
        if not candidates: return None
        n = min(candidates,key=lambda x:dist[x])
        if n == target: return dist[n]
        visited.add(n)
        for nxt,w in graph.get(n,[]):
            d = dist[n]+w
            if nxt not in dist or d < dist[nxt]: dist[nxt] = d
''', [[{},"a","a"], [{},"a","b"], [{"a":[["b",5],["c",1]],"c":[["b",1]]},"a","b"]] + [[{str(i):[[str(j),rng.randrange(10)] for j in range(n) if j != i and rng.random() < .3] for i in range(n)},"0",str(n-1)] for n in [rng.randrange(2,9) for _ in range(80)]])

# Balance checksums and exact-rank boundaries so trivial policies do not earn
# nearly-perfect rewards by exploiting skewed random input distributions.
for task in tasks:
    scope = {}
    exec(solutions[task['task_id']],scope)
    if task['task_id'] == 'luhn':
        for i in range(8,len(task['cases'])):
            prefix = ''.join(rng.choice('0123456789') for _ in range(rng.randrange(1,18)))
            digit = next(d for d in range(10) if scope['solve'](prefix+str(d)))
            text = prefix+str(digit if i%2 else (digit+1)%10)
            task['cases'][i] = {'args':[text],'expected':scope['solve'](text)}
    if task['task_id'] == 'nearest-percentile':
        for i in range(4,len(task['cases'])):
            values = [rng.randrange(-100,101) for _ in range(2*rng.randrange(1,15))]
            p = [0,50,100][i%3]
            task['cases'][i] = {'args':[values,p],'expected':scope['solve'](values,p)}

if __name__ == '__main__':
    Path('tasks.json').write_text(json.dumps(tasks,ensure_ascii=False,indent=2)+'\n')
    Path('solutions.json').write_text(json.dumps(solutions,ensure_ascii=False,indent=2)+'\n')
    Path('tasks.jsonl').write_text(''.join(json.dumps({**t,"split":"train"},ensure_ascii=False)+'\n' for t in tasks))
    print(f'Generated {len(tasks)} tasks, {sum(len(t["cases"]) for t in tasks)} deterministic cases.')
