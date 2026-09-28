# Decisions

- The specification was supplied at repository root as `GOAL_SPEC.md`; progress records this path discrepancy until a canonical `docs/GOAL_SPEC.md` is established.
- The external `VUEL.for` has no data-ingestion route for per-host fiber volumes. The conservative interface decision is a plain-text/CSV output plus documentation, without changing UEL numerics.
- The working tree is OneDrive-synchronised. Keep `.git` excluded from OneDrive sync where possible because sync conflicts can corrupt Git metadata.
- “90-90” is interpreted as alternating orthogonal 0/90 cross-ply layers: even layers use `t0`, odd layers use `t90`.
- Native Abaqus/Explicit `T3D2` truss and `B31` beam section syntax is emitted, but final keyword acceptance requires an Abaqus/Explicit run (UNVERIFIED locally, as required by the no-Abaqus environment rule).
