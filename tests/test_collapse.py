"""Tests for multi-layer hex collapse and plywise integration (T-036)."""
from __future__ import annotations

import copy
from pathlib import Path
import pytest
import numpy as np

import sys
# Ensure outbox/T-036 modules are prioritized
_T036_DIR = Path(__file__).resolve().parent.parent
if str(_T036_DIR) not in sys.path:
    sys.path.insert(0, str(_T036_DIR))

import embmesh
_t036_embmesh = str(_T036_DIR / 'embmesh')
if _t036_embmesh not in embmesh.__path__:
    embmesh.__path__.insert(0, _t036_embmesh)

# If plywise was already imported, reload it from outbox/T-036
if 'embmesh.plywise' in sys.modules:
    import importlib
    importlib.reload(sys.modules['embmesh.plywise'])

from embmesh.collapse import collapse_layers, collapse_deck_text, collapse_deck
from embmesh.plywise import write_plywise_deck, EmbmeshError
from embmesh.parser import parse_deck
from embmesh.model import Part, Element, Deck, Instance
from embmesh.geometry import HEX_FACES, hex_volume


def _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5):
    """Create a conforming multi-layer flat plate deck."""
    nodes = {}
    node_id = 1
    node_grid = {}
    for j in range(ny + 1):
        for k in range(nz + 1):
            for i in range(nx + 1):
                nodes[node_id] = np.array([i * dx, j * dy, k * dz], float)
                node_grid[(i, j, k)] = node_id
                node_id += 1

    elements = {}
    elem_id = 1
    for j in range(ny):
        for k in range(nz):
            for i in range(nx):
                # Standard Abaqus C3D8 connectivity:
                # bottom face (zeta=-1, y=j*dy): n0, n1, n2, n3
                # top face (zeta=+1, y=(j+1)*dy): n4, n5, n6, n7
                c = (
                    node_grid[(i, j, k)],
                    node_grid[(i + 1, j, k)],
                    node_grid[(i + 1, j, k + 1)],
                    node_grid[(i, j, k + 1)],
                    node_grid[(i, j + 1, k)],
                    node_grid[(i + 1, j + 1, k)],
                    node_grid[(i + 1, j + 1, k + 1)],
                    node_grid[(i, j + 1, k + 1)],
                )
                elements[elem_id] = Element(elem_id, c, 'C3D8R')
                elem_id += 1

    part = Part('Plate', nodes=nodes, elements=elements)
    deck = Deck()
    deck.parts['Plate'] = part
    deck.instances['Plate-1'] = Instance('Plate-1', 'Plate')
    return deck, node_grid


