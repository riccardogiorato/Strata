"""Pinned harness A/B on identical production Strata. See README for interpretation."""
from pathlib import Path
import contextlib, copy, hashlib, http.client, http.server, importlib.util, json, os, re, resource, shutil, signal, subprocess, sys, threading, time, traceback
import campaign as c
ROOT=c.ROOT; R=c.R; P=R/'private'; REPO=ROOT.parent/'local-ai-rtx2080'
SOURCE=ROOT
PI=Path('/home/riccardogiorato/.local/share/mise/installs/pi/1.4.0/pi/pi')
FX=REPO/'experiments/pi-fx-strata-20261030/private/bin/fx'
MASTER=P/'tasks'; WORK=P/'work'
import metrics as m
TASKS=sorted(p.name for p in MASTER.iterdir()) if MASTER.exists() else []
CAP=600
def dump(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2)+'\n')
def manifest(base):
 if not base.exists():return {}
 return {str(p.relative_to(base)):('link:'+os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest()) for p in base.rglob('*') if (p.is_symlink() or p.is_file()) and not any(t in p.parts for t in ['node_modules','__pycache__','.git'])}
class Proxy(http.server.BaseHTTPRequestHandler):
 protocol_version='HTTP/1.0'
 context=None
 def log_message(self,*a):pass
 def do_GET(self):
  self.send_error(404)
 def do_POST(self):
  ctx=dict(Proxy.context);start=time.monotonic();body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  ix=ctx['counter'][0];ctx['counter'][0]+=1
  prefix=ctx['dir']/f'request-{ix:03}'
  dump(str(prefix)+'.client.json',body)
  body.update(model='local-model',temperature=0,seed=42,max_tokens=ctx.get('max_output',32768),chat_template_kwargs={'enable_thinking':True})
  for k in ['max_completion_tokens','reasoning_effort','reasoning','top_p','top_k','frequency_penalty','presence_penalty']:body.pop(k,None)
  if body.get('stream'):body['stream_options']={'include_usage':True}
  dump(str(prefix)+'.sent.json',body)
  conn=http.client.HTTPConnection('127.0.0.1',8087,timeout=CAP+60)
  row={'index':ix,'start':time.time(),'stream':body.get('stream'),'messages':len(body.get('messages',[])),'tools':len(body.get('tools',[])),'first_delta_s':None,'first_content_s':None,'reasoning_chars':0}
  try:
   conn.request('POST',self.path,json.dumps(body).encode(),{'Content-Type':'application/json'})
   resp=conn.getresponse();row['status']=resp.status
   self.send_response(resp.status);self.send_header('Content-Type',resp.getheader('Content-Type','application/json'));self.send_header('Connection','close');self.end_headers()
   with Path(str(prefix)+'.response').open('wb') as log:
    for line in resp:
     log.write(line);self.wfile.write(line);self.wfile.flush()
     if line.startswith(b'data: {'):
      x=json.loads(line[6:]);
      if x.get('usage'):row['usage']=x['usage']
      if x.get('timings'):row['timings']=x['timings']
      for choice in x.get('choices',[]):
       delta=choice.get('delta',{})
       row['reasoning_chars']+=len(delta.get('reasoning_content') or delta.get('reasoning') or '')
       if any(delta.get(k) for k in ['content','reasoning_content','reasoning','tool_calls']) and row['first_delta_s'] is None:row['first_delta_s']=time.monotonic()-start
       if delta.get('content') and row['first_content_s'] is None:row['first_content_s']=time.monotonic()-start
       if choice.get('finish_reason'):row['finish_reason']=choice['finish_reason']
  except Exception as e:row['error']=repr(e)
  finally:
   row['wall_s']=time.monotonic()-start;dump(str(prefix)+'.metrics.json',row);conn.close()

def sandbox(work,arm,profile):
 # HOME is unchanged; its path lives in the private /home mount with no real user files.
 args=['bwrap','--die-with-parent','--unshare-pid','--new-session','--ro-bind','/','/','--tmpfs','/home','--tmpfs','/tmp','--proc','/proc','--dev','/dev','--dir',str(Path.home()),'--bind',str(work),'/tmp/work','--chdir','/tmp/work','--ro-bind',str(PI.parent),'/tmp/pi-bin','--ro-bind',str(FX),'/tmp/fx','--setenv','PATH','/usr/local/bin:/usr/bin:/bin','--setenv','PI_OFFLINE','1','--setenv','FX_AUTO_UPGRADE','0','--setenv','FX_HERDR','0','--setenv','FX_PROVIDER','strata','--setenv','FX_SOUND','off']
 if arm=='pi':args+=['--bind',str(profile),'/tmp/pi-agent','--setenv','PI_CODING_AGENT_DIR','/tmp/pi-agent']
 else:args+=['--bind',str(profile),str(Path.home()/'.fx')]
 return args

def native_slice(log,offset,out):
 out.write_bytes(log.read_bytes()[offset:]);rows,_=m.engine_rows(out)
 for i,row in enumerate(rows):row['initial_request']=i==0
 return rows

def telemetry(stop):
 with (R/'telemetry.jsonl').open('a') as f:
  while not stop.is_set():
   row={'at':time.time(),'loadavg':Path('/proc/loadavg').read_text().strip(),'cpu':Path('/proc/stat').read_text().splitlines()[0],'meminfo':Path('/proc/meminfo').read_text()}
   row['processes']=subprocess.check_output(['ps','-eo','pid,etimes,pcpu,rss,comm','--sort=-pcpu'],text=True).splitlines()[:16]
   row['gpu']=subprocess.check_output(['nvidia-smi','--query-gpu=utilization.gpu,power.draw,temperature.gpu,clocks.sm,memory.used','--format=csv,noheader'],text=True).strip()
   f.write(json.dumps(row)+'\n');f.flush();stop.wait(5)

