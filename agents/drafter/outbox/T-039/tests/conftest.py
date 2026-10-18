import sys
from pathlib import Path

outbox_root = Path(__file__).resolve().parents[1]
repo_root = Path(__file__).resolve().parents[5]

if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

import embmesh
outbox_embmesh = str(outbox_root / 'embmesh')
if outbox_embmesh not in embmesh.__path__:
    embmesh.__path__.insert(0, outbox_embmesh)

if str(outbox_root) not in sys.path:
    sys.path.insert(0, str(outbox_root))
