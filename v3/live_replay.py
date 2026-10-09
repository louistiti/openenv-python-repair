"""Replay all declared IDs through a real network WebSocket, not TestClient."""
import asyncio
import json
from pathlib import Path
from websockets.asyncio.client import connect
from tasks import TASK_IDS,make_task

async def send(sock,kind,data):
    await sock.send(json.dumps({'type':kind,'data':data}))
    response=json.loads(await asyncio.wait_for(sock.recv(),timeout=20))
    assert response['type']=='observation',response
    return response['data']

async def main():
    rows=[]
    for task_id in TASK_IDS:
        task=make_task(task_id,1234)
        async with connect('ws://127.0.0.1:8766/ws') as sock:
            initial=await send(sock,'reset',{'task_id':task_id,'seed':1234})
            assert initial['observation']['files']==task.starter
            floor=await send(sock,'step',{'operation':'submit'})
            assert floor['done'] and 0<=floor['reward']<1
            await send(sock,'reset',{'task_id':task_id,'seed':1234})
            for path in task.mutations:
                written=await send(sock,'step',{'operation':'write','path':path,'code':task.solution[path]})
                assert not written['done'] and written['reward']==0
            result=await send(sock,'step',{'operation':'test'})
            assert not result['done'] and result['reward']==0
            terminal=await send(sock,'step',{'operation':'submit'})
            assert terminal['done'] and terminal['reward']==1
            rows.append({'task_id':task_id,'seed':1234,'starter_reward':floor['reward'],'oracle_reward':terminal['reward'],'done':True})
    report={'transport':'real_network_websocket','task_ids':len(rows),'all_passed':True,'rows':rows,'model_rollouts':0}
    Path('live-replay-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'task_ids':len(rows),'all_passed':True}))

if __name__=='__main__':
    asyncio.run(main())
