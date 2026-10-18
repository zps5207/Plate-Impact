from pathlib import Path
import pytest
from embmesh.plywise import write_plywise_deck

DECK = Path(__file__).resolve().parents[1] / "Meshing" / "plate1hex_curved_ball.inp"


@pytest.mark.skipif(not DECK.exists(), reason="one-hex test deck not present")
def test_four_ply_pipeline(tmp_path):
    out = tmp_path / "o.inp"
    meta = write_plywise_deck(DECK, out, plies=4, layup=[0, 90, 45, -45], fiber_diameter=0.0005,
                              cohesion="Cohesion", plate_node_contact=True, fiber_node_contact=True,
                              ball_instance="Ball-1")
    text = out.read_text()
    assert "*Contact Pair" not in text  # Abaqus/Explicit rejects cohesive behavior on contact pairs
    assert sum(1 for l in text.splitlines() if l.endswith(" , Cohesion")) == 3
    assert text.count("*Contact, op=NEW") == 1
    assert text.count("*Embedded Element, host elset=Ply-") == 4
    assert "EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF" in text
    assert meta["ball_contact"]["interaction"] != "Cohesion"
    assert meta["warnings"] == []
