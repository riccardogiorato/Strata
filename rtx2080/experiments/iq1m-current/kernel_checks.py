import os, subprocess, time
import campaign as c
c.check_gpu()
env={**os.environ,'STRATA_PF_FUSED':'1','STRATA_PF_FUSED_SM75':'1','STRATA_PF_FUSED_SM75_IQ':'1','STRATA_PF_FUSED_IQ1_M':'1'}
build=c.ROOT/'build/iq1m-current';exe=str(build/'prefill_fused_iq_test')
checks=[('ctest',['ctest','--test-dir',str(build),'-R','^prefill_fused_iq_test_iq1m','--output-on-failure']),('reference',[exe,'--only=IQ1_M','--require-iq1','--no-timing']),('chunks',[exe,'--only=IQ1_M','--require-iq1','--no-ref','--chunks=4096,4608,8192']),('memcheck',['/opt/cuda/bin/compute-sanitizer','--tool','memcheck','--error-exitcode','1',exe,'--only=IQ1_M','--require-iq1','--no-ref','--chunks=256']),('iq2s-reference',[exe,'--only=IQ2_S','--no-timing']),('iq2xxs-reference',[exe,'--only=IQ2_XXS','--no-timing'])]
for label,cmd in checks:
    with (c.R/('kernel-'+label+'.log')).open('w') as log:
        proc=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
    c.record(event='kernel_check',label=label,exit=proc.returncode)
    if proc.returncode:raise SystemExit(proc.returncode)
c.dump(c.R/'kernel.complete.json',{'complete':True,'at':time.time()})
