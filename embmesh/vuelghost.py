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
NSVARS_DAMAGE = 159
NPROPS_DAMAGE = 39
MATRIX_MODELS = ("legacy", "ductile-damage")
RATE_MODES = {"plastic": 0.0, "total": 1.0}
USER_SUBROUTINE = {"legacy": "VUEL_failure.for", "ductile-damage": "VUEL_material.for"}


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
    # "ductile-damage" selects the Stage 8 matrix (uel/VUEL_material.for, MAT_MODEL=1): rate-dependent
    # perfectly plastic J2 with energy-based ductile damage, read from the host material card.
    matrix_model: str = "legacy"
    rate_mode: str = "plastic"
    gf: float | None = None

    def validate(self):
        if self.matrix_model not in MATRIX_MODELS:
            raise ValueError(f"--matrix-model must be one of {MATRIX_MODELS}")
        if self.rate_mode not in RATE_MODES:
            raise ValueError(f"--matrix-rate-mode must be one of {tuple(RATE_MODES)}")
        if self.gf is not None and self.gf <= 0.0:
            raise ValueError("--matrix-gf must be positive")
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
    yield_blocks = []
    epsf_rows = []
    gf = None
    for block in blocks[1:]:
        name, block_options = _keyword(block[0])
        rows = [_float_fields(x) for x in block[1:] if x.strip() and not x.lstrip().startswith("**")]
        rows = [x for x in rows if x]
        if name == "density" and rows:
            density = rows[0][0]
        elif name == "elastic" and rows and len(rows[0]) >= 2:
            young, poisson = rows[0][:2]
        elif name == "plastic":
            plastic = [x[:2] for x in rows if len(x) >= 2]
            rate = block_options.get("rate")
            yield_blocks.append((float(rate) if isinstance(rate, str) else None, plastic))
        elif name == "damage initiation" and rows:
            ductile_failure_strain = rows[0][0]
            epsf_rows = [(row[2] if len(row) > 2 else None, row[0]) for row in rows]
        elif name == "damage evolution" and rows and str(block_options.get("type", "")).lower() == "energy":
            gf = rows[0][0]
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
        "yield_blocks": yield_blocks,
        "epsf_rows": epsf_rows,
        "gf": gf,
    }


def _damage_tables(inferred, options, eps_fail, sigy0):
    """Rate tables for the Stage 8 matrix from the host card: [(rate, sigma_y)], [(rate, eps_f)], Gf."""
    blocks = inferred["yield_blocks"]
    if options.sigy0 is not None or len(blocks) == 0:
        ytab = [(1.0, sigy0)]
    else:
        ytab = []
        for rate, points in blocks:
            if any(abs(stress - points[0][0]) > 1e-9 * abs(points[0][0]) for stress, _ in points[1:]):
                raise ValueError("matrix model 'ductile-damage' is perfectly plastic; the host *Plastic "
                                 "table has hardening (use the legacy model or remove it)")
            ytab.append((rate, points[0][0]))
        if len(ytab) > 1 and any(rate is None for rate, _ in ytab):
            raise ValueError("host *Plastic blocks need rate= when there is more than one")
        ytab = sorted((1.0 if rate is None else rate, stress) for rate, stress in ytab)
    if options.eps_fail is not None or not inferred["epsf_rows"]:
        etab = [(ytab[0][0], eps_fail)]
    else:
        etab = sorted((ytab[0][0] if rate is None else rate, eps) for rate, eps in inferred["epsf_rows"])
    if len(ytab) > 5 or len(etab) > 5:
        raise ValueError("the Stage 8 matrix supports at most 5 rate points per table")
    gf = options.gf if options.gf is not None else inferred["gf"]
    if gf is None:
        raise ValueError("matrix model 'ductile-damage' needs *Damage Evolution, type=ENERGY on the host "
                         "material or --matrix-gf")
    return ytab, etab, gf


def _damage_props(inferred, options, ytab, etab, gf):
    pairs = lambda tab: [x for pair in tab + [(0.0, 0.0)] * (5 - len(tab)) for x in pair]
    return [inferred["young"], inferred["poisson"], inferred["density"], options.rayleigh_beta,
            options.bulk_viscosity_linear, options.bulk_viscosity_quadratic, 10.0, ytab[0][1], 0.0, 1.0,
            0.0, 0.0, 0.0,
            1.0, RATE_MODES[options.rate_mode], gf, 0.0, float(len(ytab)), float(len(etab)),
            *pairs(ytab), *pairs(etab)]


