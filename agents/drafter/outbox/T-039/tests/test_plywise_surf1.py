"""Test restoration of element-based plate impact surface (Surf-1) in plywise decks."""
from pathlib import Path
import pytest

from embmesh.plywise import write_plywise_deck
from embmesh.parser import parse_deck


def make_synthetic_plate_ball_deck(surf1_face='bottom', ball_pos='bottom', add_side_face=False):
    """Build a valid 4-element 1-hex plate deck with Ball-1 and Surf-2."""
    s = """*Heading
*Part, name=Plate
*Node
1, 0.0, 0.0, 0.0
2, 0.01, 0.0, 0.0
3, 0.01, 0.01, 0.0
4, 0.0, 0.01, 0.0
5, 0.0, 0.0, 0.001
6, 0.01, 0.0, 0.001
7, 0.01, 0.01, 0.001
8, 0.0, 0.01, 0.001
9, 0.02, 0.0, 0.0
10, 0.02, 0.01, 0.0
11, 0.02, 0.0, 0.001
12, 0.02, 0.01, 0.001
13, 0.0, 0.02, 0.0
14, 0.01, 0.02, 0.0
15, 0.0, 0.02, 0.001
16, 0.01, 0.02, 0.001
17, 0.02, 0.02, 0.0
18, 0.02, 0.02, 0.001
*Element, type=C3D8R
1, 1, 2, 3, 4, 5, 6, 7, 8
2, 2, 9, 10, 3, 6, 11, 12, 7
3, 4, 3, 14, 13, 8, 7, 16, 15
4, 3, 10, 17, 14, 7, 12, 18, 16
*Elset, elset=Plate_Mat
1, 2, 3, 4
*Solid Section, elset=Plate_Mat, material=Plate_Mat
*End Part
*Part, name=Ball
*Node
101, 0.005, 0.005, 0.0
102, 0.015, 0.005, 0.0
103, 0.015, 0.015, 0.0
104, 0.005, 0.015, 0.0
105, 0.005, 0.005, 0.002
106, 0.015, 0.005, 0.002
107, 0.015, 0.015, 0.002
108, 0.005, 0.015, 0.002
*Element, type=C3D8R
101, 101, 102, 103, 104, 105, 106, 107, 108
*Elset, elset=Ball_Mat
101
*Solid Section, elset=Ball_Mat, material=Plate_Mat
*End Part
*Assembly, name=Assembly
*Instance, name=Plate-1, part=Plate
0, 0, 0
*End Instance
"""
    ball_z = -0.005 if ball_pos == 'bottom' else 0.008
    s += f"""*Instance, name=Ball-1, part=Ball
0, 0, {ball_z}
*End Instance
*Elset, elset=_Surf-2_S1, internal, instance=Ball-1
101
*Surface, type=ELEMENT, name=Surf-2
_Surf-2_S1, S1
"""
    if surf1_face == 'bottom':
        s += """*Elset, elset=_Surf-1_S1, internal, instance=Plate-1
1, 2, 3, 4
*Surface, type=ELEMENT, name=Surf-1
_Surf-1_S1, S1
"""
    elif surf1_face == 'top':
        s += """*Elset, elset=_Surf-1_S2, internal, instance=Plate-1
1, 2, 3, 4
*Surface, type=ELEMENT, name=Surf-1
_Surf-1_S2, S2
"""
    elif surf1_face == 'both':
        s += """*Elset, elset=_Surf-1_S1, internal, instance=Plate-1
1, 2, 3, 4
*Elset, elset=_Surf-1_S2, internal, instance=Plate-1
1, 2, 3, 4
"""
        if add_side_face:
            s += """*Elset, elset=_Surf-1_S3, internal, instance=Plate-1
1, 2
*Surface, type=ELEMENT, name=Surf-1
_Surf-1_S1, S1
_Surf-1_S2, S2
_Surf-1_S3, S3
"""
        else:
            s += """*Surface, type=ELEMENT, name=Surf-1
_Surf-1_S1, S1
_Surf-1_S2, S2
"""
    s += """*End Assembly
*Material, name=Plate_Mat
*Density
7800.
*Elastic
2.1e11, 0.3
*Plastic
4.0e8, 0.0
6.0e8, 0.2
*Damage Initiation, criterion=DUCTILE
0.1, 0.0, 0.0
*Damage Evolution, type=DISPLACEMENT
1e-5
*Material, name=Fiber
*Density
1500.
*Elastic
1.0e11, 0.3
*Surface Interaction, name=General
*Friction
0.2
*Surface Behavior, pressure-overclosure=HARD
*Step, name=Step-1
*Dynamic, Explicit
, 0.001
*Contact, op=NEW
*Contact Inclusions
Surf-1 , Surf-2
Surf-2 , Surf-1
Surf-1 ,
Surf-2 ,
*Contact Property Assignment
 ,  , General
*End Step
"""
    return s


