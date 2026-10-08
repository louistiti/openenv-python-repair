"""Replay every task against a real image/server over persistent WebSockets."""
import asyncio
import json
import sys
from pathlib import Path

import requests
import websockets

async def main(base):
    tasks=json.loads(Path('tasks.json').read_text())
    solutions=json.loads(Path('solutions.json').read_text())
    schema=requests.get(base+'/schema',timeout=15).json()
    assert schema['action']['properties']['operation']['enum']==['write','test','submit']
    assert requests.get(base+'/health',timeout=15).status_code==200
    assert requests.get(base+'/state',timeout=15).status_code==200
    assert requests.post(base+'/reset',json={'task_id':tasks[-1]['task_id']},timeout=15).json()['observation']['task_id']==tasks[-1]['task_id']
    terminal=requests.post(base+'/step',json={'action':{'operation':'submit'}},timeout=15).json()
    assert terminal['done'] and 0<=terminal['reward']<=1
    results=[]
    for task in tasks:
        async with websockets.connect(base.replace('http','ws',1)+'/ws') as socket:
            async def call(kind,data):
                await socket.send(json.dumps({'type':kind,'data':data}))
                r=json.loads(await asyncio.wait_for(socket.recv(),10))
                assert r['type']=='observation',r
                return r['data']
            initial=await call('reset',{'task_id':task['task_id'],'seed':42})
            assert initial['observation']['task_id']==task['task_id']
            floor=await call('step',{'operation':'submit'})
            assert floor['done'] and 0<=floor['reward']<1
            await call('reset',{'task_id':task['task_id'],'seed':42})
            await call('step',{'operation':'write','code':solutions[task['task_id']]})
            oracle=await call('step',{'operation':'submit'})
            assert oracle['done'] and oracle['reward']==1,oracle
            reset=await call('reset',{'task_id':task['task_id'],'seed':42})
            assert reset['observation']['source']==initial['observation']['source']
            results.append({'task_id':task['task_id'],'cases':len(task['cases']),'oracle_reward':oracle['reward'],'starter_reward':floor['reward'],'reset_verified':True})
    print(json.dumps({'health':True,'schema':True,'state':True,'http_terminal':True,'tasks':results},indent=2))

if __name__=='__main__': asyncio.run(main(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000'))
