import importlib.util
from pathlib import Path
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[5]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
import embmesh

_plycohesive_path = Path(__file__).resolve().parent.parent / "embmesh" / "plycohesive.py"
_spec = importlib.util.spec_from_file_location("embmesh.plycohesive", str(_plycohesive_path))
_mod = importlib.util.module_from_spec(_spec)
sys.modules["embmesh.plycohesive"] = _mod
_spec.loader.exec_module(_mod)

from embmesh.plycohesive import (
    cohesive_contact_lines,
    has_surface_interaction,
    insert_cohesive_contact,
    insert_cohesive_contact_into_deck,
)
from embmesh.errors import MesherInputError
from embmesh.plywise import interface_pairs
from embmesh.parser import parse_deck


def minimal_deck(interaction_name="Cohesion", has_step=True, has_interactions_comment=True):
    lines = [
        "*Heading",
        "** Test deck",
        "*Part, name=Plate",
        "*Node",
        "1, 0., 0., 0.",
        "2, 1., 0., 0.",
        "3, 1., 1., 0.",
        "4, 0., 1., 0.",
        "5, 0., 0., 1.",
        "6, 1., 0., 1.",
        "7, 1., 1., 1.",
        "8, 0., 1., 1.",
        "*Element, type=C3D8R",
        "1, 1, 2, 3, 4, 5, 6, 7, 8",
        "*End Part",
        "*Assembly, name=Assembly",
        "*Instance, name=Ply-1, part=Plate",
        "*End Instance",
        "*Instance, name=Ply-2, part=Plate",
        "0., 0., 1.",
        "*End Instance",
        "*Surface, type=ELEMENT, name=Ply-1_top",
        "Ply-1.1, S2",
        "*Surface, type=ELEMENT, name=Ply-2_bottom",
        "Ply-2.1, S1",
        "*End Assembly",
    ]
    if interaction_name:
        lines += [
            "** INTERACTION PROPERTIES",
            f"*Surface Interaction, name={interaction_name}",
            "*Cohesive Behavior",
            "4.36e+11, 2.62e+11, 2.62e+11",
            "*Damage Initiation, criterion=MAXS",
            "1.2e+06, 1.8e+06, 1.8e+06",
            "*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power=1.",
            "544., 1088., 1088.",
        ]
    if has_step:
        lines += [
            "*Step, name=Step-1, nlgeom=YES",
            "*Dynamic, Explicit",
            ", 7e-05",
        ]
        if has_interactions_comment:
            lines += [
                "** ",
                "** INTERACTIONS",
                "** ",
            ]
        lines += [
            "** OUTPUT REQUESTS",
            "*Output, field",
            "*Node Output",
            "U",
            "*End Step",
        ]
    return "\n".join(lines) + "\n"


def test_n_plies_gives_n_minus_1_pairs_and_surface_order():
    # 4 plies -> 3 interface pairs
    pairs = interface_pairs(4)
    assert pairs == [
        ("Ply-1_top", "Ply-2_bottom"),
        ("Ply-2_top", "Ply-3_bottom"),
        ("Ply-3_top", "Ply-4_bottom"),
    ]

    # Test default slave="lower"
    lines_lower = cohesive_contact_lines(pairs, interaction="Cohesion", slave="lower", unique_cpset=True)
    assert len([l for l in lines_lower if l.startswith("*Contact Pair")]) == 3
    assert "Ply-1_top, Ply-2_bottom" in lines_lower
    assert "Ply-2_top, Ply-3_bottom" in lines_lower
    assert "Ply-3_top, Ply-4_bottom" in lines_lower
    assert "*Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion_1" in lines_lower
    assert "*Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion_2" in lines_lower
    assert "*Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion_3" in lines_lower

    # Test slave="upper"
    lines_upper = cohesive_contact_lines(pairs, interaction="Cohesion", slave="upper", unique_cpset=True)
    assert "Ply-2_bottom, Ply-1_top" in lines_upper
    assert "Ply-3_bottom, Ply-2_top" in lines_upper
    assert "Ply-4_bottom, Ply-3_top" in lines_upper

    # Non-unique cpset
    lines_shared_cpset = cohesive_contact_lines(pairs, interaction="Cohesion", slave="lower", unique_cpset=False)
    assert "*Contact Pair, interaction=Cohesion, mechanical constraint=KINEMATIC, cpset=cohesion" in lines_shared_cpset

    # Invalid slave raises ValueError
    with pytest.raises(ValueError, match="slave must be 'lower' or 'upper'"):
        cohesive_contact_lines(pairs, slave="middle")


