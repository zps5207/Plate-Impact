"""Mesher-generated node-to-ball general contact for Abaqus/Explicit decks."""
from __future__ import annotations

from pathlib import Path
import re
import numpy as np


BALL_ELSET = "EMBMESH_BALL_ELEMENTS"
BALL_SURFACE = "EMBMESH_BALL_SURF"
PLATE_NSET = "EMBMESH_PLATE_ALL_NODES"
PLATE_SURFACE = "EMBMESH_PLATE_NODES"
FIBER_NSET = "EMBMESH_FIBER_ALL_NODES"
FIBER_SURFACE = "EMBMESH_FIBER_NODES"
CONTACT_INTERACTION = "EMBMESH_CONTACT"


def _keyword(line):
    fields = [x.strip() for x in line.strip()[1:].split(",")]
    name = fields[0].lower()
    opts = {}
    for field in fields[1:]:
        if "=" in field:
            key, value = field.split("=", 1)
            opts[key.strip().lower()] = value.strip()
        elif field:
            opts[field.lower()] = True
    return name, opts


def _set_lines(keyword, name, instance, labels):
    labels = sorted(set(int(x) for x in labels))
    result = [f"*{keyword}, {keyword.lower()}={name}, instance={instance}"]
    result += [", ".join(str(x) for x in labels[i:i + 16])
               for i in range(0, len(labels), 16)]
    return result


def median_host_edge_length(elements, nodes):
    """Median of the 12 edge lengths of every selected eight-node host."""
    edge_indices = ((0, 1), (1, 2), (2, 3), (3, 0),
                    (4, 5), (5, 6), (6, 7), (7, 4),
                    (0, 4), (1, 5), (2, 6), (3, 7))
    lengths = []
    for element in elements.values():
        conn = element.connectivity[:8]
        if len(conn) != 8:
            continue
        for a, b in edge_indices:
            lengths.append(float(np.linalg.norm(nodes[conn[a]] - nodes[conn[b]])))
    if not lengths:
        raise ValueError("cannot calculate automatic contact thickness: selected host has no eight-node element edges")
    return float(np.median(lengths))


def median_fiber_segment_length(fibers):
    lengths = [float(np.linalg.norm(np.asarray(b) - np.asarray(a)))
               for fiber in fibers for a, b in zip(fiber.points[:-1], fiber.points[1:])]
    if not lengths:
        raise ValueError("cannot calculate automatic fiber contact thickness: no fiber segments were generated")
    return float(np.median(lengths))


def resolve_contact_thickness(spec, host_edge, fiber_segment, plate, fibers):
    """Return per-surface thicknesses in deck units.

    ``auto`` is half the median selected-host edge for plate contact.  Fiber
    contact uses half the smaller of that spacing and the median generated
    segment length, limiting rather than enlarging the unvalidated fiber
    contact envelope.
    """
    if isinstance(spec, str) and spec.strip().lower() == "auto":
        return (0.5 * host_edge if plate else None,
                0.5 * min(host_edge, fiber_segment) if fibers else None)
    try:
        value = float(spec)
    except (TypeError, ValueError):
        raise ValueError("--contact-thickness must be a non-negative number or 'auto'")
    if value < 0:
        raise ValueError("--contact-thickness must be non-negative")
    return (value if plate else None, value if fibers else None)


def _first_interaction(lines):
    for line in lines:
        if line.lstrip().startswith("*") and not line.lstrip().startswith("**"):
            name, opts = _keyword(line)
            if name == "surface interaction":
                interaction = str(opts.get("name", "")).strip()
                if interaction:
                    return interaction
    return None


def _block_data_end(lines, keyword_index, limit):
    i = keyword_index + 1
    # Insert before the next keyword or comment so generated data stays
    # adjacent to the user block it extends (and, for contact properties,
    # visibly inside *Contact before subsequent output-request comments).
    while i < limit and not lines[i].lstrip().startswith("*"):
        i += 1
    return i


def _augment_step_contact(lines, pairs, interaction, thicknesses):
    step = next((i for i, line in enumerate(lines)
                 if line.lstrip().startswith("*") and
                 not line.lstrip().startswith("**") and _keyword(line)[0] == "step"), None)
    if step is None:
        raise ValueError("source deck has no *Step in which to create ball contact")
    end_step = next((i for i in range(step + 1, len(lines))
                     if lines[i].lstrip().startswith("*") and
                     not lines[i].lstrip().startswith("**") and
                     _keyword(lines[i])[0] == "end step"), None)
    if end_step is None:
        raise ValueError("source deck has no matching *End Step")
    contact = next((i for i in range(step + 1, end_step)
                    if lines[i].lstrip().startswith("*") and
                    not lines[i].lstrip().startswith("**") and
                    _keyword(lines[i])[0] == "contact"), None)
    thickness_lines = []
    for surface, value in thicknesses:
        if value is not None and value > 0:
            thickness_lines += ["*Surface Property Assignment, property=THICKNESS",
                                f"{surface}, {value:.15g}"]
    pair_lines = [f"{left} , {right}" for left, right in pairs]
    if contact is None:
        block = ["** embmesh generated node-to-ball contact", "*Contact, op=NEW",
                 "*Contact Inclusions"] + pair_lines + [
                 "*Contact Property Assignment", f" ,  , {interaction}"] + thickness_lines
        return lines[:end_step] + block + lines[end_step:], False

    # Abaqus permits one *Contact per step. Extend its inclusions and keep all
    # user-authored lines intact.
    inclusions = next((i for i in range(contact + 1, end_step)
                       if lines[i].lstrip().startswith("*") and
                       not lines[i].lstrip().startswith("**") and
                       _keyword(lines[i])[0] == "contact inclusions"), None)
    if inclusions is None:
        lines[contact + 1:contact + 1] = ["*Contact Inclusions"] + pair_lines
        end_step += 1 + len(pair_lines)
    else:
        insert_at = _block_data_end(lines, inclusions, end_step)
        lines[insert_at:insert_at] = pair_lines
        end_step += len(pair_lines)

    prop = next((i for i in range(contact + 1, end_step)
                 if lines[i].lstrip().startswith("*") and
                 not lines[i].lstrip().startswith("**") and
                 _keyword(lines[i])[0] == "contact property assignment"), None)
    if prop is None:
        lines[end_step:end_step] = ["*Contact Property Assignment", f" ,  , {interaction}"] + thickness_lines
    else:
        insert_at = _block_data_end(lines, prop, end_step)
        lines[insert_at:insert_at] = thickness_lines
    return lines, True


