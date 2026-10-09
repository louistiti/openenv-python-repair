"""Every designed defect must fail its intended edge group, not just random noise."""
import pytest
from execution import grade
from tasks import make_task

TARGETS=[
    ('ledger','identity.py','identity'),('ledger','lots.py','fifo'),('ledger','charges.py','fee'),
    ('capacity','events.py','half_open'),('capacity','rules.py','strict'),('capacity','merge.py','merge'),
    ('workflow','graph.py','missing'),('workflow','timing.py','join'),('workflow','report.py','deadline'),
    ('incident','order.py','ties'),('incident','window.py','boundary'),('incident','resetter.py','reset_scope'),
    ('sensor','dedup.py','dedup'),('sensor','convert.py','convert'),('sensor','stats.py','median'),
    ('reconcile','parse.py','quoting'),('reconcile','keys.py','unicode'),('reconcile','amounts.py','sign'),
    ('allocation','network.py','reroute'),('allocation','paths.py','reroute'),('allocation','augment.py','bottleneck'),
    ('expression','lex.py','literal'),('expression','binding.py','power'),('expression','unary.py','unary'),
]

@pytest.mark.parametrize('family,path,group',TARGETS)
def test_every_defect_has_deterministic_edge_witness(family,path,group):
    for seed in range(3):
        task=make_task(f'{family}-3',seed)
        cases=[c for c in task.hidden if c['group']==group]
        assert cases
        assert grade(task.solution,cases)['reward']==1
        single=dict(task.solution,**{path:task.starter[path]})
        assert grade(single,cases)['reward']==0,(family,path,group,seed)
