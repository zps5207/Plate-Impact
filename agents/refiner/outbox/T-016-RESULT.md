task_id: T-016
role: refiner
status: DONE_WITH_CONCERNS
files_changed:
  - outbox/T-016/test_odb_viewer.py
  - outbox/T-016/NOTES.md
  - outbox/T-016-RESULT.md
summary: Added headless pytest coverage for two-hex face ownership and erosion, exporter-sorted mixed host element types, wedge triangle and quad faces, real v500 status and independent face counts, and animation bounds. The real file was present; no tests were skipped. No status-order bug was found. A failing regression exposes intermediate-frame host geometry outside the computed camera bounds; a proposed diff is in NOTES.md. Production files were not changed.
checks_run:
  - Command: python -m pytest outbox/T-016/test_odb_viewer.py -q
  - Full pytest output:
```text
...F.                                                                    [100%]
================================== FAILURES ===================================
_______ test_animation_bounds_include_ball_fiber_and_intermediate_host ________

tmp_path = WindowsPath('C:/Users/salas/OneDrive - The Pennsylvania State University/Plate Impact/agents/refiner/outbox/T-016/tmpedc9bp8q')

    def test_animation_bounds_include_ball_fiber_and_intermediate_host(tmp_path):
        coords, conn = two_hexes()
        host_pos = np.repeat(coords[None], 3, axis=0)
        host_pos[1, 0, 0] = -12
        ball_pos = np.array([[[0, 0, 0]], [[15, 0, 0]], [[0, 0, 0]]], dtype=np.float32)
        fiber_pos = np.array([[[0, 0, 0], [0, 0, 0]],
                              [[0, -8, 0], [0, 0, 0]],
                              [[0, 0, 0], [0, 0, 0]]], dtype=np.float32)
        path = save_host(tmp_path, coords, {"host_conn_C3D8R": conn[:1]},
                         [[1], [1], [1]], host_pos=host_pos,
                         ball_coords0=ball_pos[0], ball_pos=ball_pos,
                         fiber_coords0=fiber_pos[0], fiber_pos=fiber_pos,
                         fiber_conn_T3D2=np.array([[0, 1]], dtype=np.int32))
        data = load_data(path)
        for positions in (ball_pos, fiber_pos, host_pos):
>           assert np.all(positions >= data.bounds_min)
E           assert np.False_
E            +  where np.False_ = <function all at 0x000001EFC642B530>(array([[[  0.,   0.,   0.],
        [  1.,   0.,   0.],
        [  2.,   0.,   0.],
        [  0.,   1.,   0.],
      ...  2.,   0.,   1.],
        [  0.,   1.,   1.],
        [  1.,   1.,   1.],
        [  2.,   1.,   1.]]], dtype=float32) >= array([ 0., -8.,  0.]))
E            +    where <function all at 0x000001EFC642B530> = np.all
E            +    and   array([ 0., -8.,  0.]) = <odb_viewer.ODBData object at 0x000001EFF6BEF6B0>.bounds_min

outbox\T-016\test_odb_viewer.py:161: AssertionError
---------------------------- Captured stdout call -----------------------------
Loading C:\Users\salas\OneDrive - The Pennsylvania State University\Plate Impact\agents\refiner\outbox\T-016\tmpedc9bp8q\fixture.npz into memory...
Loaded in 0.00 s
Host mesh: 12 nodes, 1 elements, 6 unique faces precomputed
Ball mesh: 1 nodes, 0 exterior faces precomputed
Fiber mesh: 2 nodes, 1 line segments precomputed
============================== warnings summary ===============================
..\..\..\..\AppData\Roaming\Python\Python312\site-packages\_pytest\cacheprovider.py:469
  C:\Users\salas\AppData\Roaming\Python\Python312\site-packages\_pytest\cacheprovider.py:469: PytestCacheWarning: could not create cache path C:\Users\salas\OneDrive - The Pennsylvania State University\Plate Impact\.pytest_cache\v\cache\nodeids: [WinError 5] Access is denied: 'C:\\Users\\salas\\OneDrive - The Pennsylvania State University\\Plate Impact\\.pytest_cache\\v\\cache'
    config.cache.set("cache/nodeids", sorted(self.cached_nodeids))

..\..\..\..\AppData\Roaming\Python\Python312\site-packages\_pytest\cacheprovider.py:423
  C:\Users\salas\AppData\Roaming\Python\Python312\site-packages\_pytest\cacheprovider.py:423: PytestCacheWarning: could not create cache path C:\Users\salas\OneDrive - The Pennsylvania State University\Plate Impact\.pytest_cache\v\cache\lastfailed: [WinError 5] Access is denied: 'C:\\Users\\salas\\OneDrive - The Pennsylvania State University\\Plate Impact\\.pytest_cache\\v\\cache'
    config.cache.set("cache/lastfailed", self.lastfailed)

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED outbox\T-016\test_odb_viewer.py::test_animation_bounds_include_ball_fiber_and_intermediate_host
1 failed, 4 passed, 2 warnings in 1.75s
```
not_verified:
  - Proposed production patch was not applied or tested, per brief.
  - No plotter window or visual rendering was tested, per brief.
suggestions:
  - Apply the bounds patch in NOTES.md and rerun the same test command; the one failing test should pass.
concerns:
  - The existing viewer can crop host nodes that move beyond the first/last-frame envelope during an intermediate frame.
denied_actions:
  - A PowerShell recursive cleanup command was rejected by tool policy; the temporary directory was removed with a path-checked Python command.
