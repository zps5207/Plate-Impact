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
    "CENTROID", "CONTOURS_ON_DEF", "DEFORMED", "ELEMENT_NODAL", "FEATURE", "FREE",
    "INTEGRATION_POINT", "INVARIANT", "NODAL", "OFF", "ON", "PNG",
    "SHADED", "SOLID", "THICK", "UNIFORM", "WHOLE_ELEMENT", "WIREFRAME",
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
    assert parsed.passes == "status,displacement,fibers"

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

    class Recorder:
        def __init__(self):
            self.calls = []

        def setValues(self, **values):
            self.calls.append(values)

    class DisplayGroup:
        def __init__(self, name, leaf):
            self.name = name
            self.leaf = leaf
            self.replaced = []
            self.added = []

        def replace(self, leaf):
            self.leaf = leaf
            self.replaced.append(leaf)

        def add(self, leaf):
            self.added.append(leaf)

    class DisplayGroupInstance:
        def __init__(self):
            self.options = Recorder()
            self.odbDisplayOptions = types.SimpleNamespace(
                commonOptions=self.options)
            self.lock_calls = []

        def setValues(self, **values):
            self.lock_calls.append(values)

    class OdbDisplay:
        def __init__(self, display, common):
            self.display = display
            self.commonOptions = common
            self.displayGroupInstances = {}
            self.visible_groups = []

        def setValues(self, visibleDisplayGroups):
            self.visible_groups.append(visibleDisplayGroups)
            self.displayGroupInstances = dict(
                (group.name, DisplayGroupInstance())
                for group in visibleDisplayGroups)

    class Session:
        def __init__(self):
            self.displayGroups = {}

        def DisplayGroup(self, name, leaf):
            group = DisplayGroup(name, leaf)
            self.displayGroups[name] = group
            return group

    module.display_group.LeafFromElementSets = (
        lambda **values: ("element_sets", values))
    module.display_group.LeafFromPartInstance = (
        lambda **values: ("instances", values))
    display = Recorder()
    common = Recorder()
    annotations = Recorder()
    color_calls = []

    def strict_set_color(**values):
        keys = set(values)
        leaf_signature = {
            "leaf", "edgeColorWireHide", "edgeColorFillShade", "fillColor",
        }
        assert keys == leaf_signature, keys
        color_calls.append(values)

    module.session = Session()
    odb_display = OdbDisplay(display, common)
    viewport = types.SimpleNamespace(
        odbDisplay=odb_display,
        viewportAnnotationOptions=annotations,
        setColor=strict_set_color,
    )
    module.set_fiber_display(viewport)
    host_group = module.session.displayGroups[module.FIBER_HOST_DISPLAY_GROUP]
    content_group = module.session.displayGroups[
        module.FIBER_CONTENT_DISPLAY_GROUP]
    assert host_group.leaf[1]["elementSets"] == (module.GHOST_ELSET,)
    displayed_fiber_sets = content_group.leaf[1]["elementSets"]
    assert "EMBFIB-1.EMBMESH_FIBERS_T0" in displayed_fiber_sets
    assert "EMBFIB-1.EMBMESH_FIBERS_T90" in displayed_fiber_sets
    assert content_group.added[0][1]["partInstanceName"] == (
        module.BALL_INSTANCE,)
    assert odb_display.visible_groups[-1] == (host_group, content_group)
    assert display.calls[-1]["plotState"] == (module.DEFORMED,)
    host_instance = odb_display.displayGroupInstances[host_group.name]
    content_instance = odb_display.displayGroupInstances[content_group.name]
    host_options = host_instance.options.calls[-1]
    content_options = content_instance.options.calls[-1]
    assert host_options["renderStyle"] == module.WIREFRAME
    assert content_options["renderStyle"] == module.SHADED
    for options in (host_options, content_options):
        assert options["visibleEdges"] == module.FREE
        assert options["edgeLineThickness"] == module.THICK
        assert options["colorCodeOverride"] == module.ON
        assert options["nodeSymbols"] == module.OFF
        assert options["nodeLabels"] == module.OFF
        assert options["elemLabels"] == module.OFF
    assert host_instance.lock_calls[-1] == {"lockOptions": module.ON}
    assert content_instance.lock_calls[-1] == {"lockOptions": module.ON}
    host_override = color_calls[0]
    assert host_override["leaf"] == host_group.leaf
    assert host_override["edgeColorWireHide"] == module.HOST_COLOR
    fiber_override = color_calls[1]
    assert fiber_override["leaf"] == content_group.leaf
    assert fiber_override["edgeColorWireHide"] == module.FIBER_COLOR
    assert fiber_override["edgeColorFillShade"] == module.FIBER_COLOR
    assert fiber_override["fillColor"] == module.FIBER_COLOR
    ball_override = color_calls[2]
    assert len(color_calls) == 3
    assert ball_override["leaf"] == content_group.added[0]
    assert ball_override["fillColor"] == module.BALL_COLOR

    source = SCRIPT.read_text()
    assert source.index("executeOnCaeStartup()") < source.index(
        "import visualization")
    assert source.index("import visualization") < source.index(
        "import displayGroupOdbToolset")
    for token in (
        'GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"',
        'FIBER_INSTANCE = "EMBFIB-1"',
        'FIBER_ELSETS = ("EMBMESH_FIBERS_T0", "EMBMESH_FIBERS_T90")',
        'FIBER_HOST_DISPLAY_GROUP = "Stage6 Fiber Host Wireframe"',
        'FIBER_CONTENT_DISPLAY_GROUP = "Stage6 Fibers and Ball Shaded"',
        'variableLabel="STATUS"',
        'variableLabel="STATUS", outputPosition=status_position',
        'variableLabel=variable',
        'renderStyle=WIREFRAME',
        'visibleDisplayGroups=(host_group, content_group)',
        'lockOptions=ON',
        'leaf=ghost_leaf',
        'leaf=fiber_leaf',
        'edgeColorFillShade=FIBER_COLOR',
        'visibleEdges=FREE',
        'edgeLineThickness=THICK',
        'nodeSymbols=OFF',
        'leaf=ball_leaf',
        'elif pass_name == "fibers":',
        '"selected_odb_frame_indices"',
        '"camera": camera',
        'imageSize=(args.image_width, args.image_height)',
        'ARGUMENTS_ONLY_ENV = "ABQ_RENDER_ARGUMENTS_ONLY"',
        'write_run_status("COMPLETE", **result)',
        'except BaseException as exc:',
    ):
        assert token in source, token
    assert 'variableLabel="STATUS", outputPosition=INTEGRATION_POINT' not in source
    assert 'colors={' not in source
    assert 'translucencies={' not in source
    assert 'nodeSymbolColor=FIBER_COLOR' not in source
    assert 'nodeSymbolColor=BALL_COLOR' not in source
    assert 'initialColor=HOST_COLOR' not in source
    assert 'translucency=FIBER_HOST_TRANSLUCENCY' not in source
    fiber_display_start = source.index("def set_fiber_display")
    content_options_call = source.index(
        "content_instance.odbDisplayOptions.commonOptions",
        fiber_display_start)
    assert content_options_call < source.index(
        "viewport.setColor(\n        leaf=ghost_leaf", fiber_display_start)
    assert content_options_call < source.index(
        "viewport.setColor(\n        leaf=fiber_leaf", fiber_display_start)
    assert content_options_call < source.index(
        "viewport.setColor(\n        leaf=ball_leaf", fiber_display_start)
    print("render contract checks: PASS")


if __name__ == "__main__":
    main()
