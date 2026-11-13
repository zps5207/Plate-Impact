"""Extract stress triaxiality, principal stress sign, and PEEQ just before deletion.

Designed for Abaqus Python on ROAR HPC.
Usage:
    abaqus python extract_triaxiality_odb.py <odb_path> <output_json> [--max-samples N]

Memory and performance optimization:
1. First pass: scans STATUS field output across frames to determine the exact
   last-alive frame index for every deleted host element.
2. Groups deleted elements by their last-alive frame.
3. Second pass: for frames with deletions, accesses bulkDataBlocks of S and PEEQ
   to extract the pre-deletion stress state for each deleted element without
   instantiating millions of Python field objects.
4. Computes:
   - hydrostatic stress sigma_m = (S11 + S22 + S33) / 3
   - pressure p = -sigma_m
   - Mises stress q = sqrt(0.5*((S11-S22)^2 + (S22-S33)^2 + (S33-S11)^2 + 6*(S12^2 + S23^2 + S13^2)))
   - triaxiality eta = sigma_m / q
   - max principal stress sigma_1 (eigenvalues of 3x3 symmetric tensor)
   - PEEQ
"""
from __future__ import print_function
import sys
import json
import math
from odbAccess import openOdb

def solve_eigenvalues_sym3x3(s11, s22, s33, s12, s13, s23):
    """Compute eigenvalues of a 3x3 symmetric matrix analytically (Cardano formula).
    Returns (sigma_1, sigma_2, sigma_3) with sigma_1 >= sigma_2 >= sigma_3.
    """
    # Invariants
    I1 = s11 + s22 + s33
    I2 = (s11*s22 + s22*s33 + s33*s11) - (s12*s12 + s23*s23 + s13*s13)
    I3 = (s11*(s22*s33 - s23*s23) -
          s12*(s12*s33 - s23*s13) +
          s13*(s12*s23 - s22*s13))
    
    # Deviatoric invariants
    p1 = s12*s12 + s23*s23 + s13*s13
    if p1 < 1.0e-20:
        # Diagonal matrix
        vals = sorted([s11, s22, s33], reverse=True)
        return vals[0], vals[1], vals[2]
    
    q = I1 / 3.0
    p2 = (s11 - q)**2 + (s22 - q)**2 + (s33 - q)**2 + 2.0*p1
    p = math.sqrt(p2 / 6.0)
    
    # Normalized determinant
    # B = (1/p) * (A - q*I)
    b11 = (s11 - q) / p
    b22 = (s22 - q) / p
    b33 = (s33 - q) / p
    b12 = s12 / p
    b13 = s13 / p
    b23 = s23 / p
    
    detB = (b11*(b22*b33 - b23*b23) -
            b12*(b12*b33 - b23*b13) +
            b13*(b12*b23 - b22*b13))
    r = detB / 2.0
    r = max(-1.0, min(1.0, r))
    
    phi = math.acos(r) / 3.0
    eig1 = q + 2.0*p*math.cos(phi)
    eig3 = q + 2.0*p*math.cos(phi + 2.0*math.pi/3.0)
    eig2 = 3.0*q - eig1 - eig3
    
    vals = sorted([eig1, eig2, eig3], reverse=True)
    return vals[0], vals[1], vals[2]