def _deck_to_lines(deck: Deck, plate_sets=True) -> list[str]:
    lines = ['*Heading', '** synthetic test deck', '*Part, name=Plate', '*Node']
    part = deck.parts['Plate']
    for nid, p in sorted(part.nodes.items()):
        lines.append(f'{nid}, {p[0]:.17g}, {p[1]:.17g}, {p[2]:.17g}')
    lines.append('*Element, type=C3D8R')
    for eid, elem in sorted(part.elements.items()):
        lines.append(f'{eid}, ' + ', '.join(map(str, elem.connectivity)))
    if plate_sets:
        lines.append('*Nset, nset=Plate, generate')
        lines.append(f'1, {len(part.nodes)}, 1')
        lines.append('*Elset, elset=Plate, generate')
        lines.append(f'1, {len(part.elements)}, 1')
        lines.append('*Solid Section, elset=Plate, material=Matrix')
        lines.append(',')
    lines.append('*End Part')

    # Add Ball part
    lines.append('*Part, name=Ball')
    lines.append('*Node')
    lines.append('1, 0.0, -1.0, 0.0')
    lines.append('2, 1.0, -1.0, 0.0')
    lines.append('3, 1.0, -1.0, 1.0')
    lines.append('4, 0.0, -1.0, 1.0')
    lines.append('5, 0.0, -0.5, 0.0')
    lines.append('6, 1.0, -0.5, 0.0')
    lines.append('7, 1.0, -0.5, 1.0')
    lines.append('8, 0.0, -0.5, 1.0')
    lines.append('*Element, type=C3D8R')
    lines.append('1, 1, 2, 3, 4, 5, 6, 7, 8')
    lines.append('*Nset, nset=Ball, generate')
    lines.append('1, 8, 1')
    lines.append('*Elset, elset=Ball')
    lines.append('1')
    lines.append('*Solid Section, elset=Ball, material=Steel')
    lines.append(',')
    lines.append('*End Part')

    lines.append('*Assembly, name=Assembly')
    lines.append('*Instance, name=Plate-1, part=Plate')
    lines.append('0., 0., 0.')
    lines.append('*End Instance')
    lines.append('*Instance, name=Ball-1, part=Ball')
    lines.append('0., 0., 0.')
    lines.append('*End Instance')

    if plate_sets:
        # Assembly sets on Plate-1
        # X-boundary nodes
        x0_nodes = [nid for nid, p in part.nodes.items() if abs(p[0]) < 1e-6]
        lines.append('*Nset, nset=X, instance=Plate-1')
        for i in range(0, len(x0_nodes), 16):
            lines.append(', '.join(map(str, x0_nodes[i:i + 16])))
        lines.append('*Elset, elset=plate, instance=Plate-1, generate')
        lines.append(f'1, {len(part.elements)}, 1')

        # Top surface S2 (high Y) and side surface S3
        top_y = max(p[1] for p in part.nodes.values())
        top_elems = [e.label for e in part.elements.values()
                     if all(part.nodes[n][1] > top_y - 0.55 for n in e.connectivity[4:8])]
        lines.append('*Elset, elset=_Surf-1_S2, internal, instance=Plate-1')
        lines.append(', '.join(map(str, sorted(top_elems))))

        # Side face on bottom layer only
        bot_elems = [e.label for e in part.elements.values()
                     if any(part.nodes[n][1] < 0.05 for n in e.connectivity[:4])]
        lines.append('*Elset, elset=_Surf-1_S3, internal, instance=Plate-1')
        lines.append(', '.join(map(str, sorted(bot_elems))))

        lines.append('*Surface, type=ELEMENT, name=Surf-1')
        lines.append('_Surf-1_S2, S2')
        lines.append('_Surf-1_S3, S3')

    # Ball surface
    lines.append('*Elset, elset=_Surf-2_S1, internal, instance=Ball-1')
    lines.append('1')
    lines.append('*Surface, type=ELEMENT, name=Surf-2')
    lines.append('_Surf-2_S1, S1')

    lines.append('*End Assembly')
    lines.append('*Material, name=Matrix')
    lines.append('*Density')
    lines.append('1000.,')
    lines.append('*Elastic')
    lines.append('3.0e9, 0.3')
    lines.append('*Step, name=Step-1')
    lines.append('*Dynamic, Explicit')
    lines.append(', 1.0e-4')
    lines.append('*End Step')
    return lines


def test_synthetic_flat_plate_5_layers():
    """Verify a synthetic 5-layer flat plate collapses to 1 layer with matching nodes."""
    deck, node_grid = _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5)
    part = deck.parts['Plate']
    assert len(part.elements) == 20
    assert len(part.nodes) == 54

    new_part, report = collapse_layers(deck, 'Plate-1', thickness_axis='y')

    assert report['columns'] == 4
    assert report['layers_per_column_min'] == 5
    assert report['layers_per_column_max'] == 5
    assert len(new_part.elements) == 4
    assert len(new_part.nodes) == 18  # 9 bottom nodes + 9 top nodes
    assert report['volume_ratio'] == pytest.approx(1.0, rel=1e-9)
    assert report['residual_max'] < 1e-12

    # Check top/bottom node matching
    for elem in new_part.elements.values():
        for n in elem.connectivity[:4]:
            assert abs(new_part.nodes[n][1] - 0.0) < 1e-12
        for n in elem.connectivity[4:]:
            assert abs(new_part.nodes[n][1] - 2.5) < 1e-12


