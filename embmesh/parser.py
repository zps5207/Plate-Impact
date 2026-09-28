from __future__ import annotations

from pathlib import Path
import re
import numpy as np
from .model import Deck, Part, Element, Instance


def _kw(line: str) -> tuple[str, dict[str, str | bool]]:
    fields = [x.strip() for x in line[1:].split(",")]
    name = fields[0].lower()
    opts: dict[str, str | bool] = {}
    for f in fields[1:]:
        if not f:
            continue
        if "=" in f:
            k, v = f.split("=", 1)
            opts[k.strip().lower()] = v.strip()
        else:
            opts[f.lower()] = True
    return name, opts


def _numbers(lines: list[str], i: int) -> tuple[list[str], int]:
    vals: list[str] = []
    while i < len(lines) and not lines[i].lstrip().startswith("*"):
        vals.extend(x.strip() for x in lines[i].split(",") if x.strip())
        i += 1
    return vals, i


def parse_deck(path_or_text: str | Path) -> Deck:
    if isinstance(path_or_text, Path):
        base_dir = path_or_text.parent
    elif isinstance(path_or_text, str) and "\n" not in path_or_text:
        try: base_dir = Path(path_or_text).parent if Path(path_or_text).exists() else Path.cwd()
        except OSError: base_dir = Path.cwd()
    else: base_dir = Path.cwd()
    if isinstance(path_or_text, Path):
        text = path_or_text.read_text()
    elif isinstance(path_or_text, str):
        try:
            p = Path(path_or_text)
            text = p.read_text() if p.exists() else path_or_text
        except OSError:
            text = path_or_text
    else:
        text = str(path_or_text)
    lines = text.splitlines()
    deck = Deck(original_lines=lines.copy())
    part: Part | None = None
    current_instance: Instance | None = None
    section: str | None = None
    opts: dict[str, str | bool] = {}
    i = 0
    while i < len(lines):
        raw = lines[i].strip()
        if not raw or raw.startswith("**"):
            i += 1; continue
        if raw.startswith("*"):
            section, opts = _kw(raw)
            if section == "part":
                part = Part(str(opts.get("name", "PART")))
                deck.parts[part.name] = part
            elif section == "end part":
                part = None
            elif section == "instance":
                current_instance = Instance(str(opts.get("name", "INSTANCE")), str(opts.get("part", "")))
                deck.instances[current_instance.name] = current_instance
            elif section == "end instance":
                current_instance = None
            elif section not in {"node", "element", "nset", "elset", "surface", "assembly", "end assembly", "material", "solid section", "beam section", "embedded element", "include"}:
                deck.unsupported.append(lines[i])
            i += 1
            continue
        vals = [x.strip() for x in raw.split(",")]
        if section == "include":
            inc = base_dir / vals[0] if vals else None
            if inc and inc.exists():
                lines[i:i+1] = inc.read_text().splitlines()
            i += 1; continue
        if section == "node":
            if part is None: part = deck.parts.setdefault("__GENERATED__", Part("__GENERATED__"))
            try: part.nodes[int(vals[0])] = np.array([float(x) for x in vals[1:4]], float)
            except (ValueError, IndexError): pass
        elif section == "element":
            if part is None: part = deck.parts.setdefault("__GENERATED__", Part("__GENERATED__"))
            try:
                label = int(vals[0]); conn = tuple(int(x) for x in vals[1:])
                typ = str(opts.get("type", "")); es = opts.get("elset")
                part.elements[label] = Element(label, conn, typ, str(es) if es else None)
                if es: part.elsets.setdefault(str(es), set()).add(label)
            except (ValueError, IndexError): pass
        elif section in {"nset", "elset"} and part is not None:
            name = str(opts.get("nset" if section == "nset" else "elset", "SET"))
            target = part.nsets if section == "nset" else part.elsets
            target.setdefault(name, set())
            if "generate" in opts and len(vals) >= 3:
                a, b, step = map(int, vals[:3]); target[name].update(range(a, b + (1 if step > 0 else -1), step))
            else:
                target[name].update(int(x) for x in vals if x.lstrip("+-").isdigit())
        elif section == "surface" and part is not None:
            name = str(opts.get("name", "SURFACE")); part.surfaces.setdefault(name, []).append((int(vals[0]), vals[1] if len(vals)>1 else ""))
        elif current_instance is not None and section == "instance":
            try:
                nums = [float(x) for x in vals]
                if len(nums) == 3 and np.allclose(current_instance.translation, 0): current_instance.translation = np.array(nums)
                elif len(nums) >= 7:
                    current_instance.rotation_origin = np.array(nums[:3]); current_instance.rotation_axis = np.array(nums[3:6])-current_instance.rotation_origin; current_instance.rotation_angle = nums[6]
            except ValueError: pass
        i += 1
    return deck
