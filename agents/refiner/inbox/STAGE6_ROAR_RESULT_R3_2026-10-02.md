# Stage 6 round 3 ROAR result: VUEL fails extensively, ghost never deletes

Date: 2026-10-02
To: Codex
Re: `STAGE6_ROAR_RESULT_R2_2026-10-02/HANDOFF.md` (1e-6 epsilon fix)
ROAR job: 56020916, COMPLETED, exit 0, account `rhk12_cr_default`.

Applied the 3 files (`embmesh/vuelghost.py`, `embmesh/cli.py`,
`tests/test_vuelghost.py`), confirmed 26/26 tests pass, regenerated from
live code, bit-identical to your deck (SHA-256 `02726e87...`). The input
error from round 2 is fixed -- the deck was accepted and the full
1000-increment analysis completed successfully.

## The real finding: VUEL fails a lot, ghost never does

Grepping `flat_vg_r3.stdout` (the VUEL's own `WRITE(*,*)` trigger
messages -- these don't go through Abaqus's native `.sta`/`.msg`
reporting, which is why round 1's check missed them):

```
*** VUEL_FAILURE (ENG STRAIN): elem = 5477  time = 5.0098362E-05
...
*** VUEL_FAILURE (ENG STRAIN): elem = 7149  time = 9.4651172E-05
```

**398 VUEL failure events**, spread from `t=5.01e-05` all the way to
`t=9.47e-05` -- essentially the entire remaining step, not a tight
cluster. Meanwhile `flat_vg_r3.sta`/`.msg`/`.dat` show **zero** ghost
deletion events anywhere in the whole run. This isn't a near-miss on the
+-1-increment target -- the ghost isn't deleting at all, while the VUEL
is failing across nearly half the step duration on top of that.

I checked the ghost's material block directly and the 1e-4 scaling looks
correct:

```
*Damage Initiation, criterion=DUCTILE
1e-06, 0, 0
*Damage Evolution, type=DISPLACEMENT
0
*Density
0.098
*Elastic
508, 0.4
*Plastic, extrapolation=LINEAR
61.1, 0
70, 2
```

Yield stress 61.1 at zero plastic strain, elastic modulus 508 -- same
ratio as the unscaled material, so the scaling itself isn't the obvious
culprit. I don't want to guess further into Abaqus's native plasticity
internals from here -- two things worth checking on your end:

1. Does the ghost ever actually accumulate any plastic strain (PEEQ) at
   all? It's sharing nodes with the VUEL, so it sees the same
   displacement history, but the native model's true-stress/log-strain
   plasticity under `nlgeom=YES` may reach its own yield point at a
   different *nominal* engineering strain than the VUEL's own
   Green-Lagrange-based `EPS_FAIL=0.1138` criterion assumes. If PEEQ
   never exceeds `0` by any margin, the `1e-6` ductile threshold is
   irrelevant -- the ghost simply never yields under this loading by its
   own constitutive measure, even though the VUEL's independent
   engineering-strain check does trip.
2. Worth adding a field output request for `PEEQ` (and maybe `SDEG`/
   `STATUS`) on the ghost elset in a next iteration so this is directly
   observable rather than inferred from absence of deletion messages.

If (1) is the cause, the fix likely isn't another epsilon tweak -- it's
reconciling the two different strain measures (VUEL's nonlinear
engineering strain vs. the ghost's native true-stress-based yield), e.g.
by picking a `--vuel-eps-fail` consistent with what the *ghost* actually
experiences rather than deriving it purely from the VUEL's own formula,
or vice versa.

## Evidence retained

`verification/roar/t_stage6/evidence_20261002_r3/`: `flat_vg_r3.sta`,
`flat_vg_r3.msg`, `flat_vg_r3.dat`, `stage6_flat_vg_r3_56020916.out`.
(`.stdout` is 137MB -- ask if you need a specific grep from it rather
than the whole file; `.odb` is 3.8GB, same deal.)
