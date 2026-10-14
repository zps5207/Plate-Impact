from __future__ import annotations

from dataclasses import dataclass
import re


VUEL_ELSET = "EMBMESH_VUEL_HOST"
GHOST_ELSET = "EMBMESH_GHOST_HOST"
GHOST_MATERIAL = "EMBMESH_GHOST_MATERIAL"
GHOST_CONTROLS = "EMBMESH_GHOST_CONTROLS"
GHOST_DIAGNOSTIC_ELSET = "EMBMESH_GHOST_DIAGNOSTICS"
GHOST_DIAGNOSTIC_VARIABLES = ("S", "LE", "PEEQ", "SDEG", "STATUS")
VUEL_DIAGNOSTICS_ELSET = "EMBMESH_VUEL_DIAGNOSTICS"
NSVARS = 107


def _keyword(line):
    fields = [x.strip() for x in line[1:].split(",")]
    name = fields[0].lower()
    options = {}
    for field in fields[1:]:
        if "=" in field:
            key, value = field.split("=", 1)
            options[key.strip().lower()] = value.strip()
        elif field:
            options[field.lower()] = True
    return name, options


def _blocks(lines):
    """Yield keyword blocks while retaining leading comments/blank lines."""
    prefix = []
    i = 0
    while i < len(lines):
        if not lines[i].lstrip().startswith("*") or lines[i].lstrip().startswith("**"):
            prefix.append(lines[i])
            i += 1
            continue
        start = i
        i += 1
        while i < len(lines) and not (
            lines[i].lstrip().startswith("*") and not lines[i].lstrip().startswith("**")
        ):
            i += 1
        yield prefix, lines[start:i]
        prefix = []
    if prefix:
        yield prefix, []


def _float_fields(line):
    try:
        return [float(x.strip()) for x in line.split(",") if x.strip()]
    except ValueError:
        return []


def _format(value):
    return f"{value:.15g}"


def _records(data_lines):
    records = []
    pending = ""
    for raw in data_lines:
        if raw.lstrip().startswith("**") or not raw.strip():
            continue
        pending = pending + raw.strip()
        if pending.endswith(","):
            continue
        records.append(pending)
        pending = ""
    if pending:
        records.append(pending)
    return records


def _set_lines(name, labels):
    result = [f"*Elset, elset={name}"]
    labels = sorted(labels)
    result.extend(", ".join(str(v) for v in labels[i:i + 16]) for i in range(0, len(labels), 16))
    return result


def _instance_set_lines(name, instance, labels):
    result = [f"*Elset, elset={name}, instance={instance}"]
    labels = sorted(labels)
    result.extend(", ".join(str(v) for v in labels[i:i + 16]) for i in range(0, len(labels), 16))
    return result


def _ghost_diagnostic_output_lines():
    return [
        "** embmesh: native ghost yield/damage/deletion diagnostics",
        "*Output, field, number interval=1000",
        f"*Element Output, elset={GHOST_DIAGNOSTIC_ELSET}",
        ", ".join(GHOST_DIAGNOSTIC_VARIABLES),
    ]


@dataclass(frozen=True)
class VuelGhostOptions:
    ghost_scale: float = 1.0e-4
    ghost_ductile_failure_strain: float | None = None
    eps_fail: float | None = None
    sigy0: float | None = None
    hardening_modulus: float | None = None
    jac_fail: float = 0.05
    degrade_time: float = 0.0
    compression_residual_bulk_fraction: float = 0.0
    rayleigh_beta: float = 0.0
    bulk_viscosity_linear: float = 0.06
    bulk_viscosity_quadratic: float = 1.2
    plasticity: bool = True

    def validate(self):
        if not (0.0 < self.ghost_scale < 1.0):
            raise ValueError("--ghost-scale must be between zero and one")
        if self.ghost_ductile_failure_strain is not None and self.ghost_ductile_failure_strain <= 0.0:
            raise ValueError("--ghost-ductile-failure-strain must be strictly positive")
        if self.eps_fail is not None and self.eps_fail <= 0.0:
            raise ValueError("--vuel-eps-fail must be positive")
        if self.sigy0 is not None and self.sigy0 < 0.0:
            raise ValueError("--vuel-yield-stress must be non-negative")
        if self.hardening_modulus is not None and self.hardening_modulus < 0.0:
            raise ValueError("--vuel-hardening-modulus must be non-negative")
        if self.jac_fail < 0.0:
            raise ValueError("--vuel-jac-fail must be non-negative")
        if self.degrade_time < 0.0:
            raise ValueError("--vuel-degrade-time must be non-negative")
        if not 0.0 <= self.compression_residual_bulk_fraction <= 1.0:
            raise ValueError("--vuel-compression-residual must be in [0, 1]")


