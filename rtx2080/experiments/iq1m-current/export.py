"""Publish compact counters and checks, never raw prompts, replies or credentials."""
import argparse, json
from pathlib import Path
import campaign as c

p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).with_name('results.json'));a=p.parse_args()
s=json.loads((c.R/'summary.json').read_text());provenance=json.loads((c.R/'provenance.json').read_text())
def speed_stats(rows):
    good=[r for r in rows if r.get('ok')]
    read=sum(r.get('read_tokens') or 0 for r in good);pm=sum(r.get('prompt_ms') or 0 for r in good)
    output=sum(r.get('generated_tokens') or 0 for r in good);dm=sum(r.get('decode_ms') or 0 for r in good)
    return {'requests':len(rows),'valid':len(good),'read_tokens':read,'prompt_ms':pm,'output_tokens':output,'decode_ms':dm,
            'weighted_prefill_tps':read*1000/pm if pm else None,'weighted_decode_tps':output*1000/dm if dm else None,
            'individual_prefill_tps':[r.get('prompt_tps') for r in good],
            'individual_decode_tps':[r.get('decode_tps') for r in good],
            'cached_tokens':[r.get('reused_tokens') for r in good],
            'ttft_s':[r.get('ttft_s') for r in good]}
out={'hardware':'RTX 2080 8GB, SM75, 165W; i5-9600K, 64GB RAM',
     'engine':'Strata 0.2.9 / engine 0.1.55 plus existing RTX 2080 patches',
     'model':'Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS 125B',
     'context_capacity':131072,'resident_kv_tokens':32768,'route_prior':1.5,
     'production_sha256':provenance['production_sha256'],
     'candidate_build':json.loads((c.R/'warp-build.json').read_text()),
     'fixture_sha256':provenance['fixture_sha256'],'arm_env_overrides':c.ARM_ENV,
     'long_prompt':s['long'],'host_load':s['host_load'],'agents':[], 'speed':[],
     'decisions':[r for line in (c.R/'results.jsonl').read_text().splitlines() if (r:=json.loads(line))['event']=='candidate_decision']}
for row in s['agent']:
    if not row['tasks']:continue
    long=bool(row['long_checks'])
    out['agents'].append({'label':row['label'],'kind':'near-capacity' if long else 'scored',
                         'phases_or_tasks':row['tasks'],'passed':sum(x['passed'] for x in row['long_checks'].values()) if long else row['passed'],
                         'wall_s':row['wall_s'],'metrics':row['metrics'],'thinking_requests':row['thinking_requests'],
                         'usage_matches':row['usage_matches'],
                         'checks':{k:{field:v[field] for field in ('passed','file_check_passed','agent_exit','tool_calls')} for k,v in row['long_checks'].items()},
                         'task_scores':[] if long else [{'task':r['task'],'passed':r['passed']} for r in row['per_task']]})
for row in s['speed']:
    d=row['results'];out['speed'].append({'label':row['path'].split('/')[0],
        'chat':speed_stats(d['chat']['requests']),
        'prompts':{name:speed_stats(v['requests']) for name,v in d['prompts'].items()},
        'failure_count':len(d['failures']),'skipped':d['skipped']})
a.output.write_text(json.dumps(out,indent=2)+'\n');print(a.output)