def test_missing_interaction_raises():
    deck = minimal_deck(interaction_name=None)
    pairs = [("Ply-1_top", "Ply-2_bottom")]
    with pytest.raises(MesherInputError, match="has no \\*Surface Interaction named 'Cohesion'"):
        insert_cohesive_contact(deck, pairs, interaction="Cohesion")

    deck_other = minimal_deck(interaction_name="OtherInteraction")
    with pytest.raises(MesherInputError, match="has no \\*Surface Interaction named 'Cohesion'"):
        insert_cohesive_contact(deck_other, pairs, interaction="Cohesion")


def test_missing_step_raises():
    deck_no_step = minimal_deck(interaction_name="Cohesion", has_step=False)
    pairs = [("Ply-1_top", "Ply-2_bottom")]
    with pytest.raises(MesherInputError, match="has no \\*Step block"):
        insert_cohesive_contact(deck_no_step, pairs, interaction="Cohesion")


def test_insertion_lands_inside_step_before_output_requests():
    deck = minimal_deck(interaction_name="Cohesion", has_step=True, has_interactions_comment=True)
    pairs = interface_pairs(3)
    out_text = insert_cohesive_contact(deck, pairs, interaction="Cohesion")

    lines = out_text.splitlines()
    step_idx = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("*step"))
    end_step_idx = next(i for i, l in enumerate(lines) if l.strip().lower().startswith("*end step"))
    output_idx = next(i for i, l in enumerate(lines) if "output requests" in l.lower() or l.strip().lower().startswith("*output"))
    contact_pair_indices = [i for i, l in enumerate(lines) if l.strip().lower().startswith("*contact pair")]

    assert len(contact_pair_indices) == 2
    for cp_idx in contact_pair_indices:
        assert step_idx < cp_idx < output_idx < end_step_idx

    # Also test deck with no existing ** INTERACTIONS comment
    deck_no_comment = minimal_deck(interaction_name="Cohesion", has_step=True, has_interactions_comment=False)
    out_text2 = insert_cohesive_contact(deck_no_comment, pairs, interaction="Cohesion")
    lines2 = out_text2.splitlines()
    step_idx2 = next(i for i, l in enumerate(lines2) if l.strip().lower().startswith("*step"))
    output_idx2 = next(i for i, l in enumerate(lines2) if "output requests" in l.lower() or l.strip().lower().startswith("*output"))
    contact_pair_indices2 = [i for i, l in enumerate(lines2) if l.strip().lower().startswith("*contact pair")]
    assert len(contact_pair_indices2) == 2
    for cp_idx in contact_pair_indices2:
        assert step_idx2 < cp_idx < output_idx2


def test_idempotent_on_rerun():
    deck = minimal_deck(interaction_name="Cohesion")
    pairs = interface_pairs(3)
    first_run = insert_cohesive_contact(deck, pairs, interaction="Cohesion")
    second_run = insert_cohesive_contact(first_run, pairs, interaction="Cohesion")

    assert first_run == second_run
    # Verify exact count of contact pairs
    lines = second_run.splitlines()
    assert len([l for l in lines if l.strip().lower().startswith("*contact pair")]) == 2


def test_round_trip_through_parser(tmp_path):
    deck = minimal_deck(interaction_name="Cohesion")
    pairs = interface_pairs(2)
    out_text = insert_cohesive_contact(deck, pairs, interaction="Cohesion")

    out_file = tmp_path / "deck_with_cohesive.inp"
    out_file.write_text(out_text, encoding="utf-8")

    parsed = parse_deck(out_file)
    assert "Plate" in parsed.parts
    assert "Ply-1" in parsed.instances
    assert "Ply-2" in parsed.instances


def test_no_invented_surface_interactions():
    deck = minimal_deck(interaction_name="Cohesion")
    original_interactions = [l for l in deck.splitlines() if l.strip().lower().startswith("*surface interaction")]
    pairs = interface_pairs(3)
    out_text = insert_cohesive_contact(deck, pairs, interaction="Cohesion")
    final_interactions = [l for l in out_text.splitlines() if l.strip().lower().startswith("*surface interaction")]

    # Exact count and content of *Surface Interaction lines must match original
    assert original_interactions == final_interactions
