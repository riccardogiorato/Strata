"""Follow-up: separate fused-buffer sizing from streaming-ring sizing on current production."""
import argparse, ast, contextlib, copy, gzip, hashlib, json, sys, threading, time
from pathlib import Path
import campaign as c
c.R=c.ROOT/'runtime/compact-20261101'
c.BASE=json.loads((c.R/'production-config.json').read_text())
c.CANDIDATE=c.ROOT/'runtime/bin/strata'
c.ARM_ENV={
 'control':{'STRATA_PF_FUSED_IQ1_M':'1','STRATA_PF_FUSED_LEGACY_LAYOUT':'1','STRATA_PF_WMMA':'0'},
 'compact':{'STRATA_PF_FUSED_IQ1_M':'1','STRATA_PF_FUSED_LEGACY_LAYOUT':'0','STRATA_PF_WMMA':'0'},
 'compact384':{'STRATA_PF_FUSED_IQ1_M':'1','STRATA_PF_FUSED_LEGACY_LAYOUT':'0','STRATA_PF_WMMA':'0','STRATA_PREFILL_RING':'384'},
 'control512':{'STRATA_PF_FUSED_IQ1_M':'1','STRATA_PF_FUSED_LEGACY_LAYOUT':'1','STRATA_PF_WMMA':'0','STRATA_PREFILL_RING':'512'},
}
for _arm in ('control','compact'):
 c.ARM_ENV[_arm+'-cpu0']={**c.ARM_ENV[_arm],'STRATA_PREFILL_CPU_SHARE':'0'}

for _arm in ('control','compact'):
 c.ARM_ENV[_arm+'-min16']={**c.ARM_ENV[_arm],'STRATA_PREFILL_CPU_SHARE_MIN':'16'}
_original_server=c.server
@contextlib.contextmanager
def server(label,arm,*args,**kwargs):
 previous=c.CANDIDATE
 c.CANDIDATE=c.ROOT/('build/iq1m-current/strata' if arm.endswith('-min16') else 'runtime/bin/strata')
 try:
  with _original_server(label,arm,*args,**kwargs) as cfg:yield cfg
 finally:c.CANDIDATE=previous
c.server=server

def protected():
 for name,want in json.loads((c.R/'protected.json').read_text()).items():
  assert hashlib.sha256((c.ROOT/name).read_bytes()).hexdigest()==want,name
 if (c.R/'candidate-build.json').exists():
  build=json.loads((c.R/'candidate-build.json').read_text());assert hashlib.sha256((c.ROOT/'build/iq1m-current/strata').read_bytes()).hexdigest()==build['sha256']

def quiet():
 def cpu():
  v=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]));return sum(v),v[3]+v[4]
 n=0
 while n<3:
  a=cpu();time.sleep(5);b=cpu();busy=1-(b[1]-a[1])/max(1,b[0]-a[0]);n=n+1 if busy<.2 else 0
  c.status(phase='quiet-host',busy=busy,quiet_samples=n)

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['edit','needle','probe','speed','agents','longagent']);p.add_argument('arms',nargs='+');p.add_argument('--prefix',required=True);a=p.parse_args()
 protected()
 import harness as h
 stop=threading.Event();threading.Thread(target=h.telemetry,args=(stop,),daemon=True).start()
 try:
  if a.mode in ('agents','longagent'):
   for required in (c.R/'measure.py',h.PI,h.FX,h.P/'pi/models.json',h.P/'pi/settings.json'):
    assert required.is_file(),f'Missing harness prerequisite: {required}'
   assert len(h.TASKS)==10, 'Expected ten scored fixtures'
   import agents
   sys.argv=['agents.py',*a.arms,'--prefix',a.prefix]+(['--long'] if a.mode=='longagent' else [])
   quiet();agents.main();protected();return
  for i,arm in enumerate(a.arms,1):
   label=f'{a.prefix}-{i}-{arm}'
   if (c.R/(label+'.complete.json')).exists():continue
   quiet();protected()
   extra={'STRATA_DUMP_FIRST_LOGITS':str(c.R/(label+'.logits'))} if a.mode in ('edit','probe') else {}
   if a.mode=='probe':
    extra.update(STRATA_PREFILL_DUMP_R=str(c.R/(label+'.residuals')),STRATA_DBG_FEAT=str(c.R/(label+'.routes')),STRATA_DBG_FEAT_LAYERS='')
   with c.server(label,arm,extra=extra):
    if a.mode=='edit':ok=c.edit(label,arm=arm,chunk='4096',route='1.5')
    elif a.mode=='needle':c.needle(label,arm=arm,chunk='4096',route='1.5');ok=True
    elif a.mode=='speed':c.speed(label);ok=True
    else:
     body=json.loads(gzip.decompress((c.R/'fixtures/edit-task.json.gz').read_bytes()))
     # A fixed shorter prefix for numerical diagnostics; retain the actual edit instruction.
     body['messages'][1]['content']=body['messages'][1]['content'][-32000:]
     body['max_tokens']=1
     _,row=c.sample(label,body,arm=arm,phase='diagnostic',chunk='4096',route='1.5');ok=True
   protected();c.dump(c.R/(label+'.complete.json'),{'complete':True,'passed':ok,'at':time.time()})
 finally:stop.set()
 c.status(phase='complete',mode=a.mode,prefix=a.prefix)
if __name__=='__main__':main()
