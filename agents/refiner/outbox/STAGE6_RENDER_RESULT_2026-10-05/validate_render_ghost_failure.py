"""Local contract checks for render_ghost_failure.py without Abaqus."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types


SCRIPT = Path(__file__).with_name("render_ghost_failure.py")
CONSTANTS = (
    "CONTOURS_ON_DEF", "FEATURE", "INTEGRATION_POINT", "INVARIANT",
    "NODAL", "OFF", "ON", "PNG", "SOLID", "UNIFORM",
)


def load_module():
    abaqus = types.ModuleType("abaqus")
    abaqus.session = object()
    constants = types.ModuleType("abaqusConstants")
    for name in CONSTANTS:
        setattr(constants, name, name)
    display_group = types.ModuleType("displayGroupOdbToolset")
    driver_utils = types.ModuleType("driverUtils")
    driver_utils.executeOnCaeStartup = lambda: None
    old_modules = {
        name: sys.modules.get(name)
        for name in (
            "abaqus", "abaqusConstants", "driverUtils", "visualization",
            "displayGroupOdbToolset")
    }
    sys.modules["abaqus"] = abaqus
    sys.modules["abaqusConstants"] = constants
    sys.modules["driverUtils"] = driver_utils
    sys.modules["visualization"] = types.ModuleType("visualization")
    sys.modules["displayGroupOdbToolset"] = display_group
    try:
        spec = importlib.util.spec_from_file_location("render_ghost_failure", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, previous in old_modules.items():
            if previous is None:
                del sys.modules[name]
            else:
                sys.modules[name] = previous


def main():
    module = load_module()
    selected = module.evenly_sample(list(range(451, 1001)), 240)
    assert len(selected) == 240
    assert selected[0] == 451 and selected[-1] == 1000
    assert selected == sorted(set(selected))

    assert module.require_key(
        {"Step-1": object()}, "step-1", "step") == "Step-1"

    view = types.SimpleNamespace(
        cameraPosition=(1, 2, 3),
        cameraTarget=(4, 5, 6),
        cameraUpVector=(0, 1, 0),
        nearPlane=0.1,
        farPlane=100.0,
        width=10.0,
        height=5.625,
    )
    camera = module.camera_state(view)
    assert camera["cameraPosition"] == [1.0, 2.0, 3.0]
    assert camera["height"] == 5.625

    source = SCRIPT.read_text()
    assert source.index("executeOnCaeStartup()") < source.index(
        "import visualization")
    assert source.index("import visualization") < source.index(
        "import displayGroupOdbToolset")
    for token in (
        'GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"',
        'variableLabel="STATUS"',
        'variableLabel=variable',
        '"selected_odb_frame_indices"',
        '"camera": camera',
        'imageSize=(args.image_width, args.image_height)',
    ):
        assert token in source, token
    print("render contract checks: PASS")


if __name__ == "__main__":
    main()
