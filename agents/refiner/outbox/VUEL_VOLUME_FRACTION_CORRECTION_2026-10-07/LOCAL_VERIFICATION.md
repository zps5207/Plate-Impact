# Local verification

## Algebra

Let every stiffness and yield quantity be multiplied by the same positive
`eta`: `C_k=eta*C`, `mu_k=eta*mu`, `SIGY0_k=eta*SIGY0`, and
`H_k=eta*H`. Then `S_trial,k=eta*S_trial` and
`SIGY_old,k=eta*SIGY_old`. The radial-return increment is therefore

`DGAMMA_k = eta*(SIGMA_trial-SIGY_old) /
             (eta*(3*mu+H)) = DGAMMA`.

The flow direction is also unchanged because both the deviatoric trial
stress and its equivalent magnitude carry `eta`. Consequently `DEP`,
`EP`, and `PEEQ` are unchanged, while corrected PK2 stress is multiplied
by `eta`. Reusing `CMAT_K` in Rayleigh stress and `BULK_MODULUS_K` in the
post-failure residual gives those stiffness-derived paths the same
scaling. Density, `CWAVE`, `QBULK`, failure thresholds, and degradation
parameters remain unscaled as required.

## Checks actually run

- New local tests: `4 passed` (`test_stage7_vf.py`). These cover the
  Vf=0 no-op, half-stress/same-plastic-state algebra, every required
  per-element constant use site, and unchanged mass/wave-speed/bulk-
  viscosity/failure paths.
- Existing repository suite: `python -m pytest -p no:cacheprovider tests
  -q` -> `26 passed in 2.24s`.
- NumPy f2py strict fixed-form parse: read `VUEL_failure.for` as
  `format:fix,strict` and emitted signatures for all six routines to
  `VUEL_failure.pyf`. The expected missing Abaqus-only `vaba_param.inc`
  warning was present; no Fortran parse failure occurred.
- Fixed-form audit: zero executable lines exceed column 72.
- Verification Python files parsed successfully with `ast.parse`.
- Generated all six decks (Stage 7 Vf=0 and Vf=0.5 in tension and
  compression, plus a frozen pre-Stage-7 Vf=0 regression in each
  direction). Every deck contains exactly 107 initial solution values;
  SVAR107 is 0 or 0.5 as named.
- SHA-256 checks confirmed all four Stage 7 `_user.for` copies match the
  deliverable VUEL and both baseline copies match the untouched project
  VUEL source.

An unscoped `pytest` at repository root was also attempted, but pytest
recursed through historical `agents/*/outbox` test copies and stopped on
duplicate-module collection errors. Scoping collection to the actual
project `tests/` directory produced the clean 26/26 result above.

## Not locally verified

- Abaqus/Explicit and Intel Fortran are unavailable locally, so there is
  no compile/link or ODB result here.
- The ROAR cases and `stage7_check_vf.py` must still supply the requested
  solver evidence for Vf=0 regression, half force, common yield strain,
  and half post-yield stress-versus-PEEQ slope.
- Abaqus does not expose this VUEL's PEEQ through ordinary element SVARS
  output in the established workflow. The ODB checker therefore infers
  uniaxial PEEQ from Green strain and reaction-derived PK2 stress; this is
  exact for the intended uniform uniaxial state but should be treated as
  an indirect check.
