"""Abaqus-python (run via `abaqus python extract_energy.py <job1> <job2> ...`) energy/mass extractor."""
import sys, json
from odbAccess import openOdb

out = {}
for job in sys.argv[1:]:
    try:
        odb = openOdb(job + '.odb', readOnly=True)
        step = odb.steps.values()[-1]
        hist = {}
        for region_key, region in step.historyRegions.items():
            for var_name, ho in region.historyOutputs.items():
                if ho.data:
                    hist[(region_key, var_name)] = ho.data[-1][1]
        mass = 0.0
        for inst in odb.rootAssembly.instances.values():
            pass
        out[job] = {'history_last': {("%s|%s" % k): v for k, v in hist.items()}}
        odb.close()
    except Exception as e:
        out[job] = {'error': repr(e)}
open('energy_summary.json', 'w').write(json.dumps(out, indent=1))
print("wrote energy_summary.json")