def test_synthetic_curved_translation_stack():
    """Verify a synthetic curved translation stack collapses to 1 layer with matching nodes."""
    # Build 3x3 curved surface in X-Z: y = 0.05*(x^2 + z^2), translated 4 layers along Y
    nx, nz, ny = 3, 3, 4
    dy = 0.25
    nodes = {}
    node_grid = {}
    node_id = 1
    for j in range(ny + 1):
        for k in range(nz + 1):
            for i in range(nx + 1):
                x = (i - 1.5) * 1.0
                z = (k - 1.5) * 1.0
                base_y = 0.05 * (x**2 + z**2)
                y = base_y + j * dy
                nodes[node_id] = np.array([x, y, z], float)
                node_grid[(i, j, k)] = node_id
                node_id += 1

    elements = {}
    elem_id = 1
    for j in range(ny):
        for k in range(nz):
            for i in range(nx):
                c = (
                    node_grid[(i, j, k)],
                    node_grid[(i + 1, j, k)],
                    node_grid[(i + 1, j, k + 1)],
                    node_grid[(i, j, k + 1)],
                    node_grid[(i, j + 1, k)],
                    node_grid[(i + 1, j + 1, k)],
                    node_grid[(i + 1, j + 1, k + 1)],
                    node_grid[(i, j + 1, k + 1)],
                )
                elements[elem_id] = Element(elem_id, c, 'C3D8R')
                elem_id += 1

    part = Part('Plate', nodes=nodes, elements=elements)
    deck = Deck()
    deck.parts['Plate'] = part
    deck.instances['Plate-1'] = Instance('Plate-1', 'Plate')

    new_part, report = collapse_layers(deck, 'Plate-1', thickness_axis='y')

    assert report['columns'] == 9
    assert report['layers_per_column_min'] == 4
    assert report['layers_per_column_max'] == 4
    assert len(new_part.elements) == 9
    assert len(new_part.nodes) == 32  # 16 bottom + 16 top
    assert report['volume_ratio'] == pytest.approx(1.0, rel=1e-8)
    assert report['residual_max'] < 1e-12

    # Verify each collapsed element's top face is exactly translated by 4*dy = 1.0
    for elem in new_part.elements.values():
        c = elem.connectivity
        for i in range(4):
            bot_pos = new_part.nodes[c[i]]
            top_pos = new_part.nodes[c[i + 4]]
            assert np.allclose(top_pos - bot_pos, [0.0, 1.0, 0.0], atol=1e-12)


def test_scrambled_hex_node_ordering():
    """Verify scrambled hex node ordering yields identical collapse."""
    deck, _ = _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5)
    orig_part, orig_report = collapse_layers(deck, 'Plate-1', thickness_axis='y')

    # Scramble elements: rotate the bottom face cyclic ordering (valid C3D8 orientation)
    # Rotating bottom face by 1: (0, 1, 2, 3) -> (1, 2, 3, 0), top face (4, 5, 6, 7) -> (5, 6, 7, 4)
    scrambled_deck = copy.deepcopy(deck)
    part = scrambled_deck.parts['Plate']
    for eid, elem in list(part.elements.items()):
        c = elem.connectivity
        if eid % 2 == 0:
            new_c = (c[1], c[2], c[3], c[0], c[5], c[6], c[7], c[4])
        else:
            new_c = (c[2], c[3], c[0], c[1], c[6], c[7], c[4], c[5])
        part.elements[eid] = Element(eid, new_c, elem.type)

    scrambled_part, scrambled_report = collapse_layers(scrambled_deck, 'Plate-1', thickness_axis='y')

    assert scrambled_report['columns'] == orig_report['columns']
    assert scrambled_report['layers_per_column_min'] == orig_report['layers_per_column_min']
    assert scrambled_report['volume_ratio'] == pytest.approx(orig_report['volume_ratio'], abs=1e-12)
    assert set(scrambled_part.nodes.keys()) == set(orig_part.nodes.keys())
    assert len(scrambled_part.elements) == len(orig_part.elements)


def test_non_uniform_layer_counts_raise():
    """Verify non-uniform layer counts across columns raise EmbmeshError."""
    deck, _ = _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5)
    part = deck.parts['Plate']
    # Delete element 1 (bottom element of first column), so col 0 starts at layer 2 (4 layers)
    del part.elements[1]

    with pytest.raises(EmbmeshError, match="Non-uniform layer count"):
        collapse_layers(deck, 'Plate-1', thickness_axis='y')


def test_sets_and_surfaces_rewritten_no_dangling_labels(tmp_path):
    """Verify sets and surfaces are rewritten without dangling labels and Ball is preserved."""
    deck, _ = _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5)
    lines = _deck_to_lines(deck, plate_sets=True)

    deck_parsed = parse_deck('\n'.join(lines))
    new_lines, report = collapse_deck_text(lines, deck_parsed, 'Plate-1', thickness_axis='y')

    # Verify Ball part and Ball-1 instance untouched
    ball_part_lines = [l for l in new_lines if '*part, name=ball' in l.lower()]
    assert len(ball_part_lines) == 1
    ball_inst_lines = [l for l in new_lines if '*instance, name=ball-1' in l.lower()]
    assert len(ball_inst_lines) == 1

    # Verify side faces dropped and top face survived
    assert report['dropped_side_faces']['Surf-1'] > 0
    assert report['surviving_faces']['Surf-1']['S2'] == 4

    # Re-parse the written text
    reparsed = parse_deck('\n'.join(new_lines))
    plate_part = reparsed.parts['Plate']
    assert len(plate_part.elements) == 4
    assert len(plate_part.nodes) == 18

    # Verify no dangling node references in Part sets
    surviving_nodes = set(plate_part.nodes.keys())
    for sname, nset in plate_part.nsets.items():
        assert set(nset).issubset(surviving_nodes), f"dangling nodes in nset {sname}"

    # Verify no dangling element references in Part sets
    surviving_elems = set(plate_part.elements.keys())
    for sname, elset in plate_part.elsets.items():
        assert set(elset).issubset(surviving_elems), f"dangling elements in elset {sname}"


