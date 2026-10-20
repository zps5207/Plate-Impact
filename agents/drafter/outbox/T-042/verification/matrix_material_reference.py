"""Matrix material constitutive reference model (Stage 8 spec).

Constitutive rules:
- Elastic: Isotropic Hooke with E = 700 MPa, nu = 0.45, rho = 980 kg/m^3.
- Plasticity: J2 (von Mises) yield, associative radial return, NO hardening.
- Rate dependence: Tabular log10-interpolated yield stress and fracture strain.
  RATE_MODE: 0 (default) = equivalent plastic strain rate (dEpeq/dt);
             1 = total equivalent strain rate sqrt(2/3 d_dev:d_dev).
- Damage onset: When PEEQ >= epsf(rate at onset). Freezes sigma_y0 and rate at onset.
- Damage evolution: Linear softening displacement ubar = L * (PEEQ - PEEQ_onset).
  Failure displacement ubar_f = 2 * Gf / sigma_y0, where Gf = 1460 J/m^2, L = V^(1/3).
  Damage D = ubar / ubar_f clamped to [0, 1], monotonic.
  Stress scaled by (1 - D). At D = 1, stress is zero.
- Energy tracking:
  Plastic dissipation W_p before onset = sigma_y0 * epsf.
  Damage dissipation W_dmd during softening = Gf / L.
  Total dissipation at D = 1 = sigma_y0 * epsf + Gf / L = 7.001460e6 J/m^3.
"""

from __future__ import print_function
import math
import numpy as np


def interp_rate_table(rate, rtab, valtab):
    """Log10-linear interpolation between table points, clamped outside."""
    if len(rtab) == 0:
        raise ValueError("Rate table cannot be empty")
    if len(rtab) == 1:
        return float(valtab[0])
    r = max(float(rate), 1.0e-12)
    if r <= rtab[0]:
        return float(valtab[0])
    if r >= rtab[-1]:
        return float(valtab[-1])
    for i in range(len(rtab) - 1):
        if rtab[i] <= r <= rtab[i + 1]:
            r0 = max(float(rtab[i]), 1.0e-12)
            r1 = max(float(rtab[i + 1]), 1.0e-12)
            u = (math.log10(r) - math.log10(r0)) / (math.log10(r1) - math.log10(r0))
            return float(valtab[i] + u * (valtab[i + 1] - valtab[i]))
    return float(valtab[-1])


