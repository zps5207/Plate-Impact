import json
import matplotlib.pyplot as plt
import numpy as np

# Load viewer data
vuel_dir = '../../Meshing/newvals-paper-tt3/results/viewer_nv3_vuel'
with open(vuel_dir + '/manifest.json') as f:
    manifest = json.load(f)

times = np.array(manifest['times_us'])
status = np.fromfile(vuel_dir + '/host_status.u8', dtype=np.uint8).reshape(len(times), 20, 10875)

# Alphabetical block order mapping
ply_names = ['Ply-1', 'Ply-10', 'Ply-11', 'Ply-12', 'Ply-13', 'Ply-14', 'Ply-15', 'Ply-16', 'Ply-17', 'Ply-18', 'Ply-19', 'Ply-2', 'Ply-20', 'Ply-3', 'Ply-4', 'Ply-5', 'Ply-6', 'Ply-7', 'Ply-8', 'Ply-9']

# Sort blocks by physical ply order (1..20)
sorted_block_indices = sorted(range(20), key=lambda i: int(ply_names[i].split('-')[1]))

# Frame 2 is t = 0.988 us (before ball contact at 0.97 us / first impact frame)
f2_dead = (status[2] == 0)

ply_stats_0p99us = {}
for block_idx in sorted_block_indices:
    name = ply_names[block_idx]
    d_total = int(f2_dead[block_idx].sum())
    d_sub0 = int(f2_dead[block_idx, :3625].sum())
    d_sub1 = int(f2_dead[block_idx, 3625:7250].sum())
    d_sub2 = int(f2_dead[block_idx, 7250:].sum())
    ply_stats_0p99us[name] = {
        "block_index": block_idx,
        "total_dead": d_total,
        "sublayer_0_bottom": d_sub0,
        "sublayer_1_middle": d_sub1,
        "sublayer_2_top": d_sub2
    }

analysis_data = {
    "total_unique_hosts": 217500,
    "total_vuel_plus_ghost_entries_odb": 435000,
    "first_increment_failed_count": 27293,
    "first_increment_time_s": 3.7981881e-08,
    "dead_at_0p49us_frame1": int((status[1] == 0).sum()),
    "dead_at_0p99us_frame2": int((status[2] == 0).sum()),
    "dead_at_100us_frame199": int((status[-1] == 0).sum()),
    "initial_contact_overclosure": {
        "overclosed_pairs_count": 354859,
        "maximum_overclosure_m": 2.11671e-04,
        "maximum_contact_adjustment_m": 2.11834e-04,
        "contact_thickness_assigned_m": 2.11666664166667e-04,
        "sublayer_thickness_m": 4.2333332833333336e-04,
        "induced_engineering_strain_pct": 50.039,
    },
    "sublayer_2_total_dead_across_all_20_plies_at_0p99us": int(sum(v["sublayer_2_top"] for v in ply_stats_0p99us.values())),
    "ply_breakdown_0p99us": ply_stats_0p99us,
    "claude_ply13_myth_explanation": "Claude observed 1 dead element in Block 12 (0-indexed block 12 = 13th block). In alphabetical order, Block 12 is Ply-20 (the top ply facing the ball, z = -1.27 to 0.0 mm). Ply-13 is Block 4, which actually had 1,565 dead elements like all other interior 0-degree plies."
}

with open('outbox/T-055/vuel_early_failure_analysis.json', 'w') as f:
    json.dump(analysis_data, f, indent=2)

print("Saved outbox/T-055/vuel_early_failure_analysis.json")

# Generate visual plot of per-ply per-sublayer failure at 0.99 us
plies = [int(ply_names[i].split('-')[1]) for i in sorted_block_indices]
sub0_counts = [ply_stats_0p99us[f"Ply-{p}"]["sublayer_0_bottom"] for p in plies]
sub1_counts = [ply_stats_0p99us[f"Ply-{p}"]["sublayer_1_middle"] for p in plies]
sub2_counts = [ply_stats_0p99us[f"Ply-{p}"]["sublayer_2_top"] for p in plies]

fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
x = np.arange(1, 21)
width = 0.28

ax.bar(x - width, sub0_counts, width, label='Sublayer 0 (Bottom / Slave Face)', color='crimson')
ax.bar(x, sub1_counts, width, label='Sublayer 1 (Middle / Fiber-bearing)', color='darkorange')
ax.bar(x + width, sub2_counts, width, label='Sublayer 2 (Top / Master Face)', color='mediumseagreen')

ax.set_xlabel('Ply Number (Ply-1 bottom of plate to Ply-20 top of plate)', fontsize=11)
ax.set_ylabel('Dead Host Elements Count at t = 0.99 us', fontsize=11)
ax.set_title('T-055: VUEL Pre-Impact Element Deletions by Ply and Sublayer (t = 0.99 us)', fontsize=13, fontweight='bold')
ax.set_xticks(x)
ax.set_xticklabels([f"P{i}" for i in x], fontsize=9)
ax.grid(True, linestyle=':', alpha=0.6, axis='y')
ax.legend(frameon=True, fontsize=10)

# Annotate Ply-20 and Ply-1
ax.annotate('Ply-20 (Top Face):\nOnly 1 dead (no slave contact above)',
            xy=(20, 1), xytext=(15, 1200),
            arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=6),
            fontsize=9, backgroundcolor='white')

ax.annotate('Sublayer 2: 0 DEAD\nin ALL 20 plies\n(Master face)',
            xy=(10, 0), xytext=(8, 400),
            arrowprops=dict(facecolor='mediumseagreen', shrink=0.05, width=1, headwidth=6),
            fontsize=9, color='darkgreen', fontweight='bold', backgroundcolor='white')

plt.tight_layout()
plt.savefig('outbox/T-055/vuel_pre_impact_deletions_by_ply.png')
plt.close()
print("Saved outbox/T-055/vuel_pre_impact_deletions_by_ply.png")
