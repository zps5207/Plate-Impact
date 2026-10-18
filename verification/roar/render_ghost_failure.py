"""Render reproducible Abaqus/CAE PNG sequences from the Stage-6 R4 ODB.

Example (run on a host with Abaqus/CAE):

    abaqus cae noGUI=render_ghost_failure.py -- flat_vg_r4.odb \
        --output-dir Flat-vuel-ghost-r4/frames

The default output contains 240 STATUS frames, 240 displacement-magnitude
frames, and 240 translucent-host fiber frames spanning step time 4.5e-5
through 1.0e-4 seconds. A JSON manifest and CSV frame map record the exact ODB
frame indices, times, camera, and rendering settings used.
"""
from __future__ import print_function

import argparse
import csv
import json
import math
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
    EXTERIOR,
    FEATURE,
    INTEGRATION_POINT,
    INVARIANT,
    NODAL,
    OFF,
    ON,
    PNG,
    PARALLEL,
    SHADED,
    SOLID,
    WIREFRAME,
    UNIFORM,
    WHOLE_ELEMENT,
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
# plywise ODBs (embmesh plywise) hold Ply-1..N hosts and Fibers-Ply-k fiber instances; set by detect_plywise()
PLYWISE_PLATE_INSTANCES = None
PLYWISE_FIBER_SETS = None


def detect_plywise(odb):
    global PLYWISE_PLATE_INSTANCES, PLYWISE_FIBER_SETS
    names = list(odb.rootAssembly.instances.keys())
    if PLATE_INSTANCE in names:
        return False
    plies = sorted((n for n in names if n.startswith("PLY-") and n.split("-")[-1].isdigit()),
                   key=lambda n: int(n.split("-")[-1]))
    if not plies:
        return False
    PLYWISE_PLATE_INSTANCES = tuple(plies)
    PLYWISE_FIBER_SETS = tuple(
        "FIBERS-PLY-{0}.FIBERS".format(n.split("-")[-1]) for n in plies
        if "FIBERS-PLY-{0}".format(n.split("-")[-1]) in names)
    return True


def plate_instance_names():
    return PLYWISE_PLATE_INSTANCES or (PLATE_INSTANCE,)


def fiber_set_names():
    if PLYWISE_FIBER_SETS is not None:
        return PLYWISE_FIBER_SETS
    return tuple("{0}.{1}".format(FIBER_INSTANCE, name) for name in FIBER_ELSETS)
