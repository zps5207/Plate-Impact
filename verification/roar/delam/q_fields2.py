from __future__ import print_function
import sys
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
st = list(odb.steps.values())[0]
print('frames', len(st.frames))
print('FIELDS', sorted(st.frames[-1].fieldOutputs.keys()))
odb.close()
