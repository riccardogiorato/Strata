"""Transparent serial cache proxy for Strata's three native agent APIs."""
import copy
import json
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

CHAT='/v1/chat/completions'
MESSAGES='/v1/messages'
RESPONSES='/v1/responses'

class Usage:
    def __init__(self, path):
        self.path=path;self.values={};self.done=False;self.failed=False
    def observe(self, value):
        kind=value.get('type')
        self.failed |= bool(value.get('error')) or kind in ('error','response.failed')
        root=value.get('response') or value.get('message') or value
        self.failed |= bool(root.get('error')) or root.get('status')=='failed'
        usage=root.get('usage') or value.get('usage') or {}
        self.values.update({k:v for k,v in usage.items() if isinstance(v,int)})
        self.done |= kind in ('message_stop','response.completed','response.incomplete')
    @property
    def total(self):
        if self.path==MESSAGES:
            return sum(self.values.get(k,0) for k in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens','output_tokens'))
        return self.values.get('total_tokens',self.values.get('input_tokens',0)+self.values.get('output_tokens',0))


def cache_request(cache, body, path, explicit):
    indexed=copy.deepcopy(body)
    indexed['_cache_api']=path
    if path==RESPONSES:
        inputs=indexed.pop('input',[])
        indexed['messages']=([{'role':'user','content':inputs}] if isinstance(inputs,str) else inputs)
        # Stateless native Responses requires full conversation; opaque function items are retained.
    request=cache.session_id(indexed,explicit)
    if path==CHAT and 'strata_prefix' not in body and 'strata_prefix' in indexed:
        body['strata_prefix']=indexed['strata_prefix']
    return request


def handler(cache):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path not in ('/health','/v1/models'):
                self.send_error(404);return
            try:
                with urllib.request.urlopen(urllib.request.Request(cache.upstream+self.path,headers=cache.headers()),timeout=10) as r:
                    data=r.read();self.send_response(r.status)
                    self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
                    self.end_headers();self.wfile.write(data)
            except Exception as exc:self.send_error(502,str(exc))
        def do_POST(self):
            path=urlsplit(self.path).path.rstrip('/')
            if path.startswith('/v1/v1/messages'):path=path.replace('/v1/v1/','/v1/',1)
            if path not in (CHAT,MESSAGES,RESPONSES,MESSAGES+'/count_tokens'):
                self.send_error(404);return
            sent=False
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=32*1024**2:raise ValueError('Invalid request size')
                body=json.loads(self.rfile.read(size))
                if not isinstance(body,dict):raise ValueError('Request must be an object')
                count_only=path.endswith('/count_tokens')
                request=None if count_only else cache_request(cache,body,path,self.headers.get('X-Session-ID'))
                stream=bool(body.get('stream')) and not count_only
                if stream and path==CHAT:body['stream_options']={**body.get('stream_options',{}),'include_usage':True}
                headers=cache.headers()
                for name in ('anthropic-version','anthropic-beta'):
                    if self.headers.get(name):headers[name]=self.headers[name]
                with cache.lock:
                    if request is not None:cache.prepare(request)
                    usage=Usage(path);success=False
                    try:
                        req=urllib.request.Request(cache.upstream+path,data=json.dumps(body).encode(),headers=headers)
                        with urllib.request.urlopen(req,timeout=1800) as response:
                            self.send_response(response.status)
                            self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                            self.send_header('Connection','close');self.end_headers();sent=True
                            if stream:
                                for line in response:
                                    self.wfile.write(line);self.wfile.flush()
                                    if line.startswith(b'data:'):
                                        raw=line[5:].strip()
                                        if raw==b'[DONE]':usage.done=True
                                        elif raw:usage.observe(json.loads(raw))
                                success=usage.done and not usage.failed
                            else:
                                data=response.read();self.wfile.write(data)
                                usage.observe(json.loads(data));success=not usage.failed
                    finally:
                        if request is not None:cache.finish(request,usage.total,success)
            except urllib.error.HTTPError as exc:
                cache.event('upstream_error',status=exc.code)
                if not sent:
                    data=exc.read();self.send_response(exc.code)
                    self.send_header('Content-Type',exc.headers.get('Content-Type','application/json'))
                    self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
                exc.close()
            except (ValueError,TypeError) as exc:
                cache.event('invalid_request',error=str(exc))
                if not sent:self.send_error(400,str(exc))
            except Exception as exc:
                cache.event('request_failed',error=str(exc))
                if not sent:self.send_error(502,str(exc))
            finally:self.close_connection=True
    return Handler
