from __future__ import annotations
import numpy as np
from concurrent.futures import ProcessPoolExecutor, as_completed
from .geometry import clip_segment_hex, clip_segment_hex_bounds, hex_volume, swept_cylinder_hex_volume

def _polyline_clip_len(points, hp, hmin=None, hmax=None):
    """Length of a (possibly multi-segment) fiber polyline clipped to one host hex.
    Segments are pruned against the host's own bbox individually -- pruning by the
    *whole polyline's* bbox (as a single straight-line check would) does nothing
    for a closed loop (e.g. a hoop fiber circling a cylindrical shell), whose
    overall bbox touches nearly every host in the ring even though any one
    segment only passes near a handful of them."""
    if hmin is None: hmin, hmax = hp.min(0), hp.max(0)
    total = 0.0
    for a, b in zip(points[:-1], points[1:]):
        if np.any(np.maximum(a, b) < hmin - 1e-9) or np.any(np.minimum(a, b) > hmax + 1e-9):
            continue
        total += clip_segment_hex(a, b, hp)
    return total

def host_volume_rows(elements, nodes, fibers):
    rows=[]
    for label,e in elements.items():
        hp=np.array([nodes[i] for i in e.connectivity[:8]],float)
        total=t0=t90=0.0
        for f in fibers:
            L=_polyline_clip_len(f.points, hp)
            total+=L
            if f.direction=="t0": t0+=L
            else: t90+=L
        area=getattr(fibers[0],"diameter",0.0) # optional metadata
        rows.append((label,hex_volume(hp),total*area if area else total,t0,t90))
    return rows

def _fiber_volume_batch(batch, nodes, fibers, diameter):
    """Picklable worker (module level, so it can be sent to a subprocess): the
    per-host body of `fiber_volume_rows`, applied to one batch of (label,
    element) items."""
    area = np.pi * diameter ** 2 / 4
    fiber_bbox = [(f, f.points.min(0), f.points.max(0)) for f in fibers]
    out = []
    for label, e in batch:
        hp = np.array([nodes[i] for i in e.connectivity[:8]], float)
        host = hex_volume(hp); l0 = l90 = 0.
        hmin, hmax = hp.min(0), hp.max(0)
        for f, fmin, fmax in fiber_bbox:
            if np.any(fmax < hmin - 1e-9) or np.any(fmin > hmax + 1e-9): continue
            L = _polyline_clip_len(f.points, hp, hmin, hmax)
            if L == 0.0: continue
            if f.direction == "t0": l0 += L
            else: l90 += L
        fv = (l0 + l90) * area
        out.append((label, host, fv, fv / host if host else 0., l0, l90))
    return out


def _fiber_volume_precise_batch(batch, nodes, fibers, diameter, n_along):
    """Picklable worker: the per-host body of `fiber_volume_rows_precise`."""
    radius = diameter / 2
    fiber_bbox = [(f, f.points.min(0) - radius, f.points.max(0) + radius) for f in fibers]
    out = []
    for label, e in batch:
        hp = np.array([nodes[i] for i in e.connectivity[:8]], float)
        host = hex_volume(hp); v0 = v90 = 0.0
        hmin, hmax = hp.min(0), hp.max(0)
        for f, fmin, fmax in fiber_bbox:
            if np.any(fmax < hmin - 1e-9) or np.any(fmin > hmax + 1e-9): continue
            pts = f.points
            V = 0.0
            for a, b in zip(pts[:-1], pts[1:]):
                if np.any(np.maximum(a, b) + radius < hmin - 1e-9) or np.any(np.minimum(a, b) - radius > hmax + 1e-9):
                    continue
                seg_len = np.linalg.norm(b - a)
                margin = min(0.5, 2 * radius / seg_len) if seg_len > 1e-12 else 0.5
                bounds = clip_segment_hex_bounds(a, b, hp)
                t_range = (max(0.0, bounds[0] - margin), min(1.0, bounds[1] + margin)) if bounds else None
                V += swept_cylinder_hex_volume(a, b, radius, hp, n_along=n_along, t_range=t_range)
            if V == 0.0: continue
            if f.direction == "t0": v0 += V
            else: v90 += V
        fv = v0 + v90
        out.append((label, host, fv, fv / host if host else 0., v0, v90))
    return out


