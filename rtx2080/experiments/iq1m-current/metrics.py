"""Normalize saved engine evidence, validating agent attribution against every usage row."""
from pathlib import Path
from collections import defaultdict
import json, re, statistics, math

R=Path(__file__).resolve().parent
E=R.parent
REQUEST=re.compile(r'strata serve: prompt (\d+) tokens = (\d+) reused \+ (\d+) read in (\d+) ms .*?, (\d+) generated in (\d+) ms.*?drafts accepted (\d+) of (\d+)')
EXPERT=re.compile(r'decode expert cache hit rate: [\d.]+% \((\d+) hits / (\d+) lookups\)(?:; (\d+) more read.*?\((?:[\d.]+)% of all (\d+) routed\))?')
KV=re.compile(r'KV streaming: ([\d.]+)% of (\d+) block reads hit VRAM, ([\d.]+) MiB read from RAM')
SUFFIX=re.compile(r'suffix drafts: (\d+) windows, (\d+) of (\d+) drafts accepted')

def readjson(p):return json.loads(p.read_text())
def dump(n,x):(R/n).write_text(json.dumps(x,indent=2)+'\n')
def pct(a,b):return 100*a/b if b else None
def engine_rows(path):
    text=path.read_text();matches=list(REQUEST.finditer(text));rows=[]
    for i,m in enumerate(matches):
        row=dict(zip(['prompt_tokens','cached_tokens','read_tokens','prefill_ms','output_tokens','decode_ms','draft_accepted','draft_offered'],map(int,m.groups())))
        assert row['prompt_tokens']==row['cached_tokens']+row['read_tokens']
        assert 0<=row['draft_accepted']<=row['draft_offered']
        block=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)]
        x=EXPERT.search(block)
        if x:
            row.update(expert_hits=int(x[1]),expert_lookups=int(x[2]),expert_pcie=int(x[3] or 0))
            assert row['expert_hits']<=row['expert_lookups']
            if x[4]:assert int(x[4])==row['expert_lookups']+row['expert_pcie']
        x=SUFFIX.search(block)
        if x:row.update(suffix_windows=int(x[1]),suffix_accepted=int(x[2]),suffix_offered=int(x[3]))
        rows.append(row)
    kv=list(KV.finditer(text))
    # Cumulative within a segment, but reset between conversations. Never sum samples.
    decreases=sum(int(b[2])<int(a[2]) for a,b in zip(kv,kv[1:]))
    final={'hit_pct':float(kv[-1][1]),'block_reads':int(kv[-1][2]),'ram_read_mib':float(kv[-1][3]),
           'observed_counter_decreases':decreases,'samples':len(kv),
           'scope':'final counter segment only, not the full process or scored suite; printed precision. Counter decreases detect some resets, not necessarily all.'} if kv else None
    return rows,final

def aggregate(rows):
    keys=['prompt_tokens','cached_tokens','read_tokens','prefill_ms','output_tokens','decode_ms','draft_accepted','draft_offered','expert_hits','expert_lookups','expert_pcie','suffix_windows','suffix_accepted','suffix_offered']
    s={k:sum(r.get(k,0) for r in rows) for k in keys}
    s.update(requests=len(rows),decode_tps=1000*s['output_tokens']/s['decode_ms'] if s['decode_ms'] else None,
             prefill_tps=1000*s['read_tokens']/s['prefill_ms'] if s['prefill_ms'] else None,
             prompt_cache_token_hit_pct=pct(s['cached_tokens'],s['prompt_tokens']),
             prompt_cache_request_hit_pct=pct(sum(r['cached_tokens']>0 for r in rows),len(rows)),
             draft_acceptance_pct=pct(s['draft_accepted'],s['draft_offered']),
             suffix_acceptance_pct=pct(s['suffix_accepted'],s['suffix_offered']),
             suffix_accepted_per_window=s['suffix_accepted']/s['suffix_windows'] if s['suffix_windows'] else None,
             expert_cache_hit_pct=pct(s['expert_hits'],s['expert_lookups']),
             expert_resident_share_all_routed_pct=pct(s['expert_hits'],s['expert_lookups']+s['expert_pcie']),
             expert_pool_miss_share_all_routed_pct=pct(s['expert_lookups']-s['expert_hits'],s['expert_lookups']+s['expert_pcie']),
             expert_pcie_share_pct=pct(s['expert_pcie'],s['expert_lookups']+s['expert_pcie']),
             prompt_min=min((r['prompt_tokens'] for r in rows),default=None),
             prompt_max=max((r['prompt_tokens'] for r in rows),default=None))
    continuation=[r for r in rows if r.get('initial_request') is False]
    s.update(continuation_requests=len(continuation),
             continuation_cache_hits=sum(r['cached_tokens']>0 for r in continuation),
             continuation_cache_request_hit_pct=pct(sum(r['cached_tokens']>0 for r in continuation),len(continuation)),
             continuation_cache_token_hit_pct=pct(sum(r['cached_tokens'] for r in continuation),sum(r['prompt_tokens'] for r in continuation)))
    gaps=[r['reply_resume_gap_tokens'] for r in continuation if 'reply_resume_gap_tokens' in r]
    s.update(reply_resume_gaps_over64=sum(g>64 for g in gaps),
             reply_resume_gap_tokens_over64=sum(g for g in gaps if g>64),
             reply_resume_gap_median=statistics.median(gaps) if gaps else None,
             reply_resume_gap_max=max(gaps) if gaps else None)
    return s
