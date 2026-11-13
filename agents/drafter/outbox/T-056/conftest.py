import sys
from pathlib import Path

outbox_dir = Path(__file__).parent.resolve()
if str(outbox_dir) not in sys.path:
    sys.path.insert(0, str(outbox_dir))

for mod in list(sys.modules):
    if mod == "embmesh" or mod.startswith("embmesh."):
        del sys.modules[mod]
