"""Abaqus Python: targeted read-only ball extraction from one bt1/bt2 ODB.

Usage: abaqus python extract_inversion_odb.py /scratch/.../b4_d4fix.odb b4_inversion.npz
Run on ROAR only if authorized by the Hub. Never submit from this worker.
Saves every existing frame through 6 us and every tenth later frame. Missing field
arrays remain NaN; available field names are saved for audit. Does not create ODB
fields that were not requested in the original analysis deck.
"""
from __future__ import print_function
import sys
import numpy as np
from odbAccess import openOdb

odb = openOdb(sys.argv[1], readOnly=True)
step = list(odb.steps.values())[0]
ball = odb.rootAssembly.instances['BALL-1']
nodes = list(ball.nodes)
elems = list(ball.elements)
nl = np.array([n.label for n in nodes], dtype=np.int32)
el = np.array([e.label for e in elems], dtype=np.int32)
nc = np.array([n.coordinates for n in nodes], dtype=np.float64)
em = dict((int(v),i) for i,v in enumerate(el))
nm = dict((int(v),i) for i,v in enumerate(nl))
conn = np.full((len(el),8),-1,dtype=np.int32)
etype = []
for i,e in enumerate(elems):
    etype.append(e.type)
    for j,v in enumerate(e.connectivity):
        conn[i,j] = nm[int(v)]

scalar_names = ('STATUS','PEEQ','PEEQR','JCCRT','DUCTCRT','SDEG','EVF','TEMP','TRIAX')
arrays = dict((k,[]) for k in scalar_names)
arrays['MISES'] = []
arrays['CPRESS_ball'] = []
arrays['V_ball'] = []
times=[]
frame_ids=[]
keys=set()

def matching(frame,prefix):
    """Preserve first matching contact field key; all names are recorded below."""
    for k in frame.fieldOutputs.keys():
        if k.split()[0] == prefix:
            return frame.fieldOutputs[k]
    return None

for fi,frame in enumerate(step.frames):
    if frame.frameValue > 6e-6 and fi%10 != 0 and fi != len(step.frames)-1:
        continue
    frame_ids.append(fi)
    times.append(frame.frameValue)
    keys.update(frame.fieldOutputs.keys())
    for name in scalar_names+('MISES',):
        a=np.full(len(el),np.nan,dtype=np.float32)
        fo=matching(frame,'S' if name=='MISES' else name)
        if fo is not None:
            try:
                sub=fo.getSubset(region=ball)
                for b in sub.bulkDataBlocks:
                    labs=b.elementLabels
                    vals=b.mises if name=='MISES' else b.data
                    for lab,val in zip(labs,vals):
                        idx=em.get(int(lab))
                        if idx is None: continue
                        try: val=float(val[0])
                        except (TypeError,IndexError): val=float(val)
                        if np.isnan(a[idx]) or val>a[idx]: a[idx]=val
            except Exception as exc:
                print('field error',name,fi,exc,flush=True)
        arrays[name].append(a)
    cp=np.full(len(nl),np.nan,dtype=np.float32)
    fo=matching(frame,'CPRESS')
    if fo is not None:
        try:
            for b in fo.getSubset(region=ball).bulkDataBlocks:
                for lab,val in zip(b.nodeLabels,b.data):
                    idx=nm.get(int(lab))
                    if idx is not None:
                        cp[idx]=max(float(np.ravel(val)[0]),cp[idx]) if np.isfinite(cp[idx]) else float(np.ravel(val)[0])
        except Exception as exc:
            print('CPRESS error',fi,exc,flush=True)
    arrays['CPRESS_ball'].append(cp)
    vel=np.full((len(nl),3),np.nan,dtype=np.float32)
    fo=matching(frame,'V')
    if fo is not None:
        try:
            for b in fo.getSubset(region=ball).bulkDataBlocks:
                for lab,val in zip(b.nodeLabels,b.data):
                    idx=nm.get(int(lab))
                    if idx is not None: vel[idx]=val
        except Exception as exc:
            print('V error',fi,exc,flush=True)
    arrays['V_ball'].append(vel)
    print('frame',fi,'t_us',frame.frameValue*1e6,flush=True)

out=dict((k,np.array(v)) for k,v in arrays.items())
out.update(times=np.array(times),frame_idx=np.array(frame_ids),
           ball_elem_labels=el,ball_elem_types=np.array(etype),
           ball_conn=conn,ball_node_labels=nl,ball_coords0=nc,
           available_field_keys=np.array(sorted(keys)))
np.savez_compressed(sys.argv[2],**out)
odb.close()
print('saved',sys.argv[2])
