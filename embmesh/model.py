from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np


@dataclass
class Element:
    label: int
    connectivity: tuple[int, ...]
    type: str = ""
    elset: str | None = None


@dataclass
class Part:
    name: str
    nodes: dict[int, np.ndarray] = field(default_factory=dict)
    elements: dict[int, Element] = field(default_factory=dict)
    nsets: dict[str, set[int]] = field(default_factory=dict)
    elsets: dict[str, set[int]] = field(default_factory=dict)
    surfaces: dict[str, list[tuple[int, str]]] = field(default_factory=dict)
    raw_keywords: list[str] = field(default_factory=list)

    def bbox(self) -> tuple[np.ndarray, np.ndarray]:
        if not self.nodes:
            z = np.zeros(3)
            return z.copy(), z.copy()
        a = np.asarray(list(self.nodes.values()), float)
        return a.min(axis=0), a.max(axis=0)


@dataclass
class Instance:
    name: str
    part: str
    translation: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation_axis: np.ndarray = field(default_factory=lambda: np.array([0.0, 0.0, 1.0]))
    rotation_origin: np.ndarray = field(default_factory=lambda: np.zeros(3))
    rotation_angle: float = 0.0

    def transform(self, points: np.ndarray) -> np.ndarray:
        # Abaqus *Instance positioning: the part is translated into the assembly first,
        # then (optionally) rotated about an axis whose point coordinates are given in
        # that already-translated (global/assembly) frame -- NOT rotated in the
        # part-local frame and translated afterward. See docs/BUGS.md BUG-003.
        p = np.asarray(points, dtype=float) + self.translation
        if abs(self.rotation_angle) > 0:
            a = self.rotation_axis / np.linalg.norm(self.rotation_axis)
            t = np.deg2rad(self.rotation_angle)
            K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
            R = np.eye(3) * np.cos(t) + (1 - np.cos(t)) * np.outer(a, a) + np.sin(t) * K
            p = (p - self.rotation_origin) @ R.T + self.rotation_origin
        return p


@dataclass
class Deck:
    parts: dict[str, Part] = field(default_factory=dict)
    instances: dict[str, Instance] = field(default_factory=dict)
    original_lines: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)

    def instance_nodes(self, name: str) -> dict[int, np.ndarray]:
        inst = self.instances[name]
        part = self.parts[inst.part]
        return {k: inst.transform(v) for k, v in part.nodes.items()}

