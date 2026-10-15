#!/usr/bin/env python3
"""Run unmodified Hermes ACP against an isolated local synthetic Chat Completions server.
Run: /Users/hong-kyungtack/.hermes/hermes-agent/.venv/bin/python probe.py
The source checkout is imported only for its existing fake HTTP server and entrypoint.
"""
import json
import os
import queue
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path('/Users/hong-kyungtack/.hermes/hermes-agent')
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_hermes_home

class ACP:
    def __init__(self, env, log, tag):
        self.log = log
        self.p = subprocess.Popen([str(ROOT/'.venv/bin/python'), str(ROOT/'hermes_cli/main.py'), 'acp'],
                                  cwd=OUT/'project', env=env, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=open(OUT/f'{tag}.stderr', 'w'),
                                  text=True, bufsize=1)
        self.q = queue.Queue()
        self.seq = 0
        threading.Thread(target=self.read, daemon=True).start()
    def read(self):
        for line in self.p.stdout:
            try:
                x = json.loads(line)
            except ValueError:
                x = {'invalid_stdout': line.strip()}
            self.log.append({'side': 'recv', 'pid': self.p.pid, 'message': x})
            self.q.put(x)
        self.q.put(None)
    def send(self, x):
        self.log.append({'side': 'send', 'pid': self.p.pid, 'message': x})
        self.p.stdin.write(json.dumps(x)+'\n')
        self.p.stdin.flush()
    def req(self, method, params, timeout=120):
        self.seq += 1
        rid = self.seq
        self.send({'jsonrpc': '2.0', 'id': rid, 'method': method, 'params': params})
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            try: x = self.q.get(timeout=max(.01,end-time.monotonic()))
            except queue.Empty: break
            if x is None: raise RuntimeError(f'ACP exited during {method}: {self.p.poll()}')
            if x.get('id') == rid: return x
            if 'id' in x and 'method' in x:
                self.send({'jsonrpc':'2.0','id':x['id'],'error':{'code':-32601,'message':'not implemented'}})
        raise TimeoutError(f'ACP {method} timed out')
    def close(self):
        self.p.stdin.close()
        try: self.p.wait(timeout=25)
        except subprocess.TimeoutExpired:
            self.p.kill(); self.p.wait()
        return self.p.returncode

def ok(x):
    if 'error' in x: raise AssertionError(x)
    return x['result']

def prompt(acp, sid, text):
    return ok(acp.req('session/prompt', {'sessionId':sid,'prompt':[{'type':'text','text':text}]}))

