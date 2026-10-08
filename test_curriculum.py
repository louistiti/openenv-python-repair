import json
from collections import Counter
from pathlib import Path

from server import TASKS, grade

MANIFEST = json.loads(Path('curriculum.json').read_text())
SOLUTIONS = json.loads(Path('solutions.json').read_text())
VIEWER = [json.loads(s) for s in Path('viewer_train.jsonl').read_text().splitlines()]


def test_curriculum_shape_and_training_selection():
    assert len(TASKS) == len(VIEWER) == 1200
    assert Counter(t['family'] for t in TASKS.values()) == {k:100 for k in MANIFEST['families']}
    assert len({(t['family'],t['bug_pattern']) for t in TASKS.values()}) == 48
    assert len(set(MANIFEST['arena_task_ids'])) == 50
    assert set(MANIFEST['arena_task_ids']) <= TASKS.keys()
    assert {(TASKS[t]['family'],TASKS[t]['bug_pattern']) for t in MANIFEST['arena_task_ids']} == {(t['family'],t['bug_pattern']) for t in TASKS.values()}


def test_variations_are_real_and_case_inputs_not_duplicated():
    for family in MANIFEST['families']:
        rows = [t for t in TASKS.values() if t['family']==family]
        assert len({t['starter'] for t in rows}) == 4
        assert len({t['case_seed'] for t in rows}) == 25
        assert len({json.dumps(t['cases'],sort_keys=True) for t in rows}) == 25
        assert len({t['prompt'] for t in rows}) >= 25
    for task in TASKS.values():
        assert len({json.dumps(c['args'],sort_keys=True) for c in task['cases']}) == len(task['cases'])


def test_lossless_viewer_rows_and_manifest_totals():
    assert sum(len(t['cases']) for t in TASKS.values()) == MANIFEST['cases_total']
    assert sum(r['arena_selected'] for r in VIEWER) == 50
    for row in VIEWER:
        task = TASKS[row['task_id']]
        assert row['num_cases']==len(task['cases'])
        assert json.loads(row['cases_json'])==task['cases']
        for field in ('family','bug_pattern','case_seed','prompt','starter'):
            assert row[field]==task[field]


def test_independent_hand_checked_semantics():
    examples = {
        'merge-intervals': ([[[4,7],[1,4],[2,3]]], [[1,7]]),
        'moving-sums': ([[2,-1,4],2], [1,3]),
        'weighted-mean': ([[2,8],[1,3]], 6.5),
        'stable-unique': ([[3,1,3,2,1]], [3,1,2]),
        'run-length': (['猫猫abbb'], [['猫',2],['a',1],['b',3]]),
        'luhn': (['79927398713'], True),
        'edit-distance': (['kitten','sitting'], 3),
        'meeting-rooms': ([[[0,1],[1,2]]], 1),
        'nearest-percentile': ([[1,2,3,4,5],50], 3),
        'fifo-inventory': ([[[2,10],[4,20]],3], [40,[[3,20]]]),
        'csv-row': (['"a,b","c""d",'], ['a,b','c"d','']),
        'shortest-path': ([{'a':[['b',9],['c',2]],'c':[['b',1]],'b':[['d',2]]},'a','d'], 5),
    }
    for family,(args,expected) in examples.items():
        result = grade(SOLUTIONS[family],{'cases':[{'args':args,'expected':expected}]})
        assert result['passed']==1, (family,result)
