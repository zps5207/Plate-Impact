"""Run the deliverable modules against the installed project package."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import embmesh

embmesh.__path__.insert(0, str(Path(__file__).parent / 'embmesh'))
from embmesh.cli import main

if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
