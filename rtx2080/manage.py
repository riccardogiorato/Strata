#!/usr/bin/env python3
"""One production profile; machine files and credentials remain under runtime/."""
import argparse, json, os, socket, subprocess, sys, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'runtime'
PROFILE = ROOT / 'rtx2080/profile.json'

def environment():
    env = dict(os.environ)
    path = RUNTIME / 'service.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                env.setdefault(key.strip(), value.strip().strip('"'))
    return env

def config():
    env = environment()
    variables = {'REPO': str(ROOT), 'MODEL_ROOT': env.get('STRATA_MODEL_ROOT', str(Path.home()/'models'))}
    def expand(value):
        if isinstance(value, dict): return {k: expand(v) for k,v in value.items()}
        if isinstance(value, list): return [expand(v) for v in value]
        if isinstance(value, str):
            for key, replacement in variables.items(): value = value.replace('${'+key+'}', replacement)
            if '${' in value: raise ValueError('Unknown profile variable: '+value)
        return value
    return expand(json.loads(PROFILE.read_text()))

def configure():
    cfg = config()
    for key in ('exe', 'cwd', 'tokenizer'):
        if not Path(cfg[key]).exists(): raise FileNotFoundError(f'{key}: {cfg[key]} (see rtx2080/README.md)')
    (RUNTIME/'logs').mkdir(parents=True, exist_ok=True)
    path = RUNTIME/'current.json'
    path.write_text(json.dumps(cfg, indent=2)+'\n')
    return path

def python():
    exe = RUNTIME/'venv/bin/python'
    if not exe.exists(): raise FileNotFoundError('Create runtime/venv and install requirements.txt first')
    return str(exe)

def api(path, body=None):
    env = environment(); cfg = config()
    headers = {'Authorization': 'Bearer '+env.get('STRATA_API_KEY',''), 'Content-Type':'application/json'}
    req = urllib.request.Request(f'http://127.0.0.1:{cfg["port"]}'+path, headers=headers,
        data=json.dumps(body).encode() if body is not None else None)
    with urllib.request.urlopen(req, timeout=180) as f: return json.load(f)

def install_service():
    configure()
    if not environment().get('STRATA_API_KEY'): raise ValueError('Set STRATA_API_KEY in runtime/service.env (chmod 600)')
    if not (RUNTIME/'service.env').exists(): raise FileNotFoundError('Persistent service needs runtime/service.env')
    unit = RUNTIME/'strata-serve.service'
    unit.write_text('[Unit]\nDescription=Strata RTX 2080: canonical rtx2080/profile.json\nAfter=network-online.target\nWants=network-online.target\nStartLimitIntervalSec=300\nStartLimitBurst=5\n\n[Service]\nType=simple\nWorkingDirectory='+str(ROOT)+'\nEnvironmentFile='+str(RUNTIME/'service.env')+'\nExecStartPre='+str(ROOT/'rtx2080/power-limit-wait.sh')+'\nExecStart='+python()+' '+str(ROOT/'rtx2080/manage.py')+' serve\nRestart=on-failure\nRestartSec=15\n\n[Install]\nWantedBy=default.target\n')
    target = Path.home()/'.config/systemd/user/strata-serve.service'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink(): target.unlink()
    elif target.exists(): raise FileExistsError('Refusing to overwrite a regular user unit: '+str(target))
    target.symlink_to(unit)
    subprocess.run(['systemctl','--user','daemon-reload'], check=True)
    subprocess.run(['systemctl','--user','enable','strata-serve.service'], check=True)
    print('Installed. Start/restart with systemctl --user restart strata-serve.service')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['configure','show','status','serve','check','bench','install-service'])
    args, rest = parser.parse_known_args()
    if args.command == 'configure': print(configure())
    elif args.command == 'show': print(json.dumps(config(), indent=2))
    elif args.command == 'status':
        cfg=config()
        print(json.dumps({'profile':str(PROFILE),'branch':subprocess.check_output(['git','-C',str(ROOT),'branch','--show-current'],text=True).strip(),'routing':cfg['env']['STRATA_ROUTE_PRIOR'],'loop_guard':cfg['reasoning_loop_recovery'],'health':api('/health')},indent=2))
    elif args.command == 'serve':
        env=environment()
        if not env.get('STRATA_API_KEY'): raise ValueError('STRATA_API_KEY is required for this profile')
        cfg = config()
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind((cfg['host'], cfg['port']))  # refuse to load a second engine on an occupied endpoint
        os.chdir(ROOT)
        os.execve(python(),[python(),str(ROOT/'strata.py'),'serve','--config',str(configure()),*rest],env)
    elif args.command == 'check':
        reply=api('/v1/chat/completions',{'model':'local-model','messages':[{'role':'user','content':'Reply exactly CONFIG_OK'}],'reasoning_effort':'none','temperature':0,'max_tokens':64})
        assert 'CONFIG_OK' in reply['choices'][0]['message']['content'],reply
        print('Chat check passed; '+json.dumps(api('/health')))
    elif args.command == 'bench':
        env=environment();env['STRATA_KEY']=env.get('STRATA_API_KEY','')
        os.execve(python(),[python(),str(ROOT/'tools/strata_bench.py'),'--url',f'http://127.0.0.1:{config()["port"]}','--runs','3','--long','--out',str(RUNTIME/'bench'),*rest],env)
    else: install_service()

if __name__ == '__main__': main()
