import importlib.util
from pathlib import Path
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import embmesh

# Load delivered plywise and cli
_outbox_t034 = Path(__file__).resolve().parent.parent
_plywise_path = _outbox_t034 / "embmesh" / "plywise.py"
_spec_pw = importlib.util.spec_from_file_location("embmesh.plywise", str(_plywise_path))
_mod_pw = importlib.util.module_from_spec(_spec_pw)
sys.modules["embmesh.plywise"] = _mod_pw
_spec_pw.loader.exec_module(_mod_pw)

_cli_path = _outbox_t034 / "embmesh" / "cli.py"
_spec_cli = importlib.util.spec_from_file_location("embmesh.cli", str(_cli_path))
_mod_cli = importlib.util.module_from_spec(_spec_cli)
sys.modules["embmesh.cli"] = _mod_cli
_spec_cli.loader.exec_module(_mod_cli)

from embmesh.plywise import write_plywise_deck, EmbmeshError
from embmesh.parser import parse_deck
from embmesh.plywise_contact import _interactions
from embmesh.errors import MesherInputError

CURVED_BALL_DECK = REPO_ROOT / "Meshing" / "plate1hex_curved_ball.inp"


def synthetic_one_hex_deck(thickness=0.01, with_cohesion=False, with_material=True):
    t = float(thickness)
    lines = [
        "*Heading",
        "** Synthetic 1-hex plate deck",
        "*Part, name=Plate",
        "*Node",
        "1, 0., 0., 0.",
        "2, 1., 0., 0.",
        "3, 1., 1., 0.",
        "4, 0., 1., 0.",
        f"5, 0., 0., {t:.17g}",
        f"6, 1., 0., {t:.17g}",
        f"7, 1., 1., {t:.17g}",
        f"8, 0., 1., {t:.17g}",
        "*Element, type=C3D8R",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*Elset, elset=Plate",
        "1",
        "*Solid Section, elset=Plate, material=Matrix",
        ",",
        "*End Part",
        "*Assembly, name=Assembly",
        "*Instance, name=Plate-1, part=Plate",
        "*End Instance",
        "*End Assembly",
    ]
    if with_material:
        lines += [
            "*Material, name=Matrix",
            "*Elastic",
            "1000., 0.3",
        ]
    if with_cohesion:
        lines += [
            "** INTERACTION PROPERTIES",
            "*Surface Interaction, name=Cohesion",
            "*Cohesive Behavior",
            " 100., 60., 60.",
            "*Damage Initiation, criterion=MAXS",
            " 1.0, 1.0, 1.0",
            "*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1.",
            " 0.5, 1.0, 1.0",
        ]
    lines += [
        "*Step, name=Step-1, nlgeom=YES",
        "*Dynamic, Explicit",
        ", 7e-05",
        "** INTERACTIONS",
        "** OUTPUT REQUESTS",
        "*Output, field",
        "*End Step",
    ]
    return "\n".join(lines) + "\n"


def test_table5_one_mm_in_mm_units(tmp_path):
    # 1 mm thick plate, 1 ply, mm units -> Table 5 values: K_I = 60, K_II = 36
    src = tmp_path / "plate_1mm.inp"
    src.write_text(synthetic_one_hex_deck(thickness=1.0))
    out = tmp_path / "out_1mm.inp"

    meta = write_plywise_deck(
        src, out, plies=1,
        cohesive_material="dyneema-hb26",
        length_units="mm",
    )
    assert meta["resulting_ply_thickness"] == pytest.approx(1.0)
    c_info = meta["cohesive_interaction"]
    assert c_info["units"] == "mm"
    assert c_info["k"] == pytest.approx([60.0, 36.0, 36.0])
    assert c_info["strength"] == pytest.approx([1.2, 1.8, 1.8])
    assert c_info["fracture_energy"] == pytest.approx([0.544, 1.088, 1.088])

    out_text = out.read_text()
    assert "*Surface Interaction, name=Cohesion_Hazzard2018" in out_text
    assert "*Cohesive Behavior\n 60, 36, 36" in out_text
    assert "*Damage Initiation, criterion=MAXS\n 1.2, 1.8, 1.8" in out_text
    assert "0.544, 1.088, 1.088" in out_text


def test_reproduces_stack_inp_for_01375_mm_ply_in_m_units(tmp_path):
    # Meshing/stack.inp has t = 0.1375 mm = 0.0001375 m
    t = 0.1375e-3
    src = tmp_path / "plate_sublam.inp"
    src.write_text(synthetic_one_hex_deck(thickness=t))
    out = tmp_path / "out_sublam.inp"

    meta = write_plywise_deck(
        src, out, plies=1,
        cohesive_material="dyneema-hb26",
        length_units="m",
        cohesive_name="Cohesion",
    )
    c_info = meta["cohesive_interaction"]
    assert c_info["units"] == "m"
    assert c_info["name"] == "Cohesion"
    # 4.36e11, 2.62e11, 1.2e6, 1.8e6, 544, 1088 to 3 sig figures
    assert c_info["k"][0] == pytest.approx(4.36e11, rel=1e-3)
    assert c_info["k"][1] == pytest.approx(2.62e11, rel=1e-3)
    assert c_info["k"][2] == pytest.approx(2.62e11, rel=1e-3)
    assert c_info["strength"] == pytest.approx([1.2e6, 1.8e6, 1.8e6])
    assert c_info["fracture_energy"] == pytest.approx([544.0, 1088.0, 1088.0])


