from pathlib import Path
from embmesh.cli import main

def test_list(tmp_path, capsys):
 p=tmp_path/'a.inp'; p.write_text('*Part, name=P\n*Node\n1,0,0,0\n*End Part\n')
 main(['list',str(p)]); assert 'part P' in capsys.readouterr().out