def _check_contact_inclusions_order(text):
    """Verify that the four element contact inclusion lines are present before property assignment."""
    lines = [line.strip() for line in text.splitlines() if not line.startswith('**')]
    inclusions_idx = next(i for i, l in enumerate(lines) if l.lower() == '*contact inclusions')
    prop_idx = next(i for i, l in enumerate(lines) if l.lower() == '*contact property assignment')
    assert inclusions_idx < prop_idx

    incl_block = lines[inclusions_idx + 1:prop_idx]
    for required in ('Surf-1 , Surf-2', 'Surf-2 , Surf-1', 'Surf-1 ,', 'Surf-2 ,'):
        assert required in incl_block


@pytest.mark.parametrize('host_mode', ['native', 'vuel-ghost'])
def test_surf1_bottom_face(tmp_path, host_mode):
    src = tmp_path / 'deck.inp'
    out = tmp_path / f'out_{host_mode}.inp'
    src.write_text(make_synthetic_plate_ball_deck(surf1_face='bottom', ball_pos='bottom'))

    kwargs = dict(plies=4, plate_node_contact=True, ball_instance='Ball-1', host_mode=host_mode)
    if host_mode == 'vuel-ghost':
        kwargs.update(layup=[0, 90, 0, 90], fiber_diameter=0.0002)

    meta = write_plywise_deck(src, out, **kwargs)
    el_contact = meta['ball_contact']['element_contact']
    assert el_contact is not None
    assert el_contact['target_instance'] == 'Ply-1'
    assert el_contact['target_side'] == 'bottom'
    assert el_contact['faces'] == ['S1']
    assert el_contact['element_count'] == 4

    out_text = out.read_text()
    # No dangling Plate-1 reference
    uncommented = [l for l in out_text.splitlines() if not l.strip().startswith('**')]
    assert not any('Plate-1' in l for l in uncommented)

    # Inclusions order verified
    _check_contact_inclusions_order(out_text)

    # Verify ghost vs native element labels
    lines = out_text.splitlines()
    surf1_elsets = [
        lines[i + 1].strip() for i, l in enumerate(lines)
        if l.startswith('*Elset, elset=_Surf-1_S1') and 'Ply-1' in l
    ]
    assert len(surf1_elsets) == 1
    if host_mode == 'vuel-ghost':
        assert el_contact['ghost_remapped'] is True
        # Ghost labels are > 4 (host elements are 1..4)
        members = [int(x.strip()) for x in surf1_elsets[0].split(',') if x.strip()]
        assert all(m > 4 for m in members)
    else:
        assert el_contact['ghost_remapped'] is False
        # Native labels are 1..4
        active_surf1_hdr = [l for l in lines if not l.startswith('**') and l.startswith('*Elset, elset=_Surf-1_S1') and 'Ply-1' in l][0]
        if 'generate' in active_surf1_hdr.lower():
            assert surf1_elsets[0] == '1, 4, 1'
        else:
            members = [int(x.strip()) for x in surf1_elsets[0].split(',') if x.strip()]
            assert set(members) == {1, 2, 3, 4}

    # Deck reparses cleanly
    deck = parse_deck(out)
    assert 'Ply-1' in deck.instances
    assert 'Ball-1' in deck.instances