def test_round_trip_through_embmesh_parser(tmp_path):
    """Verify collapsed deck written to file round-trips cleanly through parse_deck."""
    deck, _ = _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5)
    lines = _deck_to_lines(deck, plate_sets=True)
    src_path = tmp_path / 'multi_layer.inp'
    src_path.write_text('\n'.join(lines) + '\n')

    out_path = tmp_path / 'collapsed.inp'
    report = collapse_deck(src_path, out_path, instance='Plate-1', thickness_axis='y')

    assert out_path.exists()
    reparsed = parse_deck(out_path)
    assert 'Plate-1' in reparsed.instances
    assert 'Ball-1' in reparsed.instances
    assert len(reparsed.parts['Plate'].elements) == 4
    assert report['columns'] == 4
    assert report['volume_ratio'] == pytest.approx(1.0, rel=1e-9)


def test_plywise_pipeline_with_collapse_layers(tmp_path):
    """Verify write_plywise_deck with --collapse-layers runs end-to-end into plies."""
    deck, _ = _create_synthetic_flat_plate(nx=2, nz=2, ny=5, dx=1.0, dz=1.0, dy=0.5)
    lines = _deck_to_lines(deck, plate_sets=True)
    src_path = tmp_path / 'multi_layer.inp'
    src_path.write_text('\n'.join(lines) + '\n')

    out_path = tmp_path / 'plywise_output.inp'
    meta = write_plywise_deck(
        source=src_path,
        output=out_path,
        instance='Plate-1',
        plies=3,
        thickness_axis='y',
        collapse_layers=True,
    )

    assert meta['plies'] == 3
    assert 'collapse' in meta
    assert meta['collapse']['columns'] == 4
    assert meta['collapse']['layers_per_column_min'] == 5
    assert meta['collapse']['layers_per_column_max'] == 5
    assert meta['collapse']['volume_ratio'] == pytest.approx(1.0, rel=1e-9)

    out_deck = parse_deck(out_path)
    assert 'Ply-1' in out_deck.instances
    assert 'Ply-2' in out_deck.instances
    assert 'Ply-3' in out_deck.instances
    assert 'Ball-1' in out_deck.instances

    # Check interface coincidence: exactly 0.0 gap between adjacent plies
    step = np.asarray(meta['step'])
    ply_nodes = out_deck.parts['Plate'].nodes
    for elem in out_deck.parts['Plate'].elements.values():
        c = elem.connectivity
        for i in range(4):
            # bottom node translated by 1 ply step matches top node
            p_bot_plus_step = ply_nodes[c[i]] + step
            p_top = ply_nodes[c[i + 4]]
            assert np.allclose(p_bot_plus_step, p_top, atol=1e-12)


def test_invalid_mesh_inputs_raise():
    """Verify empty or non-C3D8 mesh raises EmbmeshError."""
    empty_part = Part('Empty', nodes={}, elements={})
    deck = Deck()
    deck.parts['Empty'] = empty_part
    deck.instances['Empty-1'] = Instance('Empty-1', 'Empty')

    with pytest.raises(EmbmeshError, match="has no hex mesh"):
        collapse_layers(deck, 'Empty-1')

    # Non-C3D8 element
    tet_part = Part('Tet', nodes={1: np.zeros(3)}, elements={1: Element(1, (1, 1, 1, 1), 'C3D4')})
    deck2 = Deck()
    deck2.parts['Tet'] = tet_part
    deck2.instances['Tet-1'] = Instance('Tet-1', 'Tet')

    with pytest.raises(EmbmeshError, match="not a C3D8 hex"):
        collapse_layers(deck2, 'Tet-1')
