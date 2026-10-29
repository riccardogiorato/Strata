import array, os, queue, struct, tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from serve.prefix_pages import PrefixPages, read_manifest
from serve.server import StrataEngine, SessionRefused


def manifest(path, ids, boundaries=(), *, flags=2, pages=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    (path.parent/'pages').mkdir(exist_ok=True)
    pages=pages or [(16,1,2)]
    b=b'STRPAGE1'+struct.pack('<5Q',sum(x[0] for x in pages),len(pages),len(ids),len(boundaries),flags)
    b+=array.array('i',ids).tobytes()+struct.pack(f'<{len(boundaries)}Q',*boundaries)
    for n,a,c in pages:
        b+=struct.pack('<3Q',n,a,c)
        (path.parent/'pages'/f'{a:016x}{c:016x}.blk').write_bytes(bytes([a%256])*n)
    path.write_bytes(b+bytes(8))


class FakeEngine:
    def __init__(self, ids=(), boundaries=(), ram=0):
        self.ids=ids;self.boundaries=boundaries;self.ram=ram;self.calls=[];self.refuse=False;self.refuse_kind='invalid'
    def prefix_match(self, ids,cvec=True):self.calls.append(('query',list(ids)));return self.ram
    def session_file(self,action,path):
        self.calls.append((action,path))
        if self.refuse:raise SessionRefused(self.refuse_kind,'refused')
        if action=='save':manifest(path,self.ids,self.boundaries)
        return {'tokens':len(self.ids),'bytes':16,'ms':1}


class PrefixTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.cache=None
    def tearDown(self):
        if self.cache:self.cache.close()
        self.tmp.cleanup()
    def start(self,**kw):
        self.cache=PrefixPages(self.root,min_tokens=2,**kw);return self.cache
    def seed(self,name='a',ids=range(12),boundaries=(4,8),**kw):
        path=self.root/(name*64+'.spg');manifest(path,ids,boundaries,**kw);return path
    def test_exact_boundaries_only(self):
        e=read_manifest(self.seed())
        self.assertEqual(e.match(array.array('i',[*range(10),99]),True),8)
        self.assertEqual(e.match(array.array('i',[*range(12),99]),True),12)
        self.assertEqual(e.match(array.array('i',range(8)),True),4)
        self.assertEqual(e.match(array.array('i',[0,1,99,3,4]),True),0)
        self.assertEqual(e.match(array.array('i',range(13)),False),0)
    def test_ram_wins_tie(self):
        self.seed();c=self.start();e=FakeEngine(ram=8);c.before([*range(10),99],True,e)
        self.assertEqual([x[0] for x in e.calls],['query']);self.assertEqual(c.events[-1]['event'],'ram_preferred')
    def test_disk_wins_only_when_deeper(self):
        self.seed();c=self.start();e=FakeEngine(ram=4);c.before([*range(10),99],True,e)
        self.assertEqual([x[0] for x in e.calls],['query','restore']);self.assertEqual(c.events[-1]['matched_tokens'],8)
    def test_restart_recovers_index(self):
        c=self.start();e=FakeEngine(range(12),(4,8));c.after(list(range(10)),True,e);c.close()
        c=self.start();e.calls=[];c.before([*range(12),13],True,e);self.assertEqual(e.calls[-1][0],'restore')
    def test_shared_pages_count_once_and_gc_keeps_references(self):
        a=self.seed('a',pages=[(100,1,2),(30,3,4)]);b=self.seed('b',pages=[(100,1,2),(40,5,6)])
        c=self.start(max_bytes=10000,max_entries=2);self.assertEqual(c.physical_bytes,170)
        c.max_entries=1;c.entries[a.name].accessed=0;c.enforce_quota()
        self.assertFalse(a.exists());self.assertTrue(b.exists());self.assertEqual(c.physical_bytes,140)
        self.assertTrue((self.root/'pages'/f'{1:016x}{2:016x}.blk').exists())
    def test_quota_removes_oversized_entry(self):
        self.seed();c=self.start(max_bytes=1);self.assertFalse(c.entries);self.assertEqual(c.physical_bytes,0)
    def test_native_refusal_is_a_miss(self):
        self.seed();c=self.start();e=FakeEngine();e.refuse=True;c.before([*range(12),99],True,e)
        self.assertFalse(c.entries);self.assertEqual(c.physical_bytes,0)
    def test_memory_refusal_keeps_valid_snapshot(self):
        path=self.seed();c=self.start();e=FakeEngine();e.refuse=True;e.refuse_kind='memory'
        c.before([*range(12),99],True,e)
        self.assertIn(path.name,c.entries);self.assertTrue(path.exists())
        self.assertEqual(c.events[-1]['event'],'restore_deferred')
    def test_invalid_manifest_is_collected(self):
        p=self.seed();p.write_bytes(b'wrong');c=self.start();self.assertFalse(c.entries);self.assertFalse(p.exists())
    def test_two_owners_are_rejected(self):
        self.start()
        with self.assertRaises(BlockingIOError):PrefixPages(self.root)
    def test_symlink_manifest_is_not_read(self):
        outside=self.root/'outside';outside.write_text('private');(self.root/('a'*64+'.spg')).symlink_to(outside)
        c=self.start();self.assertFalse(c.entries);self.assertEqual(outside.read_text(),'private')
    def test_images_are_not_candidates(self):
        self.seed(flags=3);c=self.start();e=FakeEngine();c.before([*range(12),99],True,e);self.assertFalse(e.calls)
    def test_exact_request_not_saved_twice(self):
        c=self.start();e=FakeEngine(range(12),(4,8));c.after(list(range(10)),True,e)
        e.calls=[];c.after(list(range(10)),True,e);self.assertFalse(e.calls)
    def test_changed_same_length_history_is_saved(self):
        c=self.start(min_gain=1);e=FakeEngine(range(12),(4,8));c.after(list(range(10)),True,e);e.calls=[];c.after([*range(9),99],True,e)
        self.assertEqual(e.calls[0][0],'save');self.assertEqual(len(c.entries),2)
    def test_small_append_defers_save(self):
        self.seed();c=self.start(min_gain=10);e=FakeEngine();c.after([*range(12),99],True,e);self.assertFalse(e.calls)
    def test_small_history_edit_defers_to_coherent_checkpoint(self):
        self.seed();c=self.start(min_gain=4);e=FakeEngine();c.after([*range(9),99],True,e)
        self.assertFalse(e.calls);self.assertEqual(c.events[-1]['new_tokens'],2)
    def test_index_handles_multiple_branches_and_cvec(self):
        import random
        rng=random.Random(42)
        for i in range(12):
            ids=[*range(32),i,*range(33,96)]
            self.seed(name=format(i,'x'),ids=ids,boundaries=(8,32,48,64,80),flags=2 if i%2 else 0)
        c=self.start()
        for i in range(150):
            branch=rng.randrange(12);n=rng.randrange(5,100);cv=bool(rng.randrange(2))
            ids=array.array('i',([*range(32),branch,*range(33,96),99])[:n])
            expected=max(e.match(ids,cv) for e in c.entries.values())
            self.assertEqual(c.best(ids,cv)[0],expected)
    def test_crash_left_temporary_files_collected(self):
        self.seed();a=self.root/'.page-tmp-old';b=self.root/'pages/.page-tmp-old'
        a.write_text('orphan');b.write_text('orphan');self.start()
        self.assertFalse(a.exists());self.assertFalse(b.exists())
    def test_corrupt_access_metadata_is_only_a_lru_miss(self):
        self.seed();(self.root/'access.json').write_text('[]');c=self.start()
        self.assertEqual(c.best(array.array('i',range(13)),True)[0],12)
    def test_lru_write_failure_does_not_break_ram_hit(self):
        self.seed();c=self.start();e=FakeEngine(ram=12)
        with patch('serve.prefix_pages.os.replace',side_effect=OSError('disk full')):
            c.before([*range(12),99],True,e)
        self.assertEqual([x[0] for x in e.calls],['query'])
        self.assertEqual(c.events[-1]['event'],'ram_preferred')
    def test_namespace_is_stable_for_profiles_but_scopes_relative_model_paths(self):
        binary=self.root/'engine';binary.write_bytes(b'fake executable')
        def open_cache(cwd,profile):
            env={'STRATA_SESSION_PAGED':'1','STRATA_PREFIX_CACHE_DIR':str(self.root/'cache')}
            engine=SimpleNamespace(spawn=(str(binary),['--pack','pack/model','--expert-profile',profile],str(cwd),None,env))
            return PrefixPages.from_engine(engine)
        a=open_cache(self.root/'model-a','one.profile');first=a.root;a.close()
        b=open_cache(self.root/'model-a','two.profile');self.assertEqual(first,b.root);b.close()
        c=open_cache(self.root/'model-b','two.profile');self.assertNotEqual(first,c.root);c.close()
    def test_disabled_does_not_read_binary(self):
        e=SimpleNamespace(spawn=('missing',[],None,None,{}))
        with patch.dict(os.environ,{},clear=True):self.assertIsNone(PrefixPages.from_engine(e))


class GeneratorTests(unittest.TestCase):
    def fake(self):
        e=StrataEngine.__new__(StrataEngine);e._last={};e.batch=0;e._prefix_pages_initialized=True;calls=[]
        e._prefix_pages=SimpleNamespace(before=lambda *a:calls.append('before'),after=lambda *a:calls.append('after'));e.alive=lambda:True
        def inner(*args):
            try:yield 42;yield 7
            finally:e.last={'finish':'stop'}
        e._generate_uncached=inner;return e,calls
    def test_eos_close_saves_after_drain(self):
        e,c=self.fake();g=e.generate([1,2],2,{},threading.Event());self.assertEqual(next(g),42);g.close();self.assertEqual(c,['before','after'])
    def test_cancel_does_not_save(self):
        e,c=self.fake();cancel=threading.Event();g=e.generate([1,2],2,{},cancel);next(g);cancel.set();g.close();self.assertEqual(c,['before'])
    def test_failure_does_not_save_old_state(self):
        e,c=self.fake()
        def broken(*args):yield 42;raise ValueError('failed')
        e._generate_uncached=broken;g=e.generate([1,2],2,{},threading.Event());next(g)
        with self.assertRaises(ValueError):next(g)
        self.assertEqual(c,['before'])
    def test_vision_bypasses_text_cache(self):
        e,c=self.fake();list(e.generate([1,2],2,{},threading.Event(),embeddings='vision'));self.assertEqual(c,[])
    def test_projection_mode_matches_native_sampling_key(self):
        e,c=self.fake();modes=[];e.info={'cvec':1}
        e._prefix_pages.before=lambda ids,cv,engine:modes.append(cv)
        list(e.generate([1,2],2,{'experimental_speed_projection':False},threading.Event()))
        e.info={'cvec':0}
        list(e.generate([1,2],2,{'experimental_speed_projection':False},threading.Event()))
        self.assertEqual(modes,[False,True])
    def test_checkpoint_opt_out_skips_persistence(self):
        e,c=self.fake();list(e.generate([1,2],2,{'strata_checkpoint':False},threading.Event()))
        self.assertEqual(c,['before'])
    def test_bad_ram_response_ends_engine(self):
        e=StrataEngine.__new__(StrataEngine);e.proc=SimpleNamespace(stdin=SimpleNamespace(write=lambda s:None,flush=lambda:None));e.lines=queue.Queue();e.lines.put('CACHEMATCH 999');e.silence_s=1;e._silent=lambda msg:RuntimeError(msg)
        with self.assertRaises(RuntimeError):e.prefix_match([1,2,3])

if __name__=='__main__':unittest.main()
