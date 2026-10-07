# Confirmed Abaqus/Explicit 2024 quirks

This is a running project-local record of Abaqus behaviors that were confirmed
on ROAR and are either easy to misread from the manuals or fail silently. Each
entry points to the fuller reproduction and evidence already kept in this
repository. Do not generalize an entry beyond the version and context tested.

## `*User Element` type keys must begin with `VU`

Abaqus/Explicit rejects Standard-style user-element keys such as `U1` with
`USER ELEMENT TYPE MUST START WITH A VU` / `U1 IS NOT A VALID ELEMENT TYPE
KEY`. Use the same Explicit key, for example `VU1`, on both `*User Element`
and `*Element`. The Fortran entry point remains `SUBROUTINE VUEL`.

Confirmed by ROAR job **55900492** after the failing `U1` attempt. See
`docs/BUGS.md` BUG-019 and `docs/VUMAT_PROGRESS_2026-09-29.md`.

## `*UEL Property` silently accepts only eight values per data line

When more than eight real properties are written on one `*UEL Property` data
line, Abaqus/Explicit silently ignores values after the eighth: there is no
input error or warning. Stage 1 initially appeared to have disabled plasticity
because `props(9)` and `props(10)` arrived as zero.

Always split property arrays into continuation data lines containing at most
eight values each. This applies even though the declared `properties=N` count
is larger. Confirmed during ROAR jobs **55971560/55971580**; see
`docs/VUEL_PLASTIC_FAILURE_STAGE1_REPORT_2026-10-01.md`.

## A VUEL's `SVARS` cannot be requested as Explicit element output

For a `*User Element` in Abaqus/Explicit 2024:

- `*Element Output` rejects `SVARS` with `UNIDENTIFIED OR INVALID OUTPUT
  REQUEST SVARS`.
- `*El Print` is an Abaqus/Standard-only keyword and Explicit rejects it with
  `THE ELPRINT KEYWORD IS NOT AVAILABLE IN Abaqus/Explicit`.

Consequently VUEL state must be diagnosed through the subroutine's own
`WRITE(*,*)` output or indirectly through supported nodal history such as
`RF`, `U`, and `V`. Confirmed in the T6 job family culminating in ROAR job
**55967626**; see `docs/VUEL_FAILURE_CRITERION_REPORT_2026-10-01.md` and
`docs/BUGS.md` BUG-021.

## `*Beam Section` geometry and `n1` belong on separate data lines

For `*Beam Section, section=CIRC`, putting `radius, n1x, n1y, n1z` on one
data line silently discards the supplied `n1`. Abaqus then uses its automatic
normal, which can be parallel to the beam axis and abort the model. Write the
radius on the first data line and the three `n1` components on the second.

The one-line form failed in ROAR job **55900412**; the two-line form passed in
jobs **55900454** and **55900492**. See `docs/BUGS.md` BUG-018.

## Windows deck-list files must not contain CRLF endings

Python's `Path.write_text()` uses the platform newline convention unless told
otherwise. A deck-list file generated on Windows with CRLF leaves a trailing
carriage return in each token consumed by a shell loop such as
`for n in $(cat decks.txt)`, making the remote filename end in `\r`.

Every generator whose output is consumed on ROAR must use
`Path.write_text(..., newline='')` for input decks, copied user-subroutine
sources, and especially deck-list files. The failure and fix were observed
during the T7 runs; see
`docs/VUEL_PLASTIC_FAILURE_STAGE1_REPORT_2026-10-01.md`.

