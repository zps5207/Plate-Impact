"""Audit VU1/ghost pairing and island memberships in the supplied Abaqus deck."""
import argparse
import collections
import json
from pathlib import Path


def blocks(path):
    head = None
    rows = []
    for raw in path.open(encoding="utf-8", errors="replace"):
        line = raw.strip()
        if not line or line.startswith("**"):
            continue
        if line.startswith("*"):
            if head:
                yield head, rows
            head, rows = line, []
        elif head:
            rows.append(line)
    if head:
        yield head, rows


def keyword(head):
    parts = [p.strip() for p in head[1:].split(",")]
    return parts[0].lower(), dict(
        (p.split("=", 1)[0].strip().lower(), p.split("=", 1)[1].strip().strip('"'))
        if "=" in p else (p.lower(), True) for p in parts[1:]
    )


def numbers(rows, generate=False):
    result = []
    for row in rows:
        vals = [int(x.strip()) for x in row.split(",") if x.strip()]
        if generate:
            result.extend(range(vals[0], vals[1] + 1, vals[2] if len(vals) > 2 else 1))
        else:
            result.extend(vals)
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("deck", type=Path)
    p.add_argument("islands", type=Path)
    args = p.parse_args()
    evidence = json.loads(args.islands.read_text())
    islands = {r["e"] for r in evidence["rows"] if r["island"]}
    near_alive = {r["e"] for r in evidence["rows"] if r["alive"]}
    elements = collections.defaultdict(dict)
    duplicate = collections.Counter()
    sets = collections.defaultdict(set)
    sections = []
    surfaces = collections.defaultdict(list)
    embedded = []
    boundaries = []
    part = instance = None
    for head, rows in blocks(args.deck):
        name, opt = keyword(head)
        if name == "part":
            part = opt["name"]
        elif name == "end part":
            part = None
        elif name == "instance":
            instance = opt["name"]
        elif name == "end instance":
            instance = None
        scope = (part or opt.get("instance") or instance or "MODEL").upper()
        if name == "element":
            typ = opt.get("type", "").upper()
            for row in rows:
                vals = numbers([row])
                label, nodes = vals[0], tuple(vals[1:])
                if label in elements[scope]:
                    duplicate[(scope, label)] += 1
                elements[scope][label] = (typ, nodes)
                if "elset" in opt:
                    sets[(scope, opt["elset"].upper())].add(label)
        elif name == "elset":
            sets[(scope, opt["elset"].upper())].update(numbers(rows, "generate" in opt))
        elif name == "solid section":
            sections.append((scope, opt.get("elset", "").upper(), opt.get("material"), opt.get("controls")))
        elif name == "surface" and opt.get("type", "").upper() == "ELEMENT":
            surfaces[opt.get("name", "")].extend((r.split(",")[0].strip().upper(), r.split(",")[-1].strip()) for r in rows)
        elif name == "embedded element":
            embedded.append((opt.get("host elset", "").upper(), [x.strip().upper() for r in rows for x in r.split(",") if x.strip()]))
        elif name == "boundary":
            boundaries.extend(r.split(",")[0].strip().upper() for r in rows)
    host = sets[("PLATE", "EMBMESH_VUEL_HOST")]
    ghost = sets[("PLATE", "EMBMESH_GHOST_HOST")]
    pair_errors = [g for g in ghost if g - 24000 not in host or elements["PLATE"].get(g, (None, None))[1] != elements["PLATE"].get(g - 24000, (None, None))[1]]
    ghost_sections = [s for s in sections if s[0].upper() == "PLATE" and s[1] == "EMBMESH_GHOST_HOST"]
    surface_members = set()
    surface_bad = []
    for setname, face in surfaces.get("Surf-1", []):
        members = sets[("PLATE-1", setname)]
        surface_members.update(members)
        surface_bad.extend(x for x in members if x in host)
    embedded_hosts = set()
    for hostset, _ in embedded:
        embedded_hosts.update(sets[("PLATE-1", hostset)])
    bc_sets = set(boundaries)
    bc_nodes = set()
    # Abaqus Nsets, rather than Elsets, specify the actual boundary nodes.
    nsets = collections.defaultdict(set)
    for head, rows in blocks(args.deck):
        name, opt = keyword(head)
        if name == "nset":
            nsets[(opt.get("instance", ""), opt.get("nset", "").upper())].update(numbers(rows, "generate" in opt))
    for name in bc_sets:
        bc_nodes.update(nsets[("Plate-1", name)])
    result = {
        "host_count": len(host), "ghost_count": len(ghost),
        "ghost_range": [min(ghost), max(ghost)], "duplicate_labels": sum(duplicate.values()),
        "missing_or_mismatched_pairs": len(pair_errors), "ghosts_outside_ghost_elset": len({g for g in range(24001, 48001)} - ghost),
        "ghost_sections": ghost_sections, "surface_1_members": len(surface_members),
        "surface_1_host_labels": len(surface_bad), "surface_1_ghost_labels": len(surface_members & ghost),
        "embedded_host_members": len(embedded_hosts), "embedded_ghost_members": len(embedded_hosts & ghost),
        "islands": len(islands), "near_alive": len(near_alive),
        "islands_in_ghost": len(islands & ghost), "islands_on_surface_1": len(islands & surface_members),
        "islands_in_embedded_host": len(islands & embedded_hosts),
        "islands_with_bc_node": sum(bool(set(elements["PLATE"][g][1]) & bc_nodes) for g in islands),
        "islands_on_ball_surface": 0,
        "island_label_mod40": dict(sorted(collections.Counter(g % 40 for g in islands).items())),
        "island_label_minmax": [min(islands), max(islands)],
        "island_host_pair_errors": len(set(pair_errors) & islands),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
