import pytest

from embmesh.parser import parse_deck
from embmesh.plywise import write_plywise_deck
from embmesh.plywise_contact import FiberInstanceRef


def _source(*, general=False, safe=False, fiber=False):
    s = '''*Part, name=Plate
*Node
1,0,0,0
2,0,1,0
3,1,1,0
4,1,0,0
5,0,0,.01
6,0,1,.01
7,1,1,.01
8,1,0,.01
*Element, type=C3D8R
1,1,2,3,4,5,6,7,8
*Elset, elset=Plate
1
*Solid Section, elset=Plate, material=Matrix
,
*End Part
*Part, name=Ball
*Node
1,0,0,.03
2,1,0,.03
3,1,1,.03
4,0,1,.03
5,0,0,.04
6,1,0,.04
7,1,1,.04
8,0,1,.04
*Element, type=C3D8R
1,1,2,3,4,5,6,7,8
*End Part
'''
    if fiber:
        s += '''*Part, name=Fibers
*Node
11,0,0,0
12,1,0,0
*Element, type=T3D2
1,11,12
*End Part
'''
    s += '''*Assembly, name=Assembly
*Instance, name=Plate-1, part=Plate
0,0,0
*End Instance
*Instance, name=Ball-1, part=Ball
0,0,0
*End Instance
'''
    if fiber:
        s += '''*Instance, name=Fibers-0-1, part=Fibers
0,0,0
*End Instance
*Instance, name=Fibers-90-2, part=Fibers
0,0,0
*End Instance
'''
    s += '''*Elset, elset=_Surf-1_S2, internal, instance=Plate-1
1
*Surface, type=ELEMENT, name=Surf-1
_Surf-1_S2, S2
*End Assembly
*Material, name=Matrix
*Elastic
1, .3
*Surface Interaction, name=Cohesion
*Cohesive Behavior
1,1,1
'''
    if safe:
        s += '*Surface Interaction, name=General\n*Friction\n0.2\n*Surface Behavior, pressure-overclosure=HARD\n'
    s += '*Step, name=Step-1\n*Dynamic, Explicit\n, .01\n'
    if general:
        s += '''*Contact, op=NEW
*Contact Inclusions
Surf-1, Surf-1
*Contact Property Assignment
 , , Cohesion
*Surface Property Assignment, property=THICKNESS
Surf-1, .001
'''
    return s + '*End Step\n'


def _run(tmp_path, text, **kwargs):
    source, out = tmp_path / 'source.inp', tmp_path / 'out.inp'
    source.write_text(text)
    meta = write_plywise_deck(source, out, plies=3, plate_node_contact=True,
                              ball_instance='Ball-1', **kwargs)
    return out.read_text(), meta, parse_deck(out)


def _set_entries(text, set_name):
    entries = {}
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(f'*Nset, nset={set_name}, instance='):
            instance = line.split('instance=', 1)[1]
            values = []
            for data in lines[i + 1:]:
                if data.startswith('*'):
                    break
                values.extend(int(x.strip()) for x in data.split(',') if x.strip())
            entries[instance] = values
    return entries


@pytest.mark.parametrize('general,safe', [(False, False), (True, True)])
def test_all_plies_noncohesive_and_limited_inclusions(tmp_path, general, safe):
    text, meta, deck = _run(tmp_path, _source(general=general, safe=safe))
    assert len(deck.instances) == 4
    assert meta['ball_contact']['plate_node_count'] == 24
    assert _set_entries(text, 'EMBMESH_PLATE_ALL_NODES') == {
        f'Ply-{k}': list(range(1, 9)) for k in range(1, 4)}
    assert meta['ball_contact']['interaction'] == ('General' if safe else 'EMBMESH_CONTACT')
    assert meta['ball_contact']['inclusion_pairs'] == [('EMBMESH_PLATE_NODES', 'EMBMESH_BALL_SURF')]
    active = [line.strip() for line in text.splitlines() if not line.startswith('**')]
    assert 'Surf-1, Surf-1' not in active
    assert ' , , Cohesion' not in active
    assert all('Ply-' not in line for line in active if 'EMBMESH_BALL_SURF' in line)
    assert any('Surf-1' in x for x in meta['ball_contact']['removed_old_references'])
    assert any('Surf-1' in x for x in meta['ball_contact']['removed_old_references'])


def test_explicit_cohesive_interaction_rejected(tmp_path):
    with pytest.raises(ValueError, match='Cohesive Behavior'):
        _run(tmp_path, _source(), ball_interaction='Cohesion')


def test_fiber_refs_and_node_contact_off_warning(tmp_path):
    refs = [FiberInstanceRef('Fibers-0-1', (11, 12)), FiberInstanceRef('Fibers-90-2', (11, 12))]
    text, meta, _ = _run(tmp_path, _source(fiber=True), fiber_node_contact=True,
                         fiber_instances=refs)
    assert meta['ball_contact']['fiber_node_count'] == 4
    assert _set_entries(text, 'EMBMESH_FIBER_ALL_NODES') == {
        ref.instance: [11, 12] for ref in refs}
    assert meta['ball_contact']['fiber_median_segment_length'] == pytest.approx(1)
    assert ('EMBMESH_FIBER_NODES', 'EMBMESH_BALL_SURF') in meta['ball_contact']['inclusion_pairs']
    source, out = tmp_path / 'source.inp', tmp_path / 'off.inp'
    meta = write_plywise_deck(source, out, plies=3)
    assert '*Surface, type=ELEMENT, name=Surf-1' in out.read_text()
    assert 'UNRESOLVABLE DECK' in meta['warnings'][0]
