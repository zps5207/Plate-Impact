r"""T-057 follow-up coupon (Hub): interior-face exposure with embedded fibers.

Answers two questions about the own-ply VUINTERACTION (baseline law):
  Q1  Is STATE stored per slave node or per (slave node, master facet) pair?
  Q2  What force does a newly exposed INTERIOR face put on an embedded fiber
      node sitting 0.2 mm behind it, and does it launch nodes?

Host: 5 x 3 x 3 C3D8R block, h = 0.5 mm (x 0..2.5, y 0..1.5, z 0..1.5 mm).
Two top-layer elements are sacrificial (low ductile strain, deleted early):
  S1 = (ix=1, iy=1, iz=2)  x 0.5-1.0, y 0.5-1.0  (interior column)
  S2 = (ix=3, iy=0, iz=2)  x 1.5-2.0, y 0.0-0.5  (on the y=0 exterior face,
                                                  like node 720 in nv3_fh)
Fibers (2-node T3D2, embedded in the whole host, both at z = 0.8 mm, i.e.
0.2 mm BELOW the face z = 1.0 that the deletion exposes):
  F1 under S1: nodes (0.6,0.75,0.8), (0.9,0.75,0.8). Nearest exterior face
      0.6 mm away -> outside TRACKING THICKNESS 0.5 mm -> never seen before
      exposure. First contact = the exposed face.
  F2 under S2: nodes (1.6,0.25,0.8), (1.9,0.25,0.8). y=0 exterior face only
      0.25 mm away -> seen from t=0 with an open gap (pen ~ -0.25 mm, d0=0).
Expected when the z=1.0 faces get exposed (pen ~ +0.2 mm):
  per-pair state : new pair arrives with st2in=0 for F1 AND F2 -> latch, no force
  per-node state : F1 latches (first ever), F2 arrives with st2in=1, d0=0
                   -> press = 2e11*2e-4 = 4e7 Pa on F2 only.
Load: top face z=1.5 pushed down at 3 m/s (smooth step 0.5 us), bottom fixed.
cx057b: same, fibers NOT embedded, fiber nodes fixed by *Boundary.
"""
from pathlib import Path

MM = 1.0e-3
H = 0.5 * MM
NX, NY, NZ = 5, 3, 3


def nid(i, j, k):
    return 1 + i + (NX + 1) * j + (NX + 1) * (NY + 1) * k


def eid(i, j, k):
    return 1 + i + NX * j + NX * NY * k


SAC = {eid(1, 1, 2), eid(3, 0, 2)}


