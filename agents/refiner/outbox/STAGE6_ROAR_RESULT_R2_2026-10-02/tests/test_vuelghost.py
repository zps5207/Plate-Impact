from embmesh.parser import parse_deck
from embmesh.vuelghost import NSVARS, VuelGhostOptions, convert_to_vuel_ghost


DECK = """*Heading
*Part, name=HOST
*Node
1, 0, 0, 0
2, 1, 0, 0
3, 1, 1, 0
4, 0, 1, 0
5, 0, 0, 1
6, 1, 0, 1
7, 1, 1, 1
8, 0, 1, 1
*Element, type=C3D8R, elset=HOSTSET
10, 1, 2, 3, 4, 5, 6, 7, 8
*Solid Section, elset=HOSTSET, material=MATRIX
,
*End Part
*Assembly, name=A
*Instance, name=HOST-1, part=HOST
*End Instance
*End Assembly
*Material, name=MATRIX
*Damage Initiation, criterion=DUCTILE
0.25, 0., 0.
*Damage Evolution, type=DISPLACEMENT
0.
*Density
1000.
*Elastic
2e9, 0.3
*Plastic
2e6, 0.
3e6, 0.1
*Step, name=S
*Dynamic, Explicit
, 1e-3
*End Step
"""


def test_vuel_ghost_conversion_has_pairs_scaled_material_and_svar107():
    deck = parse_deck(DECK)
    lines, ghosts, meta = convert_to_vuel_ghost(
        DECK.splitlines(), deck, "HOST-1", deck.parts["HOST"].elements,
        {10: 0.125}, VuelGhostOptions())
    text = "\n".join(lines)
    assert ghosts == {10: 11}
    assert f"variables={NSVARS}" in text
    assert "*Element, type=VU1, elset=EMBMESH_VUEL_HOST\n10, 1, 2, 3, 4, 5, 6, 7, 8" in text
    assert "*Element, type=C3D8R, elset=EMBMESH_GHOST_HOST\n11, 1, 2, 3, 4, 5, 6, 7, 8" in text
    assert "*Material, name=EMBMESH_GHOST_MATERIAL" in text
    assert "0.1" in text                 # scaled density: 1000 * 1e-4
    assert "200000" in text              # scaled E: 2e9 * 1e-4
    assert "200" in text                 # scaled initial yield: 2e6 * 1e-4
    assert "*Initial Conditions, type=SOLUTION" in text
    assert "HOST-1.10, 0, 0, 0, 0, 0, 0, 0" in text
    assert text.splitlines()[text.splitlines().index("HOST-1.10, 0, 0, 0, 0, 0, 0, 0") + 13].endswith("0.125")
    assert meta["fiber_volume_svar"] == 107
    assert meta["expected_host_mass_ratio_including_ghost"] == 1.0001


def test_vuel_properties_are_split_at_eight_values():
    deck = parse_deck(DECK)
    lines, _, _ = convert_to_vuel_ghost(
        DECK.splitlines(), deck, "HOST-1", deck.parts["HOST"].elements,
        {10: 0.0})
    index = lines.index("*UEL Property, elset=EMBMESH_VUEL_HOST")
    assert len([x for x in lines[index + 1].split(",") if x.strip()]) == 8
    assert len([x for x in lines[index + 2].split(",") if x.strip()]) == 5


def test_ghost_ductile_failure_strain_can_be_calibrated_independently():
    deck = parse_deck(DECK)
    lines, _, meta = convert_to_vuel_ghost(
        DECK.splitlines(), deck, "HOST-1", deck.parts["HOST"].elements,
        {10: 0.0}, VuelGhostOptions(
            eps_fail=0.1138, ghost_ductile_failure_strain=1.0e-6))
    text = "\n".join(lines)
    ghost = text.split("*Material, name=EMBMESH_GHOST_MATERIAL", 1)[1].split("*Material,", 1)[0]
    assert "*Damage Initiation, criterion=DUCTILE\n1e-06, 0, 0" in ghost
    assert meta["ghost_ductile_failure_strain"] == 1.0e-6
    # The VUEL trigger remains independently selectable.
    assert meta["vuel_properties"][6] == 0.1138


def test_ghost_ductile_failure_strain_must_be_strictly_positive():
    deck = parse_deck(DECK)
    try:
        convert_to_vuel_ghost(
            DECK.splitlines(), deck, "HOST-1", deck.parts["HOST"].elements,
            {10: 0.0}, VuelGhostOptions(
                eps_fail=0.1138, ghost_ductile_failure_strain=0.0))
    except ValueError as exc:
        assert "strictly positive" in str(exc)
    else:
        raise AssertionError("zero ghost ductile failure strain was accepted")


def test_vuel_ghost_validation_rejects_nonpositive_scale():
    deck = parse_deck(DECK)
    try:
        convert_to_vuel_ghost(
            DECK.splitlines(), deck, "HOST-1", deck.parts["HOST"].elements,
            {10: 0.0}, VuelGhostOptions(ghost_scale=0.0))
    except ValueError as exc:
        assert "ghost-scale" in str(exc)
    else:
        raise AssertionError("nonpositive ghost scale was accepted")
