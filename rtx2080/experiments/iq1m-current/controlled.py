"""Wait for a quiet host before the measured campaign; never stop unrelated work."""
from pathlib import Path
import subprocess, threading, time, sys
import campaign as c
import harness as h

def cpu():
    x=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]));return sum(x),x[3]+x[4]
quiet=0
while quiet<3:
    a=cpu();time.sleep(5);b=cpu();busy=1-(b[1]-a[1])/max(1,b[0]-a[0])
    quiet=quiet+1 if busy<.20 else 0
    c.status(phase='waiting-for-quiet-host',cpu_busy=busy,quiet_samples=quiet)
c.record(event='quiet_host',samples=3,threshold=.20)
stop=threading.Event();threading.Thread(target=h.telemetry,args=(stop,),daemon=True).start()
try:
    args=sys.argv[1:] or ['campaign.py','edit','prod','off','on','on','off','prod','--prefix','fixed']
    cmd=[str(c.PYTHON),str(Path(__file__).with_name(args[0])),*args[1:]]
    subprocess.run(cmd,check=True)
finally:stop.set()
