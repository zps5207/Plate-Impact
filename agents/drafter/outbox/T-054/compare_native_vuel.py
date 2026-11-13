import json
import numpy as np

with open('outbox/T-054/nv3_vuel_extract.json') as f:
    d1 = json.load(f)
with open('outbox/T-054/nv3_vuel_r_extract.json') as f:
    d2 = json.load(f)

# VUEL extract has status and cs
v_st_times = [item['t']*1e6 for item in d1['status']] + [(70.0e-6 + item['t'])*1e6 for item in d2['status'][1:]]
v_host_dead = [item['cnt']['host'][1] for item in d1['status']] + [item['cnt']['host'][1] for item in d2['status'][1:]]
v_fiber_dead = [item['cnt']['fiber'][1] for item in d1['status']] + [item['cnt']['fiber'][1] for item in d2['status'][1:]]

v_cs_times = [item['t']*1e6 for item in d1['cs']] + [(70.0e-6 + item['t'])*1e6 for item in d2['cs'][1:]]
v_cs_ge99 = [item['ge99'] for item in d1['cs']] + [item['ge99'] for item in d2['cs'][1:]]

# Native extract
with open('outbox/T-054/nv3_native_extract.json') as f:
    n1 = json.load(f)
with open('outbox/T-054/nv3_native_r_extract.json') as f:
    n2 = json.load(f)

n_st_times = [item['t']*1e6 for item in n1['status']] + [(70.0e-6 + item['t'])*1e6 for item in n2['status'][1:]]
n_host_dead = [item['cnt']['host'][1] for item in n1['status']] + [item['cnt']['host'][1] for item in n2['status'][1:]]
n_fiber_dead = [item['cnt']['fiber'][1] for item in n1['status']] + [item['cnt']['fiber'][1] for item in n2['status'][1:]]

n_cs_times = [item['t']*1e6 for item in n1['cs']] + [(70.0e-6 + item['t'])*1e6 for item in n2['cs'][1:]]
n_cs_ge99 = [item['ge99'] for item in n1['cs']] + [item['ge99'] for item in n2['cs'][1:]]

print("=== COMPARISON NATIVE vs VUEL ===")
# 0.99 us
idx_n_1us = np.argmin(np.abs(np.array(n_st_times) - 0.99))
idx_v_1us = np.argmin(np.abs(np.array(v_st_times) - 0.99))
print(f"At t ~ 1 us (before contact):")
print(f"  Native: deleted hosts = {n_host_dead[idx_n_1us]}, fibers = {n_fiber_dead[idx_n_1us]}")
print(f"  VUEL:   deleted hosts = {v_host_dead[idx_v_1us]} (of 435,000 total VU1+ghost), fibers = {v_fiber_dead[idx_v_1us]}")

# 70 us
idx_n_70us = np.argmin(np.abs(np.array(n_st_times) - 70.0))
idx_v_70us = np.argmin(np.abs(np.array(v_st_times) - 70.0))
idx_n_cs_70 = np.argmin(np.abs(np.array(n_cs_times) - 70.0))
idx_v_cs_70 = np.argmin(np.abs(np.array(v_cs_times) - 70.0))
print(f"\nAt t = 70 us:")
print(f"  Native: deleted hosts = {n_host_dead[idx_n_70us]} / 217,500 ({n_host_dead[idx_n_70us]/217500*100:.2f}%), CSDMG>=0.99 = {n_cs_ge99[idx_n_cs_70]}, fibers = {n_fiber_dead[idx_n_70us]}")
print(f"  VUEL:   deleted hosts = {v_host_dead[idx_v_70us]} / 435,000 ({v_host_dead[idx_v_70us]/435000*100:.2f}%), CSDMG>=0.99 = {v_cs_ge99[idx_v_cs_70]}, fibers = {v_fiber_dead[idx_v_70us]}")

# 100 us
print(f"\nAt t = 100 us:")
print(f"  Native: deleted hosts = {n_host_dead[-1]} / 217,500 ({n_host_dead[-1]/217500*100:.2f}%), CSDMG>=0.99 = {n_cs_ge99[-1]}, fibers = {n_fiber_dead[-1]}")
print(f"  VUEL:   deleted hosts = {v_host_dead[-1]} / 435,000 ({v_host_dead[-1]/435000*100:.2f}%), CSDMG>=0.99 = {v_cs_ge99[-1]}, fibers = {v_fiber_dead[-1]}")

comparison = {
    "1us": {
        "native_deleted_hosts": int(n_host_dead[idx_n_1us]),
        "vuel_deleted_hosts_total": int(v_host_dead[idx_v_1us]),
    },
    "70us": {
        "native_deleted_hosts": int(n_host_dead[idx_n_70us]),
        "vuel_deleted_hosts_total": int(v_host_dead[idx_v_70us]),
        "native_cohesive_ge99": int(n_cs_ge99[idx_n_cs_70]),
        "vuel_cohesive_ge99": int(v_cs_ge99[idx_v_cs_70]),
    },
    "100us": {
        "native_deleted_hosts": int(n_host_dead[-1]),
        "vuel_deleted_hosts_total": int(v_host_dead[-1]),
        "native_cohesive_ge99": int(n_cs_ge99[-1]),
        "vuel_cohesive_ge99": int(v_cs_ge99[-1]),
    }
}
with open('outbox/T-054/native_vs_vuel_comparison.json', 'w') as f:
    json.dump(comparison, f, indent=2)
