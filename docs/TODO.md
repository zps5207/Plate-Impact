# TODO

Prioritized pending feature work (not defects -- see `docs/BUGS.md` for those).

## High priority

- **VUEL host toggle (GUI + CLI): choose native `C3D8R` vs `*User Element` (VUEL) for the host.**
  Requested by the user (2026-09-30). Shelved for now, but high priority -- pick this
  back up before other feature work.
  - Blocker, already resolved by investigation (see `docs/BUGS.md` BUG-020): the
    mesher's existing fiber embedding is entirely built on Abaqus's native
    `*Embedded Element` constraint, which is **confirmed broken** against a VUEL
    host on real Abaqus 2024 (ROAR job 55933355, `verification/make_t5_uel_embed.py`)
    -- every embedded fiber node is rejected uniformly, regardless of actual
    position, for both native-layup and interior (non-corner) fiber nodes.
  - So a working toggle needs a **different coupling mechanism** for VUEL mode,
    not just an element-type swap:
    1. Node-snapped coupling (generate fiber nodes coincident with existing host
       mesh nodes, sharing DOFs directly -- the only coupling this project has
       confirmed works with VUEL, `docs/VUMAT_PROGRESS_2026-09-29.md`'s
       `vuel_fiber_smoke`, but only demonstrated for a single host element with
       fiber endpoints exactly at its corners). Generalizing this to a real
       multi-element host and an arbitrary diameter/pitch fiber layup is real
       design work: fiber layer positions would likely need to be constrained to
       the host's actual node grid rather than freely chosen from
       `--diameter`/`--gap`.
    2. Or some other tie/constraint mechanism (`*Tie`, `*MPC`, `*Coupling`),
       verified against real Abaqus first -- not attempted yet.
  - Once a coupling strategy is chosen and verified (small ROAR smoke test, same
    pattern as T4/T5), the toggle itself is comparatively simple: swap the host
    element/section block (`*Element,type=C3D8R`+`*Solid Section` vs
    `*User Element`+`*Element,type=VU1`+`*UEL Property`, auto-filling E/nu/density
    from the deck's existing host material) in `embmesh/writers.py`, expose
    `--host-element-type {c3d8r,vuel}` on the CLI, and add the corresponding
    combobox in `embmesh_desktop.py`.
