# Stage 7 ROAR-result reassessment

The reported checker bug is confirmed. Its former denominator floor of
`1.0` turned all subunit strain comparisons into absolute-error checks.
With true relative error, the supplied fast-run yield mismatches are:

- tension: `24.2515734%`;
- compression: `24.2110743%`.

Both yield checks therefore fail the stated 3% tolerance. The supplied
post-yield slope errors are `12.4951299%` in tension and `19.1393769%` in
compression relative to the expected half-slope. The supplied Vf=0
regression remains exact.

## Investigation of the time-matching proposal

Node 2 axial displacement is prescribed by the same `SMOOTH STEP`
amplitude in the Vf=0 and Vf=0.5 decks. Consequently, within a fixed-rate
pair, equal simulation time implies equal prescribed nominal axial strain.
Comparing at matching time is therefore not an independent remedy for the
existing matching-strain comparison. The revised checker nevertheless
records frame time and reports equal-time displacement and elastic-force
errors so this equivalence is visible in the evidence rather than assumed.

Reaction force can still contain rate-dependent inertia and lateral-mode
transients, and the two stiffnesses have different natural periods. The
useful discriminator is therefore a rate-convergence run. The revised
generator adds Vf=0 and Vf=0.5 tension/compression cases with a 0.1 s ramp,
10 times the original duration. The runner reuses the six existing fast
ODBs when present and runs only the four new slow cases. The checker reports
fast and slow results separately and declares the dynamic-artifact
hypothesis supported only if all three errors decrease and every slow-rate
acceptance check passes.

The Fortran formulation has not been changed: the available fast ODB
evidence does not yet distinguish a reaction-based dynamic artifact from a
constitutive problem. If the slow checks do not pass or do not converge
toward the expected ratios, the formulation should be returned to the
human for physics review rather than altered silently.