def _section_material(lines, part_name, selected, part_elsets):
    current_part = None
    found = set()
    for _, block in _blocks(lines):
        if not block:
            continue
        name, options = _keyword(block[0])
        if name == "part":
            current_part = str(options.get("name", ""))
        elif name == "end part":
            current_part = None
        elif name == "solid section" and current_part == part_name:
            elset = str(options.get("elset", ""))
            if selected & set(part_elsets.get(elset, ())):
                material = options.get("material")
                if material:
                    found.add(str(material))
    if len(found) != 1:
        raise ValueError(
            "VUEL+ghost mode requires the selected C3D8R hosts to share exactly one "
            f"*Solid Section material; found {sorted(found)!r}"
        )
    return found.pop()


def _material_block(lines, material_name):
    blocks = list(_blocks(lines))
    for index, (_, block) in enumerate(blocks):
        if not block:
            continue
        name, options = _keyword(block[0])
        if name != "material" or str(options.get("name", "")).lower() != material_name.lower():
            continue
        result = [block]
        for _, following in blocks[index + 1:]:
            if not following:
                break
            following_name, _ = _keyword(following[0])
            if following_name in {"material", "step"}:
                break
            result.append(following)
        return result
    raise ValueError(f"material {material_name!r} assigned to the selected host was not found")


def _material_properties(blocks):
    density = young = poisson = None
    plastic = []
    ductile_failure_strain = None
    for block in blocks[1:]:
        name, _ = _keyword(block[0])
        rows = [_float_fields(x) for x in block[1:] if x.strip() and not x.lstrip().startswith("**")]
        rows = [x for x in rows if x]
        if name == "density" and rows:
            density = rows[0][0]
        elif name == "elastic" and rows and len(rows[0]) >= 2:
            young, poisson = rows[0][:2]
        elif name == "plastic":
            plastic = [x[:2] for x in rows if len(x) >= 2]
        elif name == "damage initiation" and rows:
            ductile_failure_strain = rows[0][0]
    if density is None or young is None or poisson is None:
        raise ValueError("the host material must define scalar *Density and isotropic *Elastic data")
    if not plastic:
        raise ValueError("VUEL+ghost mode requires host *Plastic data for synchronized ductile deletion")
    sigy0 = plastic[0][0]
    hardening = 0.0
    for stress, strain in plastic[1:]:
        if strain > plastic[0][1]:
            hardening = (stress - sigy0) / (strain - plastic[0][1])
            break
    return {
        "density": density,
        "young": young,
        "poisson": poisson,
        "sigy0": sigy0,
        "hardening": max(hardening, 0.0),
        "ductile_failure_strain": ductile_failure_strain,
    }


def _scaled_ghost_material(blocks, scale, ductile_failure_strain=None):
    output = [f"*Material, name={GHOST_MATERIAL}"]
    for block in blocks[1:]:
        name, _ = _keyword(block[0])
        if name not in {"density", "elastic", "plastic", "damage initiation", "damage evolution"}:
            continue
        output.append(block[0])
        for line in block[1:]:
            values = _float_fields(line)
            if not values:
                output.append(line)
                continue
            if name in {"density", "elastic", "plastic"}:
                values[0] *= scale
            elif name == "damage initiation" and ductile_failure_strain is not None:
                values[0] = ductile_failure_strain
            output.append(", ".join(_format(value) for value in values))
    if not any(_keyword(line)[0] == "damage initiation" for line in output if line.startswith("*") and not line.startswith("**")):
        raise ValueError("the host material must define *Damage Initiation for ghost deletion")
    if not any(_keyword(line)[0] == "damage evolution" for line in output if line.startswith("*") and not line.startswith("**")):
        raise ValueError("the host material must define *Damage Evolution for ghost deletion")
    return output


