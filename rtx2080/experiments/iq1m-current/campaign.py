"""Current-production IQ1_M validation. Raw requests/results stay under runtime/."""
from pathlib import Path
import argparse, ast, contextlib, copy, gzip, hashlib, json, os, re, signal, subprocess, sys, time, urllib.request
ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'runtime/iq1m-20261031'
PYTHON=ROOT/'runtime/venv/bin/python'
CANDIDATE=ROOT/'build/iq1m-current/strata'
BASE=json.loads((R/'production-config.json').read_text())
PORT=8087
ARM_ENV={
    'prod':{'STRATA_PF_FUSED_IQ1_M':'0'},
    'off':{'STRATA_PF_FUSED_IQ1_M':'0'},
    'on':{'STRATA_PF_FUSED_IQ1_M':'1'},
    'legacy':{'STRATA_PF_FUSED_IQ1_M':'1','STRATA_PF_FUSED_LEGACY_LAYOUT':'1'},
    'fp16':{'STRATA_PF_FUSED_IQ1_M':'0','STRATA_PF_WMMA':'1'},
    'fp16-512':{'STRATA_PF_FUSED_IQ1_M':'0','STRATA_PF_WMMA':'1','STRATA_PF_WMMA_NT':'512'},
    'fp16-emb':{'STRATA_PF_FUSED_IQ1_M':'0','STRATA_PF_WMMA':'1','STRATA_EMB_REUSE_ACCOUNT':'1'},
}

def dump(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2)+'\n')
def record(**row):
    row={'at':time.time(),**row}
    with (R/'results.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
def status(**row):dump(R/'status.json',{'at':time.time(),**row})
def stop(proc):
    if proc.poll() is not None:return
    os.killpg(proc.pid,signal.SIGTERM)
    try:proc.wait(timeout=20)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
def check_gpu():
    rows=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],text=True).strip()
    if rows:raise RuntimeError('GPU occupied: '+rows)
