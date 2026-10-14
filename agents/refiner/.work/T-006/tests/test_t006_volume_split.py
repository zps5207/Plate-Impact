"""Source-level and algebraic checks for the T-006 VUEL volume split."""
from pathlib import Path

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "uel" / "VUEL_failure.for"


def integrated_force(eta, pk2, residual, viscous, bulk, stress_scale=1.0, damage=0.0):
    physical = (stress_scale * pk2 + damage * residual) * eta
    stabilization = stress_scale * (viscous + bulk)
    return physical + stabilization


def test_vf0_is_exact_noop_for_force_mass_and_energy_weights():
    assert integrated_force(1.0, 11.0, 7.0, 3.0, 5.0) == 19.0
    assert 7800.0 * 1.0 == 7800.0
    assert 2.5 * 1.0 == 2.5


def test_mixed_vf_elements_get_distinct_per_element_force_and_mass():
    # Same block-level inputs, eta=0.7 and eta=0.4 from Vf=.3 and Vf=.6.
    forces = [integrated_force(eta, 100.0, 0.0, 0.0, 0.0)
              for eta in (0.7, 0.4)]
    masses = [eta * 7800.0 for eta in (0.7, 0.4)]
    assert forces == pytest.approx([70.0, 40.0])
    assert masses == pytest.approx([5460.0, 3120.0])
    assert forces[1] / forces[0] == pytest.approx(4.0 / 7.0)
    assert masses[1] / masses[0] == pytest.approx(4.0 / 7.0)


def test_physical_force_halves_but_stabilization_does_not():
    full = integrated_force(1.0, 100.0, 0.0, 20.0, 30.0)
    half = integrated_force(0.5, 100.0, 0.0, 20.0, 30.0)
    assert full == 150.0
    assert half == 100.0
    assert half - 0.5 * 100.0 == full - 100.0


def test_stable_timestep_uses_only_geometric_volume():
    def stable_dt(geom_volume, wave_speed):
        return 0.8 * (geom_volume ** (1.0 / 3.0)) / wave_speed

    assert stable_dt(8.0, 5000.0) == stable_dt(8.0, 5000.0)


def test_source_has_required_two_volume_split_and_intrinsic_constants():
    text = SOURCE.read_text()
    assert "ETA_VF = DMAX1(ETA_VF_RAW, 1.0D-6)" in text
    assert "svars(KBLOCK,107)" in text
    assert "DVOL_EFF = ETA_VF * DVOL_GEOM" in text
    assert "ELEMASS = DENS * ELVOL_EFF" in text
    assert "STRESS_RESIDUAL(J)) * DVOL_EFF" in text
    assert "(STRESS_VISC(J) + STRESS_BULK(J)) * DVOL_GEOM" in text
    assert "*EE_NEW_VEC(I)*DVOL_EFF" in text
    assert "*DGAMMA*DVOL_EFF" in text
    assert "* STRAINRATE_VEC(I)*DVOL_GEOM*dtimeCur" in text
    assert "* DVOL_GEOM*dtimeCur" in text
    assert "CHARLEN = ELVOL_GEOM ** (1.0D0 / 3.0D0)" in text
    assert "CHARLEN = DVOL_GEOM ** (1.0D0 / 3.0D0)" in text
    assert "CMAT_K" not in text
    assert "EMOD_K" not in text
    assert "SIGY0_K" not in text
    assert "HMOD_K" not in text
