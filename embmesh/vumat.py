from __future__ import annotations

def update_tension_only(strain_increment: float, stress: float, E: float, failure_stress: float, deleted: bool=False):
    if deleted: return 0.0, True
    trial=stress+E*strain_increment
    if trial <= 0: return 0.0, False
    if trial >= failure_stress: return 0.0, True
    return trial, False