class MatrixMaterialPoint(object):
    """Single material point constitutive state for rate-dependent J2 + ductile damage."""

    def __init__(self, E=700.0e6, nu=0.45, rho=980.0, Gf=1460.0, L=1.0,
                 resstiff=0.0, rate_mode=0,
                 yield_table=((0.01, 70.0e6),),
                 fracture_table=((0.01, 0.10),)):
        self.E = float(E)
        self.nu = float(nu)
        self.rho = float(rho)
        self.Gf = float(Gf)
        self.L = float(L)
        self.resstiff = float(resstiff)
        self.rate_mode = int(rate_mode)

        # Lame constants and bulk modulus
        self.lam = self.E * self.nu / ((1.0 + self.nu) * (1.0 - 2.0 * self.nu))
        self.mu = self.E / (2.0 * (1.0 + self.nu))
        self.bulk = self.lam + 2.0 * self.mu / 3.0

        # Rate tables
        self.rtab_y = [p[0] for p in yield_table]
        self.valtab_y = [p[1] for p in yield_table]
        self.rtab_f = [p[0] for p in fracture_table]
        self.valtab_f = [p[1] for p in fracture_table]

        # State variables
        self.reset()

    def reset(self):
        # Ep in Voigt notation: [Ep11, Ep22, Ep33, 2*Ep12, 2*Ep13, 2*Ep23]
        self.ep = np.zeros(6, dtype=float)
        self.peeq = 0.0
        self.peeq_onset = 0.0
        self.sigy0_onset = 0.0
        self.rate_onset = 0.0
        self.D = 0.0
        self.status = 0  # 0: elastic, 1: plastic pre-damage, 2: softening, 3: failed
        self.plastic_dissip = 0.0
        self.damage_dissip = 0.0
        self.stress_undamaged = np.zeros(6, dtype=float)
        self.stress = np.zeros(6, dtype=float)

    def update_3d(self, strain, dstrain, dtime):
        """Perform 3D small-strain elastic-plastic + damage update for a single increment.

        strain: [e11, e22, e33, 2*e12, 2*e13, 2*e23] at end of increment
        dstrain: strain increment over dtime
        dtime: time increment > 0
        """
        if self.status == 3 or self.D >= 1.0:
            self.D = 1.0
            self.status = 3
            self.stress = np.zeros(6, dtype=float)
            return self.stress, self.peeq, self.D, self.plastic_dissip, self.damage_dissip

        dtime = max(float(dtime), 1.0e-12)

        # 1. Strain rate evaluation
        if self.rate_mode == 1:
            edot = dstrain / dtime
            tr_edot = edot[0] + edot[1] + edot[2]
            edot_dev = np.array([
                edot[0] - tr_edot / 3.0,
                edot[1] - tr_edot / 3.0,
                edot[2] - tr_edot / 3.0,
                edot[3] / 2.0,
                edot[4] / 2.0,
                edot[5] / 2.0,
            ])
            edot_eq = math.sqrt(2.0 / 3.0 * (
                edot_dev[0]**2 + edot_dev[1]**2 + edot_dev[2]**2 +
                2.0 * (edot_dev[3]**2 + edot_dev[4]**2 + edot_dev[5]**2)
            ))
            current_rate = edot_eq
        else:
            current_rate = 0.0

        # 2. Elastic trial state
        ee_trial = strain - self.ep
        tr_ee = ee_trial[0] + ee_trial[1] + ee_trial[2]
        p_hydro = self.bulk * tr_ee

        sdev_trial = np.array([
            2.0 * self.mu * (ee_trial[0] - tr_ee / 3.0),
            2.0 * self.mu * (ee_trial[1] - tr_ee / 3.0),
            2.0 * self.mu * (ee_trial[2] - tr_ee / 3.0),
            self.mu * ee_trial[3],
            self.mu * ee_trial[4],
            self.mu * ee_trial[5],
        ])

        sigma_vm_trial = math.sqrt(max(0.0, 1.5 * (
            sdev_trial[0]**2 + sdev_trial[1]**2 + sdev_trial[2]**2 +
            2.0 * (sdev_trial[3]**2 + sdev_trial[4]**2 + sdev_trial[5]**2)
        )))

        # Yield stress from table
        sigy_current = interp_rate_table(current_rate, self.rtab_y, self.valtab_y)

        # 3. Plastic return mapping (J2, no hardening)
        dgamma = 0.0
        if sigma_vm_trial > sigy_current:
            dgamma = (sigma_vm_trial - sigy_current) / (3.0 * self.mu)
            if self.rate_mode == 0:
                pl_rate = dgamma / dtime
                sigy_current = interp_rate_table(pl_rate, self.rtab_y, self.valtab_y)
                dgamma = max(0.0, (sigma_vm_trial - sigy_current) / (3.0 * self.mu))
                current_rate = pl_rate

            unit_flow = (1.5 / sigma_vm_trial) * sdev_trial
            dep = np.array([
                dgamma * unit_flow[0],
                dgamma * unit_flow[1],
                dgamma * unit_flow[2],
                2.0 * dgamma * unit_flow[3],
                2.0 * dgamma * unit_flow[4],
                2.0 * dgamma * unit_flow[5],
            ])
            self.ep += dep
            self.peeq += dgamma
            sdev_undamaged = (sigy_current / sigma_vm_trial) * sdev_trial
            if self.status == 0:
                self.status = 1  # plastic pre-damage
        else:
            sdev_undamaged = sdev_trial

        self.stress_undamaged = np.array([
            p_hydro + sdev_undamaged[0],
            p_hydro + sdev_undamaged[1],
            p_hydro + sdev_undamaged[2],
            sdev_undamaged[3],
            sdev_undamaged[4],
            sdev_undamaged[5],
        ])

        # 4. Damage onset and evolution
        epsf_current = interp_rate_table(current_rate, self.rtab_f, self.valtab_f)
        if self.status < 2:
            if self.peeq >= epsf_current:
                self.status = 2  # softening active
                self.peeq_onset = epsf_current
                self.sigy0_onset = sigy_current
                self.rate_onset = current_rate

        # Damage evolution: linear softening
        D_old = self.D
        if self.status == 2:
            ubar_f = 2.0 * self.Gf / max(self.sigy0_onset, 1.0)
            ubar = self.L * (self.peeq - self.peeq_onset)
            D_trial = ubar / ubar_f
            self.D = min(1.0, max(self.D, D_trial))
            if self.D >= 1.0:
                self.D = 1.0
                self.status = 3

        # 5. Stress scaling by (1 - D)
        stress_scale = max(self.resstiff, 1.0 - self.D) if self.D < 1.0 else self.resstiff
        self.stress = stress_scale * self.stress_undamaged

        # 6. Dissipation tracking
        if self.status < 2:
            self.plastic_dissip += sigy_current * dgamma
        else:
            delta_D = self.D - D_old
            self.damage_dissip += (self.Gf / self.L) * delta_D

        return self.stress, self.peeq, self.D, self.plastic_dissip, self.damage_dissip