def run():
    (OUT/'project').mkdir(exist_ok=True)
    home = OUT/'isolated-home'
    if home.exists():
        # Fresh probe identity on every run; don't mix old captures.
        raise RuntimeError(f'{home} already exists: move it aside before rerunning')
    home.mkdir()
    hhome = home/'.hermes'
    rpc=[]
    results={}
    with FakeLLMServer(default_text='STOCK-ACP-ANSWER', api_key='sk-fake-e2e') as srv:
        hhome.mkdir()
        (hhome/'config.yaml').write_text(
            'model:\n  provider: synthetic\n  default: fake-model\n  context_length: 128000\n'
            'providers:\n  synthetic:\n'
            f'    api: {srv.base_url}\n'
            '    api_key: sk-fake-e2e\n'
            '    transport: chat_completions\n'
            '    default_model: fake-model\n'
            '    session_affinity_header: X-Hermes-Session-ID\n'
            'agent:\n  api_max_retries: 1\n  disabled_toolsets: [memory, web, browser, terminal, file, delegation]\n'
            'memory:\n  memory_enabled: false\n  user_profile_enabled: false\n'
            'compression:\n  enabled: false\n'
            'updates:\n  check: false\n'
            'telemetry:\n  shared_metrics:\n    enabled: false\n    send: false\n    offer_version: 2\n'
        )
        (hhome/'.env').write_text('')
        # No inherited provider credentials/profile; all network requests should be loopback.
        passthrough={'PATH','LANG','LC_ALL','TZ','TERM','TMPDIR','USER','LOGNAME','SHELL'}
        env={k:v for k,v in os.environ.items() if k in passthrough}
        env.update(HOME=str(home),HERMES_HOME=str(hhome),PYTHONPATH=str(ROOT),
                   PYTHONUNBUFFERED='1', NO_COLOR='1', OPENAI_API_KEY='sk-fake-e2e',
                   HERMES_STATE_DB_GUARD_BYPASS='1')
        cwd=str(OUT/'project')
        params={'cwd':cwd,'mcpServers':[]}
        def init(acp):
            results[f'initialize_pid_{acp.p.pid}']=ok(acp.req('initialize',{'protocolVersion':1,
                'clientCapabilities':{'fs':{'readTextFile':False,'writeTextFile':False},'terminal':False},
                'clientInfo':{'name':'stock-affinity-probe','version':'1.0'}}))
        a=ACP(env,rpc,'first')
        try:
            init(a)
            sid=ok(a.req('session/new',params))['sessionId']; results['first_session']=sid
            results['first_prompt']=prompt(a,sid,'Say test one.')
        finally: results['first_exit']=a.close()
        b=ACP(env,rpc,'second')
        try:
            init(b)
            results['load']=ok(b.req('session/load',dict(params,sessionId=sid)))
            results['second_prompt']=prompt(b,sid,'Say test two.')
            second=ok(b.req('session/new',params))['sessionId']; results['second_session']=second
            results['independent_prompt']=prompt(b,second,'Say test three.')
            # A missing load must not implicitly mint a replacement under the requested id.
            results['missing_load']=b.req('session/load',dict(params,sessionId='00000000-0000-4000-8000-000000000000'))
            results['sessions_after_missing_load']=ok(b.req('session/list', {'cwd':cwd}))
            results['reset_command']=prompt(b,sid,'/reset')
            results['after_reset_prompt']=prompt(b,sid,'Say test four.')
            fork=ok(b.req('session/fork',dict(params,sessionId=second)))['sessionId']; results['fork_session']=fork
            results['fork_prompt']=prompt(b,fork,'Say test five.')
        finally: results['second_exit']=b.close()
        requests=[]
        for i,r in enumerate(srv.requests):
            if r['kind']=='get': continue
            body=r['body']
            requests.append({'index':i,'path':r['path'],'kind':r['kind'],
                'affinity':r['headers'].get('x-hermes-session-id'),
                'x_session_id':r['headers'].get('x-session-id'),
                'bb_thread_id':r['headers'].get('bb_thread_id'),
                'model':body.get('model'),'stream':body.get('stream'),
                'last_user':next((m.get('content') for m in reversed(body.get('messages',[])) if m.get('role')=='user'),None),
                'roles':[m.get('role') for m in body.get('messages',[])],
                'http_status':'response sent (fake server)', 'headers':r['headers']})
        (OUT/'acp.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rpc))
        (OUT/'http.json').write_text(json.dumps(requests,indent=2,ensure_ascii=False))
        (OUT/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
        main=[r for r in requests if r['kind']=='main']
        short=[{k:r[k] for k in ('kind','affinity','last_user','roles')} for r in requests]
        print(json.dumps({'session':sid,'other':second,'fork':fork,'http':short,'main_count':len(main),'missing_load':results['missing_load']},indent=2))
        assert results['first_exit']==results['second_exit']==0
        assert results['first_prompt']['stopReason']==results['second_prompt']['stopReason']=='end_turn'
        assert sid != second != fork and sid != fork
        expected={'Say test one.':sid,'Say test two.':sid,'Say test three.':second,
                  'Say test four.':sid,'Say test five.':fork}
        for text, key in expected.items():
            hits=[r for r in main if r['last_user']==text]
            assert len(hits)==1 and hits[0]['affinity']==key, (text,key,hits)
        assert results['missing_load'].get('result') == {} and not any(
            s['sessionId']=='00000000-0000-4000-8000-000000000000'
            for s in results['sessions_after_missing_load']['sessions'])
        assert not any(r['bb_thread_id'] for r in requests)
        (OUT/'PASS').write_text('Verified full ACP JSON-RPC and model HTTP affinity per results.json and http.json\n')
if __name__=='__main__':
    try: run()
    except BaseException:
        traceback.print_exc()
        sys.exit(1)
