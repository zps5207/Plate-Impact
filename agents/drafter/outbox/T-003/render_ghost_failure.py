"""Render reproducible Abaqus/CAE PNG sequences from the Stage-6 R4 ODB.

Example (run on a host with Abaqus/CAE):

    abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
        --output-dir Flat-vuel-ghost-r4/frames

The default output contains 240 STATUS frames, 240 displacement-magnitude
frames, and 240 wireframe-host fiber frames spanning step time 4.5e-5
through 1.0e-4 seconds. A JSON manifest and CSV frame map record the exact ODB
frame indices, times, camera, and rendering settings used.
"""
from __future__ import print_function

import argparse
import csv
import json
import os
import sys
import time
import traceback

from abaqus import session
from abaqusConstants import (
    CENTROID,
    CONTOURS_ON_DEF,
    DEFORMED,
    ELEMENT_NODAL,
    FEATURE,
    FREE,
    INTEGRATION_POINT,
    INVARIANT,
    NODAL,
    OFF,
    ON,
    PNG,
    SHADED,
    SOLID,
    THICK,
    UNIFORM,
    WHOLE_ELEMENT,
    WIREFRAME,
)
from driverUtils import executeOnCaeStartup

# Use Abaqus's standard noGUI kernel bootstrap before loading module-specific
# Visualization services.
executeOnCaeStartup()
# In an Abaqus/CAE noGUI kernel this import initializes ODB visualization
# services, including the display-group toolset module imported below.
import visualization
import displayGroupOdbToolset as display_group


GHOST_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
PLATE_INSTANCE = "PLATE-1"
BALL_INSTANCE = "BALL-1"
FIBER_INSTANCE = "EMBFIB-1"
FIBER_ELSETS = ("EMBMESH_FIBERS_T0", "EMBMESH_FIBERS_T90")
FIBER_HOST_DISPLAY_GROUP = "Stage6 Fiber Host Wireframe"
FIBER_CONTENT_DISPLAY_GROUP = "Stage6 Fibers and Ball Shaded"
HOST_COLOR = "#9EADBA"
FIBER_COLOR = "#FF0000"
BALL_COLOR = "#606060"
DEFAULT_PASSES = ("status", "displacement", "fibers")
CAMERA_VECTOR_FIELDS = ("cameraPosition", "cameraTarget", "cameraUpVector")
RENDER_OPTIONS = (
    "--output-dir", "--step", "--start-time", "--end-time",
    "--frame-count", "--fps", "--passes", "--view",
    "--image-width", "--image-height", "--deformation-scale",
)
STATUS_FILE = "render_ghost_failure.status.json"
ARGUMENTS_ONLY_ENV = "ABQ_RENDER_ARGUMENTS_ONLY"


def script_arguments(argv=None):
    """Recover renderer arguments from normal or Abaqus-rewritten argv.

    Abaqus 2024 on ROAR removes the ``--`` separator and some post-separator
    options while leaving its own launcher flags in ``sys.argv``. In that
    case the unique ``.odb`` token is the positional input and only explicitly
    recognized renderer options are retained; all Abaqus launcher flags are
    ignored. The requested ROAR output directory equals this script's default,
    so its observed removal does not change the render destination.
    """
    values = list(sys.argv if argv is None else argv)
    if "--" in values:
        return values[values.index("--") + 1:]

    odb_values = [value for value in values if value.lower().endswith(".odb")]
    if len(odb_values) != 1:
        raise ValueError(
            "expected exactly one .odb argument in Abaqus argv; found {0}: {1}".format(
                len(odb_values), repr(values)))
    recovered = [odb_values[0]]
    index = 0
    while index < len(values):
        value = values[index]
        matched = False
        for option in RENDER_OPTIONS:
            if value == option:
                if index + 1 >= len(values):
                    raise ValueError("renderer option {0} has no value".format(option))
                recovered.extend((option, values[index + 1]))
                index += 2
                matched = True
                break
            if value.startswith(option + "="):
                recovered.append(value)
                index += 1
                matched = True
                break
        if not matched:
            index += 1
    return recovered


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description="Render ghost deletion and deformation from an Abaqus ODB")
    parser.add_argument("odb", help="path to the Abaqus output database")
    parser.add_argument("--output-dir", default="Flat-vuel-ghost-r4/frames")
    parser.add_argument("--step", default="Step-1")
    parser.add_argument("--start-time", type=float, default=4.5e-5)
    parser.add_argument("--end-time", type=float, default=1.0e-4)
    parser.add_argument("--frame-count", type=int, default=240,
                        help="number of evenly sampled ODB frames (default: 240)")
    parser.add_argument("--fps", type=float, default=30.0,
                        help="intended MP4 frame rate, recorded in the manifest")
    parser.add_argument("--passes", default=",".join(DEFAULT_PASSES),
                        help="comma-separated: status,displacement,velocity,fibers")
    parser.add_argument("--view", default="Iso",
                        help="Abaqus standard view preset, e.g. Iso, Front, Top")
    parser.add_argument("--image-width", type=int, default=1920)
    parser.add_argument("--image-height", type=int, default=1080)
    parser.add_argument("--deformation-scale", type=float, default=1.0)
    return parser.parse_args(script_arguments() if argv is None else argv)


