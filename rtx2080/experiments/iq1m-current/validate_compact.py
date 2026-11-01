"""Validate the compact + tiny-chunk GPU candidate against the installed production profile."""
import argparse,json,subprocess,time
from pathlib import Path
import compact as setup
c=setup.c
p=argparse.ArgumentParser();p.add_argument('stages',nargs='*',choices=['speed','longagent','agents']);a=p.parse_args()
stages={
 'speed':(['control','compact-min16'],'final-speed'),
 'longagent':(['control','compact-min16','compact-min16','control'],'capacity-r2'),
 'agents':(['control','compact-min16','compact-min16','control'],'coding'),
}
for stage in a.stages or stages:
 setup.protected();arms,prefix=stages[stage]
 c.record(event='validation_stage_start',stage=stage)
 with (c.R/(stage+'.log')).open('a') as log:
  subprocess.run([str(c.PYTHON),str(Path(__file__).with_name('compact.py')),stage,*arms,'--prefix',prefix],stdout=log,stderr=subprocess.STDOUT,check=True)
 setup.protected()
 if stage=='longagent':
  paths=sorted((c.R/'runs').glob(prefix+'-*/long-*-check.json'))
  assert len(paths)==8 and all(json.loads(x.read_text())['passed'] for x in paths),'near-capacity checks failed'
 if stage=='agents':
  paths=sorted((c.R/'runs').glob(prefix+'-*/*/result.json'))
  assert len(paths)==40 and all(json.loads(x.read_text())['passed'] for x in paths),'scored coding checks failed'
 c.record(event='validation_stage_complete',stage=stage)
c.status(phase='validation-complete',stages=a.stages or list(stages))
