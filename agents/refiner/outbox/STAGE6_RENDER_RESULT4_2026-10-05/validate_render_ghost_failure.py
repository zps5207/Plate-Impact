"""Local contract checks for render_ghost_failure.py without Abaqus."""
from __future__ import annotations

import ast
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types


SCRIPT = Path(__file__).with_name("render_ghost_failure.py")
PROBE = Path(__file__).with_name("probe_visualization_imports.py")
CONSTANTS = (
    "CENTROID", "CONTOURS_ON_DEF", "ELEMENT_NODAL", "FEATURE",
    "INTEGRATION_POINT", "INVARIANT", "NODAL", "OFF", "ON", "PNG",
    "SOLID", "UNIFORM", "WHOLE_ELEMENT",
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


def execute_renderer_arguments_only_as_nonmain():
    abaqus = types.ModuleType("abaqus")
    abaqus.session = object()
    constants = types.ModuleType("abaqusConstants")
    for name in CONSTANTS:
        setattr(constants, name, name)
    driver_utils = types.ModuleType("driverUtils")
    driver_utils.executeOnCaeStartup = lambda: None
    replacements = {
        "abaqus": abaqus,
        "abaqusConstants": constants,
        "driverUtils": driver_utils,
        "visualization": types.ModuleType("visualization"),
        "displayGroupOdbToolset": types.ModuleType("displayGroupOdbToolset"),
    }
    previous_modules = {name: sys.modules.get(name) for name in replacements}
    previous_argv = list(sys.argv)
    previous_cwd = os.getcwd()
    previous_env = os.environ.get("ABQ_RENDER_ARGUMENTS_ONLY")
    sys.modules.update(replacements)
    try:
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                os.environ["ABQ_RENDER_ARGUMENTS_ONLY"] = "1"
                sys.argv[:] = [
                    "ABQcaeK", "-cae", "-noGUI", "-tmpdir", "/tmp",
                    "-lmlog", "ON", "flat_vg_r4.odb",
                ]
                output = io.StringIO()
                with redirect_stdout(output):
                    runpy.run_path(str(SCRIPT), run_name="abaqus_cae_nogui_loader")
                status = json.loads(Path("render_ghost_failure.status.json").read_text())
                assert status["status"] == "COMPLETE"
                assert status["mode"] == "ARGUMENTS_ONLY"
                assert status["recovered_arguments"] == ["flat_vg_r4.odb"]
                assert "recovered renderer arguments" in output.getvalue()
                return status
            finally:
                os.chdir(previous_cwd)
    finally:
        sys.argv[:] = previous_argv
        if previous_env is None:
            os.environ.pop("ABQ_RENDER_ARGUMENTS_ONLY", None)
        else:
            os.environ["ABQ_RENDER_ARGUMENTS_ONLY"] = previous_env
        for name, module in previous_modules.items():
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
    argument_status = execute_renderer_arguments_only_as_nonmain()
    assert argument_status["raw_sys_argv"][1] == "-cae"

    module = load_module()
    roar_argv = [
        "ABQcaeK", "-cae", "-noGUI", "-tmpdir", "/tmp", "-lmlog", "ON",
        "flat_vg_r4.odb",
    ]
    assert module.script_arguments(roar_argv) == ["flat_vg_r4.odb"]
    delimited = [
        "ABQcaeK", "-cae", "--", "flat_vg_r4.odb",
        "--output-dir", "Flat-vuel-ghost-r4/frames",
    ]
    assert module.script_arguments(delimited) == delimited[3:]
    rewritten_with_renderer_option = roar_argv + ["--frame-count", "12"]
    assert module.script_arguments(rewritten_with_renderer_option) == [
        "flat_vg_r4.odb", "--frame-count", "12"]
    parsed = module.parse_arguments(module.script_arguments(roar_argv))
    assert parsed.odb == "flat_vg_r4.odb"
    assert parsed.output_dir == "Flat-vuel-ghost-r4/frames"
    assert parsed.frame_count == 240

    with tempfile.TemporaryDirectory() as directory:
        module.STATUS_FILE = str(Path(directory) / "status.json")
        module.write_run_status("FAILED", exception_type="FixtureError")
        status = json.loads(Path(module.STATUS_FILE).read_text())
        assert status["status"] == "FAILED"
        assert status["exception_type"] == "FixtureError"

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

    field = types.SimpleNamespace(
        locations=[types.SimpleNamespace(position=module.WHOLE_ELEMENT)],
        values=[],
    )
    step = types.SimpleNamespace(frames=[
        types.SimpleNamespace(fieldOutputs={"STATUS": field}),
        types.SimpleNamespace(fieldOutputs={"STATUS": field}),
    ])
    selected_position, common_positions, observed_positions = (
        module.resolve_status_output_position(step, [0, 1]))
    assert selected_position == module.WHOLE_ELEMENT
    assert common_positions == [module.WHOLE_ELEMENT]
    assert observed_positions == [module.WHOLE_ELEMENT]

    fallback_field = types.SimpleNamespace(
        locations=[],
        values=[types.SimpleNamespace(position=module.CENTROID)],
    )
    assert module.field_output_positions(fallback_field) == [module.CENTROID]

    source = SCRIPT.read_text()
    assert source.index("executeOnCaeStartup()") < source.index(
        "import visualization")
    assert source.index("import visualization") < source.index(
        "import displayGroupOdbToolset")
    for token in (
        'GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"',
        'variableLabel="STATUS"',
        'variableLabel="STATUS", outputPosition=status_position',
        'variableLabel=variable',
        '"selected_odb_frame_indices"',
        '"camera": camera',
        'imageSize=(args.image_width, args.image_height)',
        'ARGUMENTS_ONLY_ENV = "ABQ_RENDER_ARGUMENTS_ONLY"',
        'write_run_status("COMPLETE", **result)',
        'except BaseException as exc:',
    ):
        assert token in source, token
    assert 'variableLabel="STATUS", outputPosition=INTEGRATION_POINT' not in source
    print("render contract checks: PASS")


if __name__ == "__main__":
    main()
