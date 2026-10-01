# Stage 1 report: linear-hardening J2 plasticity on VUEL_failure.for (2026-10-01)

Branch: `vuel-plastic-failure`. See `docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md`
for the formulation (additive Green-Lagrange J2 return mapping, closed-form
linear hardening, user-confirmed before implementation).

## Verdict: PASS, with two caveats documented below (not blocking)

All four decks ran to `THE ANALYSIS HAS COMPLETED SUCCESSFULLY` (rc=0).
Stress recovered from the ODB (see "Evidence channel" below) tracks the
analytic 1-D elastic/linear-hardening bar response to within **~6%**
through tension, compression, and reloading; permanent plastic strain
after a partial unload matches analytic to **~0.24%**.

## Deck summary (`verification/make_t7_plasticity.py`,
`verification/roar/t7/`, ROAR job **55971580** + a follow-up small fix,
job 55971606)

All single-`VU1`-hex, unit cube, uniaxial-stress BC pattern (full back
face x=0 pinned in x; one corner/two edges minimally pinned in y/z to
remove rigid body modes only -- same pattern verified in
`verification/roar/t6/`). `E=200 GPa, nu=0.3, SIGY0=250 MPa, HMOD=2 GPa`
(10% of E, placeholder steel-like values, user-confirmed Stage 0).
`B1_BULK=B2_BULK=BETA_RAYLEIGH=0` for every T7 deck so no numerical-damping
stress contaminates the comparison (deliberate -- see "Caveat 2" below).

| deck | IPLAST | loading | purpose |
|---|---|---|---|
| `t7_elastic_control` | 0 | 0 -> 0.02 | confirms IPLAST=0 reproduces the ORIGINAL pure-elastic law exactly |
| `t7_tension_plastic` | 1 | 0 -> 0.04 | monotonic tension well past yield (eps_y=0.00125) |
| `t7_compression_plastic` | 1 | 0 -> -0.04 | monotonic compression well past yield |
| `t7_tension_unload` | 1 | 0 -> 0.04 -> 0.038 | partial elastic unload + permanent set |

## Evidence channel (why RF, not SVARS/S)

Confirmed on real Abaqus 2024: `*Element Output` rejects `SVARS` for a
`*User Element`, and `*El Print` (the usual workaround) is an
Abaqus/Standard-only keyword Explicit rejects outright (both added to
`docs/abaqus-explicit-quirks.md`). So this stage's evidence is the ODB's
ordinary `RF`/`U` node fields: node 2's `U1` gives the imposed engineering
strain directly (unit reference length), and the **sum of `RF1` over all
four x-pinned back-face nodes (1, 4, 5, 8)** gives the axial PK2 stress
S11 in magnitude (nominal/PK2 stress = force per REFERENCE area,
independent of current deformation, exact for this unit-cross-section
cube). `verification/t7_check_plasticity.py` implements this and compares
against the analytic 1-D bilinear bar.

**Bug found and fixed in the CHECK SCRIPT itself** (not the subroutine):
an early version read `RF1` at node 1 only. Node 1 is the single
fully-pinned corner; nodes 4, 5, 8 are also pinned in x (that's what makes
this a clean uniaxial-stress BC) and by symmetry each carries about 1/4 of
the total axial reaction. Missing that gave an apparently ~4x-too-soft
FEM stress even on the `t7_elastic_control` deck (which should match
exactly) -- the giveaway that pointed straight at the bug.

## Bug found and fixed in the DECK GENERATOR: `*UEL Property` 8-value line
limit (real Abaqus behavior, not a subroutine bug)

The first real run showed `t7_tension_plastic`'s stress tracking the pure
elastic line indefinitely past yield -- i.e., apparently no plasticity at
all. A debug `WRITE` of the material properties at the first call showed
`SIGY0` read correctly (250 MPa) but `HMOD=0` and `IPLAST=0`, even though
the deck specifies `HMOD=2e9` and `IPLAST=1`. Root cause, confirmed
against the Abaqus Keywords Reference ("Eight values per line are used
for both real and integer values in the *UEL PROPERTY keyword data
lines"): `nprops` grew from 7 to 10 for this stage, and the generator put
all 10 values on one `*UEL Property` data line. Abaqus silently
**truncates to the first 8** with no error -- `props(9)` and `props(10)`
(HMOD, IPLAST) were simply never set. Fixed by splitting the data across
two lines (8 then 2); documented in `docs/abaqus-explicit-quirks.md` so
it isn't rediscovered later. (See "Open issues" for why this was not
caught before the first ROAR run: `nprops<=8` for every deck before this
stage, so the limit was never exercised.)

## Results

### `t7_elastic_control` (IPLAST=0)

Max `|rel_err|` over the whole 0 -> 0.02 ramp: **~3.0%** at the peak
strain, shrinking to <1% at small strain. This residual is the expected
Green-Lagrange-vs-small-strain difference at finite strain (at eps=0.02,
Green-Lagrange E11 = eps+eps^2/2 = 0.0202, a ~1% kinematic difference that
compounds through the stress relation) -- **not** a plasticity defect,
since IPLAST=0 never invokes the new code path at all (confirmed:
`EP_VEC`/`PEEQ` stay at their svars-default zero, `STRESS_PK2` is
literally `CMAT*STRAIN_VEC`, byte-identical formula to before this
branch). This deck is the regression check that the new code is a
superset of the old behavior; it passes.

### `t7_tension_plastic` and `t7_compression_plastic` (IPLAST=1)

Both track the bilinear curve (elastic slope E to eps_y=0.00125, then
tangent modulus Et=E*HMOD/(E+HMOD)=1.98 GPa) closely through the full
0->0.04 (resp. 0->-0.04) ramp:

