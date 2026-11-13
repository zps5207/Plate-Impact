"""Summarise vuint_pair.txt from the cx057 coupon (plain python3, no deps)."""
import sys
from collections import Counter, defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "vuint_pair.txt"
calls_per_kinc = Counter()
first_pair = {}            # (slv, mst tuple) -> first row
slv_first = {}             # slv -> first row
slv_rows = Counter()
first_pos = {}             # slv -> first row with pen > 0
maxf = defaultdict(lambda: (0.0, None))
nstate_seen = set()
for line in open(path):
    t = line.split()
    if not t or t[0].startswith("#"):
        continue
    if t[0] == "CALL":
        calls_per_kinc[int(t[2])] += 1
        nstate_seen.add((t[5], t[6], t[7]))
        continue
    if t[0] != "PT":
        continue
    call, kinc, k, slv = int(t[1]), int(t[2]), int(t[3]), int(t[4])
    mst = tuple(int(x) for x in t[5:9])
    v = [float(x) for x in t[9:]]
    pen, st1, st2, s1in, d0, press, area, force = v[:8]
    xyz = v[8:11]
    row = dict(call=call, kinc=kinc, mst=mst, pen=pen, st1in=st1, st2in=st2,
               d0=d0, press=press, area=area, force=force, xyz=xyz)
    slv_rows[slv] += 1
    slv_first.setdefault(slv, row)
    if (slv, mst) not in first_pair:
        first_pair[(slv, mst)] = row
    if pen > 0 and slv not in first_pos:
        first_pos[slv] = row
    if force > maxf[slv][0]:
        maxf[slv] = (force, row)

print("nnodstate/nnodmst/nstates seen:", nstate_seen)
h = Counter(calls_per_kinc.values())
print("calls per increment histogram {ncalls: nincrements}:", dict(sorted(h.items())))
print("increments with calls:", len(calls_per_kinc), "max kinc", max(calls_per_kinc) if calls_per_kinc else None)
fmt = lambda r: ("call %d kinc %d mst %s pen %.4e st1in %.4e st2in %.1f d0 %.4e press %.4e area %.3e F %.4e xyz %s"
                 % (r['call'], r['kinc'], r['mst'], r['pen'], r['st1in'], r['st2in'], r['d0'],
                    r['press'], r['area'], r['force'], ["%.3e" % c for c in r['xyz']]))
for s in sorted(slv_rows):
    print("\n=== slave %d  rows %d" % (s, slv_rows[s]))
    print(" first seen :", fmt(slv_first[s]))
    pairs = [(p, r) for p, r in first_pair.items() if p[0] == s]
    print(" distinct master facets:", len(pairs))
    for p, r in sorted(pairs, key=lambda x: x[1]['call']):
        print("   new pair  :", fmt(r))
    if s in first_pos:
        print(" first pen>0:", fmt(first_pos[s]))
    if maxf[s][1]:
        print(" max force  :", fmt(maxf[s][1]))
