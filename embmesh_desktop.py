"""Windows desktop wrapper for the embmesh command-line executable.

This intentionally keeps the mesher package unchanged.  It collects common
options and invokes the packaged ``embmesh.exe`` in a background process.
"""
from __future__ import annotations

import os
import json
import math
import re
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from embmesh.cohesive_materials import (
    MATERIAL_LABELS,
    MATERIALS,
    RATES,
    E_M_MPA,
    STIFFNESS_RATIO_II,
    cohesive_interaction,
)

EXISTING_DECK_INTERACTION = "Existing deck interaction"


def engine_path() -> Path:
    """Find embmesh.exe both beside source and inside a PyInstaller bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        candidate = Path(bundled) / "embmesh.exe"
    else:
        candidate = Path(__file__).resolve().parent / "dist" / "embmesh.exe"
    if not candidate.is_file():
        raise FileNotFoundError(f"Could not find the mesher executable: {candidate}")
    return candidate


def instance_names(list_output: str) -> list[str]:
    """Extract assembly-instance names from ``embmesh list`` output."""
    names = []
    for line in list_output.splitlines():
        if line.startswith("instance "):
            name = line[len("instance "):].split(":", 1)[0].strip()
            if name:
                names.append(name)
    return names


def list_surface_interactions(deck_path: str | Path) -> list[tuple[str, bool]]:
    """Find named interaction properties and their cohesive behavior in deck order."""
    result: list[tuple[str, bool]] = []
    name = None
    cohesive = False
    property_keywords = {'*friction', '*surface behavior', '*cohesive behavior',
                         '*damage initiation', '*damage evolution', '*damage stabilization',
                         '*contact damping', '*contact controls', '*gap conductance',
                         '*thermal conductance', '*heat generation'}
    for raw in Path(deck_path).read_text(errors='replace').splitlines():
        line = raw.strip()
        if not line.startswith('*') or line.startswith('**'):
            continue
        keyword = line.split(',', 1)[0].strip().lower()
        if keyword == '*surface interaction':
            if name is not None:
                result.append((name, cohesive))
            match = re.search(r'(?:^|,)\s*name\s*=\s*("[^"]*"|[^,]+)', line, re.I)
            name = match.group(1).strip().strip('"') if match else None
            cohesive = False
        elif name is not None:
            if keyword == '*cohesive behavior':
                cohesive = True
            elif keyword not in property_keywords:
                result.append((name, cohesive))
                name = None
    if name is not None:
        result.append((name, cohesive))
    return result


def _positive_float(value, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{label} must be a number.') from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f'{label} must be positive.')
    return number


def compute_cohesive_readout(material: str, ply_thickness: float, units: str = 'm',
                             rate: str = 'quasi-static', name: str | None = None) -> dict:
    """Compute cohesive interaction properties and formatted readout strings for a ply thickness."""
    if not ply_thickness or ply_thickness <= 0:
        raise ValueError('Ply thickness must be positive.')
    mat_key = material
    if material not in MATERIALS:
        for k, label in MATERIAL_LABELS.items():
            if material.lower() == label.lower() or material.lower() == k.lower():
                mat_key = k
                break
        else:
            raise ValueError(f'Unknown cohesive material: {material}')
    if units not in ('m', 'mm'):
        raise ValueError("Length units must be 'm' or 'mm'.")
    if rate not in RATES:
        raise ValueError(f"Cohesive rate must be one of {RATES}.")

    interaction = cohesive_interaction(mat_key, ply_thickness, units=units, rate=rate, name=name)

    t_mm = ply_thickness * (1000.0 if units == 'm' else 1.0)
    k_i_mm = E_M_MPA / t_mm
    k_ii_mm = STIFFNESS_RATIO_II * k_i_mm

    k_i_deck = interaction.k[0]
    k_ii_deck = interaction.k[1]
    t_norm_deck = interaction.strength[0]
    s_shear_deck = interaction.strength[1]
    g_ic_deck = interaction.fracture_energy[0]
    g_iic_deck = interaction.fracture_energy[1]

    warnings = list(interaction.warnings)
    if units == 'm' and ply_thickness > 0.5:
        w = f"resulting ply thickness {ply_thickness:.4g} is > 0.5 in 'm' units mode; check --length-units (likely mm geometry in m mode)"
        if w not in warnings:
            warnings.append(w)
    elif units == 'mm' and ply_thickness < 1e-3:
        w = f"resulting ply thickness {ply_thickness:.4g} is < 1e-3 in 'mm' units mode; check --length-units (likely m geometry in mm mode)"
        if w not in warnings:
            warnings.append(w)

    k_unit = 'Pa/m' if units == 'm' else 'N/mm^3'
    str_unit = 'Pa' if units == 'm' else 'MPa'
    eng_unit = 'J/m^2' if units == 'm' else 'N/mm'

    k_i_deck_str = f"{k_i_deck:.3g}".replace("+", "")
    k_ii_deck_str = f"{k_ii_deck:.3g}".replace("+", "")

    display_lines = [
        f"K_I = {k_i_mm:.4g} N/mm^3 ({k_i_deck_str} {k_unit}), K_II = {k_ii_mm:.4g} N/mm^3 ({k_ii_deck_str} {k_unit})",
        f"Strengths: Normal = {t_norm_deck:.4g} {str_unit}, Shear = {s_shear_deck:.4g} {str_unit}",
        f"Fracture energy: G_Ic = {g_ic_deck:.4g} {eng_unit}, G_IIc = {g_iic_deck:.4g} {eng_unit}",
    ]

    return {
        'material': mat_key,
        'ply_thickness': ply_thickness,
        'units': units,
        'rate': rate,
        'name': interaction.name,
        'k_i_mm': k_i_mm,
        'k_ii_mm': k_ii_mm,
        'k_i_n_mm3': k_i_mm,
        'k_ii_n_mm3': k_ii_mm,
        'k_i_deck': k_i_deck,
        'k_ii_deck': k_ii_deck,
        'k_i': k_i_deck,
        'k_ii': k_ii_deck,
        'k_i_str': k_i_deck_str,
        'k_ii_str': k_ii_deck_str,
        'normal_strength': t_norm_deck,
        'shear_strength': s_shear_deck,
        'strengths': interaction.strength,
        'g_ic': g_ic_deck,
        'g_iic': g_iic_deck,
        'fracture_energies': interaction.fracture_energy,
        'warnings': warnings,
        'display': "\n".join(display_lines),
    }


def build_plywise_command(values: dict) -> list[str]:
    """Validate form values and build CLI arguments without accessing Tk."""
    deck = Path(values.get('deck', '')).expanduser()
    if not deck.is_file():
        raise ValueError('Choose an existing .inp deck.')
    instance = str(values.get('instance', '')).strip()
    if not instance:
        raise ValueError('Select an assembly instance from the input deck.')
    output = str(values.get('output', '')).strip()
    if not output:
        raise ValueError('Choose an output folder.')
    plies = str(values.get('plies', '')).strip()
    thickness = str(values.get('ply_thickness', '')).strip()
    if bool(plies) == bool(thickness):
        raise ValueError('Provide either ply count or ply thickness.')
    command = [str(values.get('engine', 'embmesh')), 'plywise', str(deck),
               '--instance', instance, '--output', str(Path(output).expanduser() / 'output.inp')]

    if values.get('collapse_layers') or values.get('collapse'):
        command.append('--collapse-layers')

    if plies:
        try:
            count = int(plies)
        except ValueError as exc:
            raise ValueError('Ply count must be a positive integer.') from exc
        if count < 1:
            raise ValueError('Ply count must be a positive integer.')
        command += ['--plies', plies]
    else:
        _positive_float(thickness, 'Ply thickness')
        command += ['--ply-thickness', thickness]
        count = values.get('resolved_plies')
        if count is not None and (not isinstance(count, int) or count < 1):
            raise ValueError('Resolved ply count must be a positive integer.')
    layup = str(values.get('layup', '')).strip()
    if layup:
        try:
            angles = [float(x.strip()) for x in layup.split(',')]
        except ValueError as exc:
            raise ValueError('Layup must be comma-separated angles.') from exc
        if not all(math.isfinite(a) for a in angles):
            raise ValueError('Layup angles must be finite numbers.')
        _positive_float(values.get('fiber_diameter', ''), 'Fiber diameter')
        try:
            repeat = int(str(values.get('layup_repeat', '1')))
        except ValueError as exc:
            raise ValueError('Layup repeat must be a positive integer.') from exc
        if repeat < 1:
            raise ValueError('Layup repeat must be a positive integer.')
        from embmesh.plyfibers import expand_layup
        if count is not None:
            expand_layup(angles, count, bool(values.get('layup_symmetric')), repeat)
        command += ['--layup', layup, '--fiber-diameter', str(values['fiber_diameter']).strip()]
        if values.get('layup_symmetric'):
            command.append('--layup-symmetric')
        if repeat != 1:
            command += ['--layup-repeat', str(repeat)]
        gap = str(values.get('fiber_gap', '0')).strip()
        try:
            gap_number = float(gap)
        except ValueError as exc:
            raise ValueError('Fiber gap must be a non-negative number.') from exc
        if not math.isfinite(gap_number) or gap_number < 0:
            raise ValueError('Fiber gap must be a non-negative number.')
        command += ['--fiber-gap', gap]
        fiber_type = str(values.get('fiber_type', 'truss'))
        if fiber_type not in ('truss', 'beam'):
            raise ValueError('Fiber type must be truss or beam.')
        command += ['--fiber-type', fiber_type]
        material = str(values.get('fiber_material', 'Fiber')).strip()
        if not material:
            raise ValueError('Fiber material name is required.')
        command += ['--fiber-material', material]
    axis = str(values.get('thickness_axis', '')).strip()
    if axis and axis.lower() != 'auto':
        if axis.lower() not in ('x', 'y', 'z'):
            try:
                components = [float(x.strip()) for x in axis.split(',')]
            except ValueError as exc:
                raise ValueError('Thickness axis must be x, y, z, or a three-number vector.') from exc
            if len(components) != 3 or not all(math.isfinite(x) for x in components) or not any(components):
                raise ValueError('Thickness axis must be x, y, z, or a nonzero three-number vector.')
        command += ['--thickness-axis', axis]

    host_mode = str(values.get('host_mode', 'native')).strip().lower()
    if host_mode in ('vuel-ghost', 'vuel + ghost', 'vuel_ghost'):
        ghost_scale = values.get('ghost_scale', '1e-4')
        try:
            scale_val = float(ghost_scale)
        except (TypeError, ValueError) as exc:
            raise ValueError('Ghost scale must be a number strictly between 0 and 1.') from exc
        if not (0.0 < scale_val < 1.0) or not math.isfinite(scale_val):
            raise ValueError('Ghost scale must be strictly between 0 and 1.')
        command += ['--host-mode', 'vuel-ghost', '--ghost-scale', str(ghost_scale).strip()]
    elif host_mode and host_mode != 'native':
        raise ValueError(f"Unknown host mode: {values.get('host_mode')}")

    cohesion_flag = values.get('cohesion')
    cohesive_mat = values.get('cohesive_material') or values.get('cohesion_material')
    if cohesion_flag is None:
        cohesion_flag = bool(cohesive_mat and str(cohesive_mat).strip() != EXISTING_DECK_INTERACTION)

    if cohesion_flag:
        mat_key = None
        if cohesive_mat:
            s_mat = str(cohesive_mat).strip()
            if s_mat and s_mat != EXISTING_DECK_INTERACTION:
                if s_mat in MATERIALS:
                    mat_key = s_mat
                else:
                    for k, lbl in MATERIAL_LABELS.items():
                        if s_mat.lower() == lbl.lower() or s_mat.lower() == k.lower():
                            mat_key = k
                            break
                    if mat_key is None:
                        raise ValueError(f'Unknown cohesive material: {s_mat}')

        if mat_key is not None:
            command += ['--cohesive-material', mat_key]
            rate = str(values.get('cohesive_rate') or values.get('cohesion_rate') or 'quasi-static').strip()
            if rate not in ('quasi-static', 'ballistic'):
                raise ValueError("Cohesive rate must be 'quasi-static' or 'ballistic'.")
            command += ['--cohesive-rate', rate]

            units = str(values.get('length_units') or values.get('units') or 'm').strip()
            if units not in ('m', 'mm'):
                raise ValueError("Length units must be 'm' or 'mm'.")
            command += ['--length-units', units]

            c_name = values.get('cohesive_name') or values.get('cohesion_name')
            if c_name:
                c_name_str = str(c_name).strip()
                if c_name_str:
                    command += ['--cohesive-name', c_name_str]

            command.append('--cohesive-overwrite')
        else:
            interaction = str(values.get('cohesion_interaction', '')).strip()
            if not interaction:
                raise ValueError('Select a cohesive interaction.')
            command += ['--cohesion', interaction]

    if values.get('plate_node_contact') or values.get('fiber_node_contact'):
        ball = str(values.get('ball_instance', '')).strip()
        if not ball:
            raise ValueError('Select a ball instance when ball contact is enabled.')
        contact_thickness = str(values.get('contact_thickness', 'auto')).strip()
        if contact_thickness.lower() != 'auto':
            try:
                t = float(contact_thickness)
            except ValueError as exc:
                raise ValueError("Contact thickness must be non-negative or 'auto'.") from exc
            if not math.isfinite(t) or t < 0:
                raise ValueError("Contact thickness must be non-negative or 'auto'.")
        if values.get('plate_node_contact'):
            command.append('--plate-node-contact')
        if values.get('fiber_node_contact'):
            command.append('--fiber-node-contact')
        command += ['--ball-instance', ball, '--contact-thickness', contact_thickness]
        ball_interaction = str(values.get('ball_interaction', '')).strip()
        if ball_interaction and ball_interaction.lower() != 'automatic':
            command += ['--ball-interaction', ball_interaction]
    command.append('--preview')
    return command


class DesktopApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=14)
        self.master = master
        self.grid(sticky="nsew")
        master.title("Embedded Element Mesher")
        master.minsize(800, 720)
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.deck = tk.StringVar()
        self.instance = tk.StringVar()
        self.diameter = tk.StringVar(value="0.25")
        self.output = tk.StringVar()
        self.gap = tk.StringVar(value="0")
        self.fiber_type = tk.StringVar(value="truss")
        self.thickness_axis = tk.StringVar()
        self.precise_volume = tk.BooleanVar(value=False)
        self.plate_node_contact = tk.BooleanVar(value=False)
        self.fiber_node_contact = tk.BooleanVar(value=False)
        self.ball_instance = tk.StringVar()
        self.contact_thickness = tk.StringVar(value="auto")
        self.plywise = tk.BooleanVar(value=False)
        self.ply_mode = tk.StringVar(value='plies')
        self.plies = tk.StringVar(value='4')
        self.ply_thickness = tk.StringVar()
        self.layup = tk.StringVar()
        self.layup_symmetric = tk.BooleanVar(value=False)
        self.layup_repeat = tk.StringVar(value='1')
        self.fiber_material = tk.StringVar(value='Fiber')

        self.collapse_layers = tk.BooleanVar(value=False)
        self.host_mode = tk.StringVar(value='native')
        self.ghost_scale = tk.StringVar(value='1e-4')

        self.cohesion = tk.BooleanVar(value=False)
        self.cohesive_material = tk.StringVar(value=EXISTING_DECK_INTERACTION)
        self.cohesion_material = self.cohesive_material
        self.cohesive_rate = tk.StringVar(value='quasi-static')
        self.length_units = tk.StringVar(value='m')
        self.cohesive_name = tk.StringVar(value='Cohesion_Hazzard2018')
        self.cohesive_readout = tk.StringVar(value='enter a ply thickness or load a deck')
        self.cohesive_warnings = tk.StringVar()

        self.cohesion_interaction = tk.StringVar()
        self.ball_interaction = tk.StringVar(value='automatic')
        self.layup_display = tk.StringVar(value='No fibers')
        self.cohesion_help = tk.StringVar()
        self._interactions: list[tuple[str, bool]] = []
        self._running_plywise = False
        self._instance_names: list[str] = []
        self.status = tk.StringVar(value="Choose an Abaqus input deck to begin.")
        self.progress_value = tk.DoubleVar(value=0)
        self._build()
        self._build_plywise()

    def _build_plywise(self) -> None:
        for widget in self.grid_slaves():
            row = int(widget.grid_info()['row'])
            if row >= 2:
                widget.grid_configure(row=row + (2 if row >= 10 else 1))
        self.rowconfigure(14, weight=0)
        self.rowconfigure(16, weight=1)
        ttk.Checkbutton(self, text='Plywise laminate', variable=self.plywise,
                        command=self._update_plywise_controls).grid(row=2, column=0, columnspan=3, sticky='w')
        self.ply_frame = ttk.LabelFrame(self, text='Plywise laminate', padding=8)
        self.ply_frame.grid(row=11, column=0, columnspan=3, sticky='ew', pady=(0, 8))
        self.ply_frame.columnconfigure(1, weight=1)

        count = ttk.Frame(self.ply_frame)
        count.grid(row=0, column=0, columnspan=3, sticky='w')
        ttk.Radiobutton(count, text='Ply count', variable=self.ply_mode, value='plies',
                        command=self._update_ply_mode).pack(side='left')
        self.plies_entry = ttk.Entry(count, textvariable=self.plies, width=8)
        self.plies_entry.pack(side='left', padx=(4, 16))
        ttk.Radiobutton(count, text='Ply thickness', variable=self.ply_mode, value='thickness',
                        command=self._update_ply_mode).pack(side='left')
        self.ply_thickness_entry = ttk.Entry(count, textvariable=self.ply_thickness, width=12)
        self.ply_thickness_entry.pack(side='left', padx=4)

        ttk.Label(self.ply_frame, text='Layup angles').grid(row=1, column=0, sticky='w')
        ttk.Entry(self.ply_frame, textvariable=self.layup).grid(row=1, column=1, sticky='ew')
        ttk.Label(self.ply_frame, text='Comma-separated; empty for no fibers').grid(row=1, column=2, sticky='w', padx=8)

        options = ttk.Frame(self.ply_frame)
        options.grid(row=2, column=0, columnspan=3, sticky='w')
        ttk.Checkbutton(options, text='Symmetric', variable=self.layup_symmetric,
                        command=self._refresh_layup).pack(side='left')
        ttk.Label(options, text='Repeat').pack(side='left', padx=(12, 4))
        ttk.Entry(options, textvariable=self.layup_repeat, width=6).pack(side='left')

        ttk.Label(self.ply_frame, textvariable=self.layup_display).grid(row=3, column=0, columnspan=3, sticky='w')
        ttk.Label(self.ply_frame, text='Fiber material').grid(row=4, column=0, sticky='w')
        ttk.Entry(self.ply_frame, textvariable=self.fiber_material).grid(row=4, column=1, sticky='ew')

        collapse_row = ttk.Frame(self.ply_frame)
        collapse_row.grid(row=5, column=0, columnspan=3, sticky='w', pady=(2, 2))
        self.collapse_check = ttk.Checkbutton(collapse_row, text='Collapse layers to one hex',
                                             variable=self.collapse_layers)
        self.collapse_check.pack(side='left')
        self.collapse_label = ttk.Label(
            collapse_row,
            text='Use when the loaded deck has several hex layers through the thickness (virgin solid decks)',
            font=('Segoe UI', 8)
        )
        self.collapse_label.pack(side='left', padx=(8, 0))

        host_row = ttk.Frame(self.ply_frame)
        host_row.grid(row=6, column=0, columnspan=3, sticky='w', pady=(2, 2))
        ttk.Label(host_row, text='Host mode').pack(side='left')
        self.host_mode_combo = ttk.Combobox(host_row, textvariable=self.host_mode,
                                            values=('native', 'vuel-ghost'),
                                            state='readonly', width=14)
        self.host_mode_combo.pack(side='left', padx=(6, 12))
        self.host_mode_combo.bind('<<ComboboxSelected>>', lambda *_: self._update_host_mode_controls())

        self.ghost_scale_frame = ttk.Frame(host_row)
        ttk.Label(self.ghost_scale_frame, text='Ghost scale').pack(side='left')
        self.ghost_scale_entry = ttk.Entry(self.ghost_scale_frame, textvariable=self.ghost_scale, width=10)
        self.ghost_scale_entry.pack(side='left', padx=(6, 6))
        ttk.Label(self.ghost_scale_frame, text='(0 < scale < 1, default 1e-4)', font=('Segoe UI', 8)).pack(side='left')

        cohesion_row = ttk.Frame(self.ply_frame)
        cohesion_row.grid(row=7, column=0, columnspan=3, sticky='w', pady=(4, 2))
        self.cohesion_check = ttk.Checkbutton(cohesion_row, text='Cohesion', variable=self.cohesion,
                                             command=self._update_cohesive_controls)
        self.cohesion_check.pack(side='left')

        mat_labels = [EXISTING_DECK_INTERACTION] + list(MATERIAL_LABELS.values())
        self.cohesion_mat_combo = ttk.Combobox(cohesion_row, textvariable=self.cohesive_material,
                                               values=mat_labels, state='readonly', width=34)
        self.cohesion_mat_combo.pack(side='left', padx=(10, 8))
        self.cohesion_mat_combo.bind('<<ComboboxSelected>>', lambda *_: self._update_cohesive_controls())

        self.existing_cohesion_frame = ttk.Frame(self.ply_frame)
        self.existing_cohesion_frame.grid(row=8, column=0, columnspan=3, sticky='w', pady=(2, 2))
        ttk.Label(self.existing_cohesion_frame, text='Deck interaction').pack(side='left')
        self.cohesion_combo = ttk.Combobox(self.existing_cohesion_frame, textvariable=self.cohesion_interaction,
                                           state='readonly', width=24)
        self.cohesion_combo.pack(side='left', padx=(6, 8))
        self.cohesion_help_label = ttk.Label(self.existing_cohesion_frame, textvariable=self.cohesion_help)
        self.cohesion_help_label.pack(side='left')

        self.preset_cohesion_frame = ttk.Frame(self.ply_frame)
        self.preset_cohesion_frame.grid(row=8, column=0, columnspan=3, sticky='ew', pady=(2, 2))

        preset_opts = ttk.Frame(self.preset_cohesion_frame)
        preset_opts.pack(anchor='w', fill='x')
        ttk.Label(preset_opts, text='Rate').pack(side='left')
        self.cohesive_rate_combo = ttk.Combobox(preset_opts, textvariable=self.cohesive_rate,
                                                values=('quasi-static', 'ballistic'), state='readonly', width=14)
        self.cohesive_rate_combo.pack(side='left', padx=(4, 10))

        ttk.Label(preset_opts, text='Length units').pack(side='left')
        self.length_units_combo = ttk.Combobox(preset_opts, textvariable=self.length_units,
                                               values=('m', 'mm'), state='readonly', width=6)
        self.length_units_combo.pack(side='left', padx=(4, 10))

        ttk.Label(preset_opts, text='Interaction name').pack(side='left')
        self.cohesive_name_entry = ttk.Entry(preset_opts, textvariable=self.cohesive_name, width=22)
        self.cohesive_name_entry.pack(side='left', padx=(4, 0))

        self.cohesive_overwrite_label = ttk.Label(
            self.preset_cohesion_frame,
            text='Preset always overwrites an existing interaction of the same name (--cohesive-overwrite)',
            font=('Segoe UI', 8, 'italic')
        )
        self.cohesive_overwrite_label.pack(anchor='w', pady=(2, 2))

        self.cohesive_readout_label = ttk.Label(
            self.preset_cohesion_frame,
            textvariable=self.cohesive_readout,
            font=('Cascadia Mono', 8)
        )
        self.cohesive_readout_label.pack(anchor='w', pady=(2, 2))

        self.cohesive_warnings_label = ttk.Label(
            self.preset_cohesion_frame,
            textvariable=self.cohesive_warnings,
            foreground='red',
            font=('Segoe UI', 8)
        )
        self.cohesive_warnings_label.pack(anchor='w')

        contact = self.ball_instance_combo.master
        ttk.Label(contact, text='Ball interaction').grid(row=1, column=2, sticky='e')
        self.ball_interaction_combo = ttk.Combobox(contact, textvariable=self.ball_interaction,
                                                  state='disabled', width=22)
        self.ball_interaction_combo.grid(row=1, column=3, sticky='ew', padx=(6, 16))
        self.precise_check = next(w for w in self.grid_slaves() if isinstance(w, ttk.Checkbutton)
                                  and str(w.cget('text')).startswith('Calculate precise'))

        for variable in (self.plies, self.ply_thickness, self.layup, self.layup_repeat):
            variable.trace_add('write', lambda *_: self._refresh_layup())

        for var in (self.cohesive_material, self.cohesive_rate, self.length_units,
                    self.cohesive_name, self.plies, self.ply_thickness, self.thickness_axis,
                    self.instance, self.deck, self.host_mode):
            var.trace_add('write', lambda *_: self._on_field_change())

        self._update_ply_mode()
        self._update_host_mode_controls()
        self._update_plywise_controls()

    def _on_field_change(self) -> None:
        self._update_host_mode_controls()
        self._update_cohesive_controls()

    def _update_host_mode_controls(self) -> None:
        if self.host_mode.get() in ('vuel-ghost', 'vuel + ghost'):
            self.ghost_scale_frame.pack(side='left', padx=(6, 0))
        else:
            self.ghost_scale_frame.pack_forget()

    def _update_ply_mode(self) -> None:
        self.plies_entry.configure(state='normal' if self.ply_mode.get() == 'plies' else 'disabled')
        self.ply_thickness_entry.configure(state='normal' if self.ply_mode.get() == 'thickness' else 'disabled')
        self._refresh_layup()
        self._update_cohesive_readout()

    def _get_current_ply_thickness(self) -> float | None:
        if self.ply_mode.get() == 'thickness':
            val = self.ply_thickness.get().strip()
            if not val:
                return None
            try:
                t = float(val)
                return t if math.isfinite(t) and t > 0 else None
            except ValueError:
                return None
        val = self.plies.get().strip()
        if not val:
            return None
        try:
            count = int(val)
            if count < 1:
                return None
        except ValueError:
            return None
        deck_path = self.deck.get().strip()
        if not deck_path:
            return None
        path = Path(deck_path).expanduser()
        if not path.is_file():
            return None
        try:
            from embmesh.parser import parse_deck
            from embmesh.fibers import pick_thickness_axis
            import numpy as np
            deck = parse_deck(path)
            inst_name = self.instance.get().strip()
            if not inst_name and self._instance_names:
                inst_name = self._instance_names[0]
            if not inst_name and deck.instances:
                inst_name = next(iter(deck.instances.keys()))
            if not inst_name or inst_name not in deck.instances:
                return None
            instance = deck.instances[inst_name]
            part = deck.parts[instance.part]
            axis_str = self.thickness_axis.get().strip() or None
            axis = pick_thickness_axis(part.nodes, axis_str)
            pts = np.asarray(list(part.nodes.values()), float)
            proj = pts @ axis
            plate_thickness = float(proj.max() - proj.min())
            if plate_thickness > 0:
                return plate_thickness / count
        except Exception:
            return None
        return None

    def _update_cohesive_readout(self) -> None:
        mat = self.cohesive_material.get()
        if mat == EXISTING_DECK_INTERACTION:
            return
        t = self._get_current_ply_thickness()
        if t is None:
            self.cohesive_readout.set("enter a ply thickness or load a deck")
            self.cohesive_warnings.set("")
            return
        try:
            rate = self.cohesive_rate.get() or 'quasi-static'
            units = self.length_units.get() or 'm'
            name = self.cohesive_name.get() or 'Cohesion_Hazzard2018'
            res = compute_cohesive_readout(mat, t, units=units, rate=rate, name=name)
            self.cohesive_readout.set(res['display'])
            self.cohesive_warnings.set("\n".join(res['warnings']) if res['warnings'] else "")
        except Exception as exc:
            self.cohesive_readout.set(f"Could not compute readout: {exc}")
            self.cohesive_warnings.set("")

    def _update_cohesive_controls(self) -> None:
        enabled = self.cohesion.get()
        if not enabled:
            self.cohesion_mat_combo.configure(state='disabled')
            self.existing_cohesion_frame.grid_remove()
            self.preset_cohesion_frame.grid_remove()
            return

        self.cohesion_mat_combo.configure(state='readonly')
        is_preset = (self.cohesive_material.get() != EXISTING_DECK_INTERACTION)
        if is_preset:
            self.existing_cohesion_frame.grid_remove()
            self.preset_cohesion_frame.grid()
            self._update_cohesive_readout()
        else:
            self.preset_cohesion_frame.grid_remove()
            self.existing_cohesion_frame.grid()

    def _resolved_ply_count(self) -> int:
        if self.ply_mode.get() == 'plies':
            return int(self.plies.get())
        from embmesh.parser import parse_deck
        from embmesh.plywise import build_ply_part
        deck = parse_deck(self.deck.get())
        instance = deck.instances[self.instance.get()]
        _, metadata = build_ply_part(deck.parts[instance.part], ply_thickness=_positive_float(
            self.ply_thickness.get(), 'Ply thickness'), thickness_axis=self.thickness_axis.get().strip() or None)
        return metadata['plies']

    def _refresh_layup(self) -> None:
        if not self.layup.get().strip():
            self.layup_display.set('No fibers')
            return
        try:
            angles = [float(x.strip()) for x in self.layup.get().split(',')]
            repeat = int(self.layup_repeat.get())
            from embmesh.plyfibers import expand_layup
            expanded = expand_layup(angles, self._resolved_ply_count(),
                                    self.layup_symmetric.get(), repeat)
            self.layup_display.set('Per-ply angles: ' + ', '.join(f'{x:g}' for x in expanded))
        except (ValueError, KeyError, FileNotFoundError) as exc:
            self.layup_display.set(f'Layup: {exc}')

    def _update_plywise_controls(self) -> None:
        enabled = self.plywise.get()
        if enabled:
            self.ply_frame.grid()
            self.precise_check.configure(state='disabled')
            self.run_button.configure(text='Generate plywise laminate')
            self.preview_button.configure(text='View plywise preview', state='disabled')
        else:
            self.ply_frame.grid_remove()
            self.precise_check.configure(state='normal')
            self.run_button.configure(text='Generate embedded mesh')
            self.preview_button.configure(text='View fiber embedding', state='disabled')
        self._update_contact_controls()
        self._update_host_mode_controls()
        self._update_cohesive_controls()
        self._refresh_layup()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Embedded Element Mesher", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self, text="Creates an embedded-fiber Abaqus deck using the bundled mesher.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self._path_row(2, "Input deck (.inp)", self.deck, self.choose_deck, "Browse…")
        self._path_row(3, "Output folder", self.output, self.choose_output, "Browse…")
        ttk.Label(self, text="Instance name").grid(row=4, column=0, sticky="w", pady=4)
        self.instance_combo = ttk.Combobox(self, textvariable=self.instance, state="disabled")
        self.instance_combo.grid(row=4, column=1, sticky="ew", pady=4)
        ttk.Label(self, text="Select an assembly instance found in the input deck").grid(
            row=4, column=2, sticky="w", padx=(8, 0))
        self._entry_row(5, "Fiber diameter", self.diameter, "Positive length in the deck's units")
        self._entry_row(6, "In-plane gap", self.gap, "Optional; default 0")
        ttk.Label(self, text="Fiber type").grid(row=7, column=0, sticky="w", pady=4)
        ttk.Combobox(self, textvariable=self.fiber_type, values=("truss", "beam"), state="readonly", width=18).grid(
            row=7, column=1, sticky="w", pady=4)
        ttk.Label(self, text="Thickness axis").grid(row=8, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self.thickness_axis).grid(row=8, column=1, sticky="ew", pady=4)
        ttk.Label(self, text="Optional: x, y, z, or dx,dy,dz (normally auto-detected)").grid(row=8, column=2, sticky="w", padx=(8, 0))
        ttk.Checkbutton(self, text="Calculate precise per-host fiber volume (slower)", variable=self.precise_volume).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(6, 10))
        contact = ttk.LabelFrame(self, text="Ball contact", padding=8)
        contact.grid(row=10, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        ttk.Checkbutton(contact, text="Plate", variable=self.plate_node_contact,
                        command=self._update_contact_controls).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(contact, text="Fibers", variable=self.fiber_node_contact,
                        command=self._update_contact_controls).grid(row=0, column=1, sticky="w", padx=(12, 20))
        ttk.Label(contact, text="Ball instance").grid(row=0, column=2, sticky="e")
        self.ball_instance_combo = ttk.Combobox(contact, textvariable=self.ball_instance, state="disabled", width=22)
        self.ball_instance_combo.grid(row=0, column=3, sticky="ew", padx=(6, 16))
        ttk.Label(contact, text="Thickness").grid(row=0, column=4, sticky="e")
        self.contact_thickness_entry = ttk.Entry(contact, textvariable=self.contact_thickness, state="disabled", width=10)
        self.contact_thickness_entry.grid(row=0, column=5, sticky="w", padx=(6, 0))
        contact.columnconfigure(3, weight=1)
        controls = ttk.Frame(self)
        controls.grid(row=11, column=0, columnspan=3, sticky="ew")
        self.run_button = ttk.Button(controls, text="Generate embedded mesh", command=self.run_mesh)
        self.run_button.pack(side="left")
        ttk.Button(controls, text="Open output folder", command=self.open_output).pack(side="left", padx=8)
        self.preview_button = ttk.Button(controls, text="View fiber embedding", command=self.open_preview, state="disabled")
        self.preview_button.pack(side="left")
        self.progress = ttk.Progressbar(self, variable=self.progress_value, maximum=100, mode="determinate")
        self.progress.grid(row=12, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        ttk.Label(self, textvariable=self.status).grid(row=13, column=0, columnspan=3, sticky="w", pady=(0, 4))
        self.log = tk.Text(self, height=14, wrap="word", state="disabled", font=("Cascadia Mono", 9))
        self.log.grid(row=14, column=0, columnspan=3, sticky="nsew")
        self.rowconfigure(14, weight=1)

    def _update_contact_controls(self) -> None:
        enabled = self.plate_node_contact.get() or self.fiber_node_contact.get()
        self.ball_instance_combo.configure(state="readonly" if enabled and self._instance_names else "disabled")
        self.contact_thickness_entry.configure(state="normal" if enabled else "disabled")
        self.ball_interaction_combo.configure(state='readonly' if enabled and self.plywise.get() else 'disabled')
        if enabled and not self.ball_instance.get() and self._instance_names:
            candidates = [n for n in self._instance_names if n != self.instance.get()]
            self.ball_instance.set(candidates[0] if candidates else self._instance_names[0])

    def _path_row(self, row: int, label: str, value: tk.StringVar, command, button: str) -> None:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=value).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(self, text=button, command=command).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=4)

    def _entry_row(self, row: int, label: str, value: tk.StringVar, hint: str) -> None:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=value).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(self, text=hint).grid(row=row, column=2, sticky="w", padx=(8, 0))

    def choose_deck(self) -> None:
        name = filedialog.askopenfilename(title="Select Abaqus input deck", filetypes=[("Abaqus input decks", "*.inp"), ("All files", "*.*")])
        if name:
            self.deck.set(name)
            if not self.output.get():
                self.output.set(str(Path(name).with_suffix("")) + "-embmesh")
            self.load_instances(Path(name))

    def load_instances(self, deck: Path) -> None:
        """Run the lightweight parser without blocking the desktop interface."""
        try:
            self._interactions = list_surface_interactions(deck)
        except OSError as exc:
            self._interactions = []
            self.append_log(f'Could not read surface interactions: {exc}\n')
        interaction_names = [name for name, _ in self._interactions]
        noncohesive = [name for name, is_cohesive in self._interactions if not is_cohesive]
        self.cohesion_combo.configure(values=interaction_names, state='readonly' if interaction_names else 'disabled')
        self.cohesion_interaction.set('Cohesion' if 'Cohesion' in interaction_names else
                                      (interaction_names[0] if interaction_names else ''))
        self.cohesion_check.configure(state='normal')
        self.cohesion_help.set('' if interaction_names else 'No *Surface Interaction in this deck; select a preset to generate one.')
        self.ball_interaction_combo.configure(values=['automatic'] + noncohesive)
        self.ball_interaction.set('automatic')
        self.instance.set("")
        self.instance_combo.configure(values=(), state="disabled")
        self._instance_names = []
        self.ball_instance.set("")
        self._update_contact_controls()
        self._refresh_layup()
        self._update_cohesive_controls()
        self.status.set("Reading assembly instances from input deck…")
        try:
            command = [str(engine_path()), "list", str(deck)]
        except FileNotFoundError as exc:
            self.status.set("Could not find the bundled mesher executable.")
            self.append_log(f"{exc}\n")
            return
        threading.Thread(target=self._instance_worker, args=(deck, command), daemon=True).start()

    def _instance_worker(self, deck: Path, command: list[str]) -> None:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        self.master.after(0, self._instances_loaded, deck, result.returncode,
                          (result.stdout or "") + (result.stderr or ""))

    def _instances_loaded(self, deck: Path, returncode: int, output: str) -> None:
        # A user may select a different deck while this parse is running.
        if Path(self.deck.get()).expanduser() != deck:
            return
        names = instance_names(output) if returncode == 0 else []
        self._instance_names = names
        if names:
            self.instance_combo.configure(values=names, state="readonly")
            self.instance.set(names[0])
            self._update_contact_controls()
            self._update_cohesive_readout()
            self.status.set(f"Found {len(names)} assembly instance(s).")
        else:
            self.instance_combo.configure(values=(), state="disabled")
            self.status.set("No assembly instances found in the selected deck.")
            if output:
                self.append_log(output + ("\n" if not output.endswith("\n") else ""))

    def choose_output(self) -> None:
        name = filedialog.askdirectory(title="Select output folder")
        if name:
            self.output.set(name)

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def run_mesh(self) -> None:
        try:
            if self.plywise.get():
                values = dict(engine=str(engine_path()), deck=self.deck.get(), instance=self.instance.get(),
                              output=self.output.get(), plies=self.plies.get() if self.ply_mode.get() == 'plies' else '',
                              ply_thickness=self.ply_thickness.get() if self.ply_mode.get() == 'thickness' else '',
                              layup=self.layup.get(), layup_symmetric=self.layup_symmetric.get(),
                              layup_repeat=self.layup_repeat.get(), fiber_diameter=self.diameter.get(),
                              fiber_gap=self.gap.get(), fiber_type=self.fiber_type.get(),
                              fiber_material=self.fiber_material.get(), thickness_axis=self.thickness_axis.get(),
                              cohesion=self.cohesion.get(), cohesion_interaction=self.cohesion_interaction.get(),
                              cohesive_material=self.cohesive_material.get(),
                              cohesive_rate=self.cohesive_rate.get(),
                              length_units=self.length_units.get(),
                              cohesive_name=self.cohesive_name.get(),
                              collapse_layers=self.collapse_layers.get(),
                              host_mode=self.host_mode.get(),
                              ghost_scale=self.ghost_scale.get(),
                              plate_node_contact=self.plate_node_contact.get(),
                              fiber_node_contact=self.fiber_node_contact.get(), ball_instance=self.ball_instance.get(),
                              contact_thickness=self.contact_thickness.get(), ball_interaction=self.ball_interaction.get())
                if values['layup'] and self.ply_mode.get() == 'thickness':
                    values['resolved_plies'] = self._resolved_ply_count()
                command = build_plywise_command(values)
                self._start_command(command, True)
                return
            deck = Path(self.deck.get()).expanduser()
            if not deck.is_file():
                raise ValueError("Choose an existing .inp deck.")
            if not self.instance.get().strip():
                raise ValueError("Select an assembly instance from the input deck.")
            if float(self.diameter.get()) <= 0:
                raise ValueError("Fiber diameter must be positive.")
            if float(self.gap.get()) < 0:
                raise ValueError("In-plane gap cannot be negative.")
            if not self.output.get().strip():
                raise ValueError("Choose an output folder.")
            output = Path(self.output.get()).expanduser()
            command = [str(engine_path()), "visualize", str(deck), "--instance", self.instance.get().strip(),
                       "--diameter", self.diameter.get(), "--output", str(output), "--gap", self.gap.get(),
                       "--fiber-type", self.fiber_type.get(), "--preview"]
            if self.thickness_axis.get().strip():
                command += ["--thickness-axis", self.thickness_axis.get().strip()]
            if self.precise_volume.get():
                command.append("--precise-volume")
            if self.plate_node_contact.get() or self.fiber_node_contact.get():
                if not self.ball_instance.get().strip():
                    raise ValueError("Select a ball instance when ball contact is enabled.")
                thickness = self.contact_thickness.get().strip()
                if thickness.lower() != "auto":
                    if float(thickness) < 0:
                        raise ValueError("Contact thickness must be non-negative or 'auto'.")
                if self.plate_node_contact.get():
                    command.append("--plate-node-contact")
                if self.fiber_node_contact.get():
                    command.append("--fiber-node-contact")
                command += ["--ball-instance", self.ball_instance.get().strip(),
                            "--contact-thickness", thickness]
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror("Cannot generate mesh", str(exc), parent=self.master)
            return
        self._start_command(command, False)

    def _start_command(self, command: list[str], plywise: bool) -> None:
        self._running_plywise = plywise
        self.run_button.configure(state="disabled")
        self.preview_button.configure(state="disabled")
        self.progress_value.set(0)
        self.status.set("Generating plywise laminate…" if plywise else "Generating embedded mesh…")
        self.append_log("\n> " + subprocess.list2cmdline(command) + "\n")
        threading.Thread(target=self._worker, args=(command,), daemon=True).start()

    def _worker(self, command: list[str]) -> None:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors="replace")
        output = []
        assert process.stdout is not None
        for line in process.stdout:
            output.append(line)
            self.master.after(0, self._output_line, line)
        self.master.after(0, self._finished, process.wait(), "".join(output))

    def _output_line(self, line: str) -> None:
        if line.startswith("PROGRESS "):
            _, percent, message = line.rstrip("\r\n").split(" ", 2)
            self.progress_value.set(float(percent))
            self.status.set(message)
        else:
            self.append_log(line)

    def _finished(self, returncode: int, text: str) -> None:
        self.run_button.configure(state="normal")
        if returncode == 0:
            self.progress_value.set(100)
            self.preview_button.configure(state="normal")
            if self._running_plywise:
                try:
                    report = json.loads((Path(self.output.get()).expanduser() / 'report.json').read_text())
                    self.append_log(f"Resulting ply thickness: {report.get('resulting_ply_thickness')}\n")
                    for warning in report.get('warnings', []):
                        self.append_log(f'Warning: {warning}\n')
                    for reference in report.get('dangling_impact_references', []):
                        self.append_log(f'Dangling impact reference: {reference}\n')
                    self.status.set(f"Done. Ply thickness: {report.get('resulting_ply_thickness')}; "
                                    f"warnings: {len(report.get('warnings', []))}; "
                                    f"dangling references: {len(report.get('dangling_impact_references', []))}.")
                except (OSError, ValueError) as exc:
                    self.status.set('Done. Could not read plywise report; see log.')
                    self.append_log(f'Could not read report: {exc}\n')
            else:
                self.status.set("Done. View fiber embedding or open the output folder.")
            messagebox.showinfo("Embedded mesh created", "Meshing completed successfully.", parent=self.master)
        else:
            self.status.set(f"Meshing failed (exit code {returncode}). See the log below.")
            messagebox.showerror("Meshing failed", "The mesher reported an error. See the log below.", parent=self.master)

    def open_output(self) -> None:
        folder = Path(self.output.get()).expanduser()
        if not folder.is_dir():
            messagebox.showwarning("Output folder unavailable", "Generate a mesh first, or choose an existing output folder.", parent=self.master)
            return
        os.startfile(folder)  # Windows desktop app

    def open_preview(self) -> None:
        preview = Path(self.output.get()).expanduser() / "preview.html"
        if not preview.is_file():
            messagebox.showwarning("Preview unavailable", "Generate a mesh before opening its embedding preview.", parent=self.master)
            return
        os.startfile(preview)  # opens in the default browser; drag to rotate, scroll to zoom


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
