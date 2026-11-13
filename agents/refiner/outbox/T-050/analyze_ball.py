"""Analyze vp5/vp6 ball ODB extracts locally; no Abaqus or ROAR required.

Run from the project root: python agents/refiner/outbox/T-050/analyze_ball.py
"""
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "Meshing/vals-plywise-ballkeep/results"
RHO = 7850.0
V0 = 1000.0
EDGES = np.array([(0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)])
WEDGE_EDGES = np.array([(0,1),(1,2),(2,0),(3,4),(4,5),(5,3),(0,3),(1,4),(2,5)])


def volumes(x, wedge):
    # Eight times the determinant of the C3D8 centre Jacobian.
    a = (-x[:,0]+x[:,1]+x[:,2]-x[:,3]-x[:,4]+x[:,5]+x[:,6]-x[:,7])/8
    b = (-x[:,0]-x[:,1]+x[:,2]+x[:,3]-x[:,4]-x[:,5]+x[:,6]+x[:,7])/8
    c = (-x[:,0]-x[:,1]-x[:,2]-x[:,3]+x[:,4]+x[:,5]+x[:,6]+x[:,7])/8
    v = 8*np.einsum('ij,ij->i', a, np.cross(b,c))
    # C3D6 wedge: split into three tetrahedra.
    if wedge.any():
        q=x[wedge]
        def tet(i,j,k,l):
            return np.einsum('ij,ij->i',q[:,j]-q[:,i],np.cross(q[:,k]-q[:,i],q[:,l]-q[:,i]))/6
        v[wedge]=tet(0,1,2,3)+tet(1,2,4,3)+tet(2,4,5,3)
    return v


