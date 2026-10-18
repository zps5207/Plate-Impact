"""0/90 fibers on congruent translated host faces, in assembly coordinates."""
from __future__ import annotations

import numpy as np
from collections import Counter
from .fibers import Fiber, _layer_positions, flat_disc_fibers, _parse_axis
from .layup import orthogonal_directions
from .geometry import hex_volume


def _resample_by_arclength(path, target_length):
    """Arc-length stations, refined for equal straight truss chord lengths.

    Exact equal arc intervals and exact equal chords conflict at a corner. The
    correction is tiny for the shallow surfaces supported here, and every
    resulting point stays on the original geometric path.
    """
    path = np.asarray(path, float)
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    keep = np.r_[True, lengths > 1e-12]
    path = path[keep]
    if len(path) < 2:
        return None, 0., 0.
    lengths = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cum = np.r_[0., np.cumsum(lengths)]
    total = float(cum[-1])
    n = max(1, round(total / target_length))
    stations = np.linspace(0., total, n + 1)
    def sample(stations):
        indices = np.clip(np.searchsorted(cum, stations, side='right') - 1, 0, len(lengths)-1)
        weights = ((stations-cum[indices])/lengths[indices])[:, None]
        return path[indices] + weights*(path[indices+1]-path[indices])
    points=sample(stations)
    for _ in range(12):
        chords=np.linalg.norm(np.diff(points,axis=0),axis=1)
        if (chords.max()-chords.min())/np.median(chords) <= 1e-10:
            break
        intervals=np.diff(stations)+(chords.mean()-chords)
        if np.any(intervals<=0):
            raise ValueError('stacked layup: equal-chord correction produced a nonpositive interval')
        stations=np.r_[0.,np.cumsum(intervals)]
        stations[-1]=total
        points=sample(stations)
    points[0], points[-1] = path[0], path[-1]
    arc_spread=float(np.ptp(np.diff(stations))/np.mean(np.diff(stations))) if n>1 else 0.
    return points, total, arc_spread


def _segment_statistics(fibers, target_length, short_runs):
    lengths = [np.linalg.norm(np.diff(f.points, axis=0), axis=1) for f in fibers]
    all_lengths = np.concatenate(lengths) if lengths else np.empty(0)
    spreads = [(float(v.max()-v.min()) / float(np.median(v))) if len(v) else 0. for v in lengths]
    return dict(target_segment_length_m=target_length,
                shortest_fiber_segment_m=float(all_lengths.min()) if len(all_lengths) else None,
                longest_fiber_segment_m=float(all_lengths.max()) if len(all_lengths) else None,
                segment_length_over_target_min=float(all_lengths.min()/target_length) if len(all_lengths) else None,
                segment_length_over_target_median=float(np.median(all_lengths)/target_length) if len(all_lengths) else None,
                segment_length_over_target_max=float(all_lengths.max()/target_length) if len(all_lengths) else None,
                per_fiber_segment_spread_max_relative=max(spreads, default=0.),
                short_fiber_run_count=short_runs)


