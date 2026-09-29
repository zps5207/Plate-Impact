# Local VUMAT validation handoff

`validate_vumat.py` is an independent material-point transcription of the
available `vumat/VUMAT_tension_only.for` source.  It uses the requested
parameters: tensile `E = 100 GPa`, shear `G = 50 GPa`, and a chosen brittle
threshold of `2 GPa`.

It confirms the available source has the requested truss behavior: linear
tension, zero compression force, brittle deletion at the threshold, and
permanent zero stress after deletion.  It also deliberately exposes that this
source is not a beam VUMAT: it never uses a shear modulus or any non-axial
strain increment, and it retains a positive non-axial stress component rather
than suppressing bending.

The separate beam VUMAT was not present in the local tree.  Claude can use the
script's JSON output as the independent analytical oracle when the remote
source and Abaqus ODB outputs are available.