def main(name):
    z = np.load(DATA / ("ball_"+name+".npz"))
    nmap = {int(k): i for i,k in enumerate(z['ball_node_labels'])}
    wedge=(z['ball_elem_conn'][:,6]<0)
    conn = np.array([[nmap[int(n)] if n>0 else 0 for n in row] for row in z['ball_elem_conn']])
    x0 = z['ball_node_coords0'][conn]
    v0 = volumes(x0,wedge)
    edge = np.linalg.norm(x0[:,EDGES[:,0]]-x0[:,EDGES[:,1]], axis=2)
    edge[wedge]=np.nan
    q=x0[wedge]
    wedge_edge=np.linalg.norm(q[:,WEDGE_EDGES[:,0]]-q[:,WEDGE_EDGES[:,1]],axis=2)
    status = z['STATUS']
    U=z['U']; mises=z['MISES']; peeq=z['PEEQ']; top=z['top_cpress']; topinst=z['top_inst']
    times = z['times']*1e6
    labs = z['ball_elem_labels']
    cent = x0.mean(axis=1)
    print('\n',name, 'frames',len(times),'ODB frames',z['nframes_in_odb'])
    print('coordinate range mm',z['ball_node_coords0'].min(axis=0)*1e3,z['ball_node_coords0'].max(axis=0)*1e3)
    all_edge=np.concatenate([edge[~wedge].ravel(),wedge_edge.ravel()])
    print('edge quantiles mm',np.quantile(all_edge,[0,.01,.1,.5,.9,.99,1])*1e3)
    print('volume quantiles mm3',np.quantile(abs(v0),[0,.01,.5,.99,1])*1e9,'total mm3',sum(abs(v0))*1e9)
    print('initial KE J',sum(abs(v0))*RHO*V0**2/2)
    prev = np.zeros(len(labs),bool)
    for i,t in enumerate(times):
        dead = status[i] < .5
        new = dead & ~prev
        if new.any():
            ids = np.where(new)[0]
            print('DELETION t_us %.5f new %d total %d first labels %s'%(t,len(ids),dead.sum(),labs[ids[:20]].tolist()))
            if not prev.any():
                for j in ids[:30]:
                    print(' FIRST label %d xyz_mm %s edge_mm %.4f volume_mm3 %.6g initKE_mJ %.5f'%(labs[j],np.round(cent[j]*1e3,4),np.median(edge[j])*1e3,abs(v0[j])*1e9,abs(v0[j])*RHO*V0**2/2*1e3))
                print(' first batch initial KE mJ',abs(v0[ids]).sum()*RHO*V0**2/2*1e3)
        prev = dead
    ever = status[-1]<.5
    print('all deleted initial KE J',abs(v0[ever]).sum()*RHO*V0**2/2)
    loaded=z['loaded_nodes_ball_host_fiber']
    for i,t in enumerate(times):
        x=(z['ball_node_coords0']+U[i])[conn]
        ratio=np.abs(volumes(x,wedge)/v0)
        mn=np.nanmin(ratio); mx=np.nanmax(ratio)
        if i==0 or (i>0 and (mn<.1 or mx>10)) or i>=len(times)-3:
            small=np.argsort(ratio)[:5]
            print('DIST t_us %.5f min %.4g max %.4g min_labels %s loaded %s cpmaxGPa %.4g topInst %s'%(t,mn,mx,labs[small].tolist(),loaded[i].tolist(),top[i,0]/1e9,topinst[i,0]))
            if i>0 and (mn<.1 or mx>10): break
    for label in [475,479,502,509]:
        j=np.where(labs==label)[0][0]
        r=[]
        for i,t in enumerate(times):
            x=(z['ball_node_coords0']+U[i])[conn[j:j+1]]
            r.append(abs(volumes(x,np.array([wedge[j]]))[0]/v0[j]))
        edges=WEDGE_EDGES if wedge[j] else EDGES
        aspects=[]
        for i in range(len(times)):
            q=(z['ball_node_coords0']+U[i])[conn[j]]
            le=np.linalg.norm(q[edges[:,0]]-q[edges[:,1]],axis=1)
            aspects.append(np.nanmax(le)/np.nanmin(le))
        print('ERR label',label,'xyz_mm',np.round(cent[j]*1e3,4),'minvolratio',np.nanmin(r),'last ratios',np.round(r[-7:],4),'aspects init/lastfinite',aspects[0],aspects[-2],'first aspect>10 us',next((times[i] for i,a in enumerate(aspects) if a>10),None),'last mises_GPa',mises[-1,j]/1e9,'last PEEQ',peeq[-1,j],'initKE_J',abs(v0[j])*RHO*V0**2/2)
        if name=='vp6':
            print(' ERR HISTORY label',label,[(round(times[i],2),round(float(mises[i,j]/1e9),3),round(float(peeq[i,j]),3),round(float(aspects[i]),2),round(float(np.nanmax(z['CPRESS_ball'][i,conn[j,:6 if wedge[j] else 8]])/1e9),3)) for i in [0,2,8,16,32,64,len(times)-2,len(times)-1]])
    deadfirst=np.where(status[np.where((status<.5).any(axis=1))[0][0]]<.5)[0] if (status<.5).any() else []
    if len(deadfirst):
        j=deadfirst[0]
        print('sample first-dead history label',labs[j])
        for i in range(min(5,len(times))):
            print(' HIST',round(times[i],4),status[i,j],mises[i,j]/1e9,peeq[i,j],loaded[i].tolist(),top[i,0]/1e9,topinst[i,0])
        print('first batch PEQQ previous/max',np.nanmax(peeq[0,deadfirst]),np.nanmax(peeq[1,deadfirst]),'misesGPa previous/max',np.nanmax(mises[1,deadfirst])/1e9)
    for i in ([1,2,3,4,len(times)-2,len(times)-1] if name=='vp5' else [1,2,3,4,len(times)-3,len(times)-2,len(times)-1]):
        print('CONTACT %.5f us loaded %s max %.4g GPa top %s node %d xyz_mm %s ballCpMax %.4g GPa'%(times[i],loaded[i].tolist(),top[i,0]/1e9,topinst[i,0],z['top_label'][i,0],np.round(z['top_xyz0'][i,0]*1e3,3),np.nanmax(z['CPRESS_ball'][i])/1e9))


if __name__=='__main__':
    main('vp5')
    main('vp6')