def _initial_solution_lines(instance, fractions):
    lines = ["** embmesh: SVAR107 is the per-host fiber volume fraction",
             "*Initial Conditions, type=SOLUTION"]
    zeros = ["0"] * 106
    for label in sorted(fractions):
        values = zeros + [_format(fractions[label])]
        # The identifier plus SDV1..7 occupy the first line; continuation
        # lines carry eight values each, per *INITIAL CONDITIONS syntax.
        lines.append(", ".join([f"{instance}.{label}"] + values[:7]))
        for start in range(7, NSVARS, 8):
            lines.append(", ".join(values[start:start + 8]))
    return lines


def convert_to_vuel_ghost(lines, deck, instance, selected_elements, fractions, options=None):
    """Convert selected native C3D8R hosts to node-coincident VU1+ghost pairs.

    Returns ``(new_lines, ghost_label_by_host, metadata)``. The original
    material is retained for any non-host users; the ghost gets a scaled copy
    of its elastic, density, plastic, and ductile-damage data.
    """
    options = options or VuelGhostOptions()
    options.validate()
    selected = set(selected_elements)
    if set(fractions) != selected:
        missing = sorted(selected - set(fractions))[:5]
        extra = sorted(set(fractions) - selected)[:5]
        raise ValueError(f"fiber fractions must cover exactly the selected hosts (missing={missing}, extra={extra})")
    inst = deck.instances[instance]
    part = deck.parts[inst.part]
    wrong = sorted(label for label in selected if part.elements[label].type.upper() != "C3D8R")
    if wrong:
        raise ValueError(f"VUEL+ghost mode supports selected C3D8R elements only; incompatible labels: {wrong[:8]}")

    material_name = _section_material(lines, part.name, selected, part.elsets)
    source_material = _material_block(lines, material_name)
    inferred = _material_properties(source_material)
    eps_fail = options.eps_fail
    if eps_fail is None:
        eps_fail = inferred["ductile_failure_strain"]
    if eps_fail is None or eps_fail <= 0.0:
        raise ValueError("set --vuel-eps-fail or provide a positive host ductile failure strain")
    sigy0 = inferred["sigy0"] if options.sigy0 is None else options.sigy0
    hardening = inferred["hardening"] if options.hardening_modulus is None else options.hardening_modulus

    ghost_start = max(part.elements) + 1
    ghost_by_host = {label: ghost_start + i for i, label in enumerate(sorted(selected))}
    collected = {}
    transformed = []
    current_part = None
    native_section_index = 0
    for prefix, block in _blocks(lines):
        transformed.extend(prefix)
        if not block:
            continue
        name, keyword_options = _keyword(block[0])
        if name == "part":
            current_part = str(keyword_options.get("name", ""))
        if current_part == part.name and name == "element" and str(keyword_options.get("type", "")).upper() == "C3D8R":
            kept = []
            for record in _records(block[1:]):
                fields = [x.strip() for x in record.split(",") if x.strip()]
                label = int(fields[0])
                if label in selected:
                    collected[label] = tuple(int(x) for x in fields[1:])
                else:
                    kept.append(record)
            if kept:
                transformed.extend([block[0]] + kept)
            continue
        if current_part == part.name and name == "solid section":
            elset = str(keyword_options.get("elset", ""))
            members = set(part.elsets.get(elset, ()))
            if members & selected:
                remainder = members - selected
                if remainder:
                    native_section_index += 1
                    replacement = f"EMBMESH_NATIVE_REMAINDER_{native_section_index}"
                    transformed.extend(_set_lines(replacement, remainder))
                    transformed.extend([
                        re.sub(r"(?i)(elset\s*=\s*)[^,]+", rf"\g<1>{replacement}", block[0])
                    ] + block[1:])
                continue
        if current_part == part.name and name == "end part":
            if set(collected) != selected:
                missing = sorted(selected - set(collected))[:8]
                raise ValueError(f"could not find selected C3D8R records in part {part.name!r}: {missing}")
            props = [
                inferred["young"], inferred["poisson"], inferred["density"], options.rayleigh_beta,
                options.bulk_viscosity_linear, options.bulk_viscosity_quadratic, eps_fail, sigy0,
                hardening, 1.0 if options.plasticity else 0.0, options.jac_fail,
                options.degrade_time, options.compression_residual_bulk_fraction,
            ]
            transformed.extend([
                f"*User Element, type=VU1, nodes=8, coordinates=3, properties=13, variables={NSVARS}",
                "1, 2, 3",
                f"*Element, type=VU1, elset={VUEL_ELSET}",
            ])
            transformed.extend(
                f"{label}, " + ", ".join(str(n) for n in collected[label]) for label in sorted(collected)
            )
            transformed.append(f"*UEL Property, elset={VUEL_ELSET}")
            transformed.append(", ".join(_format(x) for x in props[:8]))
            transformed.append(", ".join(_format(x) for x in props[8:]))
            transformed.append(f"*Element, type=C3D8R, elset={GHOST_ELSET}")
            transformed.extend(
                f"{ghost_by_host[label]}, " + ", ".join(str(n) for n in collected[label])
                for label in sorted(collected)
            )
            transformed.extend([
                f"*Solid Section, elset={GHOST_ELSET}, controls={GHOST_CONTROLS}, material={GHOST_MATERIAL}",
                ",",
            ])
        transformed.extend(block)
        if name == "end part":
            current_part = None

    ghost_material = _scaled_ghost_material(
        source_material, options.ghost_scale,
        options.ghost_ductile_failure_strain)
    # Element-based contact surfaces on the host must follow the native ghost
    # elements: the VU1 host elements have no contact faces of their own.
    surface_elsets = set()
    for _, block in _blocks(transformed):
        if block and _keyword(block[0])[0] == "surface" \
                and str(_keyword(block[0])[1].get("type", "")).upper() == "ELEMENT":
            for record in _records(block[1:]):
                surface_elsets.add(record.split(",")[0].strip())
    final = []
    inserted_model_data = False
    for prefix, block in _blocks(transformed):
        final.extend(prefix)
        if not block:
            continue
        name, keyword_options = _keyword(block[0])
        if name == "elset" and str(keyword_options.get("elset", "")) in surface_elsets \
                and str(keyword_options.get("instance", "")) == instance:
            members = set()
            for record in _records(block[1:]):
                fields = [int(x) for x in record.split(",") if x.strip()]
                if "generate" in keyword_options:
                    step = fields[2] if len(fields) > 2 else 1
                    members.update(range(fields[0], fields[1] + 1, step))
                else:
                    members.update(fields)
            remapped = {ghost_by_host.get(m, m) for m in members}
            if remapped != members:
                header = re.sub(r",\s*generate\b", "", block[0], flags=re.I)
                final.extend([header] + _instance_set_lines("x", instance, remapped)[1:])
                continue
        if not inserted_model_data and name == "material":
            final.extend([
                f"*Section Controls, name={GHOST_CONTROLS}, element deletion=YES",
                "1., 1., 1.",
            ])
            final.extend(ghost_material)
            inserted_model_data = True
        if name == "end assembly":
            final.extend(_instance_set_lines(
                GHOST_DIAGNOSTIC_ELSET, instance, ghost_by_host.values()))
            final.extend(_instance_set_lines(
                VUEL_DIAGNOSTICS_ELSET, instance, ghost_by_host.keys()))
        if name == "end step":
            final.extend(_ghost_diagnostic_output_lines())
            final.extend([
                "** embmesh: host VU1 failure state diagnostics",
                "*Output, field, number interval=1000",
                f"*Element Output, elset={VUEL_DIAGNOSTICS_ELSET}",
                "SDV49, SDV106, SDV107",
            ])
        final.extend(block)
        if name == "end assembly":
            final.extend(_initial_solution_lines(instance, fractions))
    if not inserted_model_data:
        raise ValueError("source deck has no *Material block")

    metadata = {
        "host_mode": "vuel-ghost",
        "vuel_type": "VU1",
        "vuel_nsvars": NSVARS,
        "fiber_volume_svar": 107,
        "ghost_scale": options.ghost_scale,
        "ghost_ductile_failure_strain": (
            inferred["ductile_failure_strain"]
            if options.ghost_ductile_failure_strain is None
            else options.ghost_ductile_failure_strain),
        "ghost_label_min": min(ghost_by_host.values()),
        "ghost_label_max": max(ghost_by_host.values()),
        "ghost_diagnostic_elset": GHOST_DIAGNOSTIC_ELSET,
        "ghost_diagnostic_variables": list(GHOST_DIAGNOSTIC_VARIABLES),
        "source_host_material": material_name,
        "vuel_properties": props,
        "expected_host_mass_ratio_including_ghost": 1.0 + options.ghost_scale,
    }
    return final, ghost_by_host, metadata