def write_run_status(status, **details):
    payload = {
        "status": status,
        "unix_time": time.time(),
        "raw_sys_argv": list(sys.argv),
    }
    payload.update(details)
    with open(STATUS_FILE, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def ensure_directory(path):
    if not os.path.isdir(path):
        os.makedirs(path)


def repository_keys(repository):
    return [str(key) for key in repository.keys()]


def require_key(repository, requested, kind):
    keys = repository_keys(repository)
    lookup = dict((key.upper(), key) for key in keys)
    key = lookup.get(requested.upper())
    if key is None:
        raise RuntimeError(
            "{0} {1!r} was not found; available values: {2}".format(
                kind, requested, ", ".join(keys)))
    return key


def evenly_sample(indices, count):
    if count <= 0:
        raise ValueError("--frame-count must be positive")
    if not indices:
        raise RuntimeError("no ODB frames fall inside the requested time window")
    if count >= len(indices):
        return list(indices)
    if count == 1:
        return [indices[0]]
    sampled = []
    last = None
    for position in range(count):
        offset = int(round(position * (len(indices) - 1.0) / (count - 1.0)))
        candidate = indices[offset]
        if candidate != last:
            sampled.append(candidate)
            last = candidate
    return sampled


def camera_state(view):
    names = (
        "cameraPosition", "cameraTarget", "cameraUpVector",
        "nearPlane", "farPlane", "width", "height",
    )
    state = {}
    for name in names:
        value = getattr(view, name, None)
        if value is not None:
            if name in CAMERA_VECTOR_FIELDS:
                state[name] = [float(component) for component in value]
            else:
                state[name] = float(value)
    return state


def apply_camera(view, state):
    if state:
        values = dict(state)
        for name in CAMERA_VECTOR_FIELDS:
            if name in values:
                values[name] = tuple(values[name])
        view.setValues(**values)


def set_common_display(viewport, deformation_scale):
    viewport.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    viewport.odbDisplay.commonOptions.setValues(
        deformationScaling=UNIFORM,
        uniformScaleFactor=deformation_scale,
        visibleEdges=FEATURE,
    )
    viewport.viewportAnnotationOptions.setValues(
        triad=OFF,
        legend=ON,
        title=OFF,
        state=ON,
        annotations=ON,
        compass=OFF,
    )


def field_output_positions(field_output):
    """Return unique output positions advertised by an ODB field."""
    positions = []
    for location in getattr(field_output, "locations", ()):
        position = getattr(location, "position", None)
        if position is not None and position not in positions:
            positions.append(position)

    # FieldLocation metadata is the normal and inexpensive path. Retain a
    # values fallback for ODB/API variants that expose no locations sequence.
    if not positions:
        for value in getattr(field_output, "values", ()):
            position = getattr(value, "position", None)
            if position is not None and position not in positions:
                positions.append(position)
    return positions


def resolve_status_output_position(step, frame_indices):
    """Choose a STATUS position present in every selected ODB frame.

    Abaqus documents STATUS as a whole-element output variable, so prefer
    WHOLE_ELEMENT. Inspecting the ODB prevents another hard-coded mismatch and
    provides a useful diagnostic if an unusual database exposes it elsewhere.
    """
    per_frame = []
    observed = []
    for frame_index in frame_indices:
        positions = field_output_positions(
            step.frames[frame_index].fieldOutputs["STATUS"])
        if not positions:
            raise RuntimeError(
                "STATUS in ODB frame {0} exposes no output positions".format(
                    frame_index))
        per_frame.append(positions)
        for position in positions:
            if position not in observed:
                observed.append(position)

    common = [
        position for position in per_frame[0]
        if all(position in positions for positions in per_frame[1:])
    ]
    preferred = (
        WHOLE_ELEMENT, CENTROID, INTEGRATION_POINT, ELEMENT_NODAL, NODAL)
    for position in preferred:
        if position in common:
            return position, common, observed
    if common:
        return common[0], common, observed
    raise RuntimeError(
        "STATUS has no output position common to all selected frames; "
        "observed positions: {0}".format(
            ", ".join(str(position) for position in observed)))


def set_status_display(viewport, status_position):
    viewport.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    viewport.viewportAnnotationOptions.setValues(legend=ON)
    ghost_leaf = display_group.LeafFromElementSets(
        elementSets=(GHOST_ELSET,))
    ball_leaf = display_group.LeafFromPartInstance(
        partInstanceName=(BALL_INSTANCE,))
    viewport.odbDisplay.displayGroup.replace(leaf=ghost_leaf)
    viewport.odbDisplay.displayGroup.add(leaf=ball_leaf)
    viewport.odbDisplay.setPrimaryVariable(
        variableLabel="STATUS", outputPosition=status_position)
    viewport.odbDisplay.contourOptions.setValues(
        minAutoCompute=OFF,
        minValue=0.0,
        maxAutoCompute=OFF,
        maxValue=1.0,
        numIntervals=2,
    )


def set_motion_display(viewport, variable):
    viewport.odbDisplay.display.setValues(plotState=(CONTOURS_ON_DEF,))
    viewport.viewportAnnotationOptions.setValues(legend=ON)
    instances_leaf = display_group.LeafFromPartInstance(
        partInstanceName=(PLATE_INSTANCE, BALL_INSTANCE))
    viewport.odbDisplay.displayGroup.replace(leaf=instances_leaf)
    viewport.odbDisplay.setPrimaryVariable(
        variableLabel=variable,
        outputPosition=NODAL,
        refinement=(INVARIANT, "Magnitude"),
    )
    viewport.odbDisplay.contourOptions.setValues(
        minAutoCompute=ON,
        maxAutoCompute=ON,
        numIntervals=12,
    )


def define_session_display_group(name, leaf, additions=()):
    """Create or refresh a named display group without stale membership."""
    if name in session.displayGroups:
        group = session.displayGroups[name]
        group.replace(leaf=leaf)
    else:
        group = session.DisplayGroup(name=name, leaf=leaf)
    for addition in additions:
        group.add(leaf=addition)
    return group


def set_options(target, **kwargs):
    """Set options via setValues if available, else via attribute assignment."""
    if hasattr(target, "setValues") and callable(getattr(target, "setValues")):
        try:
            target.setValues(**kwargs)
            return
        except (AttributeError, TypeError):
            pass
    for key, value in kwargs.items():
        setattr(target, key, value)


def set_fiber_display(viewport):
    """Show a wireframe host around opaque fibers and the impactor."""
    fiber_sets = tuple(
        "{0}.{1}".format(FIBER_INSTANCE, name) for name in FIBER_ELSETS)
    ghost_leaf = display_group.LeafFromElementSets(
        elementSets=(GHOST_ELSET,))
    fiber_leaf = display_group.LeafFromElementSets(
        elementSets=fiber_sets)
    ball_leaf = display_group.LeafFromPartInstance(
        partInstanceName=(BALL_INSTANCE,))
    viewport.odbDisplay.display.setValues(plotState=(DEFORMED,))
    # Seed both display-group instances with clean geometry options before
    # assigning their distinct render styles.
    viewport.odbDisplay.commonOptions.setValues(
        renderStyle=SHADED,
        visibleEdges=FREE,
        edgeLineThickness=THICK,
        colorCodeOverride=ON,
        elemLabels=OFF,
        faceLabels=OFF,
        nodeLabels=OFF,
        nodeSymbols=OFF,
    )
    host_group = define_session_display_group(
        FIBER_HOST_DISPLAY_GROUP, ghost_leaf)
    content_group = define_session_display_group(
        FIBER_CONTENT_DISPLAY_GROUP, fiber_leaf, additions=(ball_leaf,))
    viewport.odbDisplay.setValues(
        visibleDisplayGroups=(host_group, content_group))

    display_group_instances = viewport.odbDisplay.displayGroupInstances
    host_instance_name = require_key(
        display_group_instances, FIBER_HOST_DISPLAY_GROUP,
        "host display group instance")
    content_instance_name = require_key(
        display_group_instances, FIBER_CONTENT_DISPLAY_GROUP,
        "fiber/ball display group instance")
    host_instance = display_group_instances[host_instance_name]
    content_instance = display_group_instances[content_instance_name]

    set_options(
        host_instance.odbDisplayOptions.commonOptions,
        renderStyle=WIREFRAME,
        visibleEdges=FREE,
        edgeLineThickness=THICK,
        colorCodeOverride=ON,
        elemLabels=OFF,
        faceLabels=OFF,
        nodeLabels=OFF,
        nodeSymbols=OFF,
    )
    set_options(
        content_instance.odbDisplayOptions.commonOptions,
        renderStyle=SHADED,
        visibleEdges=FREE,
        edgeLineThickness=THICK,
        colorCodeOverride=ON,
        elemLabels=OFF,
        faceLabels=OFF,
        nodeLabels=OFF,
        nodeSymbols=OFF,
    )
    # Prevent subsequent viewport option changes from resynchronizing these
    # deliberately different per-group render styles.
    set_options(host_instance, lockOptions=ON)
    set_options(content_instance, lockOptions=ON)
    viewport.viewportAnnotationOptions.setValues(legend=OFF)

    # Apply colors last. Host wireframe uses edgeColorWireHide; fibers and the
    # shaded ball use explicit edge/fill colors. No translucent filled host
    # faces remain to obscure embedded geometry.
    viewport.setColor(
        leaf=ghost_leaf,
        edgeColorWireHide=HOST_COLOR,
        edgeColorFillShade=HOST_COLOR,
        fillColor=HOST_COLOR,
    )
    viewport.setColor(
        leaf=fiber_leaf,
        edgeColorWireHide=FIBER_COLOR,
        edgeColorFillShade=FIBER_COLOR,
        fillColor=FIBER_COLOR,
    )
    viewport.setColor(
        leaf=ball_leaf,
        edgeColorWireHide=BALL_COLOR,
        edgeColorFillShade=BALL_COLOR,
        fillColor=BALL_COLOR,
    )


def render_pass(viewport, step_index, step, frame_indices, pass_name,
                output_dir, camera, frame_records, status_position):
    pass_dir = os.path.join(output_dir, pass_name)
    ensure_directory(pass_dir)

    if pass_name == "status":
        set_status_display(viewport, status_position)
    elif pass_name == "displacement":
        set_motion_display(viewport, "U")
    elif pass_name == "velocity":
        set_motion_display(viewport, "V")
    elif pass_name == "fibers":
        set_fiber_display(viewport)
    else:
        raise ValueError("unsupported render pass: {0}".format(pass_name))
    apply_camera(viewport.view, camera)

    for sequence, frame_index in enumerate(frame_indices):
        frame = step.frames[frame_index]
        viewport.odbDisplay.setFrame(step=step_index, frame=frame_index)
        stem = "{0}_{1:04d}".format(pass_name, sequence)
        target = os.path.join(pass_dir, stem)
        session.printToFile(
            fileName=target,
            format=PNG,
            canvasObjects=(viewport,),
        )
        frame_records.append({
            "pass": pass_name,
            "sequence": sequence,
            "odb_frame_index": frame_index,
            "step_time": frame.frameValue,
            "png": os.path.relpath(target + ".png", output_dir),
        })
        if sequence % 20 == 0 or sequence + 1 == len(frame_indices):
            print("{0}: rendered {1}/{2}".format(
                pass_name, sequence + 1, len(frame_indices)))


def write_manifest(output_dir, manifest, frame_records):
    manifest_path = os.path.join(output_dir, "render_manifest.json")
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    csv_path = os.path.join(output_dir, "frame_map.csv")
    with open(csv_path, "w") as handle:
        writer = csv.writer(handle)
        writer.writerow(("pass", "sequence", "odb_frame_index", "step_time", "png"))
        for record in frame_records:
            writer.writerow((
                record["pass"], record["sequence"],
                record["odb_frame_index"], record["step_time"], record["png"]))


def render(cli_arguments):
    args = parse_arguments(cli_arguments)
    passes = [value.strip().lower() for value in args.passes.split(",") if value.strip()]
    invalid = [value for value in passes
               if value not in ("status", "displacement", "velocity", "fibers")]
    if invalid:
        raise ValueError("unsupported --passes values: {0}".format(", ".join(invalid)))
    if not passes:
        raise ValueError("--passes must select at least one render pass")
    if args.end_time < args.start_time:
        raise ValueError("--end-time must be greater than or equal to --start-time")
    if args.fps <= 0.0:
        raise ValueError("--fps must be positive")
    if args.image_width <= 0 or args.image_height <= 0:
        raise ValueError("image dimensions must be positive")

    output_dir = os.path.abspath(args.output_dir)
    ensure_directory(output_dir)
    odb_path = os.path.abspath(args.odb)
    odb = session.openOdb(name=odb_path, readOnly=True)
    try:
        step_name = require_key(odb.steps, args.step, "step")
        step_names = repository_keys(odb.steps)
        step_index = step_names.index(step_name)
        step = odb.steps[step_name]
        require_key(odb.rootAssembly.instances, PLATE_INSTANCE, "instance")
        require_key(odb.rootAssembly.instances, BALL_INSTANCE, "instance")
        fiber_instance_name = require_key(
            odb.rootAssembly.instances, FIBER_INSTANCE, "instance")
        require_key(odb.rootAssembly.elementSets, GHOST_ELSET, "element set")
        fiber_instance = odb.rootAssembly.instances[fiber_instance_name]
        for fiber_elset in FIBER_ELSETS:
            require_key(fiber_instance.elementSets, fiber_elset, "fiber element set")

        eligible = [
            index for index, frame in enumerate(step.frames)
            if args.start_time <= frame.frameValue <= args.end_time
        ]
        selected = evenly_sample(eligible, args.frame_count)
        # STATUS is also used while fitting the shared camera, even when the
        # requested output passes contain only displacement or velocity.
        required_fields = set(["STATUS"])
        if "displacement" in passes:
            required_fields.add("U")
        if "velocity" in passes:
            required_fields.add("V")
        for frame_index in selected:
            available = set(repository_keys(step.frames[frame_index].fieldOutputs))
            missing = sorted(required_fields - available)
            if missing:
                raise RuntimeError(
                    "ODB frame {0} at t={1} is missing fields: {2}".format(
                        frame_index, step.frames[frame_index].frameValue,
                        ", ".join(missing)))

        status_position, status_common_positions, status_observed_positions = (
            resolve_status_output_position(step, selected))
        print("STATUS output position: {0} (common: {1})".format(
            status_position,
            ", ".join(str(value) for value in status_common_positions)))

        viewport_name = "Stage6 Ghost Failure"
        if viewport_name in session.viewports:
            viewport = session.viewports[viewport_name]
        else:
            viewport = session.Viewport(
                name=viewport_name,
                origin=(0, 0),
                width=300,
                height=168.75,
            )
        viewport.setValues(displayedObject=odb)
        session.graphicsOptions.setValues(
            backgroundStyle=SOLID,
            backgroundColor="#FFFFFF",
        )
        session.printOptions.setValues(vpBackground=ON, vpDecorations=OFF)
        session.pngOptions.setValues(
            imageSize=(args.image_width, args.image_height))
        set_common_display(viewport, args.deformation_scale)

        # Fit once at the first sampled frame with the ghost plate and ball
        # visible, then reuse the exact captured camera for every pass/frame.
        viewport.odbDisplay.setFrame(step=step_index, frame=selected[0])
        set_status_display(viewport, status_position)
        if args.view not in session.views:
            raise RuntimeError(
                "view preset {0!r} not found; available presets: {1}".format(
                    args.view, ", ".join(repository_keys(session.views))))
        viewport.view.setValues(session.views[args.view])
        viewport.view.fitView()
        camera = camera_state(viewport.view)

        records = []
        for pass_name in passes:
            render_pass(
                viewport, step_index, step, selected, pass_name,
                output_dir, camera, records, status_position)

        manifest = {
            "odb": odb_path,
            "step": step_name,
            "time_window": [args.start_time, args.end_time],
            "eligible_odb_frame_count": len(eligible),
            "selected_odb_frame_indices": selected,
            "selected_step_times": [step.frames[index].frameValue for index in selected],
            "render_passes": passes,
            "status_field": "STATUS on {0}".format(GHOST_ELSET),
            "status_output_position": str(status_position),
            "status_common_output_positions": [
                str(value) for value in status_common_positions],
            "status_observed_output_positions": [
                str(value) for value in status_observed_positions],
            "motion_fields": {"displacement": "U magnitude", "velocity": "V magnitude"},
            "fiber_render": {
                "instance": FIBER_INSTANCE,
                "element_sets": list(FIBER_ELSETS),
                "host_element_set": GHOST_ELSET,
                "host_color": HOST_COLOR,
                "fiber_color": FIBER_COLOR,
                "ball_color": BALL_COLOR,
                "plot_state": "DEFORMED",
                "host_render_style": "WIREFRAME",
                "content_render_style": "SHADED",
                "host_filled_faces": False,
                "host_display_group": FIBER_HOST_DISPLAY_GROUP,
                "content_display_group": FIBER_CONTENT_DISPLAY_GROUP,
                "visible_edges": "FREE",
                "edge_line_thickness": "THICK",
                "node_symbols": False,
                "color_code_override": True,
            },
            "image_size": [args.image_width, args.image_height],
            "intended_fps": args.fps,
            "intended_duration_seconds": len(selected) / args.fps,
            "deformation_scale": args.deformation_scale,
            "view_preset": args.view,
            "fit_view_frame_index": selected[0],
            "fit_view_step_time": step.frames[selected[0]].frameValue,
            "camera": camera,
            "background": "#FFFFFF",
            "visible_edges": "FEATURE",
            "status_contour_range": [0.0, 1.0],
            "status_contour_intervals": 2,
            "frame_records": records,
            "ffmpeg_examples": [
                "ffmpeg -framerate {0:g} -i status/status_%04d.png "
                "-c:v libx264 -pix_fmt yuv420p status.mp4".format(args.fps),
                "ffmpeg -framerate {0:g} -i displacement/displacement_%04d.png "
                "-c:v libx264 -pix_fmt yuv420p displacement.mp4".format(args.fps),
                "ffmpeg -framerate {0:g} -i fibers/fibers_%04d.png "
                "-c:v libx264 -pix_fmt yuv420p fibers.mp4".format(args.fps),
            ],
        }
        write_manifest(output_dir, manifest, records)
        print("rendered {0} PNG files into {1}".format(len(records), output_dir))
        print("manifest: {0}".format(
            os.path.join(output_dir, "render_manifest.json")))
        return {
            "output_dir": output_dir,
            "manifest": os.path.join(output_dir, "render_manifest.json"),
            "png_count": len(records),
            "status_output_position": str(status_position),
        }
    finally:
        odb.close()


def main():
    write_run_status("STARTED")
    try:
        recovered = script_arguments()
        write_run_status("STARTED", recovered_arguments=recovered)
        if os.environ.get(ARGUMENTS_ONLY_ENV) == "1":
            print("raw sys.argv: {0}".format(repr(list(sys.argv))))
            print("recovered renderer arguments: {0}".format(repr(recovered)))
            write_run_status(
                "COMPLETE",
                mode="ARGUMENTS_ONLY",
                recovered_arguments=recovered,
            )
            return
        result = render(recovered)
    except BaseException as exc:
        write_run_status(
            "FAILED",
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            traceback=traceback.format_exc(),
        )
        raise
    write_run_status("COMPLETE", **result)


# Abaqus ``cae noGUI=...`` may execute this file with a non-``__main__``
# module name. This is a single-purpose entry script, so invoke it directly.
main()