def main():
    if len(sys.argv) < 3:
        print("Usage: abaqus python extract_triaxiality_odb.py <odb_path> <output_json> [--step Step-1] [--sample-frames 1]")
        sys.exit(1)

    odb_path = sys.argv[1]
    out_json = sys.argv[2]
    
    step_name = "Step-1"
    for i, arg in enumerate(sys.argv):
        if arg == "--step" and i + 1 < len(sys.argv):
            step_name = sys.argv[i+1]

    print("Opening ODB: %s" % odb_path)
    odb = openOdb(odb_path, readOnly=True)
    
    if step_name not in odb.steps:
        step_name = list(odb.steps.keys())[0]
    step = odb.steps[step_name]
    n_frames = len(step.frames)
    print("Step: %s, total frames: %d" % (step_name, n_frames))

    # Identify host instances (PLY-*)
    root = odb.rootAssembly
    host_instances = set([k for k in root.instances.keys() if k.upper().startswith("PLY-")])
    print("Found %d host instances: %s" % (len(host_instances), sorted(list(host_instances))[:5]))

    # Phase 1: Track STATUS to determine deletion frame
    # We maintain current status per (inst_name, elem_label)
    print("Phase 1: Scanning STATUS across frames...")
    last_alive_frame = {}  # (inst_name, label) -> frame_idx
    first_dead_frame = {}  # (inst_name, label) -> frame_idx

    # Determine frame step to balance resolution and runtime
    # If > 300 frames, sample every frame for status
    frame_indices = list(range(n_frames))
    
    prev_alive = set()
    for f_idx in frame_indices:
        f = step.frames[f_idx]
        if "STATUS" not in f.fieldOutputs:
            continue
        status_fo = f.fieldOutputs["STATUS"]
        curr_alive = set()
        for b in status_fo.bulkDataBlocks:
            if b.instance is None or b.instance.name not in host_instances:
                continue
            inst_name = b.instance.name
            labels = b.elementLabels
            data = b.data.flatten()
            for lbl, val in zip(labels, data):
                key = (inst_name, int(lbl))
                if val > 0.5:
                    curr_alive.add(key)
                else:
                    if key in prev_alive and key not in first_dead_frame:
                        first_dead_frame[key] = f_idx
                        last_alive_frame[key] = f_idx - 1
        prev_alive = curr_alive
        if (f_idx + 1) % 50 == 0 or f_idx == n_frames - 1:
            print("  Frame %d / %d processed... %d deleted elements recorded" % 
                  (f_idx + 1, n_frames, len(first_dead_frame)))

    total_deleted = len(first_dead_frame)
    print("Total deleted host elements found in ODB: %d" % total_deleted)

    if total_deleted == 0:
        print("No deleted elements found. Writing empty result.")
        with open(out_json, "w") as fp:
            json.dump({"total_deleted": 0, "samples": []}, fp)
        odb.close()
        return

    # Phase 2: Group elements by last-alive frame
    frame_to_keys = {}
    for key, f_last in last_alive_frame.items():
        if f_last >= 0:
            frame_to_keys.setdefault(f_last, []).append(key)

    print("Elements distributed across %d distinct last-alive frames." % len(frame_to_keys))

    # Phase 3: Extract S and PEEQ for each frame with dying elements
    results = []
    frames_to_read = sorted(frame_to_keys.keys())
    
    # To keep extraction fast, if total elements > 5000, we can sample up to 5000 elements uniformly
    MAX_ELEMENTS = 5000
    if total_deleted > MAX_ELEMENTS:
        sample_stride = max(1, total_deleted // MAX_ELEMENTS)
        all_keys = sorted(first_dead_frame.keys())
        sampled_keys = set(all_keys[::sample_stride])
        print("Subsampling %d of %d deleted elements for stress extraction (stride %d)" % 
              (len(sampled_keys), total_deleted, sample_stride))
        # Rebuild frame_to_keys
        frame_to_keys = {}
        for key in sampled_keys:
            f_last = last_alive_frame[key]
            if f_last >= 0:
                frame_to_keys.setdefault(f_last, []).append(key)
        frames_to_read = sorted(frame_to_keys.keys())

    print("Phase 3: Extracting S and PEEQ from %d frames..." % len(frames_to_read))

    for count, f_idx in enumerate(frames_to_read):
        f = step.frames[f_idx]
        t_val = float(f.frameValue)
        target_keys = set(frame_to_keys[f_idx])
        
        has_s = "S" in f.fieldOutputs
        has_peeq = "PEEQ" in f.fieldOutputs
        
        if not has_s:
            continue
            
        s_data = {}
        for b in f.fieldOutputs["S"].bulkDataBlocks:
            if b.instance is None or b.instance.name not in host_instances:
                continue
            inst_name = b.instance.name
            labels = b.elementLabels
            data = b.data  # shape (N, 6) or (N, GP, 6)
            for i, lbl in enumerate(labels):
                key = (inst_name, int(lbl))
                if key in target_keys:
                    s_val = data[i]
                    if s_val.ndim == 2:
                        s_val = s_val.mean(axis=0)
                    s_data[key] = s_val

        peeq_data = {}
        if has_peeq:
            for b in f.fieldOutputs["PEEQ"].bulkDataBlocks:
                if b.instance is None or b.instance.name not in host_instances:
                    continue
                inst_name = b.instance.name
                labels = b.elementLabels
                data = b.data
                for i, lbl in enumerate(labels):
                    key = (inst_name, int(lbl))
                    if key in target_keys:
                        p_val = data[i]
                        if hasattr(p_val, '__len__'):
                            p_val = float(sum(p_val) / len(p_val))
                        else:
                            p_val = float(p_val)
                        peeq_data[key] = p_val

        for key in target_keys:
            if key not in s_data:
                continue
            s = s_data[key]
            s11, s22, s33 = float(s[0]), float(s[1]), float(s[2])
            s12, s13, s23 = float(s[3]), float(s[4]), float(s[5])
            
            sig_m = (s11 + s22 + s33) / 3.0
            p_hydro = -sig_m
            
            mises_sq = 0.5 * ((s11 - s22)**2 + (s22 - s33)**2 + (s33 - s11)**2 + 6.0*(s12**2 + s23**2 + s13**2))
            q_mises = math.sqrt(max(0.0, mises_sq))
            
            eta = (sig_m / q_mises) if q_mises > 1.0e-3 else 0.0
            sig1, sig2, sig3 = solve_eigenvalues_sym3x3(s11, s22, s33, s12, s13, s23)
            peeq_val = peeq_data.get(key, 0.0)
            
            results.append({
                "instance": key[0],
                "element": key[1],
                "last_alive_frame": f_idx,
                "deletion_frame": first_dead_frame[key],
                "time_us": t_val * 1e6,
                "sigma_m_MPa": sig_m / 1e6,
                "pressure_MPa": p_hydro / 1e6,
                "mises_MPa": q_mises / 1e6,
                "triaxiality": eta,
                "sigma_1_MPa": sig1 / 1e6,
                "sigma_1_sign": 1 if sig1 > 0 else (-1 if sig1 < 0 else 0),
                "peeq": peeq_val
            })
            
        if (count + 1) % 20 == 0 or (count + 1) == len(frames_to_read):
            print("  Frame %d / %d processed (%d element records accumulated)..." % 
                  (count + 1, len(frames_to_read), len(results)))

    # Compute statistics
    triax_vals = [r["triaxiality"] for r in results]
    sig1_signs = [r["sigma_1_sign"] for r in results]
    peeq_vals = [r["peeq"] for r in results]

    n_samp = len(triax_vals)
    frac_comp = sum(1 for x in triax_vals if x < 0.0) / float(n_samp) if n_samp > 0 else 0.0
    frac_low_tens = sum(1 for x in triax_vals if 0.0 <= x <= 1.0/3.0) / float(n_samp) if n_samp > 0 else 0.0
    frac_high_tens = sum(1 for x in triax_vals if x > 1.0/3.0) / float(n_samp) if n_samp > 0 else 0.0
    
    frac_sig1_neg = sum(1 for s in sig1_signs if s <= 0) / float(n_samp) if n_samp > 0 else 0.0
    frac_sig1_pos = sum(1 for s in sig1_signs if s > 0) / float(n_samp) if n_samp > 0 else 0.0

    summary = {
        "odb": odb_path,
        "step": step_name,
        "total_deleted_elements": total_deleted,
        "sampled_elements": n_samp,
        "fractions": {
            "triaxiality_lt_0_compression": frac_comp,
            "triaxiality_0_to_third_shear_low_tension": frac_low_tens,
            "triaxiality_gt_third_high_tension": frac_high_tens,
            "max_principal_stress_negative_all_compressive": frac_sig1_neg,
            "max_principal_stress_positive": frac_sig1_pos
        },
        "triaxiality_stats": {
            "min": min(triax_vals) if triax_vals else 0,
            "mean": sum(triax_vals)/float(n_samp) if n_samp else 0,
            "max": max(triax_vals) if triax_vals else 0
        },
        "peeq_stats": {
            "min": min(peeq_vals) if peeq_vals else 0,
            "mean": sum(peeq_vals)/float(n_samp) if n_samp else 0,
            "max": max(peeq_vals) if peeq_vals else 0
        },
        "records": results
    }

    print("\nExtraction Summary:")
    print("  Sampled: %d elements" % n_samp)
    print("  Fraction triaxiality < 0 (compression): %.2f%%" % (frac_comp * 100))
    print("  Fraction triaxiality [0, 1/3] (shear / low tension): %.2f%%" % (frac_low_tens * 100))
    print("  Fraction triaxiality > 1/3 (high tension): %.2f%%" % (frac_high_tens * 100))
    print("  Fraction sigma_1 <= 0 (all 3 principal stresses compressive): %.2f%%" % (frac_sig1_neg * 100))
    print("  Mean PEEQ before deletion: %.4f" % summary["peeq_stats"]["mean"])

    with open(out_json, "w") as fp:
        json.dump(summary, fp, indent=2)
    print("Wrote results to %s" % out_json)

    odb.close()

if __name__ == "__main__":
    main()