@contextlib.contextmanager
def server(label,arm,chunk='4096',route='1.5',extra=None):
    check_gpu()
    cfg=copy.deepcopy(BASE);cfg.pop('vision',None)
    cfg.update(exe=str(ROOT/'runtime/bin/strata' if arm=='prod' else CANDIDATE),host='127.0.0.1',port=PORT,api_key='',log=str(R/(label+'.engine.log')))
    cfg['env'].update(ARM_ENV[arm]);cfg['env']['STRATA_ROUTE_PRIOR']=route
    if chunk.startswith('auto:'):cfg['env']['STRATA_PREFILL_LEND_PCT']='100'
    cfg['env'].update(extra or {})
    cfg['args'][cfg['args'].index('--prefill')+1]=chunk
    profile=R/'private'/(label+'.expert-profile.bin');profile.parent.mkdir(exist_ok=True)
    profile.write_bytes((ROOT/'runtime/assets/data/expert-profile.bin').read_bytes())
    cfg['args'][cfg['args'].index('--expert-profile')+1]=str(profile)
    file=R/(label+'.config.json');dump(file,cfg)
    env={k:v for k,v in os.environ.items() if not k.startswith('STRATA_')}
    status(phase='boot',label=label,arm=arm,chunk=chunk,route=route)
    with (R/(label+'.server.log')).open('w') as log:
        proc=subprocess.Popen([str(PYTHON),'-u','-m','serve.server','--engine','strata','--config',str(file),'--host','127.0.0.1','--port',str(PORT)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        start=time.monotonic()
        try:
            while True:
                if proc.poll() is not None:raise RuntimeError(f'{label} boot exited {proc.returncode}')
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=2) as response:health=json.load(response)
                    if health.get('status')=='ok' and health.get('loaded',True):break
                except Exception:pass
                if time.monotonic()-start>600:raise TimeoutError(label+' boot')
                time.sleep(1)
            record(event='boot',label=label,arm=arm,seconds=time.monotonic()-start,
                   binary_sha256=hashlib.sha256(Path(cfg['exe']).read_bytes()).hexdigest(),
                   source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                   chunk=chunk,extra_env=extra or {})
            yield cfg
        finally:stop(proc)

def sample(label,body,**meta):
    status(phase='request',label=label,request_phase=meta.get('phase'),**{k:v for k,v in meta.items() if k!='phase'})
    body=copy.deepcopy(body);body.update(stream=True,stream_options={'include_usage':True})
    req=urllib.request.Request(f'http://127.0.0.1:{PORT}/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
    start=time.monotonic();first=None;chunks=[];usage={};timings={};content='';reasoning='';finish=None
    with urllib.request.urlopen(req,timeout=1800) as response:
        for line in response:
            if not line.startswith(b'data: '):continue
            raw=line[6:].strip()
            if raw==b'[DONE]':break
            item=json.loads(raw);chunks.append(item)
            if item.get('error'):raise RuntimeError(item['error'])
            for choice in item.get('choices',[]):
                delta=choice.get('delta',{})
                if first is None and any(delta.get(k) for k in ['content','reasoning_content','tool_calls']):first=time.monotonic()-start
                content+=delta.get('content') or '';reasoning+=delta.get('reasoning_content') or ''
                finish=choice.get('finish_reason') or finish
            usage=item.get('usage') or usage;timings=item.get('timings') or timings
    dump(R/(label+'.response.json'),chunks)
    row={'event':'request','label':label,**meta,'wall_s':time.monotonic()-start,'ttft_s':first,'usage':usage,'timings':timings,'finish':finish,'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'reasoning_chars':len(reasoning)}
    record(**row);return content,row

def code_from(text):
    m=re.search(r'```(?:python)?\s*\n(.*?)```',text,re.S);return m[1] if m else text

def edit(label,**meta):
    body=json.loads(gzip.decompress((R/'fixtures/edit-task.json.gz').read_bytes()))
    expected=(R/'fixtures/expected.py.txt').read_text()
    text,row=sample(label,body,**meta)
    try:ok=ast.dump(ast.parse(code_from(text)))==ast.dump(ast.parse(expected));err=None
    except SyntaxError as exc:ok=False;err=str(exc)
    record(event='edit_correctness',label=label,passed=ok,error=err,**meta)
    assert row['timings']['cache_n']==0 and row['usage']['prompt_tokens']==122451,row
    return ok

def needle(label,**meta):
    body=json.loads(gzip.decompress((R/'fixtures/needle.json.gz').read_bytes()))
    for phase in ['cold','warm']:
        text,row=sample(label+'-'+phase,body,phase=phase,**meta)
        try:
            tree=ast.parse(code_from(text));fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cached_value')
            ok=len(fn.body)==1 and isinstance(fn.body[0],ast.Return) and isinstance(fn.body[0].value,ast.Constant) and fn.body[0].value.value==73491
        except Exception:ok=False
        record(event='needle_correctness',label=label+'-'+phase,passed=ok,**meta)
        assert 115000<row['usage']['prompt_tokens']<125000
        if phase=='cold':assert row['timings']['cache_n']==0

def speed(label):
    with (R/(label+'.runner.log')).open('w') as log:
        subprocess.run([str(PYTHON),str(ROOT/'tools/strata_bench.py'),'--url',f'http://127.0.0.1:{PORT}','--runs','3','--long','--out',str(R/label),'--quiet'],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=2400)
    result=json.loads(next((R/label).rglob('results.json')).read_text())
    record(event='speed',label=label,failures=result['results']['failures'],skipped=result['results']['skipped'])
    assert not result['results']['failures'] and not result['results']['skipped']

def main():
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['edit','needle','speed']);p.add_argument('arms',nargs='*');p.add_argument('--chunk',default='4096');p.add_argument('--on-chunk');p.add_argument('--route',default='1.5');p.add_argument('--prefix',default='current');a=p.parse_args()
    arms=a.arms or ['prod','off','on','on','off','prod']
    for i,arm in enumerate(arms,1):
        label=f'{a.prefix}-{a.mode}-{i}-{arm}'
        if (R/(label+'.complete.json')).exists():continue
        chunk=a.on_chunk if arm not in ('prod','off') and a.on_chunk else a.chunk
        with server(label,arm,chunk,a.route):
            if a.mode=='edit':edit(label,arm=arm,chunk=chunk,route=a.route)
            elif a.mode=='needle':needle(label,arm=arm,chunk=chunk,route=a.route)
            else:speed(label)
        dump(R/(label+'.complete.json'),{'complete':True,'at':time.time()})
    status(phase='complete',mode=a.mode,prefix=a.prefix)
if __name__=='__main__':main()
