"""Summarize the compact-layout follow-up without publishing raw model replies."""
import ast, hashlib, itertools, json, re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];R=ROOT/'runtime/compact-20261101'
rows=[json.loads(x) for x in (R/'results.jsonl').read_text().splitlines()] if (R/'results.jsonl').exists() else []
boots={x['label']:x for x in rows if x['event']=='boot'}
checks={x['label']:x['passed'] for x in rows if x['event'] in ('edit_correctness','needle_correctness')}
def text(p):
 return ''.join(c.get('delta',{}).get('content','') or '' for r in json.loads(p.read_text()) for c in r.get('choices',[]))
def code(s):
 m=re.search(r'```(?:python)?\s*\n(.*?)```',s,re.S);return m[1] if m else s
out={'requests':[],'first_logits_comparisons':[]}
for x in rows:
 if x['event']!='request':continue
 t=x['timings'];u=x['usage'];label=x['label'];p=R/(label+'.response.json')
 row={'label':label,'arm':x['arm'],'phase':x.get('phase','edit'),'passed':checks.get(label),'usage':u,'timings':t,'ttft_s':x['ttft_s'],'content_sha256':x['content_sha256']}
 if row['phase']=='edit':
  try:
   tree=ast.parse(code(text(p)))
   row['remaining_1024_lines']=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Constant) and type(n.value) is int and n.value==1024]
   row['ast_sha256']=hashlib.sha256(ast.dump(tree).encode()).hexdigest()
  except SyntaxError:row['syntax_error']=True
 log=R/(label+'.engine.log')
 if log.exists():
  raw=log.read_text();m=re.search(r'prompt path borrows (\d+)',raw)
  row['borrowed_slots']=int(m[1]) if m else None
  row['engine_errors']=bool(re.search(r'CUDA error|illegal memory|^ERR ',raw,re.M))
 out['requests'].append(row)
files=list(sorted(R.glob('*.logits.0')))
for a,b in itertools.combinations(files,2):
 if a.name.split('-')[0]!=b.name.split('-')[0]:continue
 x=np.fromfile(a,dtype='<f4').astype(np.float64);y=np.fromfile(b,dtype='<f4').astype(np.float64)
 assert x.shape==y.shape and np.isfinite(x).all() and np.isfinite(y).all()
 def lp(z):
  z=z-z.max();return z-np.log(np.exp(z).sum())
 lx,ly=lp(x),lp(y)
 out['first_logits_comparisons'].append({'a':a.name,'b':b.name,'identical':bool(np.array_equal(x,y)),'max_abs':float(np.max(np.abs(x-y))),'rms':float(np.sqrt(np.mean((x-y)**2))),'kl_a_b':float(np.sum(np.exp(lx)*(lx-ly))),'same_top1':bool(np.argmax(x)==np.argmax(y))})
out['residual_comparisons']=[]
out['empty_residual_dumps']=[p.name for p in R.glob('*.residuals') if not p.stat().st_size]
rf=sorted(p for p in R.glob('*.residuals') if p.stat().st_size)
dtype=np.dtype([('position','<i8'),('r','<f4',(10240,))])
for a,b in itertools.combinations(rf,2):
 x=np.fromfile(a,dtype=dtype);y=np.fromfile(b,dtype=dtype)
 assert np.array_equal(x['position'],y['position']) and np.isfinite(x['r']).all() and np.isfinite(y['r']).all()
 delta=x['r'].astype(np.float64)-y['r'].astype(np.float64)
 changed=np.any(delta!=0,axis=1)
 out['residual_comparisons'].append({'a':a.name,'b':b.name,'rows':len(x),'changed_rows':int(changed.sum()),'first_changed_position':int(x['position'][changed][0]) if changed.any() else None,'rms':float(np.sqrt(np.mean(delta**2))),'relative_rms':float(np.sqrt(np.sum(delta**2)/np.sum(x['r'].astype(np.float64)**2))),'max_abs':float(np.max(np.abs(delta)))})
def routes(path):
 raw=path.read_bytes();off=0;records={}
 while off<len(raw):
  header=np.frombuffer(raw,dtype='<i4',count=4,offset=off);off+=16
  layer,pos,n,feature=map(int,header);assert 0<=layer<48 and n>0 and feature in (0,1)
  ids=np.frombuffer(raw,dtype='<u2',count=n*10,offset=off).reshape(n,10);off+=n*20
  weights=np.frombuffer(raw,dtype='<u2',count=n*10,offset=off).reshape(n,10);off+=n*20
  if feature:off+=n*2560*2
  records[(pos,layer)]=(ids,weights)
 assert off==len(raw)
 return records
out['route_comparisons']=[]
for a,b in itertools.combinations(sorted(p for p in R.glob('*.routes') if (R/(p.stem+'.complete.json')).exists()),2):
 x,y=routes(a),routes(b);assert x.keys()==y.keys()
 changed=[]
 for key in sorted(x):
  xi,xw=x[key];yi,yw=y[key]
  ni=int(np.any(xi!=yi,axis=1).sum());nw=int(np.any(xw!=yw,axis=1).sum())
  if ni or nw:changed.append({'position':key[0],'layer':key[1],'rows':len(xi),'changed_id_rows':ni,'changed_bf16_weight_rows':nw})
 out['route_comparisons'].append({'a':a.name,'b':b.name,'total_records':len(x),'changed_records':len(changed),'first_changed_records':changed[:4]})
(R/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
for x in out['requests']:
 print(x['label'],x['passed'],x['timings'].get('prompt_per_second',x['timings']),x.get('remaining_1024_lines'))
print('first-logit pairs',len(out['first_logits_comparisons']))
