import pytest
from embmesh.cohesive_materials import cohesive_interaction, dyneema_hb26_hazzard2018
from embmesh.errors import MesherInputError


def test_table5_one_mm_in_mm_units():
    c = dyneema_hb26_hazzard2018(1.0, units="mm")
    assert c.k == pytest.approx((60.0, 36.0, 36.0))
    assert c.strength == (1.2, 1.8, 1.8)
    assert c.fracture_energy == (0.544, 1.088, 1.088)
    # failure displacements 2G/T and 2G/S against Table 5 (0.908, 1.21)
    assert 2 * c.fracture_energy[0] / c.strength[0] == pytest.approx(0.908, abs=2e-3)
    assert 2 * c.fracture_energy[1] / c.strength[1] == pytest.approx(1.21, abs=2e-3)


def test_table7_stiffness_scales_inversely_with_thickness():
    assert dyneema_hb26_hazzard2018(5.0, units="mm").k[0] == pytest.approx(12.0)
    assert dyneema_hb26_hazzard2018(10 / 3, units="mm").k[0] == pytest.approx(18.0)


def test_si_matches_user_stack_deck_for_cross_ply_thickness():
    # Meshing/stack.inp carries 4.36e11 / 2.62e11 Pa/m, MAXS 1.2e6/1.8e6, G 544/1088: t = 0.1375 mm
    c = dyneema_hb26_hazzard2018(0.1375e-3, units="m")
    assert c.k[0] == pytest.approx(4.36e11, rel=1e-3) and c.k[1] == pytest.approx(2.62e11, rel=1e-3)
    assert c.strength == pytest.approx((1.2e6, 1.8e6, 1.8e6))
    assert c.fracture_energy == pytest.approx((544.0, 1088.0, 1088.0))
    assert c.warnings == []


def test_ballistic_rate_and_thin_warning_and_errors():
    assert dyneema_hb26_hazzard2018(1e-3, rate="ballistic").strength[1] == pytest.approx(2.6e6)
    assert dyneema_hb26_hazzard2018(0.1e-3).warnings
    with pytest.raises(MesherInputError):
        dyneema_hb26_hazzard2018(0)
    with pytest.raises(MesherInputError):
        cohesive_interaction("kevlar", 1e-3)
    lines = dyneema_hb26_hazzard2018(1e-3).inp_lines()
    assert lines[1] == "*Surface Interaction, name=Cohesion_Hazzard2018" and "*Cohesive Behavior" in lines
