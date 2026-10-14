"""Summarise the contact-workaround variants (and baseline flat_v2) into one JSON table."""
import json
import os
import sys
import numpy as np

root = sys.argv[1]
base = os.path.join(root, "..", "full")
runs = [("flat_v2 (baseline)", base, "ct_", "el_", "structure_v2.json")]
for v in ["v2_whole", "v2_whole_lin1e10", "v2_whole_lin1e12", "v2_nodes", "v2_whole_nodes", "v2_whole_g1e2", "v2_whole_pen1e4"]:
    p = os.path.join(root, v, "full")
    if os.path.isdir(p) and os.path.exists(os.path.join(p, "el_elements.csv")):
        runs.append((v, p, "ct_", "el_", "structure.json"))
out = []
for name, p, ct, el, st in runs:
    try:
        c = json.load(open(os.path.join(p, ct + "contact.json")))
        d = np.genfromtxt(os.path.join(p, el + "elements.csv"), delimiter=",", names=True)
        s = json.load(open(os.path.join(p, st)))
        h = s["history"]["Assembly ASSEMBLY"]
    except Exception as e:
        out.append({"name": name, "error": str(e)})
        continue
    alive = d["alive_end"] > 0
    pf = d["first_eng_frame"] >= 0
    near = d["r"] <= 0.010
    pen = c["penetration"]
    ke0, ke1 = h["ALLKE"]["first"], h["ALLKE"]["last"]
    # islands: alive near-axis ghosts with >=3 near neighbours and >=60% dead
    idx = np.where(near)[0]
    xyz = np.column_stack([d["x"], d["y"], d["z"]])[idx]
    al = alive[idx]
    pitch = 0.05 / 24
    dist = np.sqrt(((xyz[:, None, :] - xyz[None]) ** 2).sum(axis=2))
    nb = (dist <= 1.6 * pitch) & (dist > 0)
    isl = 0
    for i in range(len(idx)):
        if al[i] and nb[i].sum() >= 3 and (~al[nb[i]]).sum() >= 0.6 * nb[i].sum():
            isl += 1
    row = {
        "name": name,
        "t_end": c["penetration"][-1]["t"],
        "ke0": ke0, "ke_end": ke1, "ke_lost_pct": 100 * (ke0 - ke1) / ke0,
        "ie_end": h["ALLIE"]["last"], "pd_end": h["ALLPD"]["last"], "vd_end": h["ALLVD"]["last"],
        "fd_end": h["ALLFD"]["last"], "ae_end": h["ALLAE"]["last"],
        "ball_v_end": -pen[-1]["ball_mean_vz"],
        "ball_v_min": min(-p["ball_mean_vz"] for p in pen), "ball_v_max": max(-p["ball_mean_vz"] for p in pen),
        "ball_zmin_end": pen[-1]["ball_zmin"],
        "max_ball_nodes_inside": max(p["ball_nodes_inside_alive_ghost"] for p in pen),
        "distinct_ghosts_entered": len(c["hit_ever_counts"]),
        "plate_nodes_ever_contact": c["plate_nodes_ever_contact"], "plate_nodes": c["plate_nodes"],
        "max_contact_nodes_one_frame": max(n for _, _, n in c["per_frame_contact_nodes"]),
        "ghost_deleted": int((~alive).sum()), "vu1_predicted_failed": int(pf.sum()),
        "near_total": int(near.sum()), "near_alive": int((near & alive).sum()),
        "near_alive_vu1_intact": int((near & alive & ~pf).sum()),
        "near_alive_vu1_failed": int((near & alive & pf).sum()),
        "islands": isl,
        "alive_vu1_failed_total": int((alive & pf).sum()),
        "ball_elems_alive_end": pen[-1].get("ball_elems_alive"), "ball_elems_total": pen[-1].get("ball_elems_total"),
        "series_ball_v": [(p["t"], -p["ball_mean_vz"]) for p in pen][::2],
        "series_inside": [(p["t"], p["ball_nodes_inside_alive_ghost"]) for p in pen][::2],
        "series_ke": h["ALLKE"]["series"],
    }
    out.append(row)
json.dump(out, open(os.path.join(root, "summary.json"), "w"), default=float)
for r in out:
    if "error" in r:
        print(r["name"], "ERROR", r["error"])
        continue
    print("%-22s t=%.2e KElost=%5.1f%% vball_end=%6.1f inside_max=%4d entered=%4d contactNodes=%4d deleted=%4d islands=%3d nearAlive=%3d (VU1 intact %3d) ballElems=%s/%s IE=%.1f PD=%.1f" % (
        r["name"], r["t_end"], r["ke_lost_pct"], r["ball_v_end"], r["max_ball_nodes_inside"], r["distinct_ghosts_entered"],
        r["plate_nodes_ever_contact"], r["ghost_deleted"], r["islands"], r["near_alive"], r["near_alive_vu1_intact"],
        r["ball_elems_alive_end"], r["ball_elems_total"], r["ie_end"], r["pd_end"]))
