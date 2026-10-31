"""Check existing fused device code against the installed production executable."""
import re, subprocess
import campaign as c
obj=c.ROOT/'build/iq1m-current/CMakeFiles/strata_mmq.dir/src/prefill/moe_fused_iq.cu.o'
new=subprocess.check_output(['/opt/cuda/bin/cuobjdump','--dump-sass',str(obj)],text=True)
old=(c.R/'installed-kernels.sass').read_text()
def functions(text):
    out={}
    for m in re.finditer(r'Function : (\S+)(.*?)(?=Function : |\Z)',text,re.S):
        key=re.sub(r'__N__[a-f0-9]+_15_moe_fused_iq_cu_[a-f0-9]+','__N__NORMALIZED',m[1])
        out[key]=[re.sub(r'/\*.*?\*/','',s).strip() for s in re.findall(r'/\*\w+\*/\s+([^\n]+)',m[2])]
    return out
a,b=functions(old),functions(new)
changed=[k for k in a if k in b and a[k]!=b[k]]
result={'old_functions':len(a),'new_functions':len(b),'matched':len(a.keys()&b.keys()),'changed':changed,'missing':list(a.keys()-b.keys()),'added':list(b.keys()-a.keys())}
c.dump(c.R/'sass-comparison.json',result);print(result)
assert len(a)==46 and not changed and not result['missing']
