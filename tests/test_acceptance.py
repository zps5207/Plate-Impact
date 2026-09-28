import json
import numpy as np
import pytest
from embmesh.errors import HexOnlyError
from embmesh.generate import mesh_flat
from embmesh.parser import parse_deck

def test_flat_volume_and_roundtrip(tmp_path):
 f, rows = mesh_flat('examples/flat_disc.inp','DISC-1',.25,tmp_path)
 area=np.pi*.25**2/4; clipped=sum(np.linalg.norm(x.points[-1]-x.points[0]) for x in f)
 assert abs(sum(r[2] for r in rows)-clipped*area) / (clipped*area) < 1e-6
 assert abs(rows[0][3]-np.pi/4)<.02
 assert parse_deck(tmp_path/'output.inp').parts
 assert json.loads((tmp_path/'report.json').read_text())['fiber_count']==len(f)

def test_wedge_writes_nothing(tmp_path):
 with pytest.raises(HexOnlyError): mesh_flat('examples/wedge.inp','BAD-1',.2,tmp_path)
 assert not list(tmp_path.iterdir())