def stacked_surface_fibers(elems, nodes, diameter, thickness_axis=None, gap=0.,
                           reference=(1, 0, 0), end_inset=0., return_meta=False):
    coords = np.asarray(list(nodes.values()), float)
    conns = np.asarray([e.connectivity[:8] for e in elems.values()], int)
    lookup = {label: i for i, label in enumerate(nodes)}
    hexes = coords[np.vectorize(lookup.__getitem__)(conns)]
    target_length=float(np.cbrt(np.median([hex_volume(h) for h in hexes])))
    delta = hexes[:, 4:, :].mean(1) - hexes[:, :4, :].mean(1)
    axis = _parse_axis(thickness_axis)
    if axis is None:
        # Paired local hex faces reveal the stack direction even when a rotated
        # plate's overall bounding box is thicker than its in-plane extents.
        direction=np.median(delta,axis=0)
        axis=np.eye(3)[int(np.argmax(np.abs(direction)))]
    t0, t1 = orthogonal_directions(reference, axis)
    sign = 1 if np.median(delta @ axis) > 0 else -1
    spans = np.abs(delta @ axis)
    local_step = np.median(spans)
    if local_step < 1e-12:
        raise ValueError('stacked layup: degenerate stack vector')
    # The same edge pairing must describe a translation for every element.
    step_vec = np.median(delta, axis=0)
    mismatch = np.linalg.norm(hexes[:, 4:, :] - hexes[:, :4, :] - step_vec, axis=2)
    edge_lengths = np.linalg.norm(np.roll(hexes[:, :4, :], -1, axis=1)-hexes[:, :4, :], axis=2)
    inplane_edge = float(np.median(edge_lengths))
    tolerance = max(1e-8, .11 * inplane_edge)
    # A legacy flat deck may have independent meshing on its two plane faces.
    # Its node pairs need not be congruent; preserve the established flat path
    # byte for byte when all thickness coordinates occupy discrete planes.
    w=coords @ axis
    planes=np.unique(np.round(w,7))
    regular_planes=(len(planes)>2 and len(planes)<=64 and
                    np.allclose(np.diff(planes),np.median(np.diff(planes)),rtol=0,atol=1e-6))
    if regular_planes and np.max(np.abs(w-np.round(w,7)))<1e-7:
        thickness=float(w.max()-w.min())
        meta=dict(stack_vector=(axis*thickness).tolist(),theta_max_deg=0.,max_neighbour_overlap_fraction=0.,
                  congruence_mismatch_max_m=float(mismatch.max()),congruence_mismatch_mean_m=float(mismatch.mean()),
                  congruence_mismatch_p95_m=float(np.percentile(mismatch,95)),congruence_tolerance_m=tolerance,
                  layer_count=len(_layer_positions(float(w.min()),float(w.max()),diameter,gap)))
        if not meta['layer_count']:
            raise ValueError(f'stacked layup: no layer fits; diameter={diameter:.6g}, thickness={thickness:.6g}, gap={gap:.6g} m')
        fibers=flat_disc_fibers(elems,nodes,diameter,thickness_axis,gap,reference,end_inset)
        meta.update(_segment_statistics(fibers,target_length,sum(np.linalg.norm(np.diff(f.points,axis=0),axis=1).sum()<target_length/2 for f in fibers)))
        return (fibers,meta) if return_meta else fibers
    if float(mismatch.max()) > tolerance:
        raise ValueError(f'stacked layup: face translation mismatch {mismatch.max():.6g} exceeds {tolerance:.6g} m')
    # Pick one face from each reference-surface hex. The whole deck may have
    # many layers; paired faces at the minimum signed coordinate define bottom.
    face0 = hexes[:, :4, :] if sign > 0 else hexes[:, 4:, :]
    face1 = hexes[:, 4:, :] if sign > 0 else hexes[:, :4, :]
    face0_ids=conns[:,:4] if sign>0 else conns[:,4:]
    face1_ids=conns[:,4:] if sign>0 else conns[:,:4]
    upper_faces={frozenset(row) for row in face1_ids}
    on_bottom=np.asarray([frozenset(row) not in upper_faces for row in face0_ids])
    surf = face0[on_bottom]
    if not len(surf):
        raise ValueError('stacked layup: no reference face')
    # Face heights may vary due to sag. Layer thickness is found by matching
    # paired projected vertices: this avoids treating surface sag as thickness.
    thickness = float(np.ptp(coords @ axis) - np.ptp(surf @ axis))
    n_layers = len(_layer_positions(0., thickness, diameter, gap))
    if not n_layers:
        raise ValueError(f'stacked layup: no layer fits; diameter={diameter:.6g}, thickness={thickness:.6g}, gap={gap:.6g} m')
    projected = np.stack((surf @ t0, surf @ t1, surf @ axis), axis=2)
    edge_counts=Counter()
    edge_positions={}
    ref_ids=face0_ids[on_bottom]
    for ids,quad in zip(ref_ids,projected):
        for j in range(4):
            key=tuple(sorted((int(ids[j]),int(ids[(j+1)%4]))))
            edge_counts[key]+=1
            edge_positions[key]=(quad[j,:2],quad[(j+1)%4,:2])
    outline=np.asarray([edge_positions[key] for key,count in edge_counts.items() if count==1])
    edge_a=outline[:,0,:];edge_v=outline[:,1,:]-edge_a
    edge_v2=np.sum(edge_v*edge_v,axis=1)
    def clearance(u,s,along):
        p=np.array([u,s]) if along==0 else np.array([s,u])
        t=np.clip(np.sum((p-edge_a)*edge_v,axis=1)/edge_v2,0,1)
        return float(np.sqrt(np.sum((p-edge_a-t[:,None]*edge_v)**2,axis=1)).min())
    def inset_bounds(lo,hi,s,along,radius):
        if hi-lo<=2*radius:return None
        middle=.5*(lo+hi);step=max(radius/8,1e-7)
        left=lo
        while left<middle and clearance(left,s,along)<radius-1e-10:
            left=min(middle,left+step)
        if clearance(left,s,along)<radius-1e-10:return None
        a=max(lo,left-step);b=left
        for _ in range(22):
            m=.5*(a+b)
            if clearance(m,s,along)>=radius:b=m
            else:a=m
        left=b
        right=hi
        while right>middle and clearance(right,s,along)<radius-1e-10:
            right=max(middle,right-step)
        if clearance(right,s,along)<radius-1e-10:return None
        a=right;b=min(hi,right+step)
        for _ in range(22):
            m=.5*(a+b)
            if clearance(m,s,along)>=radius:a=m
            else:b=m
        return (left,a) if a>left else None
    # Bilinear gradients at quad corners and center give a conservative slope
    # estimate for this faceted host surface.
    slope_max = 0.
    for u, v in ((0,0),(1,0),(1,1),(0,1),(.5,.5)):
        du=(1-v)*(projected[:,1]-projected[:,0])+v*(projected[:,2]-projected[:,3])
        dv=(1-u)*(projected[:,3]-projected[:,0])+u*(projected[:,2]-projected[:,1])
        matrix=np.stack((du[:,:2],dv[:,:2]),axis=2)
        gradient=np.linalg.solve(matrix.transpose(0,2,1),np.stack((du[:,2],dv[:,2]),axis=1)[...,None])[...,0]
        slope_max=max(slope_max,float(np.linalg.norm(gradient,axis=1).max()))
    theta=float(np.arctan(slope_max))
    meta=dict(stack_vector=(axis*thickness).tolist(), theta_max_deg=float(np.degrees(theta)),
              max_neighbour_overlap_fraction=float(1-np.cos(theta)),
              congruence_mismatch_max_m=float(mismatch.max()),
              congruence_mismatch_mean_m=float(mismatch.mean()),
              congruence_mismatch_p95_m=float(np.percentile(mismatch,95)),
              congruence_tolerance_m=tolerance, layer_count=n_layers)
    if slope_max < 1e-9:
        fibers=flat_disc_fibers(elems,nodes,diameter,thickness_axis,gap,reference,end_inset)
        meta.update(_segment_statistics(fibers,target_length,sum(np.linalg.norm(np.diff(f.points,axis=0),axis=1).sum()<target_length/2 for f in fibers)))
        return (fibers,meta) if return_meta else fibers
    fibers=[]; label=1
    boundary_eps=max(float(np.linalg.norm(coords.max(0)-coords.min(0))),diameter)*1e-6
    # Each scanline is intersected with all projected quads in a vectorized
    # pass. An interval stores both edge crossings and their interpolated height.
    for layer,t in enumerate(_layer_positions(0.,thickness,diameter,gap)):
        along,across=(0,1) if layer%2==0 else (1,0)
        q=projected if along==0 else projected[:,:,[1,0,2]]
        lo,hi=float(q[:,:,1].min()),float(q[:,:,1].max())
        for s in _layer_positions(lo,hi,diameter,gap):
            a=q; b=np.roll(q,-1,axis=1)
            cross=((a[:,:,1]<=s)&(s<b[:,:,1]))|((b[:,:,1]<=s)&(s<a[:,:,1]))
            valid=np.where(cross.sum(axis=1)==2)[0]
            if len(valid)==0:continue
            frac=np.divide(s-a[:,:,1],b[:,:,1]-a[:,:,1],out=np.zeros_like(a[:,:,1]),where=np.abs(b[:,:,1]-a[:,:,1])>1e-14)
            uu=a[:,:,0]+frac*(b[:,:,0]-a[:,:,0]); zz=a[:,:,2]+frac*(b[:,:,2]-a[:,:,2])
            intervals=[]
            for ix in valid:
                u=uu[ix,cross[ix]]; z=zz[ix,cross[ix]]; order=np.argsort(u)
                if u[order[1]]-u[order[0]]>1e-12:
                    intervals.append((float(u[order[0]]),float(u[order[1]]),float(z[order[0]]),float(z[order[1]]),int(ix)))
            intervals.sort()
            groups=[]; group=[]; right=-np.inf
            for item in intervals:
                if group and item[0]>right+2e-8:
                    groups.append(group);group=[]
                group.append(item);right=max(right,item[1])
            if group:groups.append(group)
            for group in groups:
                bounds=inset_bounds(group[0][0],max(row[1] for row in group),s,along,diameter/2+end_inset)
                if bounds is None:continue
                left,right=bounds[0]+boundary_eps,bounds[1]-boundary_eps
                if right<=left:continue
                vertices=[]
                for u0,u1,z0,z1,eid in group:
                    v0=max(left,u0);v1=min(right,u1)
                    if v1-v0<=1e-11:continue
                    def point(u):
                        h=z0+(z1-z0)*(u-u0)/(u1-u0)+t
                        return (t0*u+t1*s+axis*h) if along==0 else (t1*u+t0*s+axis*h)
                    p0,p1=point(v0),point(v1)
                    if vertices and np.linalg.norm(p0-vertices[-1])>2e-7:
                        if len(vertices)>1:
                            points,total,arc_spread=_resample_by_arclength(vertices,target_length)
                            if points is not None:
                                fibers.append(Fiber(label,points,layer,'t0' if layer%2==0 else 't90',{'geometric_path_length_m':total,'arc_interval_spread_relative':arc_spread}));label+=1
                        vertices=[]
                    if not vertices:vertices.append(p0)
                    vertices.append(p1)
                if len(vertices)>1:
                    points,total,arc_spread=_resample_by_arclength(vertices,target_length)
                    if points is not None:
                        fibers.append(Fiber(label,points,layer,'t0' if layer%2==0 else 't90',{'geometric_path_length_m':total,'arc_interval_spread_relative':arc_spread}));label+=1
    short_runs=sum(f.curvature_data['geometric_path_length_m']<target_length/2 for f in fibers)
    meta.update(_segment_statistics(fibers,target_length,short_runs))
    meta['arc_interval_spread_max_relative']=max((f.curvature_data['arc_interval_spread_relative'] for f in fibers),default=0.)
    return (fibers,meta) if return_meta else fibers
