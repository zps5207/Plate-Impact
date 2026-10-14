"""Local contract checks for render_ghost_failure.py without Abaqus."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
import io
from pathlib import Path
import runpy
import sys
import types


SCRIPT = Path(__file__).with_name("render_ghost_failure.py")
PROBE = Path(__file__).with_name("probe_visualization_imports.py")
CONSTANTS = (
    "CONTOURS_ON_DEF", "FEATURE", "INTEGRATION_POINT", "INVARIANT",
    "NODAL", "OFF", "ON", "PNG", "SOLID", "UNIFORM",
)


def assert_unconditional_main(tree, label):
    last = tree.body[-1]
    assert isinstance(last, ast.Expr), f"{label}: final statement is not main()"
    call = last.value
    assert isinstance(call, ast.Call), f"{label}: final statement is not a call"
    assert isinstance(call.func, ast.Name) and call.func.id == "main", (
        f"{label}: final call is not main()")
    assert not call.args and not call.keywords, f"{label}: main() has arguments"
    for node in tree.body:
        if isinstance(node, ast.If):
            guarded_calls = [
                child for child in ast.walk(node)
                if isinstance(child, ast.Call)
                and isinstance(child.func, ast.Name)
                and child.func.id == "main"
            ]
            assert not guarded_calls, f"{label}: main() is still guarded by an if"


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
        tree = ast.parse(SCRIPT.read_text(), filename=str(SCRIPT))
        assert_unconditional_main(tree, SCRIPT.name)
        # Load helper definitions without executing the Abaqus/ODB entry point.
        tree.body = tree.body[:-1]
        ast.fix_missing_locations(tree)
        module = types.ModuleType("render_ghost_failure")
        module.__file__ = str(SCRIPT)
        exec(compile(tree, str(SCRIPT), "exec"), module.__dict__)
        return module
    finally:
        for name, previous in old_modules.items():
            if previous is None:
                del sys.modules[name]
            else:
                sys.modules[name] = previous


def execute_probe_as_nonmain():
    abaqus = types.ModuleType("abaqus")
    abaqus.session = types.SimpleNamespace(Viewport=lambda **kwargs: None)
    driver_utils = types.ModuleType("driverUtils")
    driver_utils.executeOnCaeStartup = lambda: None
    visualization = types.ModuleType("visualization")
    display_group = types.ModuleType("displayGroupOdbToolset")
    display_group.LeafFromElementSets = object
    display_group.LeafFromPartInstance = object
    replacements = {
        "abaqus": abaqus,
        "driverUtils": driver_utils,
        "visualization": visualization,
        "displayGroupOdbToolset": display_group,
    }
    previous = {name: sys.modules.get(name) for name in replacements}
    sys.modules.update(replacements)
    try:
        output = io.StringIO()
        with redirect_stdout(output):
            runpy.run_path(str(PROBE), run_name="abaqus_cae_nogui_loader")
        text = output.getvalue()
        assert "VISUALIZATION_IMPORT_PROBE: PASS" in text
        return text
    finally:
        for name, module in previous.items():
            if module is None:
                del sys.modules[name]
            else:
                sys.modules[name] = module


def main():
    probe_tree = ast.parse(PROBE.read_text(), filename=str(PROBE))
    assert_unconditional_main(probe_tree, PROBE.name)
    guarded_regression = ast.parse(
        'def main():\n    pass\nif __name__ == "__main__":\n    main()\n')
    try:
        assert_unconditional_main(guarded_regression, "guarded regression fixture")
    except AssertionError:
        pass
    else:
        raise AssertionError("validator accepted a guarded Abaqus entry point")
    probe_output = execute_probe_as_nonmain()
    assert "display-group constructors" in probe_output

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