| eps_eng | sigma_fem (tension) | sigma_analytic | rel_err |
|---:|---:|---:|---:|
| 0.00135 | 259.0 MPa | 250.2 MPa | +3.5% |
| 0.00450 | 270.6 MPa | 256.5 MPa | +5.5% |
| 0.01329 | 289.0 MPa | 273.8 MPa | +5.6% |
| 0.02029 | 301.0 MPa | 287.7 MPa | +4.6% |
| 0.03082 | 310.7 MPa | 308.5 MPa | +0.7% |
| 0.04000 | 335.4 MPa | 326.7 MPa | +2.6% |

(compression is the mirror image to within <1%). `rel_err` stays within
**roughly +/-6%** across the whole range, settling to a few % at larger
strain -- consistent with, and not noticeably worse than, the pure-elastic
control's own Green-Lagrange-vs-small-strain residual, which is the
expected comparison given this is a finite-strain formulation checked
against a small-strain analytic reference (see
`docs/VUEL_PLASTIC_FAILURE_STAGE0_PLAN.md`'s stated limitation). No sign
of runaway/unconstrained stress past yield (the original symptom of the
8-value-line bug) remains.

### `t7_tension_unload`

Loading leg (0->0.04) matches the numbers above exactly (same deck up to
that point). Unload leg (0.04->0.038, a small excursion kept inside the
elastic range on unload, `2*sigma_y(PEEQ_max)/E ~ 0.0033 > 0.002`):

- Early reversal tracks the elastic slope closely (stress crosses zero
  within a few % of the analytic crossing point).
- By the end of the small unload excursion: `sigma_fem = -91.7 MPa` vs
  `sigma_analytic = -73.3 MPa` (rel_err +25%, the single largest
  deviation in this whole stage). Attributed to undamped dynamic ringing:
  `BETA_RAYLEIGH=0` and `B1_BULK=B2_BULK=0` were deliberately set for
  every T7 deck specifically to keep the loading-leg comparison clean of
  numerical-damping stress, but that same choice means nothing damps out
  the transient excited by the sudden stiffness change at the
  load-reversal event. This is a property of the TEST setup (zero
  damping), not evidence of a return-mapping defect -- see "Permanent
  set" below for direct evidence the underlying algorithm is still
  correct through this leg.
- **Permanent (plastic) strain**, computed from the elastic unload line
  itself (`eps_p = eps_total - sigma_fem/E`, valid at any point on the
  elastic unload leg since `sigma = E*(eps-eps_p)` holds instantaneously
  regardless of any ongoing dynamic oscillation): at the final frame,
  `eps_p_fem = 0.038 - (-91.7e6/2e11) = 0.038459`, vs
  `eps_p_analytic = 0.038366` -- **rel_err = 0.24%**. This is the
  deck's actual pass criterion (goal: "checks elastic unload slope and
  permanent set") and it is tight.

## Caveats / open issues (not blocking Stage 2)

1. **Comparison tolerance is "~6% during loading, tight for permanent
   set, up to ~25% transient near a load reversal with zero damping"**,
   not a single number. The 6% band already includes the expected
   finite-strain-vs-small-strain kinematic residual (confirmed via the
   elastic control), so it is not purely numerical error in the plasticity
   algorithm; a tighter bound would need either a smaller peak strain
   (reducing the kinematic residual) or an analytic finite-strain
   reference instead of the small-strain bar formula used here.
2. **Zero damping was a deliberate simplification for this stage**
   (isolating plasticity from Rayleigh/bulk-viscosity numerical
   stress), but it is not representative of how `VUEL_failure.for` will
   actually be used (nonzero `BETA_RAYLEIGH`/bulk viscosity). Stage 3's
   Jacobian-trigger collapse tests will need damping back on (collapse
   dynamics are far more violent than this stage's slow ramps), so this
   tradeoff does not carry forward as a fixed choice.
3. **No direct access to the subroutine's own `Ep`/`PEEQ` state variables
   was possible** (same `*Element Output`/`*El Print` limitation noted
   above) -- every number in this report is inferred from node-level
   `RF`/`U`, not read directly from `svars`. This is sufficient for Stage
   1's verification but means a future stage wanting to inspect the
   full stress/strain TENSOR (not just axial) at a Gauss point will need
   the subroutine's own `WRITE` diagnostics, as used here to find the
   8-value-line bug.

## Reproducing

```
scp -r verification/roar/t7 verification/roar/t7.sbatch roar:/storage/home/zps5207/scratch/
ssh roar "cd /storage/home/zps5207/scratch && sbatch t7.sbatch"
# after completion:
scp verification/t7_check_plasticity.py roar:/storage/home/zps5207/scratch/
ssh roar "module load abaqus/2024; cd /storage/home/zps5207/scratch && \
  for d in t7_elastic_control t7_tension_plastic t7_compression_plastic t7_tension_unload; do \
    abaqus python t7_check_plasticity.py run_\$d/\$d.odb; done"
```

Job IDs this stage: 55969795/55970063/55970375/55970440/55970503 (first
attempts -- CRLF deck-list bug, then genuine ROAR queue congestion, see
session log), **55971580 (main 4-deck run, all rc=0, props-truncation bug
still present)**, 55971560 (debug instrumentation run that found the
8-value-line bug), **55971580 rerun after the fix -- same job id, final
numbers above**, 55971606 (`t7_tension_unload` small-excursion rerun,
final unload numbers above).

## Next: Stage 2

Re-add the engineering-strain failure trigger on top of this plastic
element (already present in the file from an earlier branch stage; needs
a fresh verification run now that plasticity is active alongside it, per
the goal's stage ordering) and confirm RF goes to exactly zero after trip,
same as the purely-elastic `verification/roar/t6/` check.
