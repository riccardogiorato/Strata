"""Publish aggregate follow-up evidence; raw text, logits and routing traces stay private."""
from collections import defaultdict
import argparse,hashlib,json,re
from pathlib import Path
import metrics
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'runtime/compact-20261101'
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).with_name('compact-results.json'));a=p.parse_args()
s=json.loads((R/'summary.json').read_text());events=[json.loads(x) for x in (R/'results.jsonl').read_text().splitlines()]
boots={x['label']:x for x in events if x['event']=='boot'}
out={'hardware':'RTX 2080 8GB / SM75 / 165W; i5-9600K; 64GB RAM','model':'Swift 1.5 Qwen3.8 Flash-Next GSQ-RCO IQ2_XS 125B','context_capacity':131072,'baseline_source_commit':'e9fe9e763d9f7b69826c990058e49f89dafeef71','baseline_profile_commit':'fcc1adff233f8d31a2ecf18c4d457a7061048721','baseline_sha256':json.loads((R/'protected.json').read_text())['runtime/bin/strata'],'candidate_build':json.loads((R/'candidate-build.json').read_text()),'long_edit':[],'diagnostics':{},'speed':[],'agents':[],'invalid_harness_runs':[]}
groups=defaultdict(list)
for row in s['requests']:
 if row['phase']=='edit':groups[(row['label'].split('-')[0],row['arm'])].append(row)
for (phase,arm),rr in groups.items():
 tt=[x['timings'] for x in rr];read=sum(x['prompt_n'] for x in tt);pm=sum(x['prompt_ms'] for x in tt);gen=sum(x['predicted_n'] for x in tt);dm=sum(x['predicted_ms'] for x in tt)
 out['long_edit'].append({'phase':phase,'arm':arm,'runs':len(rr),'passed':sum(x['passed'] for x in rr),'read_tokens':read,'prefill_ms':pm,'weighted_prefill_tps':1000*read/pm,'output_tokens':gen,'decode_ms':dm,'weighted_decode_tps':1000*gen/dm,'individual_prefill_tps':[x['prompt_per_second'] for x in tt],'remaining_1024_lines':[x.get('remaining_1024_lines') for x in rr],'ast_hashes':[x.get('ast_sha256') for x in rr],'content_hashes':[x['content_sha256'] for x in rr],'first_logits_hashes':[hashlib.sha256((R/(x['label']+'.logits.0')).read_bytes()).hexdigest() for x in rr]})
for key,predicate in {
 'minimum16_long_edits':lambda x:x['a'].startswith('minedit') and x['b'].startswith('minedit'),
 'automatic_cpu_share':lambda x:x['a'].startswith('numeric') and x['b'].startswith('numeric'),
 'cpu_share_off':lambda x:x['a'].startswith('cpuoff') and x['b'].startswith('cpuoff'),
 'minimum16_vs_cpu_off':lambda x:x['a'].startswith('cpuoff') and x['b'].startswith('minprobe'),
 'minimum16_repeats':lambda x:x['a'].startswith('minprobe') and x['b'].startswith('minprobe'),
}.items():
 pairs=[x for x in s['first_logits_comparisons'] if predicate(x)];routes=[x for x in s['route_comparisons'] if predicate(x)]
 out['diagnostics'][key]={'logit_pairs':len(pairs),'identical_logits':sum(x['identical'] for x in pairs),'max_logit_abs_difference':max((x['max_abs'] for x in pairs),default=None),'route_pairs':len(routes),'identical_route_records':sum(x['changed_records']==0 for x in routes),'first_changed_route_records':[x['first_changed_records'][:1] for x in routes if x['changed_records']]}
out['diagnostics']['trace_scope']='10254-token probe; expert IDs and BF16 routing weights, plus full FP32 first-token logits. Sparse residual dump was empty after the final tiny segment; no residual-equality claim.'
out['diagnostics']['kernel_regroup']=[]
for row in json.loads((R/'regroup-checks.json').read_text()):
 raw=(R/('regroup-'+row['format']+'.log')).read_text();changed=list(map(int,re.findall(r'regroup repeat \d+: (\d+) changed values',raw)))
 out['diagnostics']['kernel_regroup'].append({**row,'repeats':len(changed),'changed_values':changed})
def speed(rows):
 good=[x for x in rows if x.get('ok')];read=sum(x.get('read_tokens') or 0 for x in good);pm=sum(x.get('prompt_ms') or 0 for x in good);gen=sum(x.get('generated_tokens') or 0 for x in good);dm=sum(x.get('decode_ms') or 0 for x in good)
 return {'requests':len(rows),'valid':len(good),'read_tokens':read,'prefill_ms':pm,'output_tokens':gen,'decode_ms':dm,'prefill_tps':1000*read/pm if pm else None,'decode_tps':1000*gen/dm if dm else None,'drafts_offered':sum(x.get('drafts_offered') or 0 for x in good),'drafts_accepted':sum(x.get('drafts_accepted') or 0 for x in good),'ttft_s':[x.get('ttft_s') for x in good]}
