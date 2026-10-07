# Task for agy and Codex: ghost-host VUEL + fiber-volume channel in the mesher

Date: 2026-10-01
From: Claude (orchestration role from here on — see process note below)
Branch: `vuel-plastic-failure` (touches `uel/VUEL_failure.for` + `embmesh/`)

This also serves as Stage 6 of the VUEL plastic-failure project (ghost
C3D8R + embedded T3D2 fiber observation), done through the real mesher
instead of a hand-built deck. All design decisions below were confirmed
by the user directly — treat them as settled, not open questions.

## Objective

Extend the mesher so it can emit, for a given host mesh, a **VUEL-hosted**
variant alongside the existing native-only path:

1. For every host hex currently written as a real-material `C3D8R`, emit
   **two** superimposed elements on the identical node connectivity:
   - a `VU...`-type user element calling `uel/VUEL_failure.for` (Stage 5,
     commit `74fab09` — do not use `uel/VUEL.for`, that stays
     production-only and untouched), carrying the real physics
     (elasticity, J2 plasticity, engineering-strain/Jacobian failure,
     degradation ramp), and
   - a native **ghost** `C3D8R` on the same nodes, which:
     - hosts the `*Embedded Element` fibers (native embedding directly on
       a VUEL host is confirmed broken — BUG-020 /
       `docs/VUEL_HOST_TOGGLE` history — this ghost is the workaround),
     - carries a native Abaqus material (`*Elastic`, `*Density`,
       `*Plastic` with appropriate yield/hardening, `*Damage Initiation,
       criterion=DUCTILE` + `*Damage Evolution`, element deletion=YES)
       tuned so the ghost deletes within **±1 explicit time increment**
       of the VUEL's own failure trigger — same increment is the target,
       one increment either side is the acceptance tolerance.
2. **Ghost scaling (confirmed):** scale the ghost's elastic modulus and
   density both by ~1e-4 relative to the real material, so the wave speed
   `sqrt(E/rho)` is preserved (same stable time increment / dynamics
   coupling) while the ghost's actual stiffness and mass contribution to
   the structural response is negligible. The VUEL remains the element
   that carries the real mechanical response; the ghost is a scaffold for
   the embedded fibers plus a synchronized deletion trigger, nothing more.
3. **Fiber volume fraction channel into the VUEL (confirmed approach):**
   the mesher already computes this per host element (see
   `fiber_volume.csv` / `report.json`'s `volume_fraction`, already
   produced by `embmesh/volume.py`) — this is a plumbing task, not new
   physics. Since `volume_fraction` varies per element and `*UEL
   Property` is per-elset (not per-element), route it as a **new
   per-element state variable**, not a prop: bump `nsvars` 106 -> 107 and
   initialize `svars(107) = FIBER_VOL_FRAC` per VUEL element via
   `*Initial Conditions, TYPE=SOLUTION` (Abaqus supports per-element
   initial SVAR values this way). `VUEL_failure.for` needs to read
   `svars(107)` at minimum for bookkeeping/output this stage; whether it
   should actually alter the physics (e.g. scale a property with it) is
   not in scope yet — observation/plumbing only for now, matching Stage
   6's "observation only" scope. Confirm the new nsvars with a syntax/arg
   check the same way Stage 1-5 did (f2py strict fixed-form parse, hash
   checks) before calling it verified.
4. Add whatever mesher-side mode switch is needed to choose this
   ghost+VUEL path vs. the existing native-only path (CLI flag is fine;
   it does not need to be a GUI toggle yet).

## Known Abaqus quirks to not rediscover

From `docs/abaqus-explicit-quirks.md`, both confirmed on real Abaqus:
- `*UEL Property` data lines silently truncate past 8 values per line —
  no error, just wrong properties. Split long property lists accordingly
  (Stage 1 lost real debugging time to this).
- The user-element type key must start with `VU` (e.g. `VU1`), not just
  `U...`.

## Verification scope

- Use `Meshing/Flat.inp` as the host/fiber source geometry (via the
  existing `embmesh` pipeline / `Meshing/Flat-embmesh/` output) — curved
  layups are explicitly out of scope; the mesher's curved-plate path
  hasn't been verified yet ([[director-field-interpolation-spec]] is
  still unimplemented), so don't test against it.
- You run and verify your own iteration loop locally (or wherever you
  have Abaqus access) before handing anything off. The ROAR Duo/MFA
  connection is gated through a live human approval each time (see
  `agents/refiner/ROAR_SSH.md` and the Stage 5 exchange in this inbox) —
  if that's not available to you, don't block on it; verify what you can
  locally and let Claude do the final ROAR confirmation run.
- Your own pass/fail bar before handing off an `.inp`, mirroring what
  Claude will independently check on receipt:
  1. Runs to completion with no errors, and no warnings beyond ones
     already known-benign (e.g. the tar `SCHILY.fflags` type of noise —
     if something new shows up, flag it, don't wave it off).
  2. VUEL death time and ghost deletion time are within one explicit time
     increment of each other (same increment is the goal).
  3. No NaN, no negative total energy in the `.sta`/`.msg` output.
  4. Total model mass with the ghost+VUEL setup matches the expected mass
     from the real material alone to a tight tolerance (this is the
     direct check that the 1e-4 ghost scaling isn't silently doubling
     mass/stiffness).
  5. Post-host-death fiber behavior is physically sane (no blow-up
     velocities) — same kind of check used in Stage 4's orphan-node
     observation.

## Handoff protocol

When you have a Flat.inp-derived deck that clears your own checklist
above, drop it (plus whatever report/log you used to verify it) into
`agents/refiner/outbox/` and leave a short note in
`agents/refiner/inbox/` addressed to Claude with the exact path and a
one-line summary of what changed since the last handoff. Claude will run
it (on ROAR, with the user's live approval each time, same as Stage 5),
check it against the same 5-point list above, and write back into
`agents/refiner/inbox/` with either a pass or specific bugs/fixes needed.
Repeat until Flat.inp-scale clears cleanly. This is a refinement loop —
expect more than one round.

## Process note

Per the user's current direction: code editing and generation (the mesher
changes, `VUEL_failure.for`'s svars bump, any Abaqus deck changes) is
yours. Claude's role from here is orchestration — ROAR connection
handling, running/monitoring, evidence retrieval, checking your handoffs
against the criteria above, and keeping project memory/state current
across agents. Don't wait on Claude for anything except the actual ROAR
run and the pass/fail check.

## Open item if you hit it

If reading `svars(107)` cleanly requires a props/svars layout decision
beyond what's specified above (e.g. you find `nsvars=107` collides with
something, or Abaqus's per-element `*Initial Conditions, TYPE=SOLUTION`
behaves unexpectedly for a VUEL specifically), treat that as a genuine
physics/interface question and surface it back through the inbox rather
than guessing — same rule that's applied through Stages 1-5.
