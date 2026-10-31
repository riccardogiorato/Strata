import tempfile
import unittest
from pathlib import Path
from branch_cache import BranchCache, descriptor, shared

class BranchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.calls = []
        def transport(path, body):
            self.calls.append((path, body))
            if 'save' in path:
                (Path(self.tmp.name)/body['filename']).write_bytes(b'x'*10)
            return {}
        self.transport = transport
        self.c = self.fresh()
    def fresh(self, identity='one'):
        return BranchCache('', self.tmp.name, identity, max_bytes=30, min_tokens=10,
                           transport=self.transport)
    def body(self, suffix='A'):
        return {'model':'swift', 'messages':[{'role':'user','content':'x'*5000+suffix}]}
    def request(self, suffix='A'):
        return self.c.session_id(self.body(suffix), 'session')
    def test_same_length_branches_survive_restart(self):
        a,b = self.request('A'),self.request('B')
        self.c.finish(a,100);self.c.finish(b,100)
        self.assertEqual(len(self.c.rows),2)
        c=self.fresh();c.prepare(a)
        self.assertEqual(c.active,c.key(a[0]))
        self.assertEqual(c.events[-1]['event'],'branch_restore')
    def test_live_prefix_avoids_restore(self):
        a,b=self.request('A'),self.request('B')
        self.c.finish(a,100);self.c.prepare(b)
        self.assertEqual(len(self.calls),1)
    def test_old_branch_beats_live_partial(self):
        a,b=self.request('A'),self.request('B')
        self.c.finish(a,100);self.c.finish(b,100);self.c.prepare(a)
        self.assertEqual(self.c.active,self.c.key(a[0]))
    def test_scope_and_identity_isolation(self):
        a=self.request();self.c.finish(a,100)
        c=self.fresh();c.prepare(c.session_id(self.body(),'different'))
        self.assertIsNone(c.active)
        self.assertFalse(self.fresh('other').rows)
    def test_failed_branch_not_saved(self):
        self.c.finish(self.request(),100,False)
        self.assertFalse(self.c.rows)
    def test_quota_eviction(self):
        for s in 'ABCD':self.c.finish(self.request(s),100)
        self.assertEqual(len(self.c.rows),3)
        self.assertEqual(len(list(Path(self.tmp.name).glob('*.bin'))),3)
    def test_metadata_prevents_wrong_selection(self):
        a=self.body();b=self.body();b['tools']=[{'name':'test'}]
        self.assertEqual(shared(descriptor(a,'s'),descriptor(b,'s')),0)
    def test_restore_failure(self):
        a=self.request();self.c.finish(a,100);c=self.fresh()
        c.transport=lambda *a:(_ for _ in ()).throw(RuntimeError('corrupt'))
        c.prepare(a);self.assertIsNone(c.active)
        self.assertIn(c.key(a[0]),c.dirty)
    def test_missing_snapshot_not_restored(self):
        a=self.request();self.c.finish(a,100)
        for p in Path(self.tmp.name).glob('*.bin'):p.unlink()
        c=self.fresh();c.prepare(a);self.assertIsNone(c.active)
    def test_short_append_defers_disk_save(self):
        a=self.request();self.c.finish(a,100)
        b=self.body();b['messages'] += [{'role':'assistant','content':'ok'},{'role':'user','content':'continue'}]
        req=self.c.session_id(b,'session');self.c.finish(req,120)
        self.assertEqual(len(self.c.rows),1)
        self.assertEqual(self.c.events[-1]['event'],'branch_save_deferred')
        self.c.finish(req,1200);self.assertEqual(len(self.c.rows),2)
    def test_auto_pin_respects_explicit_boundary(self):
        c=self.fresh();c.auto_pin=True
        b={'messages':[{'role':'user','content':'x'*10000},{'role':'user','content':'question'}]}
        c.session_id(b,'s');self.assertEqual(b['strata_prefix'],{'message':0,'chars':10000})
        b['strata_prefix']={'message':0,'chars':20}
        c.session_id(b,'s');self.assertEqual(b['strata_prefix']['chars'],20)
    def test_auto_pin_does_not_guess_inside_last_message(self):
        c=self.fresh();c.auto_pin=True;b=self.body()
        c.session_id(b,'s');self.assertNotIn('strata_prefix',b)
    def test_request_descriptors_are_independent(self):
        a=self.request('A');b=self.request('B')
        self.c.finish(a,100);self.c.finish(b,100)
        self.assertNotEqual(self.c.rows[self.c.key(a[0])]['prefix']['digest'],
                            self.c.rows[self.c.key(b[0])]['prefix']['digest'])

if __name__=='__main__':unittest.main()
