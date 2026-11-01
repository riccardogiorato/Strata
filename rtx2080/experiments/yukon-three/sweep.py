"""Sequential isolated runs. Resume skips only explicitly completed suites."""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
R=ROOT/'runtime/yukon-three-20261101'
p=argparse.ArgumentParser();p.add_argument('mode',choices=['speed','edit','needle','agents','longagent']);p.add_argument('--prefix',required=True);p.add_argument('arms',nargs='+');a=p.parse_args()
for i,arm in enumerate(a.arms,1):
    label=f'{a.prefix}-{i}-{arm}'
    completion=label+('-1-'+arm if a.mode in ('agents','longagent') else '')+'.complete.json'
    if (R/completion).exists():continue
    print(json.dumps({'label':label,'started':time.time()}),flush=True)
    with (R/(label+'.driver.log')).open('w') as log:
        result=subprocess.run([sys.executable,str(Path(__file__).with_name('run.py')),a.mode,'--arm',arm,'--label',label],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    print(json.dumps({'label':label,'exit':result.returncode,'finished':time.time()}),flush=True)
    if result.returncode:sys.exit(result.returncode)
