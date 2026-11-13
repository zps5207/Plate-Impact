"""Measure ball-node proximity at each first host-deletion frame in vp4.

Run from the refiner directory: python outbox/T-048/ball_proximity.py
Writes outbox/T-048/{native,vuel}_ball_proximity.csv and summary lines.
This is a geometry screen only: nearest node is not proof of contact force.
"""

import csv
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def analyze(case):
    source = ROOT / 'Meshing' / 'vals-plywise-del' / 'results' / case / ('vals_' + case + '_viewer.npz')
    deaths = list(csv.DictReader((HERE.parent / 'T-045' / (case + '_deaths.csv')).open()))
    with np.load(source) as archive:
        ball_pos = archive['ball_pos']
        times = archive['times']
    rows = []
    by_frame = {}
    for row in deaths:
        by_frame.setdefault(int(row['frame']), []).append(row)
    for frame, group in sorted(by_frame.items()):
        centers = np.array([[float(row['center_' + axis + '_mm']) for axis in 'xyz'] for row in group]) / 1000.0
        prior = cKDTree(ball_pos[frame - 1]).query(centers)[0] * 1000.0
        current = cKDTree(ball_pos[frame]).query(centers)[0] * 1000.0
        for row, d_prior, d_current in zip(group, prior, current):
            rows.append({
                'frame': frame,
                'time_us': float(times[frame]) * 1e6,
                'host_element': int(row['host_element']),
                'host_size_mm': float(row['size_mm']),
                'nearest_ball_node_prior_mm': float(d_prior),
                'nearest_ball_node_current_mm': float(d_current),
                'prior_ball_within_one_host_size': int(d_prior <= float(row['size_mm'])),
                'hot_fiber_within_one_host_size': int(row['hot_within_1_size']),
            })
    dest = HERE / (case + '_ball_proximity.csv')
    with dest.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    early = [r for r in rows if r['time_us'] <= 8]
    for name, group in [('all', rows), ('<=8us', early)]:
        count = sum(r['prior_ball_within_one_host_size'] for r in group)
        print(case, name, count, '/', len(group), 'prior ball node within one host size')
    print(case, 'first five:', [(r['time_us'], r['nearest_ball_node_prior_mm']) for r in rows[:5]])


for case_name in ('native', 'vuel'):
    analyze(case_name)