FIBER_HOST_TRANSLUCENCY = 0.65
HOST_COLOR = "#9EADBA"
FIBER_COLOR = "#D00000"
BALL_COLOR = "#606060"
WIRE_HOST_COLOR = "#8C8C8C"
WIRE_FIBER_COLOR = "#0033CC"
DEFAULT_PASSES = ("status", "wire")
DEFAULT_VIEWS = ("iso", "side")
ISO_PROJECTION = [None]
CAMERA_VECTOR_FIELDS = ("cameraPosition", "cameraTarget", "cameraUpVector")
RENDER_OPTIONS = (
    "--output-dir", "--step", "--start-time", "--end-time",
    "--frame-count", "--fps", "--passes", "--view", "--views", "--closeup-scale",
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
    parser.add_argument("--views", default=",".join(DEFAULT_VIEWS),
                        help="comma list: iso (Abaqus preset fit) and/or side "
                             "(flat-on close-up of the symmetry plane through the ball)")
    parser.add_argument("--closeup-scale", type=float, default=1.0,
                        help="multiplier on the side close-up window size")
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
        state=OFF,
        annotations=OFF,
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
    viewport.odbDisplay.commonOptions.setValues(
        renderStyle=SHADED, visibleEdges=FEATURE)
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
    viewport.odbDisplay.commonOptions.setValues(
        renderStyle=SHADED, visibleEdges=FEATURE)
    viewport.viewportAnnotationOptions.setValues(legend=ON)
    instances_leaf = display_group.LeafFromPartInstance(
        partInstanceName=tuple(plate_instance_names()) + (BALL_INSTANCE,))
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


def set_fiber_display(viewport):
    """Show only the fibers and the impactor, opaque-shaded -- the host is
    excluded from the display group entirely (not just rendered as
    wireframe), per the user's stated preference: the host only ever
    obscured the fiber grid, and dropping it outright gives a clearer view
    than any host render style could.

    Earlier rounds tried to keep the host visible as a wireframe silhouette
    (two independent attempts to give the host and the fiber/ball content
    different render styles via separate simultaneous display groups both
    failed on real Abaqus 2024: DGCommonOptions has no .setValues, and the
    DisplayGroupInstance attribute involved is read-only post-construction;
    a single-shared-group global WIREFRAME render style worked but still
    required drawing the host). Simply never adding the host leaf to the
    display group sidesteps all of that.
    """
    fiber_sets = fiber_set_names()
    fiber_leaf = display_group.LeafFromElementSets(
        elementSets=fiber_sets)
    ball_leaf = display_group.LeafFromPartInstance(
        partInstanceName=(BALL_INSTANCE,))
    viewport.odbDisplay.displayGroup.replace(leaf=fiber_leaf)
    viewport.odbDisplay.displayGroup.add(leaf=ball_leaf)
    viewport.odbDisplay.display.setValues(plotState=(DEFORMED,))
    viewport.odbDisplay.commonOptions.setValues(
        renderStyle=SHADED,
        visibleEdges=FEATURE,
    )
    viewport.viewportAnnotationOptions.setValues(legend=OFF)

    viewport.setColor(
        leaf=fiber_leaf,
        edgeColorWireHide=FIBER_COLOR,
        edgeColorFillShade=FIBER_COLOR,
        fillColor=FIBER_COLOR,
        nodeSymbolColor=FIBER_COLOR,
    )
    viewport.setColor(
        leaf=ball_leaf,
        edgeColorWireHide=BALL_COLOR,
        edgeColorFillShade=BALL_COLOR,
        fillColor=BALL_COLOR,
        nodeSymbolColor=BALL_COLOR,
    )


def set_wire_display(viewport):
    """Thin grey wireframe host hexes, blue fiber elements, grey ball.

    One shared display group with a global WIREFRAME render style (the only
    approach that worked on Abaqus 2024, see set_fiber_display); colors are
    per-leaf. Exterior edges only keeps the host mesh readable.
    """
    host_leaf = display_group.LeafFromElementSets(elementSets=(GHOST_ELSET,))
    fiber_sets = fiber_set_names()
    fiber_leaf = display_group.LeafFromElementSets(elementSets=fiber_sets)
    ball_leaf = display_group.LeafFromPartInstance(
        partInstanceName=(BALL_INSTANCE,))
    viewport.odbDisplay.displayGroup.replace(leaf=host_leaf)
    viewport.odbDisplay.displayGroup.add(leaf=fiber_leaf)
    viewport.odbDisplay.displayGroup.add(leaf=ball_leaf)
    viewport.odbDisplay.display.setValues(plotState=(DEFORMED,))
    viewport.odbDisplay.commonOptions.setValues(
        renderStyle=WIREFRAME,
        visibleEdges=EXTERIOR,
        nodeSymbols=OFF,
    )
    viewport.viewportAnnotationOptions.setValues(legend=OFF)
    for leaf, color in ((host_leaf, WIRE_HOST_COLOR),
                        (fiber_leaf, WIRE_FIBER_COLOR),
                        (ball_leaf, BALL_COLOR)):
        viewport.setColor(
            leaf=leaf,
            edgeColorWireHide=color,
            edgeColorFillShade=color,
            fillColor=color,
        )


def instance_bounds(odb, name):
    low = [1e30, 1e30, 1e30]
    high = [-1e30, -1e30, -1e30]
    for node in odb.rootAssembly.instances[name].nodes:
        for axis, value in enumerate(node.coordinates):
            low[axis] = min(low[axis], float(value))
            high[axis] = max(high[axis], float(value))
    return low, high


def plate_bounds(odb):
    low = [1e30, 1e30, 1e30]
    high = [-1e30, -1e30, -1e30]
    for name in plate_instance_names():
        lo, hi = instance_bounds(odb, name)
        low = [min(a, b) for a, b in zip(low, lo)]
        high = [max(a, b) for a, b in zip(high, hi)]
    return low, high


def side_camera(odb, aspect, scale):
    """Flat-on view of the symmetry plane through the ball axis, framed on
    the ball and the plate thickness (undeformed bounds)."""
    pmin, pmax = plate_bounds(odb)
    bmin, bmax = instance_bounds(odb, BALL_INSTANCE)
    thick = min(range(3), key=lambda a: pmax[a] - pmin[a])
    center = [(bmin[a] + bmax[a]) / 2.0 for a in range(3)]
    radius = max(bmax[a] - bmin[a] for a in range(3)) / 2.0
    lateral = [a for a in range(3) if a != thick]
    up_sign = 1.0 if center[thick] > (pmin[thick] + pmax[thick]) / 2.0 else -1.0
    far_face = pmin[thick] if up_sign > 0 else pmax[thick]
    top = center[thick] + up_sign * radius
    # extend one ball radius past the far face so the ball's passage stays in frame
    low = far_face - up_sign * radius
    height = 1.15 * abs(top - low) * scale
    extent = max(pmax[a] - pmin[a] for a in range(3))
    distance = 3.0 * extent
    up_vec = [0.0, 0.0, 0.0]
    up_vec[thick] = up_sign
    width = height * aspect

    def layout(normal_axis):
        other_axis = [a for a in lateral if a != normal_axis][0]
        at_min_ = abs(center[normal_axis] - pmin[normal_axis]) <= abs(
            center[normal_axis] - pmax[normal_axis])
        side_ = -1.0 if at_min_ else 1.0
        plate_dir_ = 1.0 if (center[other_axis] - pmin[other_axis]) <= (
            pmax[other_axis] - center[other_axis]) else -1.0
        view_dir_ = [0.0, 0.0, 0.0]
        view_dir_[normal_axis] = -side_
        right_ = [view_dir_[1] * up_vec[2] - view_dir_[2] * up_vec[1],
                  view_dir_[2] * up_vec[0] - view_dir_[0] * up_vec[2],
                  view_dir_[0] * up_vec[1] - view_dir_[1] * up_vec[0]]
        return other_axis, at_min_, side_, plate_dir_, right_[other_axis] * plate_dir_ > 0

    # Prefer the symmetry plane that puts the plate on the right of the frame.
    candidates = sorted(lateral, key=lambda a: min(
        abs(center[a] - pmin[a]), abs(center[a] - pmax[a])))
    normal = candidates[0]
    for candidate in candidates:
        if layout(candidate)[4]:
            normal = candidate
            break
    other, at_min, side, plate_dir, plate_on_right = layout(normal)
    shift = (width / 2.0 - 1.5 * radius) * plate_dir * (1.0 if plate_on_right else -1.0)
    target = [0.0, 0.0, 0.0]
    target[thick] = (low + top) / 2.0
    target[other] = center[other] + shift
    target[normal] = pmin[normal] if at_min else pmax[normal]
    position = list(target)
    position[normal] += side * distance
    up = [0.0, 0.0, 0.0]
    up[thick] = up_sign
    return {
        "cameraPosition": [float(v) for v in position],
        "cameraTarget": [float(v) for v in target],
        "cameraUpVector": [float(v) for v in up],
        "nearPlane": float(distance - extent),
        "farPlane": float(distance + 2.0 * extent),
        "width": float(width),
        "height": float(height),
    }


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def side_camera_vertical(odb, aspect, scale):
    """Symmetry-plane view turned so the plate is a vertical band and the
    ball travels left to right. Parallel projection, framed on the ball's
    approach, the plate thickness and one ball radius past the far face."""
    pmin, pmax = plate_bounds(odb)
    bmin, bmax = instance_bounds(odb, BALL_INSTANCE)
    thick = min(range(3), key=lambda a: pmax[a] - pmin[a])
    center = [(bmin[a] + bmax[a]) / 2.0 for a in range(3)]
    radius = max(bmax[a] - bmin[a] for a in range(3)) / 2.0
    lateral = [a for a in range(3) if a != thick]
    up_sign = 1.0 if center[thick] > (pmin[thick] + pmax[thick]) / 2.0 else -1.0
    far_face = pmin[thick] if up_sign > 0 else pmax[thick]
    top = center[thick] + up_sign * radius
    low = far_face - up_sign * radius
    width = 1.15 * abs(top - low) * scale
    height = width / aspect
    extent = max(pmax[a] - pmin[a] for a in range(3))
    distance = 3.0 * extent
    travel = [0.0, 0.0, 0.0]
    travel[thick] = -up_sign          # ball moves toward the far face

    options = []
    # nearest symmetry plane first; camera sits outside the model looking in
    for normal in sorted(lateral, key=lambda a: min(
            abs(center[a] - pmin[a]), abs(center[a] - pmax[a]))):
        other = [a for a in lateral if a != normal][0]
        at_min = abs(center[normal] - pmin[normal]) <= abs(
            center[normal] - pmax[normal])
        side = -1.0 if at_min else 1.0
        plate_dir = 1.0 if (center[other] - pmin[other]) <= (
            pmax[other] - center[other]) else -1.0
        view_dir = [0.0, 0.0, 0.0]
        view_dir[normal] = -side
        for up_along in (1.0, -1.0):
            up = [0.0, 0.0, 0.0]
            up[other] = up_along
            right = _cross(view_dir, up)
            if right[thick] * travel[thick] > 0:
                plate_up = (up_along == plate_dir)
                options.append((not plate_up, len(options), normal, other,
                                at_min, side, plate_dir, up))
    if not options:
        raise RuntimeError("no symmetry-plane view puts the ball travel to the right")
    options.sort(key=lambda o: (o[0], o[1]))
    _, _, normal, other, at_min, side, plate_dir, up = options[0]

    target = [0.0, 0.0, 0.0]
    target[thick] = (low + top) / 2.0
    # ball axis 1.5 radii from the frame edge opposite the plate
    target[other] = center[other] + plate_dir * (height / 2.0 - 1.5 * radius)
    target[normal] = pmin[normal] if at_min else pmax[normal]
    position = list(target)
    position[normal] += side * distance
    return {
        "cameraPosition": [float(v) for v in position],
        "cameraTarget": [float(v) for v in target],
        "cameraUpVector": [float(v) for v in up],
        "nearPlane": float(distance - extent),
        "farPlane": float(distance + 2.0 * extent),
        "width": float(width),
        "height": float(height),
    }


ORBIT_VIEWS = {
    # name: (azimuth deg from the symmetry-plane corner, elevation deg, focus)
    "cut": (0.0, 35.0, "plate"),        # into the symmetry-plane cut faces
    "outer": (180.0, 35.0, "plate"),    # from the free side, over the plate
    "top": (0.0, 90.0, "plate"),        # straight down onto the impact face
    "bottom": (0.0, -90.0, "plate"),    # from beneath, the back face
    "grazing": (90.0, 8.0, "plate"),    # low angle along the plate surface
    "close": (0.0, 28.0, "ball"),       # zoomed on the contact region
}


def orbit_camera(odb, aspect, name, closeup_scale):
    """Parallel-projection camera orbiting the quarter model. Azimuth 0 looks
    from the symmetry-plane side toward the plate interior, elevation is
    measured from the lateral plane toward the ball side."""
    az, el, focus = ORBIT_VIEWS[name]
    pmin, pmax = plate_bounds(odb)
    bmin, bmax = instance_bounds(odb, BALL_INSTANCE)
    thick = min(range(3), key=lambda a: pmax[a] - pmin[a])
    center = [(bmin[a] + bmax[a]) / 2.0 for a in range(3)]
    radius = max(bmax[a] - bmin[a] for a in range(3)) / 2.0
    lateral = [a for a in range(3) if a != thick]
    up_sign = 1.0 if center[thick] > (pmin[thick] + pmax[thick]) / 2.0 else -1.0
    extent = max(pmax[a] - pmin[a] for a in range(3))
    # unit vector from the ball axis toward the plate interior, per lateral axis
    toward = {}
    for a in lateral:
        toward[a] = 1.0 if (center[a] - pmin[a]) <= (pmax[a] - center[a]) else -1.0
    e1, e2 = lateral
    norm = math.sqrt(2.0)
    # azimuth 0: camera on the symmetry-plane side, looking toward the interior
    base = [0.0, 0.0, 0.0]
    base[e1] = -toward[e1] / norm
    base[e2] = -toward[e2] / norm
    perp = [0.0, 0.0, 0.0]
    perp[e1] = -base[e2]
    perp[e2] = base[e1]
    ar, er = math.radians(az), math.radians(el)
    direction = [0.0, 0.0, 0.0]
    for axis in range(3):
        horizontal = math.cos(ar) * base[axis] + math.sin(ar) * perp[axis]
        direction[axis] = math.cos(er) * horizontal
    direction[thick] += math.sin(er) * up_sign
    if abs(el) > 89.0:
        up = list(base)
        if el < 0.0:
            up = [-v for v in up]
    else:
        up = [0.0, 0.0, 0.0]
        up[thick] = up_sign
    target = [(pmin[a] + pmax[a]) / 2.0 for a in range(3)]
    if focus == "ball":
        target = list(center)
        target[thick] = center[thick] - up_sign * radius
        width = 7.0 * radius * closeup_scale
    else:
        # the ball sits at the quarter-model corner: bias the frame toward it
        width = 1.45 * extent
        target[thick] = (pmin[thick] + pmax[thick]) / 2.0
        for a in lateral:
            target[a] = center[a] + 0.45 * (target[a] - center[a])
    height = width / aspect
    distance = 3.0 * extent
    position = [target[a] + direction[a] * distance for a in range(3)]
    return {
        "cameraPosition": [float(v) for v in position],
        "cameraTarget": [float(v) for v in target],
        "cameraUpVector": [float(v) for v in up],
        "nearPlane": float(distance - 1.5 * extent),
        "farPlane": float(distance + 2.0 * extent),
        "width": float(width),
        "height": float(height),
    }


def render_pass(viewport, step_index, step, frame_indices, pass_name,
                output_dir, cameras, frame_records, status_position):

    if pass_name == "status":
        set_status_display(viewport, status_position)
    elif pass_name == "displacement":
        set_motion_display(viewport, "U")
    elif pass_name == "velocity":
        set_motion_display(viewport, "V")
    elif pass_name == "fibers":
        set_fiber_display(viewport)
    elif pass_name == "wire":
        set_wire_display(viewport)
    else:
        raise ValueError("unsupported render pass: {0}".format(pass_name))

    for view_name, camera in cameras:
        pass_dir = os.path.join(output_dir, pass_name, view_name)
        ensure_directory(pass_dir)
        try:
            if view_name in ("side", "sidev") or view_name in ORBIT_VIEWS:
                # width/height only take effect in a parallel projection
                viewport.view.setValues(projection=PARALLEL)
            elif ISO_PROJECTION[0] is not None:
                viewport.view.setValues(projection=ISO_PROJECTION[0])
        except Exception as exc:
            print("warning: could not set projection: {0}".format(exc))
        apply_camera(viewport.view, camera)
        for sequence, frame_index in enumerate(frame_indices):
            frame = step.frames[frame_index]
            viewport.odbDisplay.setFrame(step=step_index, frame=frame_index)
            stem = "{0}_{1}_{2:04d}".format(pass_name, view_name, sequence)
            target = os.path.join(pass_dir, stem)
            session.printToFile(
                fileName=target,
                format=PNG,
                canvasObjects=(viewport,),
            )
            frame_records.append({
                "pass": pass_name,
                "view": view_name,
                "sequence": sequence,
                "odb_frame_index": frame_index,
                "step_time": frame.frameValue,
                "png": os.path.relpath(target + ".png", output_dir),
            })
            if sequence % 20 == 0 or sequence + 1 == len(frame_indices):
                print("{0}/{1}: rendered {2}/{3}".format(
                    pass_name, view_name, sequence + 1, len(frame_indices)))


def write_manifest(output_dir, manifest, frame_records):
    manifest_path = os.path.join(output_dir, "render_manifest.json")
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    csv_path = os.path.join(output_dir, "frame_map.csv")
    with open(csv_path, "w") as handle:
        writer = csv.writer(handle)
        writer.writerow(("pass", "view", "sequence", "odb_frame_index", "step_time", "png"))
        for record in frame_records:
            writer.writerow((
                record["pass"], record["view"], record["sequence"],
                record["odb_frame_index"], record["step_time"], record["png"]))


def render(cli_arguments):
    args = parse_arguments(cli_arguments)
    passes = [value.strip().lower() for value in args.passes.split(",") if value.strip()]
    invalid = [value for value in passes
               if value not in ("status", "displacement", "velocity", "fibers", "wire")]
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
        plywise_odb = detect_plywise(odb)
        print("plywise ODB: {0}; plate instances: {1}".format(
            plywise_odb, plate_instance_names()))
        if not plywise_odb:
            require_key(odb.rootAssembly.instances, PLATE_INSTANCE, "instance")
        require_key(odb.rootAssembly.instances, BALL_INSTANCE, "instance")
        require_key(odb.rootAssembly.elementSets, GHOST_ELSET, "element set")
        if not plywise_odb:
            fiber_instance_name = require_key(
                odb.rootAssembly.instances, FIBER_INSTANCE, "instance")
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
        view_names = [v.strip().lower() for v in args.views.split(",") if v.strip()]
        bad_views = [v for v in view_names
                     if v not in ("iso", "side", "sidev") and v not in ORBIT_VIEWS]
        if bad_views or not view_names:
            raise ValueError("unsupported --views values: {0}".format(args.views))
        cameras = []
        for view_name in view_names:
            if view_name == "iso":
                viewport.view.setValues(session.views[args.view])
                viewport.view.fitView()
                ISO_PROJECTION[0] = getattr(viewport.view, "projection", None)
                cameras.append((view_name, camera_state(viewport.view)))
            else:
                aspect = float(args.image_width) / float(args.image_height)
                if view_name in ORBIT_VIEWS:
                    cameras.append((view_name, orbit_camera(
                        odb, aspect, view_name, args.closeup_scale)))
                    continue
                make_camera = (side_camera_vertical if view_name == "sidev"
                               else side_camera)
                cameras.append((view_name, make_camera(
                    odb, aspect, args.closeup_scale)))
        camera = dict(cameras)

        records = []
        for pass_name in passes:
            render_pass(
                viewport, step_index, step, selected, pass_name,
                output_dir, cameras, records, status_position)

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
                "element_sets": list(fiber_set_names()),
                "host_element_set": GHOST_ELSET,
                "host_translucency": FIBER_HOST_TRANSLUCENCY,
                "host_color": HOST_COLOR,
                "fiber_color": FIBER_COLOR,
                "ball_color": BALL_COLOR,
                "plot_state": "DEFORMED",
            },
            "image_size": [args.image_width, args.image_height],
            "intended_fps": args.fps,
            "intended_duration_seconds": len(selected) / args.fps,
            "deformation_scale": args.deformation_scale,
            "view_preset": args.view,
            "views": view_names,
            "closeup_scale": args.closeup_scale,
            "wire_render": {
                "host_color": WIRE_HOST_COLOR,
                "fiber_color": WIRE_FIBER_COLOR,
                "ball_color": BALL_COLOR,
                "visible_edges": "EXTERIOR",
            },
            "fit_view_frame_index": selected[0],
            "fit_view_step_time": step.frames[selected[0]].frameValue,
            "camera": camera,
            "background": "#FFFFFF",
            "visible_edges": "FEATURE",
            "status_contour_range": [0.0, 1.0],
            "status_contour_intervals": 2,
            "frame_records": records,
            "ffmpeg_examples": [
                "ffmpeg -framerate {0:g} -i status/iso/status_iso_%04d.png "
                "-c:v libx264 -pix_fmt yuv420p status.mp4".format(args.fps),
                "ffmpeg -framerate {0:g} -i displacement/iso/displacement_iso_%04d.png "
                "-c:v libx264 -pix_fmt yuv420p displacement.mp4".format(args.fps),
                "ffmpeg -framerate {0:g} -i fibers/iso/fibers_iso_%04d.png "
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
