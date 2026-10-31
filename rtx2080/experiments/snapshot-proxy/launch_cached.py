#!/usr/bin/env python3
"""Run an isolated Strata server and its automatic SSD-session chat proxy together."""
import argparse,fcntl,hashlib,json,logging,os,signal,socket,subprocess,time,urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from branch_cache import BranchCache
from api_proxy import handler

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--auto-pin',action='store_true',help='Pin the last large complete text message before the final turn')
 p.add_argument('--config',type=Path,required=True);p.add_argument('--cache-dir',type=Path,required=True)
 p.add_argument('--python',type=Path,required=True,help='Python environment containing Strata server dependencies')
 p.add_argument('--engine-dir',type=Path,required=True,help='Source checkout containing serve/server.py')
 p.add_argument('--port',type=int,default=8088);p.add_argument('--upstream-port',type=int,default=8087);p.add_argument('--max-gib',type=float,default=16)
 a=p.parse_args()
 if a.max_gib<=0:p.error('--max-gib must be positive')
 cfg=json.loads(a.config.read_text());root=a.cache_dir.expanduser().resolve();root.mkdir(parents=True,exist_ok=True,mode=0o700);root.chmod(0o700)
 if a.port==a.upstream_port:p.error('Proxy and upstream ports must differ')
 for port in [a.port,a.upstream_port]:
  with socket.socket() as sock:
   sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
   sock.bind(('127.0.0.1',port))
 busy=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
 if busy:raise RuntimeError('GPU inference is already running. Stop that server before launching this profile.')
 # A separate identity directory prevents different models/engines sharing the same quota/index.
 identity=dict(config=cfg,executable_sha256=hashlib.sha256(Path(cfg['exe']).read_bytes()).hexdigest())
 key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest();d=root/key;d.mkdir(mode=0o700,exist_ok=True)
 lease=(d/'cache.lock').open('a')
 try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise RuntimeError('This cache already has a running owner')
 cfg.update(host='127.0.0.1',port=a.upstream_port,slot_save_path=str(d),log=str(d/'engine.log'))
 config=d/'server.json';config.write_text(json.dumps(cfg,indent=2));config.chmod(0o600)
 log=(d/'server.log').open('a');proc=None
 try:
  proc=subprocess.Popen([str(a.python.resolve()),'-u','-m','serve.server','--engine','strata','--config',str(config),'--host','127.0.0.1','--port',str(a.upstream_port)],cwd=a.engine_dir.resolve(),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  upstream=f'http://127.0.0.1:{a.upstream_port}';deadline=time.monotonic()+600
  while True:
   if proc.poll() is not None:raise RuntimeError(f'Strata exited {proc.returncode}; inspect {d}/server.log')
   try:
    with urllib.request.urlopen(upstream+'/health',timeout=2) as r:ready=json.load(r).get('status')=='ok'
    if ready:break
   except Exception:pass
   if time.monotonic()>deadline:raise TimeoutError('Strata startup exceeded ten minutes')
   time.sleep(1)
  logging.basicConfig(level=logging.INFO)
  cache=BranchCache(upstream,d,key,max_bytes=int(a.max_gib*1024**3),auto_pin=a.auto_pin)
  print(f'Cached APIs: http://127.0.0.1:{a.port}/v1 (chat/completions, responses, messages)\nCache: {d}\nUse X-Session-ID for each conversation. Ctrl+C stops both processes.',flush=True)
  with ThreadingHTTPServer(('127.0.0.1',a.port),handler(cache)) as proxy:proxy.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  if proc is not None and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=30)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
  log.close();lease.close()
if __name__=='__main__':main()
