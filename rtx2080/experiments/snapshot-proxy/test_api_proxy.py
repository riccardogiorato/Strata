import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from branch_cache import BranchCache
from api_proxy import CHAT,MESSAGES,RESPONSES,Usage,handler

class Tests(unittest.TestCase):
 def test_anthropic_cache_accounting(self):
  u=Usage(MESSAGES)
  u.observe({'type':'message_start','message':{'usage':{'input_tokens':120000,'output_tokens':0}}})
  u.observe({'type':'message_delta','usage':{'input_tokens':1,'cache_read_input_tokens':119000,'cache_creation_input_tokens':999,'output_tokens':50}})
  u.observe({'type':'message_stop'})
  self.assertEqual(u.total,120050);self.assertTrue(u.done)
 def test_response_failure(self):
  u=Usage(RESPONSES);u.observe({'type':'response.failed','response':{'status':'failed','usage':{'total_tokens':999}}})
  self.assertTrue(u.failed)
 def test_all_dialects_stream_and_nonstream(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
  seen=[]
  class Backend(BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_POST(self):
    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    seen.append((self.path,body))
    self.send_response(200);self.send_header('Content-Type','text/event-stream' if body.get('stream') else 'application/json');self.end_headers()
    if 'action=save' in self.path:
     (Path(tmp.name)/body['filename']).write_bytes(b'snapshot');self.wfile.write(b'{}');return
    if self.path.endswith('count_tokens'):self.wfile.write(b'{"input_tokens":20}');return
    if self.path==CHAT:
     result={'choices':[{'message':{'content':'ok','tool_calls':[{'function':{'name':'read_file','arguments':'{"path":"a.py"}'}}]}}],'usage':{'total_tokens':120050}}
     events=[result];end=b'data: [DONE]\n\n'
    elif self.path==MESSAGES:
     result={'type':'message','content':[{'type':'tool_use','name':'read_file','input':{'path':'a.py'}}],'usage':{'input_tokens':1,'cache_read_input_tokens':119000,'cache_creation_input_tokens':999,'output_tokens':50}}
     events=[{'type':'message_start','message':result},{'type':'message_stop'}];end=b''
    else:
     result={'status':'completed','output':[{'type':'function_call','name':'read_file','arguments':'{"path":"a.py"}'}],'usage':{'input_tokens':120000,'output_tokens':50,'total_tokens':120050}}
     events=[{'type':'response.completed','response':result}];end=b''
    if body.get('stream'):
     for event in events:self.wfile.write(b'data: '+json.dumps(event).encode()+b'\n\n')
     self.wfile.write(end)
    else:self.wfile.write(json.dumps(result).encode())
  back=ThreadingHTTPServer(('127.0.0.1',0),Backend)
  threading.Thread(target=back.serve_forever,daemon=True).start()
  cache=BranchCache(f'http://127.0.0.1:{back.server_port}',tmp.name,'test')
  proxy=ThreadingHTTPServer(('127.0.0.1',0),handler(cache));threading.Thread(target=proxy.serve_forever,daemon=True).start()
  try:
   for path in [CHAT,MESSAGES,RESPONSES]:
    for stream in [False,True]:
     body={'model':'swift','stream':stream,'max_tokens':64}
     if path==RESPONSES:body['input']='hello'
     else:body['messages']=[{'role':'user','content':'hello'}]
     req=urllib.request.Request(f'http://127.0.0.1:{proxy.server_port}'+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Session-ID':path+str(stream)})
     with urllib.request.urlopen(req) as r:data=r.read()
     self.assertIn(b'read_file',data)
     with cache.lock:pass
   self.assertEqual(len(cache.rows),6)
   self.assertTrue(all(r['tokens']==120050 for r in cache.rows.values()))
   self.assertTrue(all('_cache_api' not in body for path,body in seen))
   req=urllib.request.Request(f'http://127.0.0.1:{proxy.server_port}/v1/messages/count_tokens',data=b'{"messages":[]}',headers={'Content-Type':'application/json'})
   with urllib.request.urlopen(req) as r:self.assertEqual(json.load(r)['input_tokens'],20)
   self.assertEqual(len(cache.rows),6)
  finally:proxy.shutdown();proxy.server_close();back.shutdown();back.server_close()
if __name__=='__main__':unittest.main()
