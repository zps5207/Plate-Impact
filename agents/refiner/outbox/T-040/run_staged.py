import sys, importlib.util, runpy
from pathlib import Path
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root))
import embmesh
for name in ('plyfibers','plywise_vuel','plywise'):
    path=Path(__file__).resolve().parent/'embmesh'/f'{name}.py'
    spec=importlib.util.spec_from_file_location('embmesh.'+name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules['embmesh.'+name]=module
    spec.loader.exec_module(module)
if __name__ == '__main__':
    runpy.run_module('embmesh.cli',run_name='__main__')