def test_name_collision_and_overwrite(tmp_path):
    src = tmp_path / "plate_with_cohesion.inp"
    src.write_text(synthetic_one_hex_deck(thickness=0.01, with_cohesion=True))
    out = tmp_path / "out.inp"

    # Collision without overwrite raises clear error
    with pytest.raises((EmbmeshError, MesherInputError), match="already exists in deck"):
        write_plywise_deck(
            src, out, plies=2,
            cohesive_material="dyneema-hb26",
            cohesive_name="Cohesion",
            cohesive_overwrite=False,
        )

    # Collision with overwrite succeeds and replaces in place
    meta = write_plywise_deck(
        src, out, plies=2,
        cohesive_material="dyneema-hb26",
        cohesive_name="Cohesion",
        cohesive_overwrite=True,
    )
    assert meta["cohesion"]["interaction"] == "Cohesion"
    out_text = out.read_text()
    # Check only one Cohesion interaction definition exists
    assert out_text.count("*Surface Interaction, name=Cohesion") == 1
    # Check old stiffness (100, 60, 60) was replaced by new stiffness for 5 mm ply (1.2e10)
    assert "100., 60., 60." not in out_text


def test_block_lands_before_step_and_after_material(tmp_path):
    src = tmp_path / "plate.inp"
    src.write_text(synthetic_one_hex_deck(thickness=0.01, with_material=True))
    out = tmp_path / "out.inp"

    write_plywise_deck(
        src, out, plies=2,
        cohesive_material="dyneema-hb26",
    )
    lines = out.read_text().splitlines()
    inter_idx = next(i for i, l in enumerate(lines) if "*surface interaction, name=cohesion_hazzard2018" in l.lower())
    step_idx = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("*step"))
    mat_idx = max(i for i, l in enumerate(lines) if l.strip().lower().startswith("*material"))

    # Must be after last material and before first step
    assert mat_idx < inter_idx < step_idx


def test_contact_pairs_reference_generated_name(tmp_path):
    src = tmp_path / "plate.inp"
    src.write_text(synthetic_one_hex_deck(thickness=0.01))
    out = tmp_path / "out.inp"

    meta = write_plywise_deck(
        src, out, plies=3,
        cohesive_material="dyneema-hb26",
        cohesive_name="MyCohesivePreset",
    )
    assert meta["cohesion"]["interaction"] == "MyCohesivePreset"
    assert meta["cohesion"]["pairs"] == 2

    out_text = out.read_text()
    assert out_text.count("*Contact Pair, interaction=MyCohesivePreset") == 2
    assert "Ply-1_top, Ply-2_bottom" in out_text
    assert "Ply-2_top, Ply-3_bottom" in out_text


def test_unit_mismatch_warning(tmp_path):
    # 1.0 m thick ply in 'm' units (> 0.5) triggers warning
    src_m = tmp_path / "plate_large_m.inp"
    src_m.write_text(synthetic_one_hex_deck(thickness=1.0))
    meta_m = write_plywise_deck(
        src_m, tmp_path / "out_m.inp", plies=1,
        cohesive_material="dyneema-hb26",
        length_units="m",
    )
    assert any("> 0.5 in 'm' units mode" in w for w in meta_m["warnings"])

    # 0.0005 mm thick ply in 'mm' units (< 1e-3) triggers warning
    src_mm = tmp_path / "plate_tiny_mm.inp"
    src_mm.write_text(synthetic_one_hex_deck(thickness=0.0005))
    meta_mm = write_plywise_deck(
        src_mm, tmp_path / "out_mm.inp", plies=1,
        cohesive_material="dyneema-hb26",
        length_units="mm",
    )
    assert any("< 1e-3 in 'mm' units mode" in w for w in meta_mm["warnings"])


def test_written_deck_reparses(tmp_path):
    src = tmp_path / "plate.inp"
    src.write_text(synthetic_one_hex_deck(thickness=0.01))
    out = tmp_path / "out.inp"

    write_plywise_deck(
        src, out, plies=4,
        cohesive_material="dyneema-hb26",
    )
    parsed = parse_deck(out)
    assert "Plate" in parsed.parts
    assert len(parsed.instances) == 4
    for k in range(1, 5):
        assert f"Ply-{k}" in parsed.instances


@pytest.mark.skipif(not CURVED_BALL_DECK.exists(), reason="plate1hex_curved_ball.inp not found")
def test_ball_contact_avoids_generated_cohesive_interaction(tmp_path):
    out = tmp_path / "curved_ball_cohesive.inp"
    # plate1hex_curved_ball already has Cohesion; overwrite it with generated preset
    meta = write_plywise_deck(
        CURVED_BALL_DECK, out, plies=4,
        cohesive_material="dyneema-hb26",
        cohesive_name="Cohesion",
        cohesive_overwrite=True,
        plate_node_contact=True,
        ball_instance="Ball-1",
    )
    # Ball contact must NOT use Cohesion (which contains *Cohesive Behavior)
    assert meta["ball_contact"] is not None
    assert meta["ball_contact"]["interaction"] != "Cohesion"

    # Explicitly requesting Cohesion as ball interaction must raise error
    with pytest.raises(ValueError, match="contains \\*Cohesive Behavior"):
        write_plywise_deck(
            CURVED_BALL_DECK, tmp_path / "bad.inp", plies=4,
            cohesive_material="dyneema-hb26",
            cohesive_name="Cohesion",
            cohesive_overwrite=True,
            plate_node_contact=True,
            ball_instance="Ball-1",
            ball_interaction="Cohesion",
        )

    # _interactions must recognise generated Cohesion as cohesive (second element is True)
    lines = out.read_text().splitlines()
    inter_list = _interactions(lines)
    match = next(x for x in inter_list if x[0].lower() == "cohesion")
    assert match[1] is True, "Generated cohesive interaction must be recognized as cohesive by _interactions"
