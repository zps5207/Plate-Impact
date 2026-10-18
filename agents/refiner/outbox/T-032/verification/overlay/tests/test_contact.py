from pathlib import Path

import numpy as np
import pytest

from embmesh.contact import (add_ball_node_contact, median_host_edge_length,
                             PLATE_SURFACE, FIBER_SURFACE)
from embmesh.fibers import Fiber
from embmesh.model import Deck, Element, Instance, Part


def fixture_data(tmp_path, existing=False):
    host = Part("HOST")
    host.nodes = {i + 1: np.array(p, float) for i, p in enumerate([
        (0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0),
        (0, 0, 2), (2, 0, 2), (2, 2, 2), (0, 2, 2)])}
    host.elements[1] = Element(1, tuple(host.nodes), "C3D8R")
    ball = Part("BALL")
    ball.nodes = {i + 1: np.array(p, float) for i, p in enumerate([
        (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
        (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)])}
    ball.elements[7] = Element(7, tuple(ball.nodes), "C3D8R")
    deck = Deck(parts={"HOST": host, "BALL": ball}, instances={
        "Plate-1": Instance("Plate-1", "HOST"), "Ball-1": Instance("Ball-1", "BALL")})
    contact = ""
    if existing:
        contact = ("*Surface Interaction, name=General\n*Friction\n0.01\n"
                   "*Contact, op=NEW\n*Contact Inclusions\nUSER_A, USER_B\n"
                   "*Contact Property Assignment\n, , General\n")
    text = ("*Assembly, name=A\n*Instance, name=Plate-1, part=HOST\n*End Instance\n"
            "*Instance, name=Ball-1, part=BALL\n*End Instance\n"
            "*Instance, name=EMBFIB-1, part=EMBFIB\n*End Instance\n*End Assembly\n" +
            contact + "*Step\n*Dynamic, Explicit\n, 1e-3\n" +
            ("" if existing else "") + "*End Step\n")
    # Existing contact has to be in the step.
    if existing:
        pre, step = text.split("*Step\n", 1)
        interaction, block = contact.split("*Contact, op=NEW\n", 1)
        pre = pre.replace(contact, interaction)
        text = pre + "*Step\n*Contact, op=NEW\n" + block + step
    path = tmp_path / "output.inp"
    path.write_text(text)
    fibers = [Fiber(1, np.array([[0., 0., 0.], [1., 0., 0.], [2., 0., 0.]]), 0, "t0")]
    return path, deck, host, fibers


def call(path, deck, host, fibers, **kw):
    return add_ball_node_contact(path, deck, "Plate-1", host.elements, host.nodes,
                                 fibers, 100, kw.pop("ball_instance", "Ball-1"), **kw)


def test_both_disabled_is_byte_identical(tmp_path):
    path, deck, host, fibers = fixture_data(tmp_path)
    before = path.read_bytes()
    assert call(path, deck, host, fibers, plate=False, fiber=False) is None
    assert path.read_bytes() == before


@pytest.mark.parametrize("plate,fiber", [(True, False), (False, True), (True, True)])
def test_surface_combinations_and_all_node_counts(tmp_path, plate, fiber):
    path, deck, host, fibers = fixture_data(tmp_path)
    meta = call(path, deck, host, fibers, plate=plate, fiber=fiber)
    text = path.read_text()
    assert (PLATE_SURFACE in text) == plate
    assert (FIBER_SURFACE in text) == fiber
    assert meta["plate_node_count"] == (8 if plate else 0)
    assert meta["fiber_node_count"] == (3 if fiber else 0)
    assert text.lower().count("*contact,") == 1
    assert "*Surface, type=ELEMENT, name=EMBMESH_BALL_SURF" in text
    assert "*Friction\n0.0\n*Surface Behavior, pressure-overclosure=HARD" in text


def test_existing_contact_is_extended_and_interaction_reused(tmp_path):
    path, deck, host, fibers = fixture_data(tmp_path, existing=True)
    meta = call(path, deck, host, fibers, plate=True, fiber=True)
    text = path.read_text()
    assert text.lower().count("*contact,") == 1
    assert "USER_A, USER_B" in text
    assert "EMBMESH_PLATE_NODES , EMBMESH_BALL_SURF" in text
    assert "EMBMESH_FIBER_NODES , EMBMESH_BALL_SURF" in text
    assert meta["interaction"] == "General"
    assert meta["interaction_reused"] is True


def test_auto_and_explicit_thickness(tmp_path):
    path, deck, host, fibers = fixture_data(tmp_path)
    assert median_host_edge_length(host.elements, host.nodes) == pytest.approx(2.0)
    meta = call(path, deck, host, fibers, plate=True, fiber=True, thickness="auto")
    assert meta["plate_contact_thickness"] == pytest.approx(1.0)
    assert meta["fiber_contact_thickness"] == pytest.approx(0.5)
    path, deck, host, fibers = fixture_data(tmp_path)
    meta = call(path, deck, host, fibers, plate=True, fiber=True, thickness="0.125")
    assert meta["plate_contact_thickness"] == pytest.approx(0.125)
    assert meta["fiber_contact_thickness"] == pytest.approx(0.125)


def test_zero_thickness_writes_no_assignment(tmp_path):
    path, deck, host, fibers = fixture_data(tmp_path)
    call(path, deck, host, fibers, plate=True, thickness="0")
    assert "*Surface Property Assignment" not in path.read_text()


def test_missing_ball_is_clear(tmp_path):
    path, deck, host, fibers = fixture_data(tmp_path)
    with pytest.raises(ValueError, match="ball instance 'Missing'.*available instances"):
        call(path, deck, host, fibers, plate=True, ball_instance="Missing")
