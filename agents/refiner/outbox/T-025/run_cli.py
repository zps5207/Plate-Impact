"""Run the local embmesh copy and record wall time and process-tree peak RSS."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil

root = Path(__file__).resolve().parents[4]
here = Path(__file__).resolve().parent
deck, mode, target = sys.argv[1:]
deck = str(Path(deck).resolve())
target = str(Path(target).resolve())
command = [sys.executable, '-B', '-m', 'embmesh.cli', 'visualize', deck,
           '--instance', 'Plate-1', '--diameter', '0.001', '--curved', mode,
           '--plate-node-contact', '--fiber-node-contact', '--ball-instance', 'Ball-1', '--preview',
           '--output', target]
env = dict(os.environ, PYTHONPATH=str(here) + os.pathsep + str(root))
started = time.monotonic()
with open(here / f'{Path(target).name}.log', 'w') as log:
    child = subprocess.Popen(command, cwd=here, env=env, stdout=log, stderr=subprocess.STDOUT)
    proc = psutil.Process(child.pid)
    peak = 0
    while child.poll() is None:
        try:
            family = [proc, *proc.children(recursive=True)]
            rss = sum(p.memory_info().rss for p in family if p.is_running())
            peak = max(peak, rss)
        except psutil.Error:
            pass
        time.sleep(.5)
    code = child.wait()
record = dict(command=command, exit_code=code, wall_seconds=time.monotonic()-started,
              peak_process_tree_rss_bytes=peak)
(here / f'{Path(target).name}_run.json').write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2))
sys.exit(code)
