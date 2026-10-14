from __future__ import print_function
import sys
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
step = list(odb.steps.values())[0]
print("frames", len(step.frames))
f = step.frames[-1]
print("last_frame_time", f.frameValue)
for k, v in sorted(f.fieldOutputs.items()):
    print("FIELD", k, [c for c in v.componentLabels], v.locations[0].position)
print("ELSETS", sorted(odb.rootAssembly.elementSets.keys()))
odb.close()
