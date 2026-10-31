#!/usr/bin/env python3
"""Local serial OpenAI proxy with bounded persistent Strata session snapshots.
The upstream must have slot_save_path pointing to the same private cache directory.
Restart this proxy together with the upstream. Identity must pin model, engine and cache settings.
"""
import argparse,hashlib,json,logging,os,threading,time,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
LOG=logging.getLogger('session-cache')
class SessionCache:
 def __init__(self,upstream,directory,identity,max_bytes=16*1024**3,min_tokens=8192,min_gain=1024,transport=None,api_key=None):
  self.api_key=api_key;self.upstream=upstream.rstrip('/');self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
  self.namespace=hashlib.sha256(identity.encode()).hexdigest();self.index_path=self.directory/('index-'+self.namespace+'.json')
  self.max_bytes=max_bytes;self.min_tokens=min_tokens;self.min_gain=min_gain;self.lock=threading.Lock();self.active=None;self.transport=transport or self._transport
  self.rows=json.loads(self.index_path.read_text()) if self.index_path.exists() else {};self.events=[];self.dirty=set()
 def headers(self):
  return {'Content-Type':'application/json',**({'Authorization':'Bearer '+self.api_key} if self.api_key else {})}
 def _transport(self,path,body):
  req=urllib.request.Request(self.upstream+path,data=json.dumps(body).encode(),headers=self.headers())
  with urllib.request.urlopen(req,timeout=120) as r:return json.load(r)
 def event(self,kind,**kw):
  e=dict(event=kind,at=time.time(),**kw);self.events.append(e);del self.events[:-256];LOG.info(json.dumps(e))
 def key(self,sid):return hashlib.sha256((self.namespace+'\0'+sid).encode()).hexdigest()
 def publish(self):
  tmp=self.index_path.with_suffix('.tmp');tmp.write_text(json.dumps(self.rows,indent=2));tmp.chmod(0o600);os.replace(tmp,self.index_path)
 def prepare(self,sid):
  k=self.key(sid)
  if self.active==k:return
  row=self.rows.get(k);self.active=None
  if row and (self.directory/row['filename']).is_file():
   t=time.monotonic()
   try:self.transport('/slots/0?action=restore',{'filename':row['filename']})
   except Exception as e:self.dirty.add(k);self.event('restore_failed',key=k,error=str(e));return
   row['last_used']=time.time();self.publish();self.event('restore',key=k,seconds=time.monotonic()-t,bytes=row['bytes'])
  elif row:self.dirty.add(k)
  self.active=k
 def finish(self,sid,tokens,success=True):
  k=self.key(sid)
  if not success:self.active=None;return
  self.active=k;old=self.rows.get(k)
  if tokens<self.min_tokens or (old and k not in self.dirty and (self.directory/old['filename']).is_file() and tokens-old['tokens']<self.min_gain):return
  filename=k+'.bin';path=self.directory/filename;t=time.monotonic()
  try:self.transport('/slots/0?action=save',{'filename':filename})
  except Exception as e:self.dirty.add(k);self.event('save_failed',key=k,error=str(e));return
  if not path.is_file():self.event('save_failed',key=k,error='upstream did not create snapshot');return
  self.dirty.discard(k);self.rows[k]={'filename':filename,'tokens':tokens,'bytes':path.stat().st_size,'last_used':time.time()};self.publish()
  self.event('save',key=k,seconds=time.monotonic()-t,bytes=path.stat().st_size)
  while sum(x['bytes'] for x in self.rows.values())>self.max_bytes:
   victim=min(self.rows,key=lambda v:self.rows[v]['last_used']);row=self.rows.pop(victim);self.publish()
   (self.directory/row['filename']).unlink(missing_ok=True);self.event('evict',key=victim,bytes=row['bytes'])
 def session_id(self,body,explicit=None):
  if explicit:return explicit
  # Stable per conversation unless its first user turn is edited. Same opening may share state;
  # Strata checks actual token prefixes before reuse, so differing histories cannot silently reuse wrong cells.
  first=next((m for m in body.get('messages',[]) if m.get('role')=='user'),None)
  if first is None:raise ValueError('Use X-Session-ID or provide a user message')
  return json.dumps({'model':body.get('model'),'first_user':first},sort_keys=True)
def handler(cache):
 class Handler(BaseHTTPRequestHandler):
  def do_GET(self):
   if self.path not in ['/health','/v1/models']:self.send_error(404);return
   try:
    with urllib.request.urlopen(urllib.request.Request(cache.upstream+self.path,headers=cache.headers()),timeout=10) as r:data=r.read()
    self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
   except Exception as e:self.send_error(502,str(e))
  def do_POST(self):
   if self.path!='/v1/chat/completions':self.send_error(404);return
   sent=False
   try:
    n=int(self.headers.get('Content-Length','0'))
    if n<=0 or n>32*1024**2:raise ValueError('Invalid request size')
    body=json.loads(self.rfile.read(n));sid=cache.session_id(body,self.headers.get('X-Session-ID'));stream=bool(body.get('stream'))
    if stream:body['stream_options']={**body.get('stream_options',{}),'include_usage':True}
    with cache.lock:
     cache.prepare(sid);total=0;success=False
     try:
      req=urllib.request.Request(cache.upstream+self.path,data=json.dumps(body).encode(),headers=cache.headers())
      with urllib.request.urlopen(req,timeout=1800) as r:
       self.send_response(r.status);self.send_header('Content-Type','text/event-stream' if stream else 'application/json');self.send_header('Connection','close');self.end_headers();sent=True
       if stream:
        saw_done=False;had_error=False
        for line in r:
         self.wfile.write(line);self.wfile.flush()
         if line.startswith(b'data: '):
          raw=line[6:].strip()
          if raw==b'[DONE]':saw_done=True
          else:
           x=json.loads(raw);had_error|=bool(x.get('error'));u=x.get('usage') or {};total=u.get('total_tokens',total)
        success=saw_done and not had_error
       else:
        data=r.read();self.wfile.write(data);x=json.loads(data);success=not x.get('error');total=(x.get('usage') or {}).get('total_tokens',0)
     finally:cache.finish(sid,total,success)
   except urllib.error.HTTPError as e:
    cache.event('upstream_error',status=e.code)
    if not sent:
     data=e.read();self.send_response(e.code);self.send_header('Content-Type',e.headers.get('Content-Type','application/json'));self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
    e.close()
   except Exception as e:
    cache.event('request_failed',error=str(e))
    if not sent:self.send_error(502,str(e))
   finally:self.close_connection=True
 return Handler
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--upstream',default='http://127.0.0.1:8087');p.add_argument('--cache-dir',required=True);p.add_argument('--identity',required=True);p.add_argument('--port',type=int,default=8088);p.add_argument('--max-gib',type=float,default=16);p.add_argument('--min-tokens',type=int,default=8192);p.add_argument('--min-gain',type=int,default=1024);p.add_argument('--upstream-key-env');a=p.parse_args()
 logging.basicConfig(level=logging.INFO);c=SessionCache(a.upstream,a.cache_dir,a.identity,int(a.max_gib*1024**3),a.min_tokens,a.min_gain,api_key=os.environ[a.upstream_key_env] if a.upstream_key_env else None)
 ThreadingHTTPServer(('127.0.0.1',a.port),handler(c)).serve_forever()
if __name__=='__main__':main()
