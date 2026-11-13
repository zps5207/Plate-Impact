"""confirm_deck_builder.py - Generate nv3_vuel_fixed.inp with corrected contact sets.

Fix: Removes all interior ply nodes (Ply-1 to Ply-19) from EMBMESH_PLATE_ALL_NODES,
retaining ONLY Ply-20 nodes. This eliminates artificial 0.2117 mm contact thickness
from all 19 inter-ply cohesive interfaces, removing the 354,859 initial overclosures
and 0.2118 mm slave-node adjustments that caused 28,521 VUEL elements to fail in increment 1.
"""
import sys
from pathlib import Path

def patch_deck(src_inp, dst_inp):
    print(f"Reading {src_inp}...")
    with open(src_inp, 'r') as fin, open(dst_inp, 'w') as fout:
        skipping_plate_nset = False
        for line in fin:
            # Check for EMBMESH_PLATE_ALL_NODES on interior plies
            if line.startswith('*Nset, nset=EMBMESH_PLATE_ALL_NODES, instance=Ply-'):
                inst = line.strip().split('instance=')[1]
                if inst != 'Ply-20':
                    # Skip interior plies
                    skipping_plate_nset = True
                    continue
                else:
                    skipping_plate_nset = False
                    fout.write(line)
                    continue
            
            if skipping_plate_nset:
                if line.startswith('*'):
                    skipping_plate_nset = False
                    fout.write(line)
                # otherwise skip node numbers
                continue

            fout.write(line)
    print(f"Wrote patched deck to {dst_inp}!")

if __name__ == '__main__':
    src = Path('../../Meshing/newvals-paper-tt3/vuel/nv_vuel.inp')
    dst = Path('outbox/T-055/nv3_vuel_fixed.inp')
    if src.exists():
        patch_deck(src, dst)
    else:
        print(f"Source deck {src} not found locally.")