@pytest.mark.parametrize('host_mode', ['native', 'vuel-ghost'])
def test_surf1_top_face(tmp_path, host_mode):
    src = tmp_path / 'deck.inp'
    out = tmp_path / f'out_{host_mode}.inp'
    src.write_text(make_synthetic_plate_ball_deck(surf1_face='top', ball_pos='top'))

    kwargs = dict(plies=4, plate_node_contact=True, ball_instance='Ball-1', host_mode=host_mode)
    if host_mode == 'vuel-ghost':
        kwargs.update(layup=[0, 90, 0, 90], fiber_diameter=0.0002)

    meta = write_plywise_deck(src, out, **kwargs)
    el_contact = meta['ball_contact']['element_contact']
    assert el_contact is not None
    assert el_contact['target_instance'] == 'Ply-4'
    assert el_contact['target_side'] == 'top'
    assert el_contact['faces'] == ['S2']

    out_text = out.read_text()
    _check_contact_inclusions_order(out_text)

    # Deck reparses cleanly
    deck = parse_deck(out)
    assert 'Ply-4' in deck.instances


def test_surf1_both_faces_selects_nearest_and_drops_side_faces(tmp_path):
    src = tmp_path / 'deck.inp'
    out = tmp_path / 'out_both.inp'
    # Both bottom and top faces, plus S3 side face. Ball is at bottom.
    src.write_text(make_synthetic_plate_ball_deck(surf1_face='both', ball_pos='bottom', add_side_face=True))

    meta = write_plywise_deck(src, out, plies=4, plate_node_contact=True, ball_instance='Ball-1')
    el_contact = meta['ball_contact']['element_contact']
    assert el_contact is not None
    assert el_contact['target_instance'] == 'Ply-1'
    assert el_contact['target_side'] == 'bottom'
    # Side face S3 is never kept, only S1 bottom face is kept
    assert el_contact['faces'] == ['S1']
    assert 'nearest to ball' in el_contact['selection_reason']

    out_text = out.read_text()
    # Confirm no S3 in active Surf-1 definition
    uncommented = [l for l in out_text.splitlines() if not l.strip().startswith('**')]
    assert not any('_Surf-1_S3' in l for l in uncommented)
    _check_contact_inclusions_order(out_text)


def test_no_surf1_safeguard(tmp_path):
    # Deck with no Surf-1 element surface
    s = make_synthetic_plate_ball_deck()
    # Remove Surf-1 definition lines
    lines = [l for l in s.splitlines() if 'surf-1' not in l.lower()]
    src = tmp_path / 'no_surf1.inp'
    out = tmp_path / 'out_no_surf1.inp'
    src.write_text('\n'.join(lines) + '\n')

    meta = write_plywise_deck(src, out, plies=4, plate_node_contact=True, ball_instance='Ball-1')
    assert meta['ball_contact']['element_contact'] is None
    out_text = out.read_text()
    assert 'Surf-1' not in [l for l in out_text.splitlines() if not l.startswith('**')]


def test_node_contact_off_safeguard(tmp_path):
    src = tmp_path / 'deck.inp'
    out = tmp_path / 'out_off.inp'
    src.write_text(make_synthetic_plate_ball_deck(surf1_face='bottom', ball_pos='bottom'))

    meta = write_plywise_deck(src, out, plies=4, plate_node_contact=False, ball_instance='Ball-1')
    assert meta['ball_contact'] is None
    assert any('UNRESOLVABLE DECK' in w for w in meta['warnings'])