def _mean_matrix_length(part, fractions):
    """Mean effective length (eta*V0)^(1/3) of the hosts, as the VUEL uses for the damage softening."""
    import numpy as np
    from .volume import hex_volume
    lengths = []
    for label, vf in fractions.items():
        coords = np.array([part.nodes[i] for i in part.elements[label].connectivity[:8]], float)
        lengths.append((max(1.0 - vf, 1e-6) * hex_volume(coords)) ** (1.0 / 3.0))
    return float(np.mean(lengths))


def _scaled_ghost_material(blocks, scale, ductile_failure_strain=None, instant_delete=False):
    output = [f"*Material, name={GHOST_MATERIAL}"]
    for block in blocks[1:]:
        name, _ = _keyword(block[0])
        if name not in {"density", "elastic", "plastic", "damage initiation", "damage evolution"}:
            continue
        if name == "damage evolution" and instant_delete:
            # the ghost only mirrors the VU1 host: delete it as soon as its ductile initiation strain is hit
            output.extend(["*Damage Evolution, type=DISPLACEMENT", "0."])
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


def _initial_solution_lines(instance, fractions, nsvars=NSVARS):
    lines = ["** embmesh: SVAR107 is the per-host fiber volume fraction",
             "*Initial Conditions, type=SOLUTION"]
    zeros = ["0"] * 106
    for label in sorted(fractions):
        values = zeros + [_format(fractions[label])] + ["0"] * (nsvars - 107)
        # The identifier plus SDV1..7 occupy the first line; continuation
        # lines carry eight values each, per *INITIAL CONDITIONS syntax.
        lines.append(", ".join([f"{instance}.{label}"] + values[:7]))
        for start in range(7, nsvars, 8):
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
    damage = options.matrix_model == "ductile-damage"
    nsvars = NSVARS_DAMAGE if damage else NSVARS
    ghost_fail = options.ghost_ductile_failure_strain
    if damage:
        ytab, etab, gf = _damage_tables(inferred, options, eps_fail, sigy0)
        if ghost_fail is None:
            # VU1 is dead near eps_f + 2*Gf/(sigma_y0*L); the ghost follows at that strain
            ghost_fail = max(e for _, e in etab) + 2.0 * gf / ytab[0][1] / _mean_matrix_length(part, fractions)

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
            if damage:
                props = _damage_props(inferred, options, ytab, etab, gf)
            else:
                props = [
                    inferred["young"], inferred["poisson"], inferred["density"], options.rayleigh_beta,
                    options.bulk_viscosity_linear, options.bulk_viscosity_quadratic, eps_fail, sigy0,
                    hardening, 1.0 if options.plasticity else 0.0, options.jac_fail,
                    options.degrade_time, options.compression_residual_bulk_fraction,
                ]
            transformed.extend([
                f"** embmesh: matrix model {options.matrix_model}; compile with user={USER_SUBROUTINE[options.matrix_model]}",
                f"*User Element, type=VU1, nodes=8, coordinates=3, properties={len(props)}, variables={nsvars}",
                "1, 2, 3",
                f"*Element, type=VU1, elset={VUEL_ELSET}",
            ])
            transformed.extend(
                f"{label}, " + ", ".join(str(n) for n in collected[label]) for label in sorted(collected)
            )
            transformed.append(f"*UEL Property, elset={VUEL_ELSET}")
            for start in range(0, len(props), 8):
                transformed.append(", ".join(_format(x) for x in props[start:start + 8]))
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
        source_material, options.ghost_scale, ghost_fail, instant_delete=damage)
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
            final.extend(_initial_solution_lines(instance, fractions, nsvars))
    if not inserted_model_data:
        raise ValueError("source deck has no *Material block")

    metadata = {
        "host_mode": "vuel-ghost",
        "vuel_type": "VU1",
        "vuel_nsvars": nsvars,
        "matrix_model": options.matrix_model,
        "user_subroutine": USER_SUBROUTINE[options.matrix_model],
        "fiber_volume_svar": 107,
        "ghost_scale": options.ghost_scale,
        "ghost_ductile_failure_strain": (
            inferred["ductile_failure_strain"] if ghost_fail is None else ghost_fail),
        "ghost_label_min": min(ghost_by_host.values()),
        "ghost_label_max": max(ghost_by_host.values()),
        "ghost_diagnostic_elset": GHOST_DIAGNOSTIC_ELSET,
        "ghost_diagnostic_variables": list(GHOST_DIAGNOSTIC_VARIABLES),
        "source_host_material": material_name,
        "vuel_properties": props,
        **({"matrix_rate_mode": options.rate_mode, "matrix_yield_table": ytab,
            "matrix_fracture_strain_table": etab, "matrix_gf": gf} if damage else {}),
        "expected_host_mass_ratio_including_ghost": 1.0 + options.ghost_scale,
    }
    return final, ghost_by_host, metadata
