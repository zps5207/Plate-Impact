from embmesh_desktop import instance_names


def test_instance_names_from_list_output():
    output = "part P: nodes=8 elements=1\ninstance PLATE-1: part=P translation=[0.0, 0.0, 0.0]\ninstance BALL-1: part=B\n"
    assert instance_names(output) == ["PLATE-1", "BALL-1"]
