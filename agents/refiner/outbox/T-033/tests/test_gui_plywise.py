from pathlib import Path

import pytest

from embmesh_desktop import DesktopApp, build_plywise_command, list_surface_interactions


ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'Meshing').exists():
    ROOT = Path(__file__).resolve().parents[5]


def values(tmp_path):
    deck = tmp_path / 'source.inp'
    deck.write_text('*Heading\n')
    return dict(engine='embmesh.exe', deck=str(deck), instance='Plate-1', output=str(tmp_path),
                plies='4', ply_thickness='', layup='0,90,45,-45', layup_repeat='1',
                fiber_diameter='0.0005', fiber_gap='0', fiber_type='truss', fiber_material='Fiber',
                cohesion=True, cohesion_interaction='Cohesion', cohesion_slave='lower',
                plate_node_contact=True, fiber_node_contact=True, ball_instance='Ball-1',
                contact_thickness='auto', ball_interaction='General')


def test_full_plywise_command(tmp_path):
    args = build_plywise_command(values(tmp_path))
    assert args[:4] == ['embmesh.exe', 'plywise', str(tmp_path / 'source.inp'), '--instance']
    for flag in ('--plies', '--layup', '--fiber-diameter', '--cohesion',
                 '--plate-node-contact', '--fiber-node-contact', '--ball-instance',
                 '--ball-interaction', '--preview'):
        assert flag in args
    assert args[args.index('--output') + 1] == str(tmp_path / 'output.inp')


def test_thickness_symmetric_repeat(tmp_path):
    v = values(tmp_path)
    v.update(plies='', ply_thickness='0.002', resolved_plies=4, layup='0,90',
             layup_symmetric=True)
    args = build_plywise_command(v)
    assert args[args.index('--ply-thickness') + 1] == '0.002'
    assert '--layup-symmetric' in args
    assert '--plies' not in args


def test_no_layup(tmp_path):
    v = values(tmp_path)
    v.update(layup='', fiber_diameter='', cohesion=False)
    args = build_plywise_command(v)
    assert '--layup' not in args and '--fiber-diameter' not in args
    assert '--plate-node-contact' in args


@pytest.mark.parametrize('changes,match', [
    ({'layup': 'bad'}, 'Layup'),
    ({'fiber_diameter': ''}, 'Fiber diameter'),
    ({'plies': '', 'ply_thickness': ''}, 'either ply count'),
    ({'plies': '4', 'ply_thickness': '.002'}, 'either ply count'),
    ({'plies': '0'}, 'Ply count'),
    ({'plies': '3'}, 'expanded layup'),
    ({'plies': '', 'ply_thickness': '-1'}, 'Ply thickness'),
])
def test_validation(tmp_path, changes, match):
    v = values(tmp_path)
    v.update(changes)
    with pytest.raises(ValueError, match=match):
        build_plywise_command(v)


def test_surface_interactions_in_stack():
    interactions = list_surface_interactions(ROOT / 'Meshing' / 'stack.inp')
    assert ('Cohesion', True) in interactions
    assert ('General', False) in interactions


def test_non_plywise_argument_list_unchanged(tmp_path, monkeypatch):
    import tkinter as tk
    import embmesh_desktop as desktop
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('No Tk display')
    root.withdraw()
    try:
        app = DesktopApp(root)
        deck = tmp_path / 'source.inp'
        deck.write_text('*Heading\n')
        app.deck.set(str(deck))
        app.instance.set('Plate-1')
        app.output.set(str(tmp_path))
        app.diameter.set('0.25')
        app.gap.set('0')
        monkeypatch.setattr(desktop, 'engine_path', lambda: Path('embmesh.exe'))
        captured = []
        monkeypatch.setattr(app, '_start_command', lambda command, plywise: captured.append((command, plywise)))
        app.run_mesh()
        assert captured == [(['embmesh.exe', 'visualize', str(deck), '--instance', 'Plate-1',
                             '--diameter', '0.25', '--output', str(tmp_path), '--gap', '0',
                             '--fiber-type', 'truss', '--preview'], False)]
        app.plywise.set(True)
        app._update_plywise_controls()
        assert app.ply_frame.grid_info()
    finally:
        root.destroy()
