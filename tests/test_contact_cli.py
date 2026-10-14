import pytest

from embmesh.cli import build_parser


def test_node_contact_cli_defaults_off():
    args = build_parser().parse_args(["visualize", "a.inp", "--instance", "P-1",
                                      "--diameter", "1", "--output", "out"])
    assert not args.plate_node_contact
    assert not args.fiber_node_contact
    assert args.ball_instance is None
    assert args.contact_thickness == "auto"


def test_node_contact_cli_options():
    args = build_parser().parse_args(["visualize", "a.inp", "--instance", "P-1",
                                      "--diameter", "1", "--output", "out",
                                      "--plate-node-contact", "--fiber-node-contact",
                                      "--ball-instance", "Ball-1", "--contact-thickness", "0.2"])
    assert args.plate_node_contact and args.fiber_node_contact
    assert args.ball_instance == "Ball-1"
    assert args.contact_thickness == "0.2"
