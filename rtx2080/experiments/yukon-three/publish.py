"""Create one compact public evidence file from completed private measurements."""
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'runtime/yukon-three-20261101'
sys.path.insert(0,str(ROOT/'rtx2080/experiments/iq1m-current'))
import metrics
from summarize import collect
s=collect();events=[json.loads(x) for x in (R/'results.jsonl').read_text().splitlines()]
keys=['requests','prompt_min','prompt_max','read_tokens','prefill_ms','output_tokens','decode_ms','decode_tps','prefill_tps','draft_acceptance_pct','expert_cache_hit_pct','expert_pcie_share_pct','prompt_cache_token_hit_pct','continuation_cache_token_hit_pct','continuation_cache_request_hit_pct']
def compact(d):return {k:d.get(k) for k in keys}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
out={'date':'2026-11-01','hardware':s['hardware'],'model':'Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS (mixed quantization), 125B MoE',
 'context_capacity':131072,'resident_int8_kv':32768,'route_prior':1.5,'mtp_spec':4,'mtp_min_p':0.7,
 'production_base_commit':'83ecef965dde2900e75f8272b409359118df8629',
 'experimental_engine_code_commit':'0f3c06654bd54ed62fb361f699dc8640d3d65b82',
 'protected_files':json.loads((R/'protected.json').read_text()),
 'limitations':['Single RTX 2080; only CUDA SM75 built/tested.','Usual speed suite: three runs, thinking off; request nonces vary.','Fixed 122451-token edit: one run per candidate, controls bracket the sequence.','Near-capacity agent: one scenario plus follow-up per arm, thinking on; not the full ten-task coding suite.','Native tokens / native time used for throughput. Prefix and expert hit rates are distinct.','Initial uncorrected profile excluded; corrected profile is instrumented diagnostic evidence.','No candidate enabled in production.'],
 'kernels':{},'smoke':{},'profile':{},'speed':{},'high_context':{},'long_agent':{},'policy':{}}
for name in ['gdn-extended.log','gdn-extended-split.log','head-layout-control.log','projections-idle.log']:
 p=R/name
 out['kernels'][name]={'sha256':sha(p),'pass_lines':[x for x in p.read_text().splitlines() if x.startswith('PASS')],
                     'representative_timings':[x for x in p.read_text().splitlines() if any(k in x for k in ['T=5 keep=5 ','T=8 keep=8 ','T=1 rows=-4 ','T=5 rows=-4 ','T=4096 '])]}
for arm in ['candidate-off','commit','projections','head','head-layout']:
 checks=[x for x in s['checks'] if x.get('event')=='smoke_correctness' and x['arm']==arm]
 out['smoke'][arm]={'passed':sum(x['passed'] for x in checks),'total':len(checks)}
p=R/'baseline-profile-idle.engine.log';lines=p.read_text().splitlines()
out['profile']={'log_sha256':sha(p),'decode_diagnostics':[x for x in lines if x.startswith('strata decode timing:') and not x.startswith('strata decode timing: 1 windows')],
                'commit_diagnostics':[x for x in lines if 'commit graph' in x and 'ms GPU' in x],
                'head_ms_per_window':[float(re.search(r' head ([\d.]+)',x)[1]) for x in lines if x.startswith('strata decode GPU stages') and re.search(r' head ([\d.]+)',x)]}
first_hash=next(x['content_sha256'] for x in events if x.get('event')=='request' and x['label']=='high-a-1-candidate-off')
for label,row in s['runs'].items():
 if not row['complete']:continue
 base={'arm':row['arm'],'binary_sha256':row['binary_sha256'],'engine_log_sha256':row['engine_log_sha256'],'native':compact(row['native'])}
 if label.startswith('speed-'):
  base.update(speed=row['speed'],gpu_telemetry=row.get('gpu_telemetry'));out['speed'][label]=base
 elif label.startswith('high-'):
  req=next(x for x in events if x.get('event')=='request' and x['label']==label)
  base.update(passed=next(x['passed'] for x in s['checks'] if x['label']==label),
              text_identical_to_first_control=req['content_sha256']==first_hash,ttft_s=req['ttft_s'],timings=req['timings'])
  out['high_context'][label]=base
 elif label.startswith('agent-long-') and 'agents' in row:
  a=row['agents'];assert all(t['reconciliation']['reconciled'] for t in a['tasks']),label
  base.update(native=compact(a['native']),checks=row['long_checks'],passed=a['passed'],total=len(row['long_checks']),
              reasoning_chars=sum(t['reasoning_chars'] for t in a['tasks']),tool_calls=sum(t['tool_calls'] for t in a['tasks']),
              tool_errors=sum(t['tool_errors'] for t in a['tasks']),reconciled=True)
  out['long_agent'][label]=base
 elif label.startswith('policy-'):
  native,_=metrics.engine_rows(R/(label+'.engine.log'));reqs=row['requests'];rec=metrics.reconcile(native,reqs)
  assert rec['reconciled'],(label,rec)
  base['phases']={req['phase']:compact(metrics.aggregate([n])) for req,n in zip(reqs,native)}
  base['reconciled']=True;out['policy'][label]=base
outpath=Path(__file__).with_name('results.json');outpath.write_text(json.dumps(out,indent=2)+'\n');print(outpath)
