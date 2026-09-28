# Mesher theory

Hex point location uses trilinear C3D8 shape functions and Newton iteration in natural coordinates. Segment clipping locates parameter transitions at host boundaries and multiplies inside length by the circular area \(A=\pi d^2/4\). Flat layups use alternating orthogonal directions (even layers `t0`, odd layers `t90`) and pitch `d+gap`. Curved implementations should use the front/back surface normal average director and RK4 streamlines as specified by `GOAL_SPEC.md`.

