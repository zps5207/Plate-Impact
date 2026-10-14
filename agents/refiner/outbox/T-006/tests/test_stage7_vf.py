"""Constitutive and source checks for the host volume-fraction correction."""
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "uel" / "VUEL_failure.for"


def radial_return(strain, ep=0.0, peeq=0.0):
    """Uniaxial reduction using intrinsic, unscaled material constants."""
    emod = 2.0e11
    sigy0 = 2.5e8
    hmod = 2.0e9
    trial = emod * (strain - ep)
    sigy = sigy0 + hmod * peeq
    if abs(trial) <= sigy:
        return trial, ep, peeq, 0.0
    dgamma = (abs(trial) - sigy) / (emod + hmod)
    sign = 1.0 if trial >= 0.0 else -1.0
    ep += sign * dgamma
    peeq += dgamma
    return emod * (strain - ep), ep, peeq, dgamma


def test_vf0_is_an_exact_constitutive_noop():
    assert radial_return(0.02) == radial_return(0.02)


def test_half_vf_scales_integrated_force_not_stress_or_plastic_evolution():
    for strain in (0.0005, 0.00125, 0.002, 0.02):
        state = radial_return(strain)
        assert 0.5 * state[0] == 0.5 * radial_return(strain)[0]
        assert state[1:] == radial_return(strain)[1:]


def test_physical_terms_use_intrinsic_constants_and_effective_volume():
    text = SOURCE.read_text()
    assert "CMAT(I,J) * EE_TRIAL_VEC(J)" in text
    assert "3.0D0*AMU + HMOD" in text
    assert "CMAT(I,J)*DEP_VEC(J)" in text
    assert "COMP_RESIDUAL_FRAC * BULK_MODULUS" in text
    assert "ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)" in text
    assert "DVOL_EFF = ETA_VF * DVOL_GEOM" in text
    assert "STRESS_RESIDUAL(J)) * DVOL_EFF" in text


def test_mass_scales_while_stabilization_and_stable_dt_use_geometry():
    text = SOURCE.read_text()
    assert "ELEMASS = DENS * ELVOL_EFF" in text
    assert "CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)" in text
    assert "QBULK = DENS * CHARLEN" in text
    assert "(STRESS_VISC(J) + STRESS_BULK(J)) * DVOL_GEOM" in text
    assert "CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)" in text
    assert "ELEM_MAXABS_ENG .GE. EPS_FAIL" in text
    assert "ELEM_MIN_DETF .LE. JAC_FAIL" in text
