"""Run the final matched validation sequentially on the single GPU."""
import argparse, hashlib, json, subprocess, time
from pathlib import Path
import campaign as c

p=argparse.ArgumentParser()
p.add_argument('candidate',choices=['fp16','fp16-512','legacy','on'])
p.add_argument('--stages',nargs='+',choices=['needle','longagent','speed','agents'],default=['needle','longagent','speed','agents'])
a=p.parse_args()
scripts=Path(__file__).resolve().parent
commands={
    'needle':['campaign.py','needle','prod',a.candidate,a.candidate,'prod','--prefix','final'],
    'longagent':['agents.py','prod',a.candidate,a.candidate,'prod','--long','--prefix','capacity'],
    'speed':['campaign.py','speed','prod',a.candidate,'--prefix','final'],
    'agents':['agents.py','prod',a.candidate,a.candidate,'prod','--prefix','scored'],
}
def protected():
    expected=json.loads((c.R/'protected.json').read_text())
    assert all(hashlib.sha256((c.ROOT/name).read_bytes()).hexdigest()==value for name,value in expected.items()),'Production changed during A/B'
protected()
identity=hashlib.sha256(c.CANDIDATE.read_bytes()).hexdigest()
for stage in a.stages:
    c.record(event='final_stage_start',stage=stage,candidate=a.candidate,binary_sha256=identity)
    with (c.R/f'final-{stage}.log').open('a') as log:
        subprocess.run([str(c.PYTHON),'-u',str(scripts/'controlled.py'),*commands[stage]],stdout=log,stderr=subprocess.STDOUT,check=True)
    protected()
    assert hashlib.sha256(c.CANDIDATE.read_bytes()).hexdigest()==identity,'Candidate replaced during validation'
    c.record(event='final_stage_complete',stage=stage,candidate=a.candidate)
c.status(phase='final-validation-complete',candidate=a.candidate,stages=a.stages)
