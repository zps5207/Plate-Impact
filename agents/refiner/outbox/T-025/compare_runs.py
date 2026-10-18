"""Compare three written CLI reports and the v500 baseline fiber section."""
import json
import sys
from pathlib import Path
import numpy as np

curved,flat_stacked,flat_plain,baseline=map(Path,sys.argv[1:5])
reports=[json.loads((p/'report.json').read_text()) for p in (curved,flat_stacked,flat_plain)]

def deck_stats(path):
    nodes={};length=0.;segments=0;fiber_runs=0;in_fiber=False;section=''
    for line in path.read_text().splitlines():
        stripped=line.strip()
        if stripped.lower().startswith('*part, name=embfib'):
            in_fiber=True;continue
        if in_fiber and stripped.lower().startswith('*end part'):
            break
        if not in_fiber:continue
        if stripped.startswith('*'):
            section=stripped.split(',')[0].lower();continue
        if not stripped or stripped.startswith('**'):continue
        if section=='*node':
            a=stripped.split(',');nodes[int(a[0])]=np.array(list(map(float,a[1:4])))
        if section=='*element':
            a=[int(x) for x in stripped.split(',') if x.strip()]
            if len(a)==3:
                length+=float(np.linalg.norm(nodes[a[1]]-nodes[a[2]]));segments+=1
    return dict(nodes=len(nodes),fiber_runs=len(nodes)-segments,segments=segments,
                length_m=length,volume_m3=length*np.pi*.001**2/4)

curved_deck=deck_stats(curved/'output.inp')
stacked_deck=deck_stats(flat_stacked/'output.inp')
plain_deck=deck_stats(flat_plain/'output.inp')
baseline_deck=deck_stats(baseline)
same=(flat_stacked/'output.inp').read_bytes()==(flat_plain/'output.inp').read_bytes()
result=dict(curved_report=reports[0],flat_stacked_report=reports[1],flat_plain_report=reports[2],
            curved_deck=curved_deck,flat_stacked_deck=stacked_deck,flat_plain_deck=plain_deck,
            baseline_v500=baseline_deck,flat_output_identical=bool(same),
            curved_vs_flat_fiber_volume_rel_change=curved_deck['volume_m3']/stacked_deck['volume_m3']-1)
Path(sys.argv[5]).write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if not k.endswith('_report')},indent=2))
if not same:sys.exit(1)
