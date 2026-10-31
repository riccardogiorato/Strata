"""Separate IQ1 arithmetic, compact layout and the existing FP16 WMMA alternative."""
import sys,time
import campaign as c
cases={
    'legacy':('on',{'STRATA_PF_FUSED_LEGACY_LAYOUT':'1'}),
    'fp16':('off',{'STRATA_PF_WMMA':'1'}),
    'profile-off':('off',{'STRATA_PREFILL_TIMING':'1'}),
    'profile-on':('on',{'STRATA_PREFILL_TIMING':'1'}),
}
for i,case in enumerate(sys.argv[1:] or ['legacy','fp16'],1):
    arm,extra=cases[case];label=f'diagnostic-{i}-{case}'
    if (c.R/(label+'.complete.json')).exists():continue
    with c.server(label,arm,extra=extra):c.edit(label,arm=case,chunk='4096',route='1.5')
    c.dump(c.R/(label+'.complete.json'),{'complete':True,'at':time.time()})
