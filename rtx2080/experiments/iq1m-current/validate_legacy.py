"""Finish the remaining INT8 candidate after its paired 121K screen."""
import hashlib,json,subprocess
from pathlib import Path
import campaign as c
scripts=Path(__file__).resolve().parent
identity=hashlib.sha256(c.CANDIDATE.read_bytes()).hexdigest()
def protected():
    for name,value in json.loads((c.R/'protected.json').read_text()).items():
        assert hashlib.sha256((c.ROOT/name).read_bytes()).hexdigest()==value,name
    assert hashlib.sha256(c.CANDIDATE.read_bytes()).hexdigest()==identity
stages=[
    ('speed',['campaign.py','speed','legacy','--prefix','legacyfinal']),
    ('longagent',['agents.py','legacy','legacy','--long','--prefix','int8capacity']),
    ('agents',['agents.py','prod','legacy','legacy','prod','--prefix','scored']),
]
protected()
for stage,args in stages:
    c.record(event='final_stage_start',stage=stage,candidate='legacy',binary_sha256=identity)
    with (c.R/f'legacy-final-{stage}.log').open('a') as log:
        subprocess.run([str(c.PYTHON),'-u',str(scripts/'controlled.py'),*args],stdout=log,stderr=subprocess.STDOUT,check=True)
    protected();c.record(event='final_stage_complete',stage=stage,candidate='legacy')
    if stage=='longagent':
        checks=list((c.R/'runs').glob('int8capacity-*/long-*-check.json'))
        assert len(checks)==4
        if not all(json.loads(p.read_text())['passed'] for p in checks):
            c.record(event='candidate_decision',candidate='legacy',decision='not promoted; failed near-capacity quality gate')
            c.status(phase='validation-complete',candidate='legacy',quality_gate_passed=False)
            break
else:c.status(phase='validation-complete',candidate='legacy',quality_gate_passed=True)
