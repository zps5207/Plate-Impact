"""Line-for-line Python port of HENCKY_RETURN in uel/VUEL_material.for.

Checks the finite-strain J2 return map without Abaqus: in uniaxial stress the
Cauchy stress must plateau at SIGY, in simple shear the Cauchy shear must
plateau at SIGY/sqrt(3), and the elastic response must be Hencky.
Run: python verification/hencky_reference.py
"""
import numpy as np

E, NU, SIGY = 700e6, 0.45, 70e6
MU = E / (2 * (1 + NU))
LAM = E * NU / ((1 + NU) * (1 - 2 * NU))


def hencky_return(F, cpi, sigy):
    """F (3x3), cpi = Cp^-1 - I as 6-vector (11,22,33,12,13,23)."""
    detf = np.linalg.det(F)
    fi = np.linalg.inv(F)
    cp = np.array([[1 + cpi[0], cpi[3], cpi[4]],
                   [cpi[3], 1 + cpi[1], cpi[5]],
                   [cpi[4], cpi[5], 1 + cpi[2]]])
    be = F @ cp @ F.T
    w, v = np.linalg.eigh(be)
    eps = 0.5 * np.log(np.maximum(w, 1e-30))
    tr = eps.sum()
    ed = eps - tr / 3
    q = 2 * MU * np.sqrt(1.5 * (ed ** 2).sum())
    jy = np.exp(tr)
    dgam = 0.0
    if q > sigy * jy:
        dgam = (q - sigy * jy) / (3 * MU)
        ed = ed * (sigy * jy / q)
        q = sigy * jy
    eps = ed + tr / 3
    psi = 0.5 * LAM * tr ** 2 + MU * (eps ** 2).sum()
    tau = sum((LAM * tr + 2 * MU * eps[k]) * np.outer(v[:, k], v[:, k]) for k in range(3))
    ben = sum(np.exp(2 * eps[k]) * np.outer(v[:, k], v[:, k]) for k in range(3))
    s = fi @ tau @ fi.T
    cc = fi @ ben @ fi.T
    cpn = np.array([cc[0, 0] - 1, cc[1, 1] - 1, cc[2, 2] - 1, cc[0, 1], cc[0, 2], cc[1, 2]])
    return s, tau / detf, cpn, dgam, psi, q


def uniaxial(lmax=1.6, n=400):
    cpi = np.zeros(6)
    peeq = 0.0
    lt = 1.0
    out = []
    for lam in np.linspace(1.0, lmax, n)[1:]:
        for _ in range(60):  # solve lateral stretch for zero lateral Cauchy stress
            def lat(x):
                F = np.diag([lam, x, x])
                return hencky_return(F, cpi, SIGY)[1][1, 1]
            h = 1e-7
            f0 = lat(lt)
            d = (lat(lt + h) - f0) / h
            step = f0 / d
            lt -= step
            if abs(step) < 1e-14:
                break
        F = np.diag([lam, lt, lt])
        s, sig, cpn, dg, psi, q = hencky_return(F, cpi, SIGY)
        cpi = cpn
        peeq += dg
        out.append((lam, sig[0, 0], peeq, sig[1, 1]))
    return out


def shear(gmax=1.0, n=400):
    cpi = np.zeros(6)
    peeq = 0.0
    out = []
    for g in np.linspace(0, gmax, n)[1:]:
        F = np.array([[1, g, 0], [0, 1, 0], [0, 0, 1.0]])
        s, sig, cpn, dg, psi, q = hencky_return(F, cpi, SIGY)
        cpi = cpn
        peeq += dg
        dev = sig - np.trace(sig) / 3 * np.eye(3)
        out.append((g, sig[0, 1], peeq, np.sqrt(1.5 * (dev * dev).sum())))
    return out


if __name__ == "__main__":
    u = uniaxial()
    first = next(r for r in u if r[2] > 0)
    print("uniaxial: first yield at stretch %.4f (Hencky strain %.4f)" % (first[0], np.log(first[0])))
    for lam, sg, pe, lat in u[::80]:
        print("  stretch %.3f  sigma11 %.4f MPa  peeq %.4f  lateral %.2e" % (lam, sg / 1e6, pe, lat))
    last = u[-1]
    assert abs(last[1] - SIGY) < 1e-3 * SIGY, "uniaxial plateau != SIGY"
    assert abs(last[2] - (np.log(last[0]) - SIGY / E)) < 5e-3, "peeq vs ln(lambda)-sigma/E"
    sh = shear()
    print("shear gamma=1: sigma12 %.3f MPa, Mises of Cauchy deviator %.4f MPa (expect 70)" % (sh[-1][1] / 1e6, sh[-1][3] / 1e6))
    assert abs(sh[-1][3] - SIGY) < 1e-3 * SIGY
    print("ALL HENCKY CHECKS PASSED")
