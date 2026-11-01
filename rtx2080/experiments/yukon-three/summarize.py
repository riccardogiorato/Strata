"""Publish only compact counters; prompts, model output and local config stay private."""
from pathlib import Path
import hashlib,json,statistics,sys
ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'runtime/yukon-three-20261101'
sys.path.insert(0,str(ROOT/'rtx2080/experiments/iq1m-current'))
import metrics as m

def read(p):return json.loads(p.read_text())
def rate(rows,tokens,ms):
    n=sum(r.get(tokens,0) or 0 for r in rows);t=sum(r.get(ms,0) or 0 for r in rows)
    return {'tokens':n,'milliseconds':t,'tok_s':1000*n/t if t else None,'requests':len(rows)}

def collect():
    events=[json.loads(s) for s in (R/'results.jsonl').read_text().splitlines()]
    out={'hardware':'RTX 2080 SM75, 8 GiB, 165 W; i5-9600K; 64 GiB RAM',
         'capacity_tokens':131072,'resident_kv_tokens':32768,
         'runs':{},'checks':[x for x in events if x.get('event') in ('edit_correctness','needle_correctness','smoke_correctness')],
         'kernel_logs':{}}
    for name in ['gdn-final.log','gdn-split-control.log','head-layout-control.log','projections-idle.log']:
        p=R/name
        if p.exists():out['kernel_logs'][name]=p.read_text().splitlines()
    for ev in events:
        if ev.get('event')!='boot':continue
        label=ev['label'];log=R/(label+'.engine.log')
        row={k:ev[k] for k in ['arm','binary_sha256','source_commit','chunk','extra_env']}
        row['complete']=(R/(label+'.complete.json')).exists()
        row['engine_log_sha256']=hashlib.sha256(log.read_bytes()).hexdigest() if log.exists() else None
        if log.exists():
            native,kv=m.engine_rows(log);row['native']=m.aggregate(native);row['final_kv_segment']=kv
            row['projection_path_observed']='Yukon: adjacent alpha/beta prefill GEMM active' in log.read_text()
        source=R/(label+'.source.json')
        if source.exists():row['source']=read(source)
        speed=list((R/label).glob('*/results.json'))
        if speed:
            s=read(speed[0])['results'];row['speed']={'failures':s['failures'],'skipped':s['skipped'],
                'chat_decode':rate(s['chat']['requests'],'generated_tokens','decode_ms'),
                'chat_median_decode':s['chat']['decode_tps'],
                'prompt':{k:rate(v['requests'],'read_tokens','prompt_ms') for k,v in s['prompts'].items()},
                'prompt_median':{k:v['prompt_tps'] for k,v in s['prompts'].items()},
                'agent_prefix_hit':s['agent'].get('hit_pct')}
        tasks=list((R/'runs'/label).glob('*/result.json'))
        if tasks:
            ns=[];tr=[]
            for p in sorted(tasks):
                t=read(p);ns+=t['native'];tr.append({k:t[k] for k in ['task','passed','verify_passed','violations','errors','tool_calls','tool_errors','exit','wall_s']})
                tr[-1]['reconciliation']=m.reconcile(t['native'],t['http'])
            row['agents']={'passed':sum(t['passed'] for t in tr),'tasks':tr,'native':m.aggregate(ns)}
            row['long_checks']={p.stem:read(p) for p in (R/'runs'/label).glob('long-*-check.json')}
        row['requests']=[{k:v for k,v in x.items() if k not in ('at','content_sha256')} for x in events if x.get('event')=='request' and (x['label']==label or x['label'].startswith(label+'-'))]
        out['runs'][label]=row
    return out

if __name__=='__main__':
    out=collect();dest=R/'summary.json';dest.write_text(json.dumps(out,indent=2)+'\n')
    for label,row in out['runs'].items():
        if 'speed' in row:
            s=row['speed'];print(label,'chat',round(s['chat_decode']['tok_s'],2),'32K',round(s['prompt']['32K']['tok_s'],2))
        if 'agents' in row:print(label,'agents',row['agents']['passed'],len(row['agents']['tasks']),'decode',row['agents']['native']['decode_tps'])
    print(dest)
