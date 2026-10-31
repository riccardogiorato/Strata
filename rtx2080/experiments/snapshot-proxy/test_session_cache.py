import tempfile,unittest
from pathlib import Path
from session_cache import SessionCache
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.calls=[]
  def transport(path,body):
   self.calls.append((path,body))
   if 'save' in path:(Path(self.tmp.name)/body['filename']).write_bytes(b'x'*10)
   return {'ok':True}
  self.c=SessionCache('',self.tmp.name,'model-v1',max_bytes=20,min_tokens=10,min_gain=5,transport=transport)
 def test_restart_restores(self):
  self.c.finish('a',20);other=SessionCache('',self.tmp.name,'model-v1',transport=self.c.transport);other.prepare('a');self.assertIn('restore',self.calls[-1][0])
 def test_identity_isolation(self):
  self.c.finish('a',20);other=SessionCache('',self.tmp.name,'model-v2',transport=self.c.transport);other.prepare('a');self.assertEqual(len(self.calls),1)
 def test_lru_bounded(self):
  for s in ['a','b','c']:self.c.finish(s,20)
  self.assertNotIn(self.c.key('a'),self.c.rows);self.assertEqual(sum(r['bytes'] for r in self.c.rows.values()),20)
 def test_failed_request_never_saved(self):
  self.c.finish('a',20,False);self.assertFalse(self.calls);self.assertIsNone(self.c.active)
 def test_small_progress_does_not_rewrite(self):
  self.c.finish('a',20);self.c.finish('a',22);self.assertEqual(len(self.calls),1)
 def test_session_id_cannot_escape_directory(self):
  self.c.finish('../../oops',20);self.assertEqual(len(list(Path(self.tmp.name).glob('*.bin'))),1)
 def test_restore_failure_falls_back(self):
  self.c.finish('a',20);self.c.active=None
  self.c.transport=lambda *args:(_ for _ in ()).throw(RuntimeError('bad snapshot'))
  self.c.prepare('a');self.assertEqual(self.c.events[-1]['event'],'restore_failed');self.assertIsNone(self.c.active)

 def test_failed_restore_is_replaced_even_without_token_growth(self):
  self.c.finish('a',20);self.c.active=None;transport=self.c.transport
  self.c.transport=lambda *args:(_ for _ in ()).throw(RuntimeError('bad snapshot'))
  self.c.prepare('a');self.c.transport=transport;self.c.finish('a',20)
  self.assertEqual(sum('save' in p for p,b in self.calls),2)
  self.assertNotIn(self.c.key('a'),self.c.dirty)
 def test_missing_snapshot_is_recreated(self):
  self.c.finish('a',20);row=self.c.rows[self.c.key('a')]
  (Path(self.tmp.name)/row['filename']).unlink();self.c.active=None
  self.c.prepare('a');self.c.finish('a',20)
  self.assertTrue((Path(self.tmp.name)/row['filename']).is_file())

class ProxyTests(unittest.TestCase):
 def test_stream_forwarding_snapshot_and_upstream_error(self):
  import json,threading,urllib.request
  from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
  from session_cache import handler
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  class Backend(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    if body.get("reject"):
     self.send_response(400);self.end_headers();self.wfile.write(b'{"error":"invalid request"}');return
    self.send_response(200);self.end_headers()
    if 'action=save' in self.path:
     (Path(tmp.name)/body['filename']).write_bytes(b'snapshot');self.wfile.write(b'{"ok":true}');return
    chunks=[{'choices':[{'delta':{'content':'hello'},'finish_reason':None}]},{'choices':[],'usage':{'total_tokens':10000}}]
    for x in chunks:self.wfile.write(b'data: '+json.dumps(x).encode()+b'\n\n')
    self.wfile.write(b'data: [DONE]\n\n')
  back=ThreadingHTTPServer(('127.0.0.1',0),Backend);threading.Thread(target=back.serve_forever,daemon=True).start()
  c=SessionCache(f'http://127.0.0.1:{back.server_port}',tmp.name,'test');proxy=ThreadingHTTPServer(('127.0.0.1',0),handler(c));threading.Thread(target=proxy.serve_forever,daemon=True).start()
  try:
   req=urllib.request.Request(f'http://127.0.0.1:{proxy.server_port}/v1/chat/completions',data=json.dumps({'messages':[{'role':'user','content':'hi'}],'stream':True}).encode(),headers={'Content-Type':'application/json','X-Session-ID':'a'})
   with urllib.request.urlopen(req) as r:data=r.read()
   self.assertIn(b'hello',data);self.assertIn(b'[DONE]',data);self.assertEqual(len(c.rows),1);self.assertEqual(next(iter(c.rows.values()))['tokens'],10000)
   bad=urllib.request.Request(f'http://127.0.0.1:{proxy.server_port}/v1/chat/completions',data=json.dumps({'messages':[{'role':'user','content':'bad'}],'reject':True}).encode(),headers={'Content-Type':'application/json','X-Session-ID':'b'})
   with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(bad)
   self.assertEqual(caught.exception.code,400);self.assertIn(b'invalid request',caught.exception.read());caught.exception.close();self.assertEqual(len(c.rows),1)
  finally:proxy.shutdown();proxy.server_close();back.shutdown();back.server_close()

if __name__=='__main__':unittest.main()