def run_uniaxial_tension(rate, eps_max=0.25, L=1.0):
    """Run 1D uniaxial-stress tension test with refined steps around onset and softening."""
    pt = MatrixMaterialPoint(L=L, rate_mode=0)
    ey = 70.0e6 / pt.E
    eps_onset = ey + 0.10
    ubar_f = 2.0 * pt.Gf / 70.0e6
    delta_eps_f = ubar_f / L
    eps_fail = eps_onset + delta_eps_f

    # Create dense grid: elastic (0 to ey), plateau (ey to onset), softening (onset to fail), post-fail
    st1 = np.linspace(0.0, ey, 200, endpoint=False)
    st2 = np.linspace(ey, eps_onset, 400, endpoint=False)
    st3 = np.linspace(eps_onset, eps_fail, 500, endpoint=True)
    st4 = np.linspace(eps_fail, eps_max, 100)[1:]
    strain_grid = np.concatenate([st1, st2, st3, st4])

    history = []
    t = 0.0
    for i, e11 in enumerate(strain_grid):
        t = e11 / rate
        dt = (strain_grid[i] - strain_grid[i - 1]) / rate if i > 0 else (e11 / rate if e11 > 0 else 1.0e-6)

        # In uniaxial stress (sigma_22 = sigma_33 = 0):
        if e11 <= ey:
            e22 = -pt.nu * e11
        elif e11 <= eps_fail:
            # Poisson contraction: elastic lateral + plastic isochoric lateral (-0.5*d_e_pl)
            # Exactly solves sigma_22 = 0: e22 = -nu*ey - 0.5*(e11 - ey)
            e22 = -pt.nu * ey - 0.5 * (e11 - ey)
        else:
            e22 = -pt.nu * ey - 0.5 * (eps_fail - ey)

        strain = np.array([e11, e22, e22, 0.0, 0.0, 0.0])
        dstrain = strain - (history[-1]["strain"] if history else np.zeros(6))
        pt.update_3d(strain, dstrain, dt)

        history.append({
            "t": t,
            "strain": strain.copy(),
            "eps_axial": e11,
            "stress_axial": pt.stress[0],
            "peeq": pt.peeq,
            "D": pt.D,
            "plastic_dissip": pt.plastic_dissip,
            "damage_dissip": pt.damage_dissip,
            "total_dissip": pt.plastic_dissip + pt.damage_dissip,
        })

    return history


