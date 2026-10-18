"""Thickness-dependent cohesive interface presets for plywise decks.

Dyneema HB26: Hazzard et al., Composites Part A 115 (2018) 31-45, section 2.5 and Table 5.
The paper joins one-element-thick sub-laminates with a bi-linear, mixed-mode (power law, exponent 1)
cohesive interface. Only the initial stiffness depends on sub-laminate thickness t_SL:

    K_I  = E_m / t_SL            (Eq. 11)
    K_II = 0.6 * K_I             (stiffness ratio K_II/K_I = 0.6)

Table 5 (t_SL = 1 mm) gives K_I = 60 N/mm^3, so E_m = 60 MPa; the paper does not print E_m separately,
so that value is inferred from Table 5 and Table 7 (K_I = 12 N/mm^3 at 5 mm, 18 at 3.33 mm). Strengths
and fracture energies are thickness independent in the paper:
    T = 1.2 MPa (mode I), S = 1.8 MPa (mode II, quasi-static), G_Ic = 0.544 N/mm, G_IIc = 1.088 N/mm.
For ballistic impact the paper raises the mode II strength to 2.6 MPa (section 5; the text says "from 1.6",
Table 5 says 1.8). Whether the mode I strength changes with rate is not stated, so it is left at 1.2 MPa.
The paper reports reduced load bearing for t_SL below 0.125 mm and does not cover thinner layers.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .errors import MesherInputError

E_M_MPA = 60.0                 # inferred, see module docstring
STIFFNESS_RATIO_II = 0.6
T_MODE_I_MPA = 1.2
S_MODE_II_MPA = {"quasi-static": 1.8, "ballistic": 2.6}
G_IC_N_PER_MM = 0.544
G_IIC_N_PER_MM = 1.088
POWER_LAW = 1.0
MIN_VALID_THICKNESS_MM = 0.125

# length unit of the deck -> millimetres per model length unit
_UNITS = {"m": 1000.0, "mm": 1.0}


@dataclass
class CohesiveInteraction:
    name: str
    k: tuple[float, float, float]          # traction/separation stiffness: Knn, Kss, Ktt
    strength: tuple[float, float, float]   # MAXS: normal, shear1, shear2
    fracture_energy: tuple[float, float, float]
    power: float = POWER_LAW
    source: str = ""
    warnings: list[str] = field(default_factory=list)

    def inp_lines(self):
        fmt = lambda v: ", ".join(f"{x:.6g}" for x in v)
        return [f"** {self.source}" if self.source else "** cohesive interface preset",
                f"*Surface Interaction, name={self.name}",
                "*Cohesive Behavior", f" {fmt(self.k)}",
                "*Damage Initiation, criterion=MAXS", f" {fmt(self.strength)}",
                f"*Damage Evolution, type=ENERGY, mixed mode behavior=POWER LAW, power={self.power:g}",
                f"{fmt(self.fracture_energy)}"]


def dyneema_hb26_hazzard2018(ply_thickness, units="m", rate="quasi-static", name="Cohesion_Hazzard2018"):
    """Cohesive interface for Dyneema HB26 plies of thickness `ply_thickness` (in deck length units).

    units: 'm' (SI: Pa, Pa/m, J/m^2) or 'mm' (N, mm, MPa: MPa, MPa/mm = N/mm^3, N/mm).
    """
    if units not in _UNITS:
        raise MesherInputError(f"unknown unit system {units!r}; choose 'm' or 'mm'")
    if rate not in S_MODE_II_MPA:
        raise MesherInputError(f"unknown rate preset {rate!r}; choose {sorted(S_MODE_II_MPA)}")
    if not ply_thickness or ply_thickness <= 0:
        raise MesherInputError("ply thickness must be positive")
    t_mm = ply_thickness * _UNITS[units]
    k_i = E_M_MPA / t_mm                       # N/mm^3 (= MPa/mm)
    k = (k_i, STIFFNESS_RATIO_II * k_i, STIFFNESS_RATIO_II * k_i)
    t_mpa, s_mpa = T_MODE_I_MPA, S_MODE_II_MPA[rate]
    g = (G_IC_N_PER_MM, G_IIC_N_PER_MM, G_IIC_N_PER_MM)
    if units == "m":
        k = tuple(v * 1e9 for v in k)          # N/mm^3 -> Pa/m
        strength = (t_mpa * 1e6, s_mpa * 1e6, s_mpa * 1e6)
        g = tuple(v * 1e3 for v in g)          # N/mm -> J/m^2
    else:
        strength = (t_mpa, s_mpa, s_mpa)
    warnings = []
    if t_mm < MIN_VALID_THICKNESS_MM:
        warnings.append(f"ply thickness {t_mm:.4g} mm is below 0.125 mm; Hazzard et al. 2018 report reduced "
                        "load bearing there and do not cover thinner layers")
    return CohesiveInteraction(
        name=name, k=k, strength=strength, fracture_energy=g,
        source=f"Hazzard et al. 2018 (Dyneema HB26), t_SL = {t_mm:.6g} mm, {rate}",
        warnings=warnings)


MATERIALS = {"dyneema-hb26": dyneema_hb26_hazzard2018}
MATERIAL_LABELS = {"dyneema-hb26": "Dyneema HB26 (Hazzard et al. 2018)"}
RATES = tuple(S_MODE_II_MPA)


def cohesive_interaction(material, ply_thickness, units="m", rate="quasi-static", name=None):
    try:
        build = MATERIALS[material]
    except KeyError:
        raise MesherInputError(f"unknown cohesive material {material!r}; choose {sorted(MATERIALS)}") from None
    return build(ply_thickness, units=units, rate=rate, **({"name": name} if name else {}))
