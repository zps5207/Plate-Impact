# abaqus python diag_fh.py <odb>   -- locate the nv3_fh blow-up (read-only)
from __future__ import print_function
import sys, math
from odbAccess import openOdb
odb = openOdb(sys.argv[1], readOnly=True)
step = odb.steps[list(odb.steps.keys())[-1]]

print('=== DEEP PENETRATION NODE SETS ===')
ra = odb.rootAssembly
for sn in list(ra.nodeSets.keys()):
    if 'DEEP' not in sn.upper():
        continue
    ns = ra.nodeSets[sn]
    print(sn)
    for inst_name, nodes in zip(ns.instanceNames, ns.nodes):
        zs = sorted(n.coordinates[2] * 1e3 for n in nodes)
        print('  %-24s %6d nodes  z %.3f..%.3f mm  first labels %s' % (
            inst_name, len(nodes), zs[0] if zs else 0, zs[-1] if zs else 0,
            [n.label for n in nodes[:8]]))

print('=== HISTORY ENERGIES (whole model) ===')
for rn, reg in step.historyRegions.items():
    keys = [k for k in reg.historyOutputs.keys() if k.startswith('ALL') or k == 'ETOTAL' or k == 'DT']
    if not keys:
        continue
    print('region', rn)
    data = dict((k, reg.historyOutputs[k].data) for k in keys)
    times = [t for t, v in data[keys[0]]]
    print('t_us ' + ' '.join('%10s' % k for k in keys))
    for i, t in enumerate(times):
        if t < 1.0e-6 and i % 3:
            continue
        row = []
        for k in keys:
            d = data[k]
            row.append('%10.4g' % (d[i][1] if i < len(d) else float('nan')))
        print('%5.3f ' % (t * 1e6) + ' '.join(row))

print('=== FRAMES ===')
for fr in step.frames:
    t = fr.frameValue
    if t < 1.25e-6:
        continue
    print('\n--- frame %d  t=%.3f us' % (fr.frameId, t * 1e6))
    fo = fr.fieldOutputs
    print('fields:', ' '.join(sorted(fo.keys()))[:600])
    # top nodal speeds
    if 'V' in fo:
        vals = fo['V'].values
        top = sorted(vals, key=lambda v: -(v.magnitude or 0.0))[:12]
        print('top |V| nodes:')
        for v in top:
            inst = v.instance.name if v.instance else '?'
            try:
                c = v.instance.getNodeFromLabel(v.nodeLabel).coordinates
                cs = '(%.2f,%.2f,%.2f)mm' % (c[0]*1e3, c[1]*1e3, c[2]*1e3)
            except Exception:
                cs = ''
            print('  %-22s n%-8d |V|=%10.4g %s' % (inst, v.nodeLabel, v.magnitude, cs))
    # contact pressure maxima per field name
    for k in fo.keys():
        if k.startswith('CPRESS') or k.startswith('CSHEAR') or k.startswith('CNAREA'):
            try:
                vals = fo[k].values
                if not vals:
                    continue
                vm = max(vals, key=lambda v: abs(v.data))
                print('  %-45s max=%10.4g at %s n%d  (n=%d)' % (k, vm.data, vm.instance.name if vm.instance else '?', vm.nodeLabel, len(vals)))
            except Exception as e:
                print('  ', k, 'err', e)
    # deleted elements per instance
    if 'STATUS' in fo:
        cnt = {}
        for v in fo['STATUS'].values:
            n = v.instance.name if v.instance else '?'
            a = cnt.setdefault(n, [0, 0])
            a[0] += 1
            if v.data < 0.5:
                a[1] += 1
        tot = sum(a[1] for a in cnt.values())
        print('  deleted (STATUS=0) total %d; by instance: %s' % (tot, ', '.join('%s:%d' % (n, a[1]) for n, a in sorted(cnt.items()) if a[1])))
    # highest element strain energy density / stress
    if 'LE' in fo:
        vals = fo['LE'].values
        top = sorted(vals, key=lambda v: -(v.maxPrincipal or 0.0))[:5]
        print('  top LE maxPrincipal:', ', '.join('%s e%d %.3g' % (v.instance.name, v.elementLabel, v.maxPrincipal) for v in top))
odb.close()
