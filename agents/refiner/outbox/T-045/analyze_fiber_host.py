"""Analyze vp4 viewer exports. Run: python analyze_fiber_host.py [project-root].

Writes per-frame CSVs and JSON beside this script. Coordinates are SI metres.
Viewer exports contain host STATUS, but no fiber STATUS or exact nodal velocity.
"""
import csv
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[3]
RESULTS = ROOT / 'Meshing/vals-plywise-del/results'
AREA = 3.137e-7
RHO_F = 981.0
RHO_H = 980.0


def hexa_volumes(x, conn):
    # Three edge vectors at local corner 1; the regular C3D8R host is a
    # structured brick mesh. This is exact for parallelepipeds.
    p = x[conn]
    return np.abs(np.einsum('ij,ij->i', p[:, 1]-p[:, 0],
                            np.cross(p[:, 3]-p[:, 0], p[:, 4]-p[:, 0])))


def read_energy(path):
    a = np.genfromtxt(path, delimiter=',', names=True)
    return a['time'], a['ALLKE'] / 1000.0  # CSV values are mJ


def vuel_mass(deck):
    """Read Plate VU1 geometry and per-instance SVAR107, weighted by volume."""
    values={}; nodes={}; elements={}; active=False; section=None; in_plate=False
    with deck.open() as f:
        for line in f:
            if line.startswith('*Part, name=Plate'):
                in_plate=True
            elif line.startswith('*End Part'):
                in_plate=False
            if line.startswith('*Node') and in_plate:
                section='node'; continue
            if line.startswith('*Element, type=VU1') and in_plate:
                section='vuel'; continue
            if line.startswith('*Initial Conditions, type=SOLUTION'):
                active=True; section=None; continue
            if line.startswith('*'):
                active=False; section=None
            if section=='node' and line[0].isdigit():
                fields=line.strip().split(',')
                nodes[int(fields[0])]=np.array([float(x) for x in fields[1:4]])
            if section=='vuel' and line[0].isdigit():
                fields=line.strip().split(',')
                elements[int(fields[0])]=[int(x) for x in fields[1:9]]
            if active and line.startswith('Ply-'):
                label=line.split(',')[0]
                instance,element=label.split('.')
                fields=line.strip().split(',')[1:]
                for _ in range(19):
                    fields.extend(next(f).strip().split(','))
                values[(instance,int(element))]=float(fields[106])
    volume={label:float(hexa_volumes(np.array([nodes[n] for n in conn]),
                                     np.arange(8).reshape(1,8))[0])
            for label,conn in elements.items()}
    weighted=sum(volume[label]*(1-vf) for (instance,label),vf in values.items())
    geometric=sum(volume[label] for instance,label in values)
    return RHO_H*weighted, np.mean(list(values.values())), RHO_H*geometric, len(values)


