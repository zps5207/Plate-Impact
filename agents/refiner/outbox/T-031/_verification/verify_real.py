from pathlib import Path
import json

from embmesh.plywise import write_plywise_deck
from embmesh.parser import parse_deck

root = Path(__file__).resolve().parents[5]
work = Path(__file__).resolve().parent
source = (root / 'Meshing/plate1hex_curved_hostonly.inp').read_text()
stack = (root / 'Meshing/stack.inp').read_text().splitlines()
part_start = next(i for i, line in enumerate(stack) if line.lower().startswith('*part, name=ball'))
part_end = next(i for i in range(part_start + 1, len(stack)) if stack[i].strip().lower() == '*end part')
inst_start = next(i for i, line in enumerate(stack) if line.lower().startswith('*instance, name=ball-1'))
inst_end = next(i for i in range(inst_start + 1, len(stack)) if stack[i].strip().lower() == '*end instance')
source = source.replace('*Assembly, name=Assembly', '\n'.join(stack[part_start:part_end + 1]) + '\n*Assembly, name=Assembly', 1)
source = source.replace('*End Assembly', '\n'.join(stack[inst_start:inst_end + 1]) + '\n*End Assembly', 1)
inp, out = work / 'real_source.inp', work / 'real_output.inp'
inp.write_text(source)
report = write_plywise_deck(inp, out, plies=10, plate_node_contact=True, ball_instance='Ball-1')
parse_deck(out)
lines = out.read_text().splitlines()
start = next(i for i, line in enumerate(lines) if line.startswith('*Contact, op=NEW'))
end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith('**') or lines[i].startswith('*End Step')), len(lines))
print('CONTACT BLOCK')
print('\n'.join(lines[start:end]))
print('REPORT CONTACT')
print(json.dumps(report['ball_contact'], indent=2))