def _run_batched(elements, worker, worker_args, progress=None, n_jobs=2, batches_per_job=4):
    """Split `elements.items()` into small batches and run `worker(batch,
    *worker_args)` over them, distributed across up to `n_jobs` concurrent
    worker processes (default 2 -- this per-host geometry work is CPU-bound and
    releases no GIL, so real processes, not threads, are needed to actually run
    concurrently). More, smaller batches than `n_jobs` (rather than exactly
    `n_jobs` one-shot halves) keep the progress callback responsive while still
    only ever running `n_jobs` batches at once. Falls back to a single-process
    loop for small hosts counts or `n_jobs<=1`, where process-spawn overhead
    would outweigh the benefit. Returns rows in the same order as
    `elements.items()`."""
    items = list(elements.items())
    total = len(items)
    if total == 0:
        return []
    n_jobs = max(1, min(n_jobs, total))
    use_processes = n_jobs > 1 and total >= 2 * n_jobs
    n_batches = max(n_jobs, min(total, n_jobs * batches_per_job)) if use_processes else 1
    size = -(-total // n_batches)
    batches = [items[i:i + size] for i in range(0, total, size)]
    rows_by_label = {}
    done = 0
    if use_processes:
        with ProcessPoolExecutor(max_workers=n_jobs) as pool:
            futures = {pool.submit(worker, batch, *worker_args): len(batch) for batch in batches}
            for fut in as_completed(futures):
                for row in fut.result():
                    rows_by_label[row[0]] = row
                done += futures[fut]
                if progress:
                    progress(done, total)
    else:
        for batch in batches:
            for row in worker(batch, *worker_args):
                rows_by_label[row[0]] = row
            done += len(batch)
            if progress:
                progress(done, total)
    return [rows_by_label[label] for label, _ in items]


def fiber_volume_rows(elements, nodes, fibers, diameter, progress=None, n_jobs=2):
    """Per-host centerline-length x area fiber volume, computed across `n_jobs`
    concurrent worker processes (default 2; pass `n_jobs=1` to force the
    original single-process loop)."""
    return _run_batched(elements, _fiber_volume_batch, (nodes, fibers, diameter), progress=progress, n_jobs=n_jobs)


def fiber_volume_rows_precise(elements, nodes, fibers, diameter, n_along=7, progress=None, n_jobs=2):
    """Per-host fiber volume using true cross-section-weighted cylinder/hex
    intersection (`swept_cylinder_hex_volume`) instead of `fiber_volume_rows`'s
    centerline-length x full-cross-section-area approximation. Slower (each
    candidate segment/host pair costs ~n_along*24 point-in-hex evaluations
    instead of ~1), but accounts for a fiber running near a host face/edge/
    corner -- where the length-based method silently assigns the *whole* disk
    to one host even though part of it geometrically belongs to a neighbor.
    Same row layout as `fiber_volume_rows` (t0/t90 columns hold volume, not
    length, here -- since a fiber's in-host cross-section fraction can vary
    along its own length, a single "length" number is no longer meaningful).
    Radius is bumped by a small margin when bbox-pruning so cross-sections
    whose *disk* pokes into a host, even though the centerline itself does
    not, are not missed. For each candidate segment, the *centerline*'s
    clipped range against this host (from `clip_segment_hex_bounds`, padded by
    roughly one fiber diameter in parametric terms) is used to restrict where
    the `n_along`-station quadrature actually looks -- important because a
    single fiber segment is very often much longer than any one host (the
    common flat-plate case), and spending all n_along stations on the *whole*
    segment for every host it merely touches wastes almost all of them and
    reintroduces the along-axis alignment error `swept_cylinder_hex_volume`
    documents. When the centerline never enters this host at all (only the
    disk might, near a face), the full segment is scanned as a fallback.

    Computed across `n_jobs` concurrent worker processes (default 2; pass
    `n_jobs=1` to force the original single-process loop) -- see `_run_batched`.
    """
    return _run_batched(elements, _fiber_volume_precise_batch, (nodes, fibers, diameter, n_along),
                         progress=progress, n_jobs=n_jobs)
