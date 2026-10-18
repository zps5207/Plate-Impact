from pathlib import Path
import sys
import pytest

_T035_DIR = Path(__file__).resolve().parent.parent
if str(_T035_DIR) not in sys.path:
    sys.path.insert(0, str(_T035_DIR))

# Ensure delivered version of embmesh_desktop is used
import embmesh_desktop
if hasattr(embmesh_desktop, '__file__') and str(_T035_DIR) not in str(Path(embmesh_desktop.__file__).resolve()):
    import importlib
    embmesh_desktop = importlib.reload(embmesh_desktop)

from embmesh_desktop import (
    DesktopApp,
    build_plywise_command,
    list_surface_interactions,
    compute_cohesive_readout,
    EXISTING_DECK_INTERACTION,
)


ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / 'Meshing').exists():
    ROOT = Path(__file__).resolve().parents[5]


def values(tmp_path):
    deck = tmp_path / 'source.inp'
    deck.write_text('*Heading\n')
    return dict(engine='embmesh.exe', deck=str(deck), instance='Plate-1', output=str(tmp_path),
                plies='4', ply_thickness='', layup='0,90,45,-45', layup_repeat='1',
                fiber_diameter='0.0005', fiber_gap='0', fiber_type='truss', fiber_material='Fiber',
                cohesion=True, cohesion_interaction='Cohesion', 
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


def test_preset_ballistic_mm_command(tmp_path):
    v = values(tmp_path)
    v.update(
        cohesive_material='dyneema-hb26',
        cohesive_rate='ballistic',
        length_units='mm',
        cohesive_name='Cohesion_Preset',
    )
    args = build_plywise_command(v)
    assert args[args.index('--cohesive-material') + 1] == 'dyneema-hb26'
    assert args[args.index('--cohesive-rate') + 1] == 'ballistic'
    assert args[args.index('--length-units') + 1] == 'mm'
    assert args[args.index('--cohesive-name') + 1] == 'Cohesion_Preset'
    assert '--cohesive-overwrite' in args
    assert '--cohesion' not in args


def test_preset_label_command(tmp_path):
    v = values(tmp_path)
    v.update(
        cohesive_material='Dyneema HB26 (Hazzard et al. 2018)',
        cohesive_rate='quasi-static',
        length_units='m',
    )
    args = build_plywise_command(v)
    assert args[args.index('--cohesive-material') + 1] == 'dyneema-hb26'
    assert args[args.index('--cohesive-rate') + 1] == 'quasi-static'
    assert args[args.index('--length-units') + 1] == 'm'
    assert '--cohesive-overwrite' in args
    assert '--cohesion' not in args


def test_existing_interaction_mode_unchanged(tmp_path):
    v = values(tmp_path)
    v.update(
        cohesion=True,
        cohesion_interaction='Cohesion',
        
        cohesive_material=EXISTING_DECK_INTERACTION,
    )
    args = build_plywise_command(v)
    assert args[args.index('--cohesion') + 1] == 'Cohesion'
    assert '--cohesion-slave' not in args
    assert '--cohesive-material' not in args
    assert '--cohesive-overwrite' not in args


def test_collapse_layers_flag(tmp_path):
    v = values(tmp_path)
    assert '--collapse-layers' not in build_plywise_command(v)
    v['collapse_layers'] = True
    assert '--collapse-layers' in build_plywise_command(v)


def test_host_mode_flags(tmp_path):
    v = values(tmp_path)
    # Native is default (no flag emitted)
    args_native = build_plywise_command(v)
    assert '--host-mode' not in args_native
    assert '--ghost-scale' not in args_native

    # VUEL + ghost emits --host-mode and --ghost-scale
    v.update(host_mode='vuel-ghost', ghost_scale='1e-4')
    args_vuel = build_plywise_command(v)
    assert args_vuel[args_vuel.index('--host-mode') + 1] == 'vuel-ghost'
    assert args_vuel[args_vuel.index('--ghost-scale') + 1] == '1e-4'

    # Also accepts display label 'VUEL + ghost'
    v['host_mode'] = 'VUEL + ghost'
    args_vuel2 = build_plywise_command(v)
    assert args_vuel2[args_vuel2.index('--host-mode') + 1] == 'vuel-ghost'

    # Ghost scale validation: strictly 0 < x < 1
    v['ghost_scale'] = '0'
    with pytest.raises(ValueError, match='Ghost scale'):
        build_plywise_command(v)
    v['ghost_scale'] = '1'
    with pytest.raises(ValueError, match='Ghost scale'):
        build_plywise_command(v)
    v['ghost_scale'] = '-0.1'
    with pytest.raises(ValueError, match='Ghost scale'):
        build_plywise_command(v)
    v['ghost_scale'] = 'invalid'
    with pytest.raises(ValueError, match='Ghost scale'):
        build_plywise_command(v)

    # Unknown host mode
    v.update(host_mode='invalid_mode', ghost_scale='1e-4')
    with pytest.raises(ValueError, match='Unknown host mode'):
        build_plywise_command(v)


def test_live_readout_values():
    # 1 mm ply in mm units: equals Table 5 (K_I 60, K_II 36 N/mm^3)
    res_mm = compute_cohesive_readout('dyneema-hb26', 1.0, units='mm', rate='quasi-static')
    assert res_mm['k_i_mm'] == pytest.approx(60.0)
    assert res_mm['k_ii_mm'] == pytest.approx(36.0)
    assert res_mm['k_i_deck'] == pytest.approx(60.0)
    assert res_mm['k_ii_deck'] == pytest.approx(36.0)
    assert '60' in res_mm['display']
    assert '36' in res_mm['display']

    # 0.1375 mm ply in m units: gives 4.36e11 / 2.62e11
    res_m = compute_cohesive_readout('dyneema-hb26', 0.1375e-3, units='m', rate='quasi-static')
    assert res_m['k_i_deck'] == pytest.approx(4.36e11, rel=1e-3)
    assert res_m['k_ii_deck'] == pytest.approx(2.62e11, rel=1e-3)
    assert '4.36e11' in res_m['display']
    assert '2.62e11' in res_m['display']


@pytest.mark.parametrize('changes,match', [
    ({'cohesive_material': 'unknown'}, 'Unknown cohesive material'),
    ({'cohesive_material': 'dyneema-hb26', 'length_units': 'inches'}, 'Length units'),
    ({'cohesive_material': 'dyneema-hb26', 'cohesive_rate': 'hypersonic'}, 'Cohesive rate'),
])
def test_cohesive_validation(tmp_path, changes, match):
    v = values(tmp_path)
    v.update(changes)
    with pytest.raises(ValueError, match=match):
        build_plywise_command(v)


def test_tk_smoke_test_toggles_new_controls(tmp_path):
    import tkinter as tk
    import embmesh_desktop as desktop
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip('No Tk display')
    root.withdraw()
    try:
        app = desktop.DesktopApp(root)
        app.plywise.set(True)
        app._update_plywise_controls()

        # Toggle collapse
        assert not app.collapse_layers.get()
        app.collapse_layers.set(True)
        assert app.collapse_layers.get()

        # Toggle host mode
        assert app.host_mode.get() == 'native'
        app.host_mode.set('vuel-ghost')
        app._update_host_mode_controls()
        assert app.ghost_scale_frame.winfo_manager() == 'pack'
        app.host_mode.set('native')
        app._update_host_mode_controls()
        assert app.ghost_scale_frame.winfo_manager() == ''

        # Cohesive material controls
        app.cohesion.set(True)
        app.cohesive_material.set('Dyneema HB26 (Hazzard et al. 2018)')
        app._update_cohesive_controls()

        # Readout with thickness mode: 1 mm in mm units -> 60 and 36
        app.ply_mode.set('thickness')
        app.ply_thickness.set('1.0')
        app.length_units.set('mm')
        app._update_cohesive_readout()
        assert '60' in app.cohesive_readout.get()
        assert '36' in app.cohesive_readout.get()

        # Readout with m units: 0.1375 mm in m units -> 4.36e11 and 2.62e11
        app.ply_thickness.set('0.0001375')
        app.length_units.set('m')
        app._update_cohesive_readout()
        assert '4.36e11' in app.cohesive_readout.get()
        assert '2.62e11' in app.cohesive_readout.get()

        # When thickness unknown
        app.ply_thickness.set('')
        app.deck.set('')
        app._update_cohesive_readout()
        assert 'enter a ply thickness or load a deck' in app.cohesive_readout.get()

        # Readout with plies mode and loaded deck
        curved_ball = ROOT / 'Meshing' / 'plate1hex_curved_ball.inp'
        if curved_ball.exists():
            app.deck.set(str(curved_ball))
            app.instance.set('Plate-1')
            app.ply_mode.set('plies')
            app.plies.set('4')
            app.length_units.set('m')
            app._update_cohesive_readout()
            assert 'K_I' in app.cohesive_readout.get()
            assert 'enter a ply thickness or load a deck' not in app.cohesive_readout.get()
    finally:
        root.destroy()
