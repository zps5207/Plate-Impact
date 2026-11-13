import json
import matplotlib.pyplot as plt
import numpy as np

# Load native extract files
with open('outbox/T-054/nv3_native_extract.json') as f:
    d1 = json.load(f)
with open('outbox/T-054/nv3_native_r_extract.json') as f:
    d2 = json.load(f)

# Merge cs data
times_cs = []
cs_ge99 = []
cs_ge50 = []
cs_max = []

for item in d1['cs']:
    times_cs.append(item['t'] * 1e6)
    cs_ge99.append(item['ge99'])
    cs_ge50.append(item['ge50'])
    cs_max.append(item['max'])

# For restart, skip frame 0 (which is identical to 70 us)
for item in d2['cs'][1:]:
    times_cs.append((70.0e-6 + item['t']) * 1e6)
    cs_ge99.append(item['ge99'])
    cs_ge50.append(item['ge50'])
    cs_max.append(item['max'])

times_cs = np.array(times_cs)
cs_ge99 = np.array(cs_ge99)
cs_ge50 = np.array(cs_ge50)
cs_max = np.array(cs_max)

# Merge status data
times_st = []
host_dead = []
fiber_dead = []

for item in d1['status']:
    times_st.append(item['t'] * 1e6)
    host_dead.append(item['cnt']['host'][1])
    fiber_dead.append(item['cnt']['fiber'][1])

for item in d2['status'][1:]:
    times_st.append((70.0e-6 + item['t']) * 1e6)
    host_dead.append(item['cnt']['host'][1])
    fiber_dead.append(item['cnt']['fiber'][1])

times_st = np.array(times_st)
host_dead = np.array(host_dead)
fiber_dead = np.array(fiber_dead)

# Load viewer data for plug perforation timing
# Specifically, when does each ply suffer its first deletion in the ball footprint (r <= 4.76 mm)?
manifest_path = '../../Meshing/newvals-paper-tt3/results/viewer_nv3_native/manifest.json'
with open(manifest_path) as f:
    manifest = json.load(f)
times_viewer = np.array(manifest['times_us'])
hs = np.fromfile('../../Meshing/newvals-paper-tt3/results/viewer_nv3_native/host_status.u8', dtype=np.uint8).reshape(len(times_viewer), 20, 3, 3625)

# Calculate footprint deletions per ply over time
# We know from analyze_native_viewer.py which elements are in footprint
with open('outbox/T-054/native_viewer_analysis.json') as f:
    nv_analysis = json.load(f)

# Find first deletion time per ply
ply_first_del_t = []
ply_footprint_del_t = []
for p in range(20):
    ply_dead = (hs[:, p, :, :] == 0).sum(axis=(1, 2))
    first_idx = np.where(ply_dead > 0)[0]
    if len(first_idx) > 0:
        ply_first_del_t.append(times_viewer[first_idx[0]])
    else:
        ply_first_del_t.append(np.nan)

# Save timing metrics
results = {
    "total_cohesive_points": d1['cs'][0]['n'],
    "delamination_initiation_time_us": float(times_cs[np.where(cs_max > 0.01)[0][0]]) if np.any(cs_max > 0.01) else None,
    "delamination_first_ge99_time_us": float(times_cs[np.where(cs_ge99 > 0)[0][0]]) if np.any(cs_ge99 > 0) else None,
    "delamination_ge99_count_70us": int(cs_ge99[np.argmin(np.abs(times_cs - 70.0))]),
    "delamination_ge99_count_100us": int(cs_ge99[-1]),
    "host_deletion_initiation_time_us": float(times_st[np.where(host_dead > 0)[0][0]]),
    "host_deletion_70us": int(host_dead[np.argmin(np.abs(times_st - 70.0))]),
    "host_deletion_100us": int(host_dead[-1]),
    "ply_first_deletion_times_us": [float(x) for x in ply_first_del_t],
    "full_perforation_time_us": float(max(ply_first_del_t)),
}

with open('outbox/T-054/delamination_timing_analysis.json', 'w') as f:
    json.dump(results, f, indent=2)

print("Delamination Analysis Summary:")
print(f"  Delamination initiation (max CSDMG > 0.01): {results['delamination_initiation_time_us']:.3f} us")
print(f"  First full interface failure (CSDMG >= 0.99): {results['delamination_first_ge99_time_us']:.3f} us")
print(f"  CSDMG >= 0.99 points at 70 us: {results['delamination_ge99_count_70us']} / {results['total_cohesive_points']} ({results['delamination_ge99_count_70us']/results['total_cohesive_points']*100:.2f}%)")
print(f"  CSDMG >= 0.99 points at 100 us: {results['delamination_ge99_count_100us']} / {results['total_cohesive_points']} ({results['delamination_ge99_count_100us']/results['total_cohesive_points']*100:.2f}%)")
print(f"  Host deletion initiation: {results['host_deletion_initiation_time_us']:.3f} us")
print(f"  Full plate perforation (all 20 plies have deleted hosts): {results['full_perforation_time_us']:.3f} us")

# Create comparison plot
fig, ax1 = plt.subplots(figsize=(10, 6), dpi=150)

color = 'tab:red'
ax1.set_xlabel('Time (us)', fontsize=12)
ax1.set_ylabel('Deleted Host Elements Count', color=color, fontsize=12)
ax1.plot(times_st, host_dead, color=color, linewidth=2.5, label='Deleted Host Elements')
ax1.tick_params(axis='y', labelcolor=color)
ax1.grid(True, linestyle=':', alpha=0.6)

# Mark perforation
ax1.axvline(results['full_perforation_time_us'], color='darkred', linestyle='--', linewidth=1.5,
            label=f"Full Plate Perforation ({results['full_perforation_time_us']:.1f} us)")

ax2 = ax1.twinx()
color = 'tab:blue'
ax2.set_ylabel('Cohesive Damage Points (CSDMG >= 0.99)', color=color, fontsize=12)
ax2.plot(times_cs, cs_ge99, color=color, linewidth=2.5, label='Delaminated Points (CSDMG >= 0.99)')
ax2.plot(times_cs, cs_ge50, color='tab:cyan', linewidth=1.5, linestyle='--', label='Damaged Points (CSDMG >= 0.50)')
ax2.tick_params(axis='y', labelcolor=color)

# Combine legends
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left', frameon=True, fontsize=10)

plt.title('Native Run: Host Deletion vs Delamination Timing (0 - 100 us)', fontsize=13, fontweight='bold')
plt.tight_layout()
plt.savefig('outbox/T-054/deleted_count_and_cohesive_damage_vs_time.png')
plt.close()
print("Saved figure outbox/T-054/deleted_count_and_cohesive_damage_vs_time.png")
