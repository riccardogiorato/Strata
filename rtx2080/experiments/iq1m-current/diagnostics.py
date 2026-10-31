"""Separate IQ1 arithmetic, compact layout and the existing FP16 WMMA alternative."""
import argparse,time
import campaign as c
cases={
    'compact':('on',{}),
    'legacy-emb':('on',{'STRATA_PF_FUSED_LEGACY_LAYOUT':'1','STRATA_EMB_REUSE_ACCOUNT':'1'}),
    'legacy':('on',{'STRATA_PF_FUSED_LEGACY_LAYOUT':'1'}),
    'fp16':('off',{'STRATA_PF_WMMA':'1'}),
    'profile-off':('off',{'STRATA_PREFILL_TIMING':'1'}),
    'profile-on':('on',{'STRATA_PREFILL_TIMING':'1'}),
}
p=argparse.ArgumentParser();p.add_argument('cases',nargs='*');p.add_argument('--prefix',default='diagnostic');p.add_argument('--chunk',default='4096');a=p.parse_args()
for i,case in enumerate(a.cases or ['legacy','fp16'],1):
    arm,extra=cases[case];label=f'{a.prefix}-{i}-{case}'
    if (c.R/(label+'.complete.json')).exists():continue
    with c.server(label,arm,chunk=a.chunk,extra=extra):c.edit(label,arm=case,chunk=a.chunk,route='1.5')
    c.dump(c.R/(label+'.complete.json'),{'complete':True,'at':time.time()})