def add_ball_node_contact(path, deck, host_instance, host_elements, host_nodes,
                          fibers, node_offset, ball_instance, plate=False,
                          fiber=False, thickness="auto", fiber_instance="EMBFIB-1"):
    """Patch the generated deck and return report-ready contact metadata."""
    if not (plate or fiber):
        return None
    if not ball_instance:
        raise ValueError("--ball-instance is required when node contact is enabled")
    if ball_instance not in deck.instances:
        choices = ", ".join(sorted(deck.instances)) or "none"
        raise ValueError(f"ball instance {ball_instance!r} was not found; available instances: {choices}")
    ball = deck.instances[ball_instance]
    ball_part = deck.parts.get(ball.part)
    if ball_part is None or not ball_part.elements:
        raise ValueError(f"ball instance {ball_instance!r} has no parsed elements")

    host_edge = median_host_edge_length(host_elements, host_nodes)
    fiber_segment = median_fiber_segment_length(fibers) if fiber else None
    plate_thickness, fiber_thickness = resolve_contact_thickness(
        thickness, host_edge, fiber_segment, plate, fiber)
    fiber_labels = range(node_offset, node_offset + sum(len(f.points) for f in fibers))
    host_part = deck.parts[deck.instances[host_instance].part]

    lines = Path(path).read_text().splitlines()
    end_assembly = max(i for i, line in enumerate(lines)
                       if line.lstrip().startswith("*") and
                       not line.lstrip().startswith("**") and
                       _keyword(line)[0] == "end assembly")
    assembly_data = _set_lines("Elset", BALL_ELSET, ball_instance, ball_part.elements)
    assembly_data += [f"*Surface, type=ELEMENT, name={BALL_SURFACE}", f"{BALL_ELSET},"]
    pairs = []
    thicknesses = []
    if plate:
        assembly_data += _set_lines("Nset", PLATE_NSET, host_instance, host_part.nodes)
        assembly_data += [f"*Surface, type=NODE, name={PLATE_SURFACE}", f"{PLATE_NSET},"]
        pairs.append((PLATE_SURFACE, BALL_SURFACE))
        thicknesses.append((PLATE_SURFACE, plate_thickness))
    if fiber:
        assembly_data += _set_lines("Nset", FIBER_NSET, fiber_instance, fiber_labels)
        assembly_data += [f"*Surface, type=NODE, name={FIBER_SURFACE}", f"{FIBER_NSET},"]
        pairs.append((FIBER_SURFACE, BALL_SURFACE))
        thicknesses.append((FIBER_SURFACE, fiber_thickness))
    lines[end_assembly:end_assembly] = ["** embmesh generated ball-contact sets and surfaces"] + assembly_data

    interaction = _first_interaction(lines)
    reused = interaction is not None
    if interaction is None:
        interaction = CONTACT_INTERACTION
        first_step = next(i for i, line in enumerate(lines)
                          if line.lstrip().startswith("*") and
                          not line.lstrip().startswith("**") and _keyword(line)[0] == "step")
        lines[first_step:first_step] = [
            "** embmesh generated frictionless hard contact interaction",
            f"*Surface Interaction, name={interaction}",
            "*Friction", "0.0",
            "*Surface Behavior, pressure-overclosure=HARD",
        ]
    lines, extended = _augment_step_contact(lines, pairs, interaction, thicknesses)
    Path(path).write_text("\n".join(lines) + "\n")
    return {
        "enabled": True,
        "ball_instance": ball_instance,
        "ball_surface": BALL_SURFACE,
        "ball_element_count": len(ball_part.elements),
        "plate_surface": PLATE_SURFACE if plate else None,
        "plate_node_count": len(host_part.nodes) if plate else 0,
        "fiber_surface": FIBER_SURFACE if fiber else None,
        "fiber_node_count": sum(len(f.points) for f in fibers) if fiber else 0,
        "host_median_edge_length": host_edge,
        "fiber_median_segment_length": fiber_segment,
        "plate_contact_thickness": plate_thickness,
        "fiber_contact_thickness": fiber_thickness,
        "interaction": interaction,
        "interaction_reused": reused,
        "existing_contact_extended": extended,
    }
