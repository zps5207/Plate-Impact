from collections import Counter
from pathlib import Path
import numpy as np
from embmesh.parser import parse_deck
from embmesh.geometry import hex_thickness_axis
from embmesh.plywise import _SIGNS, oriented_faces

root = Path(__file__).resolve().parents[5]
for source in (root / 'Meshing/Flat-curved-p0/Flatv2_curved.inp',
               root / 'agents/refiner/outbox/T-024/curved_hostonly.inp'):
    deck = parse_deck(source)
    part = deck.parts[deck.instances['Plate-1'].part]
    axes = Counter()
    bottom, top = set(), set()
    for elem in part.elements.values():
        pts = np.array([part.nodes[n] for n in elem.connectivity])
        axis = hex_thickness_axis(pts)
        axes[axis] += 1
        _, _, pairs = oriented_faces(pts, np.array([0., 0., 1.]))
        bottom.update(elem.connectivity[a] for a, _ in pairs)
        top.update(elem.connectivity[b] for _, b in pairs)
    print(source.name, len(part.nodes), len(part.elements), axes,
          len(bottom), len(top), len(bottom & top), len((bottom | top) ^ set(part.nodes)))
