# T-016 notes

The two-type fixture writes `host_conn_C3D8R` before `host_conn_C3D6R`, while its status columns follow the exporter's sorted type order (`C3D6R`, then `C3D8R`). The viewer deletes the intended type, so no status-order bug was found.

The real v500 file was present. Its status counts and face sets passed the independent reference check at frames 0, middle, and last. No tests were skipped.

## Confirmed bounds bug

`test_animation_bounds_include_ball_fiber_and_intermediate_host` fails because `_compute_animation_bounds()` checks only the first and last frames of `host_pos`. A visible host node at x = -12 in frame 1 of 3 falls outside the returned minimum x = 0. The ball at x = 15 and fiber at y = -8 are covered. A middle-frame host deformation can therefore be clipped by camera framing.

Proposed patch to `verification/roar/odb_viewer.py` (not applied):

```diff
@@ def _compute_animation_bounds(self) -> tuple[np.ndarray, np.ndarray]:
         if self.has_host and len(self.host_coords0) > 0:
             mins.append(self.host_coords0.min(axis=0))
             maxs.append(self.host_coords0.max(axis=0))
-            # Include visible host faces from first and last frames
-            for f_idx in [0, self.n_frames - 1]:
-                faces = self.get_host_faces(f_idx)
-                if len(faces) > 0:
-                    idx = 0
-                    used = []
-                    while idx < len(faces):
-                        n = faces[idx]
-                        used.extend(faces[idx + 1 : idx + 1 + n])
-                        idx += n + 1
-                    if used:
-                        p_used = self.host_pos[f_idx, np.unique(used)]
-                        mins.append(p_used.min(axis=0))
-                        maxs.append(p_used.max(axis=0))
+            if self.host_pos.size:
+                mins.append(self.host_pos.min(axis=(0, 1)))
+                maxs.append(self.host_pos.max(axis=(0, 1)))
```

This takes the envelope of all host nodes across all frames. It may include deleted or interior nodes, yielding a wider camera view, but guarantees all host positions fit. The production file was read only.
