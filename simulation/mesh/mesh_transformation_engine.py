"""Vertex-level mesh transformation operations for Phase 8."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import numpy as np


def unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return np.array([0.0, 1.0, 0.0], dtype=float)
    return vector / norm


def rotation_matrix(axis: np.ndarray, angle_degrees: float) -> np.ndarray:
    axis = unit(axis)
    angle = math.radians(angle_degrees)
    x, y, z = axis
    c = math.cos(angle)
    s = math.sin(angle)
    return np.array(
        [
            [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
            [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
            [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
        ]
    )


class MeshTransformationEngine:
    """Apply deterministic vertex transforms to mesh dictionaries."""

    def __init__(self, meshes: dict[str, dict[str, Any]]) -> None:
        self.meshes = deepcopy(meshes)
        self.history: list[dict[str, Any]] = []

    def translate_mesh(self, structure_name: str, translation: list[float]) -> None:
        vector = np.asarray(translation, dtype=float)
        before = self.meshes[structure_name]["vertices"].copy()
        self.meshes[structure_name]["vertices"] = before + vector
        self._record(structure_name, "translate_mesh", before, self.meshes[structure_name]["vertices"], {"translation": translation})

    def rotate_mesh(self, structure_name: str, axis: list[float], angle_degrees: float) -> None:
        vertices = self.meshes[structure_name]["vertices"]
        center = vertices.mean(axis=0)
        matrix = rotation_matrix(np.asarray(axis, dtype=float), angle_degrees)
        before = vertices.copy()
        self.meshes[structure_name]["vertices"] = (vertices - center) @ matrix.T + center
        self._record(structure_name, "rotate_mesh", before, self.meshes[structure_name]["vertices"], {"axis": axis, "angle_degrees": angle_degrees})

    def scale_mesh(self, structure_name: str, scale: list[float] | float) -> None:
        vertices = self.meshes[structure_name]["vertices"]
        center = vertices.mean(axis=0)
        factors = np.asarray(scale if isinstance(scale, list) else [scale, scale, scale], dtype=float)
        before = vertices.copy()
        self.meshes[structure_name]["vertices"] = (vertices - center) * factors + center
        self._record(structure_name, "scale_mesh", before, self.meshes[structure_name]["vertices"], {"scale": factors.tolist()})

    def expand_disc_height(self, disc_name: str, percent: float, neighbor_names: list[str]) -> None:
        self._scale_disc_along_minor_axis(disc_name, 1.0 + percent / 100.0, neighbor_names, "expand_disc_height", percent)

    def compress_disc_height(self, disc_name: str, percent: float, neighbor_names: list[str]) -> None:
        self._scale_disc_along_minor_axis(disc_name, max(0.01, 1.0 - percent / 100.0), neighbor_names, "compress_disc_height", percent)

    def apply_local_alignment_change(self, structure_name: str, axis: list[float], angle_degrees: float) -> None:
        self.rotate_mesh(structure_name, axis, angle_degrees)
        self.history[-1]["operation"] = "apply_local_alignment_change"

    def _scale_disc_along_minor_axis(
        self, disc_name: str, factor: float, neighbor_names: list[str], operation: str, percent: float
    ) -> None:
        vertices = self.meshes[disc_name]["vertices"]
        center = vertices.mean(axis=0)
        axis = self._minor_axis(vertices)
        before = vertices.copy()
        offsets = vertices - center
        axial = offsets @ axis
        radial = offsets - np.outer(axial, axis)
        self.meshes[disc_name]["vertices"] = center + radial + np.outer(axial * factor, axis)
        self._record(disc_name, operation, before, self.meshes[disc_name]["vertices"], {"percent": percent, "scale_factor": factor, "axis": axis.tolist()})

        delta = (self._height(before, axis) * factor - self._height(before, axis)) / 2.0
        if len(neighbor_names) >= 2:
            self.translate_mesh(neighbor_names[0], (-axis * delta).tolist())
            self.translate_mesh(neighbor_names[1], (axis * delta).tolist())

    def _minor_axis(self, vertices: np.ndarray) -> np.ndarray:
        centered = vertices - vertices.mean(axis=0)
        values, vectors = np.linalg.eigh(np.cov(centered.T))
        return unit(vectors[:, np.argsort(values)[0]])

    def _height(self, vertices: np.ndarray, axis: np.ndarray) -> float:
        projection = vertices @ axis
        return float(projection.max() - projection.min())

    def _record(self, name: str, operation: str, before: np.ndarray, after: np.ndarray, parameters: dict[str, Any]) -> None:
        displacement = np.linalg.norm(after - before, axis=1)
        self.history.append(
            {
                "structure_name": name,
                "operation": operation,
                "parameters": parameters,
                "vertices_moved": int(np.count_nonzero(displacement > 1e-9)),
                "average_displacement": float(displacement.mean()) if displacement.size else 0.0,
                "max_displacement": float(displacement.max()) if displacement.size else 0.0,
            }
        )
