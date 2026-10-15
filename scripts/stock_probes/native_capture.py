#!/usr/bin/env python3
"""Exercise installed stock CLIs against a loopback-only synthetic streaming server.
Only whitelisted identity fields and outcome summaries are persisted. No real keys.
"""
import http.server
import json
import os
import pathlib
import re
import subprocess
import threading
import time
import uuid
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parent
ROOT.mkdir(parents=True, exist_ok=True)
CODEX = '/Users/hong-kyungtack/.local/bin/codex'
CLAUDE = '/Users/hong-kyungtack/.local/bin/claude'
REQUESTS = []
LOCK = threading.Lock()
HEADERS = ('session_id', 'session-id', 'x-claude-code-session-id', 'x-session-id', 'x-codex-session-id', 'x-cliproxy-conversation-id')

def field(x):
    return x if isinstance(x, (str, int, float, bool)) or x is None else None

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, format, *_): pass
    def do_GET(self):
        self.send_response(404); self.send_header('Content-Length', '0'); self.end_headers()
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get('content-length', '0')))
        try: body = json.loads(raw)
        except (ValueError, UnicodeError): body = {}
        h = {k.lower(): v for k, v in self.headers.items() if k.lower() in HEADERS}
        metadata = body.get('metadata') if isinstance(body, dict) else None
        metadata = metadata if isinstance(metadata, dict) else {}
        try: nested_user = json.loads(metadata.get('user_id','{}'))
        except (ValueError, TypeError): nested_user = {}
        nested_user = nested_user if isinstance(nested_user,dict) else {}
        entry = {'path': self.path, 'headers': h, 'body': {
            'session_id': field(body.get('session_id')), 'session-id': field(body.get('session-id')),
            'user': field(body.get('user')), 'previous_response_id': field(body.get('previous_response_id')),
            'metadata.user_id.session_id': field(nested_user.get('session_id')), 'metadata.user_id.keys':sorted(nested_user),
            'metadata.session_id': field(metadata.get('session_id')),
            'metadata.keys': sorted(metadata), 'model': field(body.get('model')),
            'stream': field(body.get('stream')),
            'input_count': len(body.get('input', [])) if isinstance(body.get('input'), list) else None,
            'messages_count': len(body.get('messages', [])) if isinstance(body.get('messages'), list) else None}}
        with LOCK: REQUESTS.append(entry)
        if urlsplit(self.path).path.endswith('/messages/count_tokens'):
            payload = json.dumps({'input_tokens': 10}).encode()
            self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload); return
        if urlsplit(self.path).path.endswith('/messages'):
            mid = 'msg_' + uuid.uuid4().hex
            if not body.get('stream'):
                payload=json.dumps({'id':mid,'type':'message','role':'assistant','model':body.get('model','claude-sonnet-4-5'),'content':[{'type':'text','text':'Synthetic done.'}],'stop_reason':'end_turn','stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':5}}).encode()
                self.send_response(200); self.send_header('Content-Type','application/json'); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload); return
            events = [('message_start', {'type':'message_start','message':{'id':mid,'type':'message','role':'assistant','model':body.get('model','claude-sonnet-4-5'),'content':[],'stop_reason':None,'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0}}}),('content_block_start',{'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}),('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':'Synthetic done.'}}),('content_block_stop',{'type':'content_block_stop','index':0}),('message_delta',{'type':'message_delta','delta':{'stop_reason':'end_turn','stop_sequence':None},'usage':{'output_tokens':5}}),('message_stop',{'type':'message_stop'})]
            data = ''.join('event: '+event+'\ndata: '+json.dumps(item)+'\n\n' for event,item in events).encode()
        else:
            rid = 'resp_' + uuid.uuid4().hex
            msg = {'id':'msg_'+uuid.uuid4().hex,'type':'message','status':'completed','role':'assistant','content':[{'type':'output_text','text':'Synthetic done.','annotations':[]}]}
            resp = {'id':rid,'object':'response','created_at':int(time.time()),'status':'completed','model':body.get('model','test-model'),'output':[msg],'parallel_tool_calls':False,'usage':{'input_tokens':10,'output_tokens':5,'total_tokens':15},'error':None,'incomplete_details':None}
            events = [('response.created', {'type':'response.created','response':{**resp,'status':'in_progress','output':[]}}),('response.output_item.added',{'type':'response.output_item.added','output_index':0,'item':{**msg,'status':'in_progress','content':[]}}),('response.content_part.added',{'type':'response.content_part.added','item_id':msg['id'],'output_index':0,'content_index':0,'part':{'type':'output_text','text':'','annotations':[]}}),('response.output_text.delta',{'type':'response.output_text.delta','item_id':msg['id'],'output_index':0,'content_index':0,'delta':'Synthetic done.'}),('response.output_text.done',{'type':'response.output_text.done','item_id':msg['id'],'output_index':0,'content_index':0,'text':'Synthetic done.'}),('response.content_part.done',{'type':'response.content_part.done','item_id':msg['id'],'output_index':0,'content_index':0,'part':msg['content'][0]}),('response.output_item.done',{'type':'response.output_item.done','output_index':0,'item':msg}),('response.completed',{'type':'response.completed','response':resp})]
            data = ''.join('event: '+event+'\ndata: '+json.dumps(item)+'\n\n' for event,item in events).encode()
        self.send_response(200); self.send_header('Content-Type','text/event-stream'); self.send_header('Cache-Control','no-cache'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)


