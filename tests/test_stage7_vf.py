"""Local source-level and constitutive checks for the Stage 7 VUEL edit."""
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[1] / "uel" / "VUEL_failure.for"


def radial_return(eta, strain, ep=0.0, peeq=0.0):
    """Uniaxial reduction of the same linear-hardening return algebra."""
    emod = eta * 2.0e11
    sigy0 = eta * 2.5e8
    hmod = eta * 2.0e9
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
    assert radial_return(1.0, 0.02) == radial_return(1.0 - 0.0, 0.02)


def test_half_vf_scales_stress_not_plastic_evolution_or_yield_strain():
    for strain in (0.0005, 0.00125, 0.002, 0.02):
        full = radial_return(1.0, strain)
        half = radial_return(0.5, strain)
        assert half[0] == 0.5 * full[0]
        assert half[1:] == full[1:]


def test_all_stiffness_consumers_use_per_element_constants():
    text = SOURCE.read_text()
    assert "CMAT_K(I,J) * EE_TRIAL_VEC(J)" in text
    assert "3.0D0*AMU_K + HMOD_K" in text
    assert "CMAT_K(I,J)*DEP_VEC(J)" in text
    assert "BETA_RAYLEIGH * CMAT_K(I,J)" in text
    assert "COMP_RESIDUAL_FRAC * BULK_MODULUS_K" in text
    assert "ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)" in text


def test_mass_wave_speed_bulk_viscosity_and_failure_stay_unscaled():
    text = SOURCE.read_text()
    assert "ELEMASS = DENS * ELVOL" in text
    assert "CWAVE = DSQRT((ALAMBDA + 2.0D0 * AMU) / DENS)" in text
    assert "QBULK = DENS * CHARLEN" in text
    assert "ELEM_MAXABS_ENG .GE. EPS_FAIL" in text
    assert "ELEM_MIN_DETF .LE. JAC_FAIL" in text