def build(embed=True):
    L = ["*Heading",
         "** T-057 Hub coupon: interior-face exposure with embedded fibers",
         "** SI units: m, kg, s, Pa, N, J",
         "*Part, name=Host", "*Node"]
    for k in range(NZ + 1):
        for j in range(NY + 1):
            for i in range(NX + 1):
                L.append(f" {nid(i,j,k)}, {i*H:.6e}, {j*H:.6e}, {k*H:.6e}")
    keep, sac = [], []
    for k in range(NZ):
        for j in range(NY):
            for i in range(NX):
                e = eid(i, j, k)
                c = [nid(i, j, k), nid(i+1, j, k), nid(i+1, j+1, k), nid(i, j+1, k),
                     nid(i, j, k+1), nid(i+1, j, k+1), nid(i+1, j+1, k+1), nid(i, j+1, k+1)]
                (sac if e in SAC else keep).append(f" {e}, " + ", ".join(map(str, c)))
    L += ["*Element, type=C3D8R, elset=HOST_KEEP"] + keep
    L += ["*Element, type=C3D8R, elset=HOST_SAC"] + sac
    L += ["*Elset, elset=HOST_ALL", " HOST_KEEP, HOST_SAC",
          "*Solid Section, elset=HOST_KEEP, material=HostKeep", ",",
          "*Solid Section, elset=HOST_SAC, material=HostSac", ","]
    bot = [nid(i, j, 0) for j in range(NY + 1) for i in range(NX + 1)]
    top = [nid(i, j, NZ) for j in range(NY + 1) for i in range(NX + 1)]
    L += ["*Nset, nset=BOTTOM"] + _rows(bot) + ["*Nset, nset=TOP"] + _rows(top)
    L += ["*End Part",
          "*Part, name=Fiber", "*Node",
          f" 1, {0.6*MM:.6e}, {0.75*MM:.6e}, {0.8*MM:.6e}",
          f" 2, {0.9*MM:.6e}, {0.75*MM:.6e}, {0.8*MM:.6e}",
          f" 3, {1.6*MM:.6e}, {0.25*MM:.6e}, {0.8*MM:.6e}",
          f" 4, {1.9*MM:.6e}, {0.25*MM:.6e}, {0.8*MM:.6e}",
          "*Element, type=T3D2, elset=FIBERS", " 1, 1, 2", " 2, 3, 4",
          "*Solid Section, elset=FIBERS, material=Fiber", " 3.1370687601686238e-07",
          "*Nset, nset=FIBER_NODES", " 1, 2, 3, 4",
          "*End Part",
          "*Assembly, name=Assembly",
          "*Instance, name=Host-1, part=Host", "*End Instance",
          "*Instance, name=Fiber-1, part=Fiber", "*End Instance",
          *(["*Embedded Element, host elset=Host-1.HOST_ALL", "Fiber-1.FIBERS"] if embed else []),
          "*Surface, type=ELEMENT, name=HOST_SURF",
          "Host-1.HOST_ALL,", "Host-1.HOST_ALL, INTERIOR",
          "*Surface, type=NODE, name=FIBER_SURF", "Fiber-1.FIBER_NODES,",
          "*End Assembly",
          "*Material, name=HostKeep", "*Density", " 1460.", "*Elastic", " 3.4e+09, 0.35",
          "*Material, name=HostSac",
          "*Damage Initiation, criterion=DUCTILE",
          " 0.002, -3.0, 0.", " 0.002, 3.0, 0.",
          "*Damage Evolution, type=DISPLACEMENT", " 0.",
          "*Density", " 1460.", "*Elastic", " 3.4e+09, 0.35",
          "*Plastic", " 3.4e+06, 0.",
          "*Material, name=Fiber", "*Density", " 1800.", "*Elastic", " 2.3e+11, 0.2",
          "*Surface Interaction, name=FiberHostBaseline, USER=INTERACTION, "
          "PROPERTIES=2, DEPVAR=2, TRACKING THICKNESS=0.0005",
          "",
          " 2.0e+11, 0.01",
          "*Amplitude, name=RAMP, definition=SMOOTH STEP",
          " 0., 0., 5.0e-07, 1.",
          "*Boundary", "Host-1.BOTTOM, 1, 3",
          *([] if embed else ["Fiber-1.FIBER_NODES, 1, 3"]),
          "*Step, name=Step-1", "*Dynamic, Explicit", ", 6.0e-06",
          "*Boundary, type=VELOCITY, amplitude=RAMP", "Host-1.TOP, 3, 3, -3.0",
          "*Contact, op=NEW",
          "*Contact Inclusions", "FIBER_SURF , HOST_SURF",
          "*Contact Property Assignment", "FIBER_SURF , HOST_SURF , FiberHostBaseline",
          "*Contact Controls Assignment, nodal erosion=YES",
          "*Surface Property Assignment, property=THICKNESS", "FIBER_SURF, 0.000632",
          "*Output, history, time interval=5e-08",
          "*Energy Output", "ALLIE, ALLKE, ETOTAL, ALLPD, ALLWK, ALLCW",
          "*Element Output, elset=Host-1.HOST_SAC", "STATUS",
          "*Node Output, nset=Fiber-1.FIBER_NODES", "U3, V1, V2, V3",
          "*Output, field, time interval=1e-07",
          "*Node Output", "U, V",
          "*Element Output", "STATUS, S, LE, PEEQ, SDEG",
          "*Contact Output", "CSTRESS, CDISP",
          "*End Step"]
    return "\n".join(L) + "\n"


def _rows(ids, n=12):
    return [" " + ", ".join(map(str, ids[i:i+n])) for i in range(0, len(ids), n)]


if __name__ == "__main__":
    d = Path(__file__).resolve().parent
    for name, emb in (("cx057", True), ("cx057b", False)):
        p = d / (name + ".inp")
        p.write_text(build(emb), encoding="ascii", newline="\n")
        print("wrote", p)