def run(label, argv, env, cwd):
    start = len(REQUESTS)
    try:
        p = subprocess.run(argv, env=env, cwd=cwd, capture_output=True, text=True, timeout=65, stdin=subprocess.DEVNULL)
        # Only report sanitized diagnostics: do not persist potentially sensitive CLI output.
        ids = re.findall(r'(?i)(?:thread_id|session_id|session id)["\s:=]+["\s]*([0-9a-f-]{36})', p.stdout + '\n' + p.stderr)
        diagnostics = []
        if p.returncode:
            for text in (p.stdout, p.stderr):
                try:
                    data = json.loads(text)
                    diagnostics.extend(str(x)[:300] for x in data.get('errors',[]) if isinstance(x,str))
                    diagnostics.append(str(data.get('subtype',''))[:100])
                except (ValueError,AttributeError):
                    # Synthetic test only; avoid saving complete prompts or system data.
                    diagnostics.extend(re.findall(r'(?:API Error|Error|error): [^\n]{1,180}',text)[:2])
        return {'label':label,'exit':p.returncode,'request_indices':list(range(start,len(REQUESTS))), 'cli_ids':list(dict.fromkeys(ids)), 'synthetic_answer_seen':'Synthetic done.' in (p.stdout+p.stderr), 'error_kind': ('no_requests' if start == len(REQUESTS) else 'nonzero_exit' if p.returncode else None), 'diagnostics': diagnostics[:3]}
    except subprocess.TimeoutExpired:
        return {'label':label,'timeout_seconds':65,'request_indices':list(range(start,len(REQUESTS)))}


def main():
    server = http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    home = ROOT/'home'; ch = ROOT/'codex-home'; cc = ROOT/'claude-config'; work = ROOT/'work'
    for p in (home,ch,cc,work): p.mkdir(exist_ok=True)
    # Start with only standard process necessities. Never inherit actual provider credentials or proxy custom headers.
    base = {k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TERM','TMPDIR') if k in os.environ}
    base.update(HOME=str(home), TMPDIR=str(ROOT), CI='1', NO_COLOR='1', DISABLE_TELEMETRY='1', DO_NOT_TRACK='1')
    ce = {**base,'CODEX_HOME':str(ch),'OPENAI_API_KEY':'synthetic-not-a-real-token','TEST_SYNTHETIC_KEY':'synthetic-not-a-real-token'}
    cx = ['-c','model_provider="synthetic"','-c',f'model_providers.synthetic.base_url="{url}/v1"','-c','model_providers.synthetic.name="Synthetic"','-c','model_providers.synthetic.wire_api="responses"','-c','model_providers.synthetic.env_key="TEST_SYNTHETIC_KEY"']
    ae = {**base,'CLAUDE_CONFIG_DIR':str(cc),'ANTHROPIC_BASE_URL':url,'ANTHROPIC_API_KEY':'synthetic-not-a-real-token','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}
    results = []
    try:
        results.append(run('codex_first',[CODEX,'exec','--json','--skip-git-repo-check','-s','read-only','-C',str(work),'-m','test-model',*cx,'Reply briefly without tools.'],ce,work))
        cid = next(iter(results[-1].get('cli_ids',[])),None)
        if cid:
            results.append(run('codex_resume',[CODEX,'exec','resume','--json','--skip-git-repo-check','-m','test-model',*cx,cid,'Reply briefly again without tools.'],ce,work))
        else: results.append({'label':'codex_resume','not_attempted':'No saved CLI session ID extracted from first process'})
        results.append(run('codex_new',[CODEX,'exec','--json','--skip-git-repo-check','-s','read-only','-C',str(work),'-m','test-model',*cx,'Start a distinct conversation without tools.'],ce,work))
        opts = [CLAUDE,'--bare','-p','--output-format','json','--model','claude-sonnet-4-5','--tools=']
        results.append(run('claude_first',[*opts,'Reply briefly without tools.'],ae,work))
        aid = next(iter(results[-1].get('cli_ids',[])),None)
        if aid: results.append(run('claude_resume',[*opts,'--resume',aid,'Reply briefly again without tools.'],ae,work))
        else: results.append({'label':'claude_resume','not_attempted':'No saved CLI session ID extracted from first process'})
        results.append(run('claude_new',[*opts,'Start a distinct conversation without tools.'],ae,work))
    finally: server.shutdown()
    evidence = {'synthetic_backend':True,'loopback_only':True,'versions':{'codex':'0.162.1','claude':'2.1.296'},'requests':REQUESTS,'runs':results}
    (ROOT/'evidence.json').write_text(json.dumps(evidence,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'evidence':str(ROOT/'evidence.json'),'runs':results,'requests':len(REQUESTS)},indent=2))

if __name__ == '__main__': main()