def run_uniaxial_compression(rate, eps_max=0.25, L=1.0):
    """Run 1D uniaxial-stress compression test with refined steps around onset and softening."""
    pt = MatrixMaterialPoint(L=L, rate_mode=0)
    ey = 70.0e6 / pt.E
    eps_onset = ey + 0.10
    ubar_f = 2.0 * pt.Gf / 70.0e6
    delta_eps_f = ubar_f / L
    eps_fail = eps_onset + delta_eps_f

    st1 = np.linspace(0.0, ey, 200, endpoint=False)
    st2 = np.linspace(ey, eps_onset, 400, endpoint=False)
    st3 = np.linspace(eps_onset, eps_fail, 500, endpoint=True)
    st4 = np.linspace(eps_fail, eps_max, 100)[1:]
    mag_grid = np.concatenate([st1, st2, st3, st4])

    history = []
    for i, mag in enumerate(mag_grid):
        e11 = -mag
        t = mag / rate
        dt = (mag_grid[i] - mag_grid[i - 1]) / rate if i > 0 else (mag / rate if mag > 0 else 1.0e-6)

        if mag <= ey:
            e22 = pt.nu * mag
        elif mag <= eps_fail:
            e22 = pt.nu * ey + 0.5 * (mag - ey)
        else:
            e22 = pt.nu * ey + 0.5 * (eps_fail - ey)

        strain = np.array([e11, e22, e22, 0.0, 0.0, 0.0])
        dstrain = strain - (history[-1]["strain"] if history else np.zeros(6))
        pt.update_3d(strain, dstrain, dt)

        history.append({
            "t": t,
            "strain": strain.copy(),
            "eps_axial": e11,
            "stress_axial": pt.stress[0],
            "peeq": pt.peeq,
            "D": pt.D,
            "plastic_dissip": pt.plastic_dissip,
            "damage_dissip": pt.damage_dissip,
            "total_dissip": pt.plastic_dissip + pt.damage_dissip,
        })

    return history


def run_pure_shear(rate, gamma_max=0.50, L=1.0):
    """Run pure shear test with refined steps around onset and softening."""
    pt = MatrixMaterialPoint(L=L, rate_mode=0)
    tau_y = 70.0e6 / math.sqrt(3.0)
    gamma_y = tau_y / pt.mu
    gamma_onset = gamma_y + 0.10 * math.sqrt(3.0)
    ubar_f = 2.0 * pt.Gf / 70.0e6
    delta_gamma_f = (ubar_f / L) * math.sqrt(3.0)
    gamma_fail = gamma_onset + delta_gamma_f

    st1 = np.linspace(0.0, gamma_y, 200, endpoint=False)
    st2 = np.linspace(gamma_y, gamma_onset, 400, endpoint=False)
    st3 = np.linspace(gamma_onset, gamma_fail, 500, endpoint=True)
    st4 = np.linspace(gamma_fail, gamma_max, 100)[1:]
    gamma_grid = np.concatenate([st1, st2, st3, st4])

    history = []
    for i, gamma in enumerate(gamma_grid):
        t = gamma / rate
        dt = (gamma_grid[i] - gamma_grid[i - 1]) / rate if i > 0 else (gamma / rate if gamma > 0 else 1.0e-6)

        strain = np.array([0.0, 0.0, 0.0, gamma, 0.0, 0.0])
        dstrain = strain - (history[-1]["strain"] if history else np.zeros(6))
        pt.update_3d(strain, dstrain, dt)

        history.append({
            "t": t,
            "strain": strain.copy(),
            "gamma": gamma,
            "tau": pt.stress[3],
            "peeq": pt.peeq,
            "D": pt.D,
            "plastic_dissip": pt.plastic_dissip,
            "damage_dissip": pt.damage_dissip,
            "total_dissip": pt.plastic_dissip + pt.damage_dissip,
        })

    return history


