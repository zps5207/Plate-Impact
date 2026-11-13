from __future__ import annotations
from .model import Deck, Element
from .errors import HexOnlyError
from .geometry import hex_center_jacobian

HEX_TYPES = {"C3D8", "C3D8R", "C3D8I", "C3D8H", "C3D8RH", "C3D8IH", "C3D20", "C3D20R"}

def select_elements(deck: Deck, instance: str, elset: str | None = None) -> tuple[dict[int, Element], dict[int, object]]:
    ins = deck.instances[instance]; part = deck.parts[ins.part]
    if elset:
        # Abaqus set names are case-insensitive.
        match = next((k for k in part.elsets if k.lower() == elset.lower()), None)
        if match is None:
            raise KeyError(f"elset {elset!r} not found on part {part.name!r}; available: {sorted(part.elsets)}")
        labels = part.elsets[match]
        elems = {k: v for k, v in part.elements.items() if k in labels}
        if not elems:
            raise ValueError(f"elset {elset!r} selects zero elements")
    else: elems = dict(part.elements)
    all_nodes = deck.instance_nodes(instance)
    used = {n for e in elems.values() for n in e.connectivity}
    nodes = {n: all_nodes[n] for n in used if n in all_nodes}
    bad = {}; inverted=[]
    for e in elems.values():
        typ = e.type.upper()
        if typ not in HEX_TYPES or len(e.connectivity) not in (8, 20): bad[typ] = bad.get(typ, 0) + 1
        if len(e.connectivity)==8:
            p=[nodes[i] for i in e.connectivity]
            if hex_center_jacobian(p)<=0: inverted.append(e.label)
    if bad: raise HexOnlyError("unsupported host element types: " + ", ".join(f"{k} ({v})" for k,v in sorted(bad.items())))
    if inverted: raise ValueError("degenerate/inverted hex element labels: " + ", ".join(map(str,inverted)))
    return elems, nodes
