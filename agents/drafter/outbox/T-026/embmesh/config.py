from __future__ import annotations
import json
from pathlib import Path
def load_config(path):
    p=Path(path); text=p.read_text()
    if p.suffix.lower()=='.json': out=json.loads(text)
    else:
      try:
        import yaml
        out=yaml.safe_load(text)
      except ImportError as e: raise RuntimeError('YAML config requires PyYAML; use JSON for minimal dependencies') from e
    if out.get('gap',0)<0 or out.get('gap_inplane',out.get('gap',0))<0 or out.get('gap_layer',out.get('gap',0))<0: raise ValueError('fiber gap must be non-negative')
    if out.get('fiber_type','truss') not in ('truss','beam'): raise ValueError('fiber_type must be truss or beam')
    if 'fiber_diameter' not in out: raise ValueError('fiber_diameter is required')
    return out
