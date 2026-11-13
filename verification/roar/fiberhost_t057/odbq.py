from odbAccess import openOdb
o=openOdb('cx057.odb',readOnly=True); s=o.steps['Step-1']
for f in [s.frames[i] for i in (0,10,20,30,40,59)]:
    st=f.fieldOutputs['STATUS'].getSubset(region=o.rootAssembly.instances['HOST-1'].elementSets['HOST_SAC'])
    pe=f.fieldOutputs['PEEQ'].getSubset(region=o.rootAssembly.instances['HOST-1'].elementSets['HOST_SAC'])
    print('t=%.2e STATUS %s PEEQ %s'%(f.frameValue,[v.data for v in st.values],['%.2e'%v.data for v in pe.values]))
    print('  fieldkeys', [k for k in f.fieldOutputs.keys() if k.startswith('C')])
for k in s.historyRegions.keys(): print('HR',k, list(s.historyRegions[k].historyOutputs.keys())[:8])