def run(case):
    path = RESULTS / case / f'vals_{case}_viewer.npz'
    d = np.load(path)
    t = d['times']; fc = d['fiber_conn_T3D2']; f0 = d['fiber_coords0']
    hc = d['host_conn_C3D8R']; h0 = d['host_coords0']; status = d['host_status']
    fp = d['fiber_pos']; hp = d['host_pos']
    length0 = np.linalg.norm(f0[fc[:, 1]]-f0[fc[:, 0]], axis=1)
    seg_mass = RHO_F * AREA * length0
    fib_mass_node = np.bincount(fc.ravel(), weights=np.repeat(seg_mass/2, 2), minlength=len(f0))
    hv = hexa_volumes(h0, hc)
    hmass_node = np.bincount(hc.ravel(), weights=np.repeat(RHO_H*hv/8, 8), minlength=len(h0))
    size = np.cbrt(hv)
    # The z-coordinate tracks ply. Alternating in-plane orientation is inferred
    # from the reference segment vector; it does not require instance labels.
    mid0 = (f0[fc[:, 0]]+f0[fc[:, 1]])/2
    ply = np.clip(np.floor((mid0[:, 2]+.0254)/.00127).astype(int)+1, 1, 20)
    direction = np.where(np.abs(f0[fc[:,1],0]-f0[fc[:,0],0]) >=
                         np.abs(f0[fc[:,1],1]-f0[fc[:,0],1]), 'x', 'y')
    et, eke = read_energy(RESULTS / case / f'energy_{case}.csv')
    rows = []; deaths = []; by_ply = []; prev_f = None; prev_h = None
    prev_fspeed = None
    summary = {'case':case, 'frames':len(t), 'host_elements':len(hc),
               'fiber_segments':len(fc), 'fiber_mass_kg':float(seg_mass.sum()),
               'host_geometric_mass_kg':float((RHO_H*hv).sum()),
               'host_element_size_mm_p50':float(np.median(size)*1e3),
               'energy_peak_J':float(np.max(eke))}
    if case == 'vuel':
        mass,mean_vf,deck_geom,count=vuel_mass(ROOT/'Meshing/vals-plywise-del/vuel/output.inp')
        if count != len(hc):
            raise ValueError(f'expected {len(hc)} SVAR107 values, got {count}')
        summary['host_mean_Vf']=float(mean_vf)
        summary['host_effective_mass_kg']=mass
        summary['host_deck_geometric_mass_kg']=deck_geom
    else:
        summary['host_effective_mass_kg']=summary['host_geometric_mass_kg']
    summary['host_volume_range_m3']=[float(hv.min()),float(hv.max())]
    summary['total_host_plus_fiber_mass_kg']=summary['host_effective_mass_kg']+summary['fiber_mass_kg']
    for i, ti in enumerate(t):
        f = fp[i].astype(np.float64); h = hp[i].astype(np.float64)
        stretch = np.linalg.norm(f[fc[:, 1]]-f[fc[:, 0]],axis=1)/length0
        disp = np.linalg.norm(f-f0,axis=1)
        if i:
            dt = ti-t[i-1]
            fspeed = np.linalg.norm((f-prev_f)/dt,axis=1)
            hspeed = np.linalg.norm((h-prev_h)/dt,axis=1)
            fke = .5*np.dot(fib_mass_node,fspeed**2)
            hke = .5*np.dot(hmass_node,hspeed**2)
        else:
            fspeed = np.zeros(len(f)); hspeed = np.zeros(len(h)); fke=hke=0.
        q = np.percentile(stretch,[50,90,99,99.9,100])
        row = {'frame':i,'time_us':ti*1e6,'stretch_p50':q[0],
               'stretch_p90':q[1],'stretch_p99':q[2],
               'stretch_p999':q[3],'stretch_max':q[4],
               'frac_stretch_gt_1p04':np.mean(stretch>1.04),
               'frac_stretch_gt_1p10':np.mean(stretch>1.1),
               'frac_stretch_gt_2':np.mean(stretch>2),
               'fiber_disp_gt_1mm':int(np.count_nonzero(disp>.001)),
               'fiber_disp_gt_10mm':int(np.count_nonzero(disp>.01)),
               'fiber_max_disp_mm':float(disp.max()*1000),
               'fiber_speed_gt_1000ms':int(np.count_nonzero(fspeed>1000)),
               'fiber_speed_gt_10000ms':int(np.count_nonzero(fspeed>10000)),
               'fiber_max_speed_ms':float(fspeed.max()),
               'host_max_speed_ms':float(hspeed.max()),
               'fiber_KE_J_fd':float(fke),'host_KE_J_fd_geom':float(hke),
               'ALLKE_J':float(np.interp(ti,et,eke)),
               'host_dead':int(np.count_nonzero(status[i]==0))}
        rows.append(row)
        for p in range(1,21):
            for axis in ('x','y'):
                mask=(ply==p)&(direction==axis)
                if not mask.any(): continue
                segment_nodes=np.unique(fc[mask].ravel())
                by_ply.append({'frame':i,'time_us':ti*1e6,'ply':p,'direction':axis,
                    'segment_count':int(mask.sum()),
                    'stretch_gt_1p04':int(np.count_nonzero(stretch[mask]>1.04)),
                    'stretch_gt_1p10':int(np.count_nonzero(stretch[mask]>1.1)),
                    'stretch_gt_2':int(np.count_nonzero(stretch[mask]>2)),
                    'max_stretch':float(stretch[mask].max()),
                    'nodes_disp_gt_10mm':int(np.count_nonzero(disp[segment_nodes]>.01)),
                    'nodes_speed_gt_1000ms':int(np.count_nonzero(fspeed[segment_nodes]>1000))})
        if i:
            dying = np.flatnonzero((status[i-1]>0)&(status[i]==0))
            if len(dying):
                # Snapshot immediately before first observed deletion. Query
                # current and previous positions to bound sampling ambiguity.
                ctr = prev_h[hc[dying]].mean(axis=1)
                pre_stretch = np.linalg.norm(prev_f[fc[:,1]]-prev_f[fc[:,0]],axis=1)/length0
                fast = prev_fspeed>1000 if prev_fspeed is not None else np.zeros(len(f0),dtype=bool)
                hot_nodes = np.zeros(len(f0),dtype=bool)
                hot_nodes[fc[pre_stretch>1.1].ravel()] = True
                hot_nodes |= fast
                near_all = cKDTree(prev_f).query(ctr)[0]
                near_hot = (cKDTree(prev_f[hot_nodes]).query(ctr)[0] if hot_nodes.any()
                            else np.full(len(dying),np.inf))
                for el, da, dh, sz, xyz in zip(dying,near_all,near_hot,size[dying],ctr):
                    deaths.append({'frame':i,'time_us':ti*1e6,'host_element':int(el),
                        'center_x_mm':xyz[0]*1000,'center_y_mm':xyz[1]*1000,
                        'center_z_mm':xyz[2]*1000,'size_mm':sz*1000,
                        'nearest_fiber_mm':da*1000,'nearest_hot_mm':dh*1000,
                        'any_within_1_size':int(da<=sz),
                        'hot_within_1_size':int(dh<=sz)})
        prev_f=f; prev_h=h; prev_fspeed=fspeed
    for filename, data in [(f'{case}_frames.csv',rows),(f'{case}_deaths.csv',deaths),
                           (f'{case}_ply_direction.csv',by_ply)]:
        with (HERE/filename).open('w',newline='') as out:
            w=csv.DictWriter(out,fieldnames=list(data[0]) if data else ['frame'])
            w.writeheader(); w.writerows(data)
    summary['deleted_elements']=len(deaths)
    summary['deletion_first_frame']=min((x['frame'] for x in deaths),default=None)
    summary['fraction_deletions_any_within_size']=float(np.mean([x['any_within_1_size'] for x in deaths])) if deaths else None
    summary['fraction_deletions_hot_within_size']=float(np.mean([x['hot_within_1_size'] for x in deaths])) if deaths else None
    summary['peak_fiber_KE_J_fd']=max(x['fiber_KE_J_fd'] for x in rows)
    summary['peak_host_KE_J_fd_geom']=max(x['host_KE_J_fd_geom'] for x in rows)
    summary['peak_stretch']=max(x['stretch_max'] for x in rows)
    summary['peak_fraction_gt_1p1']=max(x['frac_stretch_gt_1p10'] for x in rows)
    summary['first_stretch_gt_1p065_frame']=next((x['frame'] for x in rows if x['stretch_max']>1.065),None)
    summary['fiber_mass_by_ply_direction_g']={f'{p}_{axis}':float(seg_mass[(ply==p)&(direction==axis)].sum()*1000)
        for p in range(1,21) for axis in ('x','y')}
    (HERE/f'{case}_summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    for name in ('vuel','native'):
        run(name)
