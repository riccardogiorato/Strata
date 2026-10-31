"""Summarize measured throughput, correctness and cache counters without raw prompts."""
from collections import defaultdict
import json, statistics
import campaign as c
import metrics
rows=[json.loads(s) for s in (c.R/'results.jsonl').read_text().splitlines()] if (c.R/'results.jsonl').exists() else []
groups=defaultdict(list);checks={r['label']:r for r in rows if r['event'].endswith('_correctness')}
for r in rows:
    if r['event']=='request':groups[(r['label'].split('-')[0],r.get('arm'),r.get('chunk'),r.get('route'),r.get('phase','edit'))].append(r)
summary={'long':[], 'agent':[], 'speed':[], 'host_load':[], 'kernel':[r for r in rows if r['event']=='kernel_check']}
telemetry=[]
for line in (c.R/'telemetry.jsonl').read_text().splitlines():
    try:
        r=json.loads(line);ticks=list(map(int,r['cpu'].split()[1:9]));telemetry.append((r['at'],sum(ticks),ticks[3]+ticks[4]))
    except (ValueError,KeyError):pass
telemetry.sort()
for r in rows:
    if r['event']!='request' or not r['label'].startswith('final-') or r.get('phase')!='cold':continue
    samples=[x for x in telemetry if r['at']-r['wall_s']<=x[0]<=r['at']]
    busy=[100*(1-(b[2]-a[2])/(b[1]-a[1])) for a,b in zip(samples,samples[1:]) if b[1]>a[1]]
    summary['host_load'].append({'label':r['label'],'samples':len(busy),'mean_cpu_busy_pct':statistics.mean(busy) if busy else None,'peak_cpu_busy_pct':max(busy,default=None)})
for key,rr in groups.items():
    t=[r['timings'] for r in rr];tokens=sum(x.get('prompt_n',0) for x in t);ms=sum(x.get('prompt_ms',0) for x in t)
    # HTTP prompt_n is unread tokens; independently retain usage to audit it.
    summary['long'].append({'group':key,'runs':len(rr),'weighted_prefill_tps':1000*tokens/ms if ms else None,'individual_prefill_tps':[x.get('prompt_per_second') for x in t], 'prompt_tokens':[r['usage']['prompt_tokens'] for r in rr],'cached_tokens':[x.get('cache_n') for x in t], 'output_tokens':[r['usage']['completion_tokens'] for r in rr], 'weighted_decode_tps':1000*sum(x.get('predicted_n',0) for x in t)/sum(x.get('predicted_ms',1) for x in t), 'ttft_s':[r['ttft_s'] for r in rr], 'correct':[checks.get(r['label'],{}).get('passed') for r in rr]})
for suite in sorted((c.R/'runs').glob('*')) if (c.R/'runs').exists() else []:
    rr=[json.loads(p.read_text()) for p in sorted(suite.glob('*/result.json'))]
    native=[n for r in rr for n in r['native']]
    summary['agent'].append({'label':suite.name,'tasks':len(rr),'passed':sum(r['passed'] for r in rr),'wall_s':sum(r['wall_s'] for r in rr),'metrics':metrics.aggregate(native),'thinking_requests':sum(h.get('reasoning_chars',0)>0 for r in rr for h in r['http']), 'usage_matches':all(r['native_usage_match'] for r in rr),'per_task':[{'task':r['task'],'passed':r['passed'],'wall_s':r['wall_s'],'metrics':r['metrics']} for r in rr], 'long_checks':{p.name:json.loads(p.read_text()) for p in suite.glob('long-*-check.json')}})
for p in c.R.glob('*speed*/**/results.json'):
    d=json.loads(p.read_text());summary['speed'].append({'path':str(p.relative_to(c.R)),'results':d.get('results')})
c.dump(c.R/'summary.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k not in ['speed','agent']},indent=2))
for a in summary['agent']:print(a['label'],a['passed'],a['tasks'],a['metrics']['decode_tps'],a['metrics']['prefill_tps'],a['metrics']['expert_cache_hit_pct'])
