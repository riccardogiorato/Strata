"""Opt-in persistent prefix pages for the single native Strata engine.

Native manifests provide exact tokens and coherent hybrid-state boundaries. This layer selects a snapshot only
when it offers more reuse than the live/native RAM cache. Native restore validates model, config and all bytes.
The native serializer shares immutable pages; eviction accounts for unique physical bytes, not logical snapshots.
"""
from __future__ import annotations
import array
from collections import Counter
import contextlib
try:
    import fcntl
except ImportError:
    fcntl = None
import hashlib
import json
import logging
import math
import os
import re
import struct
import time
from dataclasses import dataclass
from pathlib import Path

LOG = logging.getLogger('strata.prefix_pages')
NAME = re.compile(r'[0-9a-f]{64}\.spg\Z')
PAGE = re.compile(r'[0-9a-f]{32}\.blk\Z')

@dataclass
class Entry:
    path: Path
    ids: array.array
    boundaries: tuple[int, ...]
    flags: int
    logical: int
    pages: tuple[str, ...]
    accessed: float

    def match(self, ids: array.array, cvec: bool) -> int:
        if self.flags & 1 or bool(self.flags & 2) != cvec:
            return 0
        # Check deepest first. array equality uses native integer comparisons, not a Python loop per token.
        for n in reversed(self.boundaries):
            if 0 < n < len(ids) and n <= len(self.ids) and self.ids[:n] == ids[:n]:
                return n
        return 0


def read_manifest(path: Path, accessed: float | None = None) -> Entry:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        st = os.fstat(f.fileno())
        import stat
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 56 <= st.st_size <= 64 * 1024**2:
            raise ValueError('invalid manifest file')
        b = f.read()
    if b[:8] != b'STRPAGE1':
        raise ValueError('not a page manifest')
    logical, nr, ni, nc, flags = struct.unpack_from('<5Q', b, 8)
    if nr > 1048576 or ni > 4194304 or nc > 65536 or len(b) != 56 + 4*ni + 8*nc + 24*nr or flags & ~3:
        raise ValueError('invalid manifest counts')
    ids = array.array('i'); ids.frombytes(b[48:48+4*ni])
    import sys
    if sys.byteorder != 'little': ids.byteswap()
    at = 48 + 4*ni
    boundaries = struct.unpack_from(f'<{nc}Q', b, at); at += 8*nc
    refs = [struct.unpack_from('<3Q', b, at + 24*i) for i in range(nr)]
    if any(not 0 < n <= 2*1024**2 for n, _, _ in refs) or sum(r[0] for r in refs) != logical:
        raise ValueError('invalid page sizes')
    if any(n > ni for n in boundaries): raise ValueError('invalid checkpoint')
    # Manifest checksum and each page are checked again by the native parser before device state changes.
    return Entry(path, ids, tuple(sorted(set((*boundaries, ni)))), flags, logical,
                 tuple(f'{a:016x}{c:016x}.blk' for _, a, c in refs), accessed or st.st_mtime)