def main():
    print("=" * 78)
    print("MATRIX MATERIAL CONSTITUTIVE REFERENCE MODEL (STAGE 8)")
    print("=" * 78)
    rates = [0.01, 1.0, 1000.0]

    # Verification 1: Uniaxial tension at 3 rates
    print("\n--- UNIAXIAL TENSION (0.01, 1.0, 1000.0 /s) ---")
    tens_histories = {}
    for r in rates:
        hist = run_uniaxial_tension(rate=r, eps_max=0.25)
        tens_histories[r] = hist

        # 1. Elastic slope at eps = 0.05
        h_el = next(h for h in hist if h["eps_axial"] >= 0.05)
        slope_el = h_el["stress_axial"] / h_el["eps_axial"]

        # 2. Plateau stress at eps = 0.15
        h_plat = next(h for h in hist if h["eps_axial"] >= 0.15)
        sig_plat = h_plat["stress_axial"]

        # 3. Damage onset point (first point with D > 0)
        h_onset = next(h for h in hist if h["D"] > 0.0)

        # 4. Full failure point (first point with D == 1)
        h_fail = next(h for h in hist if h["D"] >= 1.0)

        print("Rate {:>7.2f} /s:".format(r))
        print("  Elastic slope (at eps=0.05) : {:12.4e} Pa (expected 7.0000e+08)".format(slope_el))
        print("  Yield plateau (at eps=0.15) : {:12.4e} Pa (expected 7.0000e+07)".format(sig_plat))
        print("  Onset strain / PEEQ         : {:12.6f} / {:12.6f} (expected PEEQ = 0.10)".format(
            h_onset["eps_axial"], h_onset["peeq"]))
        print("  Failure strain (D=1.0)      : {:12.6f} (expected ~0.200042)".format(h_fail["eps_axial"]))
        print("  W_plastic at D=1.0          : {:12.4e} J/m^3 (expected 7.0000e+06)".format(h_fail["plastic_dissip"]))
        print("  W_damage at D=1.0           : {:12.4e} J/m^3 (expected 1.4600e+03)".format(h_fail["damage_dissip"]))
        print("  Total dissipation at D=1.0  : {:12.4e} J/m^3 (expected 7.0015e+06)".format(h_fail["total_dissip"]))

    h0 = tens_histories[0.01]
    h1 = tens_histories[1.0]
    h2 = tens_histories[1000.0]
    diff_0_1 = max(abs(h0[i]["stress_axial"] - h1[i]["stress_axial"]) for i in range(len(h0)))
    diff_0_2 = max(abs(h0[i]["stress_axial"] - h2[i]["stress_axial"]) for i in range(len(h0)))
    print("  Rate independence check (tension): max diff 0.01 vs 1.0: {:.2e} Pa, vs 1000: {:.2e} Pa".format(
        diff_0_1, diff_0_2))

    # Verification 2: Uniaxial compression at 3 rates
    print("\n--- UNIAXIAL COMPRESSION (0.01, 1.0, 1000.0 /s) ---")
    comp_histories = {}
    for r in rates:
        hist = run_uniaxial_compression(rate=r, eps_max=0.25)
        comp_histories[r] = hist
        h_el = next(h for h in hist if h["eps_axial"] <= -0.05)
        h_plat = next(h for h in hist if h["eps_axial"] <= -0.15)
        h_fail = next(h for h in hist if h["D"] >= 1.0)
        print("Rate {:>7.2f} /s:".format(r))
        print("  Elastic slope (at eps=-0.05): {:12.4e} Pa (expected 7.0000e+08)".format(
            h_el["stress_axial"] / h_el["eps_axial"]))
        print("  Yield plateau (at eps=-0.15): {:12.4e} Pa (expected -7.0000e+07)".format(h_plat["stress_axial"]))
        print("  Failure strain (D=1.0)      : {:12.6f} (expected ~ -0.200042)".format(h_fail["eps_axial"]))
        print("  Total dissipation at D=1.0  : {:12.4e} J/m^3 (expected 7.0015e+06)".format(h_fail["total_dissip"]))

    # Verification 3: Pure shear at 3 rates
    print("\n--- PURE SHEAR (0.01, 1.0, 1000.0 /s) ---")
    shear_histories = {}
    for r in rates:
        hist = run_pure_shear(rate=r, gamma_max=0.50)
        shear_histories[r] = hist
        h_el = next(h for h in hist if h["gamma"] >= 0.05)
        h_plat = next(h for h in hist if h["gamma"] >= 0.25)
        h_fail = next(h for h in hist if h["D"] >= 1.0)
        mu_exp = 700.0e6 / (2.0 * 1.45)
        tau_y_exp = 70.0e6 / math.sqrt(3.0)
        print("Rate {:>7.2f} /s:".format(r))
        print("  Shear modulus (at gamma=0.05): {:12.4e} Pa (expected {:12.4e})".format(
            h_el["tau"] / h_el["gamma"], mu_exp))
        print("  Yield shear tau (gamma=0.25) : {:12.4e} Pa (expected {:12.4e})".format(
            h_plat["tau"], tau_y_exp))
        print("  Failure gamma (D=1.0)        : {:12.6f} (expected ~ 0.340656)".format(h_fail["gamma"]))
        print("  Total dissipation at D=1.0   : {:12.4e} J/m^3 (expected 7.0015e+06)".format(h_fail["total_dissip"]))

    print("\n" + "=" * 78)
    print("ALL REFERENCE CHECKS COMPLETED SUCCESSFULLY.")
    print("=" * 78)


if __name__ == "__main__":
    main()