def run_task(label,arm,task,engine_log,prompt=None,resume=False,phase=None,max_output=32768):
 dest=R/'runs'/label/(task+('-'+phase if phase else ''));dest.mkdir(parents=True,exist_ok=True)
 work=WORK/label/task;profile=P/'profiles'/label/task
 if not resume:
  assert not work.exists(),f'Preserve {work}'
  if (MASTER/task).exists():shutil.copytree(MASTER/task,work,symlinks=True)
  else:work.mkdir(parents=True)
  shutil.copytree(P/arm,profile)
  if max_output!=32768:
   cp=profile/('models.json' if arm=='pi' else 'settings.json');cfg=json.loads(cp.read_text())
   if arm=='pi':cfg['providers']['strata']['models'][0]['maxTokens']=max_output
   else:cfg['providers']['strata']['model_metadata']['local-model']['max_output_tokens']=max_output
   dump(cp,cfg)
 prompt=prompt or (work/'TASK.md').read_text()
 prompt+='\nWork only in /tmp/work. Do not delegate or use subagents. Complete the task and run its verification command. Do not change the task instructions or verification fixtures.'
 cmd=sandbox(work,arm,profile)
 if arm=='pi':
  cmd+=['/tmp/pi-bin/pi','--no-extensions','--no-mcp','--no-skills','--no-prompt-templates','--thinking','off','--provider','strata','--model','local-model','--mode','json','--session-dir','/tmp/pi-agent/sessions','-p']
  if resume:cmd+=['--continue']
 else:
  cmd+=['/tmp/fx','ask','--json','--full-access','--model','local-model']
  if resume:cmd+=['--resume','last']
 # stdin avoids Linux's per-argument limit for long prompts.
 cmd=[sys.executable,str(R/'measure.py'),str(dest/'resources.json'),*cmd]
 start=time.monotonic();offset=engine_log.stat().st_size
 Proxy.context={'dir':dest,'counter':[0],'max_output':max_output}
 with (dest/'stdout.log').open('w') as out,(dest/'stderr.log').open('w') as err:
  with subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=out,stderr=err,start_new_session=True,env={'HOME':str(Path.home()),'USER':os.environ.get('USER',''),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TERM':'dumb'}) as proc:
   try:proc.communicate(prompt.encode(),timeout=CAP);rc=proc.returncode
   except subprocess.TimeoutExpired:
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    rc=124
 wall=time.monotonic()-start
 rows=native_slice(engine_log,offset,dest/'engine.log')
 calls=[];errors=[]
 if arm=='pi':
  for line in (dest/'stdout.log').read_text().splitlines():
   try:ev=json.loads(line)
   except ValueError:continue
   if ev.get('type')=='tool_execution_end':calls.append({'name':ev.get('toolName'),'error':ev.get('isError',False)})
   if ev.get('type')=='message_end' and ev.get('message',{}).get('stopReason')=='error':errors.append(ev['message'].get('errorMessage'))
 else:
  try:
   result=json.loads((dest/'stdout.log').read_text());calls=result.get('tool_calls',[])
   if result.get('error'):errors.append(result['error'])
  except ValueError:errors.append('No valid fx result')
 violations=[]
 protected=['TASK.md','verify.sh','tests','test','docs','wheels','protected']+{'task2-react-fix':['render-check.mjs','package.json'],'task4-python-bugfix':['test_metrics.py'],'task5-js-to-ts':['tsconfig.json'],'task9-tb-analyze-access-logs':['access_log'],'task10-tb-bank-trans-filter':['data/bank_transactions.csv']}.get(task,[])
 if (MASTER/task).exists():
  for rel in protected:
   a=MASTER/task/rel;b=work/rel
   if a.is_dir() and manifest(a)!=manifest(b):violations.append(rel)
   elif a.is_file() and (not b.exists() or a.read_bytes()!=b.read_bytes()):violations.append(rel)
 verified=None
 if (work/'verify.sh').exists():
  with (dest/'verify.log').open('w') as f:
   try:verified=subprocess.run(sandbox(work,arm,profile)+['bash','verify.sh'],stdout=f,stderr=subprocess.STDOUT,timeout=180,env={'HOME':str(Path.home()),'USER':os.environ.get('USER',''),'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}).returncode==0
   except subprocess.TimeoutExpired:verified=False
 requests=[json.loads(p.read_text()) for p in sorted(dest.glob('request-*.metrics.json'))]
 usage_match=len(rows)==len(requests) and all((n['prompt_tokens'],n['output_tokens'],n['cached_tokens'])==(h.get('usage',{}).get('prompt_tokens'),h.get('usage',{}).get('completion_tokens'),h.get('usage',{}).get('prompt_tokens_details',{}).get('cached_tokens',0)) for n,h in zip(rows,requests))
 row={'label':label,'arm':arm,'task':task,'wall_s':wall,'exit':rc,'passed':bool(verified and not violations and not errors and calls and rc==0),'verify_passed':verified,'violations':violations,'errors':errors,'tool_calls':len(calls),'tool_errors':sum(bool(x.get('error',False)) or x.get('status') not in (None,'success') for x in calls),'metrics':m.aggregate(rows),'native':rows,'http':requests,'native_usage_match':usage_match}
 dump(dest/'result.json',row)
 print(json.dumps({k:row[k] for k in ['label','task','wall_s','exit','passed','tool_calls','errors']}),flush=True)
 return row