class PrefixPages:
    def __init__(self, root: Path, *, max_bytes=16*1024**3, max_entries=128, min_tokens=8192, min_gain=1024):
        if fcntl is None: raise ValueError("persistent prefix pages currently require Linux/POSIX")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink(): raise ValueError('cache root cannot be a symlink')
        self.root.chmod(0o700)
        self.owner = os.open(self.root/'.owner.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try: fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException: os.close(self.owner); self.owner = None; raise
        self.max_bytes, self.max_entries = int(max_bytes), int(max_entries)
        self.min_tokens, self.min_gain = int(min_tokens), int(min_gain)
        if min(self.max_bytes, self.max_entries, self.min_tokens, self.min_gain) < 0:
            self.close(); raise ValueError('cache limits must be nonnegative')
        self.entries: dict[str, Entry] = {}
        self.events = []
        try: access = json.loads((self.root/'access.json').read_text())
        except (OSError, ValueError): access = {}
        if not isinstance(access, dict): access = {}
        access = {k: v for k, v in access.items() if isinstance(v, (int, float)) and math.isfinite(v)}
        for p in self.root.iterdir():
            if NAME.fullmatch(p.name):
                try: self.entries[p.name] = read_manifest(p, access.get(p.name))
                except (OSError, ValueError, struct.error) as e: self.event('invalid_manifest', name=p.name, error=str(e))
        self.enforce_quota()

    @classmethod
    def from_engine(cls, engine):
        if not getattr(engine, "spawn", None): return None
        exe, args, cwd, _, given, *_ = engine.spawn
        env = {**os.environ, **(given or {})}
        directory = env.get('STRATA_PREFIX_CACHE_DIR')
        if not directory: return None
        if not 0 <= int(env.get('STRATA_SESSION_PAGE_HOT_MIB', '256')) <= 16384:
            raise ValueError('hot page budget must be in 0..16384 MiB')
        if env.get('STRATA_SESSION_PAGED') != '1':
            raise ValueError('persistent prefix cache requires STRATA_SESSION_PAGED=1')
        if any(a in args for a in ('--batch', '--layer-split', '--peer-device')):
            raise ValueError('persistent prefix pages currently require a single serial engine')
        # Conservative namespace: pin the executable and engine arguments. Operational profile paths may change
        # between restarts; the native model/config fingerprint remains the final compatibility authority.
        identity_args=[]; skip=False
        for a in args:
            if skip: skip=False; continue
            if a == '--expert-profile': skip=True; continue
            identity_args.append(a)
        relevant = {k: v for k, v in env.items() if k.startswith('STRATA_') and
                    not k.startswith(('STRATA_PREFIX_', 'STRATA_SESSION_PAGE_')) and
                    k not in ('STRATA_DUMP_FIRST_LOGITS', 'STRATA_SESSION_PAGED')}
        binary = Path(exe)
        if not binary.is_absolute(): binary = Path(cwd or os.getcwd())/binary
        with binary.open('rb') as f: digest = hashlib.file_digest(f, 'sha256').hexdigest()
        namespace = hashlib.sha256(json.dumps([digest, str(Path(cwd or os.getcwd()).resolve()), identity_args, relevant], sort_keys=True).encode()).hexdigest()
        root = Path(directory).expanduser()
        if not root.is_absolute(): root = Path(cwd or os.getcwd())/root
        return cls(root/namespace,
                   max_bytes=int(env.get('STRATA_PREFIX_DISK_MIB', '16384'))*1024**2,
                   max_entries=int(env.get('STRATA_PREFIX_MAX_ENTRIES', '128')),
                   min_tokens=int(env.get('STRATA_PREFIX_MIN_TOKENS', '8192')),
                   min_gain=int(env.get('STRATA_PREFIX_SAVE_GAIN', '1024')))

    def reindex(self):
        self.prefixes = {}
        for entry in self.entries.values():
            if entry.flags & 1: continue
            raw = memoryview(entry.ids).cast('B')
            h = hashlib.sha256(); previous = 0
            for n in entry.boundaries:
                h.update(raw[previous*4:n*4]); previous = n
                self.prefixes.setdefault((bool(entry.flags & 2), n, h.digest()), []).append(entry)
        self.lengths = sorted({key[1] for key in self.prefixes})

    def best(self, prompt, cvec):
        raw = memoryview(prompt).cast('B'); h = hashlib.sha256(); previous = 0
        best = (0, None)
        for n in self.lengths:
            if n >= len(prompt): break
            h.update(raw[previous*4:n*4]); previous = n
            matches = self.prefixes.get((cvec, n, h.digest()))
            if matches: best = (n, max(matches, key=lambda e: e.accessed))
        return best

    def close(self):
        if getattr(self, 'owner', None) is not None:
            os.close(self.owner); self.owner = None

    def __del__(self): self.close()

    def event(self, kind, **fields):
        event = {'event': kind, 'at': time.time(), **fields}
        self.events.append(event); self.events[:] = self.events[-256:]
        LOG.info('%s', json.dumps(event))
        # Server deployments do not always install a logging handler for new modules.
        print('[strata prefix pages] ' + json.dumps(event), flush=True)

    @contextlib.contextmanager
    def pages_lock(self):
        fd = os.open(self.root/'.pages.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally: os.close(fd)

    def publish_access(self):
        tmp = self.root/'.access.tmp'
        try:
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as f: json.dump({k: e.accessed for k, e in self.entries.items()}, f)
            os.replace(tmp, self.root/'access.json')
        except OSError as e:
            # Lost recency is harmless: a full/unwritable disk must not break a usable RAM hit or restored state.
            self.event('access_write_failed', error=str(e))

    def enforce_quota(self):
        with self.pages_lock():
            pages = self.root/'pages'
            if pages.is_symlink(): raise ValueError('pages folder cannot be a symlink')
            files = {p.name: p.lstat().st_size for p in pages.iterdir() if PAGE.fullmatch(p.name)} if pages.exists() else {}
            # Remove invalid manifests too: they are not reachable cache entries, never model files.
            for p in self.root.iterdir():
                if NAME.fullmatch(p.name) and p.name not in self.entries: p.unlink()
            refs = Counter(name for e in self.entries.values() for name in set(e.pages))
            manifest_bytes = {name: e.path.stat().st_size for name, e in self.entries.items()}
            physical = sum(files.get(name, 0) for name in refs) + sum(manifest_bytes.values())
            while self.entries and (len(self.entries) > self.max_entries or physical > self.max_bytes):
                name = min(self.entries, key=lambda k: self.entries[k].accessed)
                entry = self.entries.pop(name); entry.path.unlink(missing_ok=True)
                physical -= manifest_bytes[name]
                for page in set(entry.pages):
                    refs[page] -= 1
                    if not refs[page]:
                        physical -= files.get(page, 0); del refs[page]
                self.event('evict', name=name, logical_bytes=entry.logical)
            reclaimed=0
            for name, size in files.items():
                if name not in refs: (pages/name).unlink(); reclaimed += size
            self.physical_bytes = sum(size for name, size in files.items() if name in refs)
            self.manifest_bytes = sum(e.path.stat().st_size for e in self.entries.values())
            self.logical_bytes = sum(e.logical for e in self.entries.values())
            self.publish_access()
            # No writer is active while this lock is held: crash-left temporary objects are unreachable.
            for directory in (self.root, pages):
                if directory.exists():
                    for tmp in directory.glob('.page-tmp-*'): tmp.unlink()
            if reclaimed: self.event('gc', bytes=reclaimed)
            self.reindex()

    def before(self, ids, cvec, engine):
        prompt = array.array('i', ids)
        score, entry = self.best(prompt, cvec)
        if score < self.min_tokens: self.event('miss', prompt_tokens=len(ids)); return
        ram = engine.prefix_match(ids, cvec)
        if ram >= score:
            entry.accessed=time.time(); self.publish_access(); self.event('ram_preferred', ram_tokens=ram, disk_tokens=score); return
        t=time.monotonic()
        try: result=engine.session_file('restore', str(entry.path))
        except Exception as e:
            # A native refusal leaves live state intact. A dead/desynchronized engine must propagate to the normal
            # server recovery path, never be treated as a successful cache miss.
            if e.__class__.__name__ != 'SessionRefused': raise
            self.entries.pop(entry.path.name, None); entry.path.unlink(missing_ok=True)
            self.event('restore_refused', error=str(e)); self.enforce_quota(); return
        entry.accessed=time.time(); self.publish_access()
        self.event('restore', seconds=time.monotonic()-t, matched_tokens=score, logical_bytes=entry.logical,
                   native_ms=result.get('ms'))

    def after(self, ids, cvec, engine):
        if len(ids) < self.min_tokens: return
        prompt=array.array('i', ids)
        key=hashlib.sha256(prompt.tobytes() + bytes([cvec])).hexdigest()+'.spg'
        if key in self.entries:
            self.entries[key].accessed=time.time(); self.publish_access(); self.event('save_skipped_exact'); return
        saved, _ = self.best(prompt, cvec)
        if saved and len(prompt)-saved < self.min_gain:
            self.event('save_deferred', new_tokens=len(prompt)-saved); return
        t=time.monotonic(); path=self.root/key
        try:
            engine.session_file('save', str(path))
            self.entries[key]=read_manifest(path, time.time())
            self.enforce_quota()
            self.event('save', seconds=time.monotonic()-t, entries=len(self.entries),
                       logical_bytes=self.logical_bytes, physical_bytes=self.physical_bytes, manifest_bytes=self.manifest_bytes)
        except Exception as e:
            if e.__class__.__name__ in ('EngineDied', 'EngineSilent', 'EngineStuck'): raise
            self.event('save_failed', error=str(e))
