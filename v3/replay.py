"""Replay oracle, starters and every single-defect ablation on fresh seeds."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path
from execution import grade
from tasks import TASK_IDS, make_task


def replay(count,start):
    rows=[]
    for task_id in TASK_IDS:
        floors=[]
        partials=[]
        workspace_hashes=set()
        case_hashes=set()
        for seed in range(start,start+count):
            task=make_task(task_id,seed)
            oracle=grade(task.solution,task.hidden)
            assert oracle['reward']==1,(task_id,seed,'oracle',oracle)
            floor=grade(task.starter,task.hidden)
            assert 0<=floor['reward']<1,(task_id,seed,'floor',floor)
            floors.append(floor['reward'])
            # Keep exactly one remaining defect at a time, not just the original bundle.
            for path in task.mutations:
                single=dict(task.solution,**{path:task.starter[path]})
                result=grade(single,task.hidden)
                assert result['reward']<1,(task_id,seed,'single undetected',path,result)
                partials.append(result['reward'])
            workspace_hashes.add(hashlib.sha256(json.dumps(task.starter,sort_keys=True).encode()).hexdigest())
            case_hashes.add(hashlib.sha256(json.dumps(task.hidden,sort_keys=True).encode()).hexdigest())
        row={'task_id':task_id,'episodes':count,'oracle_reward':1.0,'starter_reward_min':min(floors),
            'starter_reward_max':max(floors),'starter_reward_mean':statistics.mean(floors),
            'single_mutations_detected':len(partials),'single_mutation_reward_min':min(partials),
            'single_mutation_reward_max':max(partials),'distinct_workspaces':len(workspace_hashes),
            'distinct_hidden_sets':len(case_hashes)}
        rows.append(row)
        print(json.dumps(row),flush=True)
    return {'seed_start':start,'seeds_per_task':count,'task_ids':len(TASK_IDS),
            'episodes':count*len(TASK_IDS),'all_oracles_perfect':True,'all_starters_imperfect':True,
            'all_single_defects_detected':True,'model_rollouts':0,'rows':rows}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--seeds',type=int,default=50)
    parser.add_argument('--start',type=int,default=1000)
    parser.add_argument('--output',default='replay-results.json')
    args=parser.parse_args()
    assert args.seeds>0
    result=replay(args.seeds,args.start)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