for path in sorted(R.glob('*speed*/**/results.json')):
 data=json.loads(path.read_text())['results'];label=path.relative_to(R).parts[0]
 out['speed'].append({'label':label,'arm':boots[label]['arm'],'chat':speed(data['chat']['requests']),'prompts':{k:speed(v['requests']) for k,v in data['prompts'].items()},'failures':len(data['failures']),'skipped':data['skipped']})
 agent=data.get('agent',{});requests=[row for session in agent.get('sessions',[]) for row in session]
 prompt=sum(row.get('prompt_tokens',0) for row in requests);cached=sum(row.get('reused_tokens',0) for row in requests)
 out['speed'][-1]['synthetic_agent']={'metrics':speed(requests),'prompt_tokens':prompt,'cached_tokens':cached,'cache_token_hit_pct':100*cached/prompt if prompt else None,'continuation_ttft_s':agent.get('turn_ttft_s'),'reread_tokens_per_session':agent.get('reread_tokens'),'new_tokens_per_session':agent.get('new_tokens')}
combined=defaultdict(lambda:{'native':[],'http':[],'checks':0,'passed':0,'wall_s':0,'audits':[]})
for suite in sorted((R/'runs').glob('*')) if (R/'runs').exists() else []:
 native=[];http=[];scores=[];audits=[];wall=0
 for path in sorted(suite.glob('*/result.json')):
  data=json.loads(path.read_text());resume=path.parent.name.endswith('-followup')
  for x in data['native']:
   if resume:x['initial_request']=False
   native.append(x)
  for i,x in enumerate(data['http']):x['initial_request']=i==0 and not resume;http.append(x)
  audits.append(metrics.reconcile(data['native'],data['http']));wall+=data['wall_s'];scores.append({'task':data['task'],'passed':data['passed']})
 if not native and not http:
  out['invalid_harness_runs'].append({'label':suite.name,'phases':len(scores),'api_requests':0,'engine_requests':0,'reason':'measurement wrapper missing; harness exited before calling model'})
  continue
 checks=[json.loads(p.read_text()) for p in suite.glob('long-*-check.json')]
 out['agents'].append({'label':suite.name,'arm':boots[suite.name]['arm'],'kind':'near-capacity' if checks else 'scored','checks':len(checks) if checks else len(scores),'passed':sum(x['passed'] for x in checks or scores),'task_scores':[] if checks else scores,'native_metrics':metrics.aggregate(native),'initial_native_metrics':metrics.aggregate([x for x in native if x.get('initial_request') is True]),'client_cache':metrics.client_cache(http),'wall_s':wall,'usage_reconciled':all(x['reconciled'] for x in audits),'internal_continuations':sum(x['internal_continuations'] for x in audits)})
 item=combined[('near-capacity' if checks else 'scored',boots[suite.name]['arm'])]
 item['native']+=native;item['http']+=http;item['checks']+=len(checks or scores);item['passed']+=sum(x['passed'] for x in checks or scores);item['wall_s']+=wall;item['audits']+=audits
out['agent_comparison']=[{'kind':kind,'arm':arm,'checks':d['checks'],'passed':d['passed'],'wall_s':d['wall_s'],'native_metrics':metrics.aggregate(d['native']),'initial_native_metrics':metrics.aggregate([x for x in d['native'] if x.get('initial_request') is True]),'client_cache':metrics.client_cache(d['http']),'usage_reconciled':all(x['reconciled'] for x in d['audits'])} for (kind,arm),d in combined.items()]
out['per_task']=[]
task_groups=defaultdict(list)
for suite in (R/'runs').glob('coding-*'):
 for path in suite.glob('*/result.json'):
  row=json.loads(path.read_text());task_groups[(row['task'],boots[suite.name]['arm'])].append(row)
for (task,arm),rr in sorted(task_groups.items()):
 native=[x for row in rr for x in row['native']];m=metrics.aggregate(native)
 out['per_task'].append({'task':task,'arm':arm,'runs':len(rr),'passed':sum(x['passed'] for x in rr),'output_tokens':m['output_tokens'],'prefill_tps':m['prefill_tps'],'decode_tps':m['decode_tps'],'expert_cache_hit_pct':m['expert_cache_hit_pct'],'wall_s':sum(row['wall_s'] for row in rr)})
out['allocation_observations']=[]
for label in boots:
 if not label.startswith(('final-speed','capacity-r2','coding')):continue
 path=R/(label+'.engine.log')
 if not path.exists():continue
 events=[]
 for line in path.read_text().splitlines():
  m=re.search(r'VRAM (\d+) MiB kept free: the expert cache (\d+) -> (\d+) of (\d+) slots .*?, (\d+) MiB free now, prompt chunk (\d+)',line)
  if m:events.append(dict(zip(['requested_free_mib','before_slots','after_slots','capacity_slots','actual_free_mib','prompt_chunk'],map(int,m.groups()))))
 unique=[]
 for row in events:
  if row not in unique:unique.append(row)
 if events:out['allocation_observations'].append({'label':label,'arm':boots[label]['arm'],'resize_events':len(events),'captured_window_sizes':sorted(set(map(int,re.findall(r'capturing the (\d+)-token window',path.read_text())))),'distinct_events':unique})
out['provenance_note']='Boot source_commit records the checkout used by the harness; the native executable sources are the baseline_source_commit and candidate_build.source_commit above, matched by executable SHA256.'
out['not_tested']=['HIP','Windows','other GPUs']
a.output.write_text(json.dumps(out,indent=2)+'\n');print(a.output)
