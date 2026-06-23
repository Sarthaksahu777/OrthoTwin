"""Geometry-first anatomical modification engine for Phase 7.

Operations modify surgical geometry objects and graph relationships first.
Downstream metrics are rebuilt later by state_rebuilder.py.
"""

from __future__ import annotations

import math
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from OrthoTwin.simulation.surgery.surgical_objects import build_surgical_objects


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def vector(a: list[float], b: list[float]) -> list[float]:
    return [float(b[i]) - float(a[i]) for i in range(3)]


def add(a: list[float], b: list[float]) -> list[float]:
    return [float(a[i]) + float(b[i]) for i in range(3)]


def scale(v: list[float], factor: float) -> list[float]:
    return [float(item) * factor for item in v]


def length(v: list[float]) -> float:
    return math.sqrt(sum(float(item) ** 2 for item in v))


def unit(v: list[float]) -> list[float]:
    norm = length(v)
    if norm == 0:
        return [0.0, 1.0, 0.0]
    return [float(item) / norm for item in v]


def midpoint(a: list[float], b: list[float]) -> list[float]:
    return [(float(a[i]) + float(b[i])) / 2.0 for i in range(3)]


class AnatomicalModificationEngine:
    """Apply deterministic anatomy edits to a surgical object state."""

    def __init__(self, surgical_state: dict[str, Any] | None = None) -> None:
        self.state = deepcopy(surgical_state or build_surgical_objects())
        self.objects = self.state["objects"]
        self.graph = self.state["graph_state"]
        self.history = self.state.setdefault("modification_history", [])

    def restore_disc_height(self, disc_id: str, restoration_percent: float) -> dict[str, Any]:
        old_height = self._disc_height(disc_id)
        new_height = old_height * (1.0 + restoration_percent / 100.0)
        return self._set_disc_height(
            disc_id,
            new_height,
            "restore_disc_height",
            {"restoration_percent": restoration_percent},
        )

    def collapse_disc(self, disc_id: str, collapse_percent: float) -> dict[str, Any]:
        old_height = self._disc_height(disc_id)
        new_height = old_height * (1.0 - collapse_percent / 100.0)
        return self._set_disc_height(
            disc_id,
            new_height,
            "collapse_disc",
            {"collapse_percent": collapse_percent},
        )

    def insert_implant(self, disc_id: str, implant_height: float) -> dict[str, Any]:
        result = self._set_disc_height(
            disc_id,
            implant_height,
            "insert_implant",
            {"implant_height": implant_height},
        )
        implant_id = f"implant_{disc_id}"
        self.objects[implant_id] = {
            "id": implant_id,
            "object_type": "Implant",
            "geometry": {
                "centroid": deepcopy(self.objects[disc_id]["geometry"].get("centroid")),
                "height": implant_height,
                "occupies_disc_space": disc_id,
            },
            "relationships": {
                "target_disc": disc_id,
                "attached_to": deepcopy(self.objects[disc_id]["relationships"].get("neighbors", [])),
            },
            "measurements": {"implant_height": implant_height},
            "constraints": {
                "maintain_disc_space": True,
                "material_model": "placeholder_not_physical",
            },
        }
        result["created_objects"].append(implant_id)
        return self._snapshot(result)

    def insert_spacer(self, disc_id: str, expansion_percent: float) -> dict[str, Any]:
        old_height = self._disc_height(disc_id)
        spacer_height = old_height * (1.0 + expansion_percent / 100.0)
        result = self._set_disc_height(
            disc_id,
            spacer_height,
            "insert_spacer",
            {"expansion_percent": expansion_percent, "spacer_height": spacer_height},
        )
        spacer_id = f"spacer_{disc_id}"
        self.objects[spacer_id] = {
            "id": spacer_id,
            "object_type": "Spacer",
            "geometry": {
                "centroid": deepcopy(self.objects[disc_id]["geometry"].get("centroid")),
                "height": spacer_height,
                "occupies_disc_space": disc_id,
            },
            "relationships": {
                "target_disc": disc_id,
                "attached_to": deepcopy(self.objects[disc_id]["relationships"].get("neighbors", [])),
            },
            "measurements": {"spacer_height": spacer_height},
            "constraints": {
                "maintain_spacing": True,
                "material_model": "placeholder_not_physical",
            },
        }
        result["created_objects"].append(spacer_id)
        return self._snapshot(result)

    def translate_vertebra(self, vertebra_id: str, translation: list[float]) -> dict[str, Any]:
        obj = self._object(vertebra_id)
        old_centroid = deepcopy(obj["geometry"]["centroid"])
        obj["geometry"]["centroid"] = add(old_centroid, translation)
        self.graph["nodes"][vertebra_id]["centroid"] = deepcopy(obj["geometry"]["centroid"])
        result = {
            "operation": "translate_vertebra",
            "target": vertebra_id,
            "parameters": {"translation": translation},
            "geometry_changes": [
                {
                    "object_id": vertebra_id,
                    "field": "centroid",
                    "before": old_centroid,
                    "after": deepcopy(obj["geometry"]["centroid"]),
                }
            ],
            "relationship_changes": [],
            "created_objects": [],
        }
        return self._snapshot(result)

    def apply_fusion(self, vertebra_a: str, vertebra_b: str) -> dict[str, Any]:
        common_discs = sorted(
            set(self.graph["nodes"][vertebra_a].get("neighbors", []))
            & set(self.graph["nodes"][vertebra_b].get("neighbors", []))
        )
        fused_disc = common_discs[0] if common_discs else None
        fusion_id = f"fusion_{vertebra_a}_{vertebra_b}"
        self.objects[fusion_id] = {
            "id": fusion_id,
            "object_type": "FusionSegment",
            "geometry": {
                "vertebra_a_centroid": deepcopy(self.objects[vertebra_a]["geometry"]["centroid"]),
                "vertebra_b_centroid": deepcopy(self.objects[vertebra_b]["geometry"]["centroid"]),
                "motion_segment_removed": fused_disc,
            },
            "relationships": {
                "vertebra_a": vertebra_a,
                "vertebra_b": vertebra_b,
                "fused_disc": fused_disc,
            },
            "measurements": {"segment_distance": length(vector(self.objects[vertebra_a]["geometry"]["centroid"], self.objects[vertebra_b]["geometry"]["centroid"]))},
            "constraints": {"relative_motion_locked": True, "load_transfer_path": "direct_bridge_proxy"},
        }
        for node_id in (vertebra_a, vertebra_b):
            self.objects[node_id]["constraints"]["fused_with"] = vertebra_b if node_id == vertebra_a else vertebra_a
        self.graph.setdefault("edges", []).append(
            {
                "source": vertebra_a,
                "target": vertebra_b,
                "edge_type": "fusion_lock_geometry",
                "motion_segment_removed": fused_disc,
            }
        )
        result = {
            "operation": "apply_fusion",
            "target": fusion_id,
            "parameters": {"vertebra_a": vertebra_a, "vertebra_b": vertebra_b},
            "geometry_changes": [],
            "relationship_changes": [
                {"type": "fusion_lock_added", "vertebra_a": vertebra_a, "vertebra_b": vertebra_b, "fused_disc": fused_disc}
            ],
            "created_objects": [fusion_id],
        }
        return self._snapshot(result)

    def correct_alignment(self, vertebra_id: str, correction_vector: list[float]) -> dict[str, Any]:
        result = self.translate_vertebra(vertebra_id, correction_vector)
        correction_id = f"alignment_correction_{vertebra_id}"
        self.objects[correction_id] = {
            "id": correction_id,
            "object_type": "AlignmentCorrection",
            "geometry": {"correction_vector": correction_vector},
            "relationships": {"target_vertebra": vertebra_id},
            "measurements": {"translation_magnitude": length(correction_vector)},
            "constraints": {"geometric_correction_only": True},
        }
        result["operation"] = "correct_alignment"
        result["created_objects"].append(correction_id)
        return self._snapshot(result)

    def _set_disc_height(
        self, disc_id: str, new_height: float, operation: str, parameters: dict[str, Any]
    ) -> dict[str, Any]:
        disc = self._object(disc_id)
        old_height = self._disc_height(disc_id)
        neighbors = [
            node_id
            for node_id in disc["relationships"].get("neighbors", [])
            if node_id in self.objects and self.objects[node_id]["object_type"] == "Vertebra"
        ]
        geometry_changes = [
            {
                "object_id": disc_id,
                "field": "height",
                "before": old_height,
                "after": new_height,
            }
        ]
        delta = new_height - old_height
        if len(neighbors) >= 2:
            a, b = neighbors[:2]
            ca = self.objects[a]["geometry"]["centroid"]
            cb = self.objects[b]["geometry"]["centroid"]
            axis = unit(vector(ca, cb))
            self._move_vertebra(a, scale(axis, -delta / 2.0), geometry_changes)
            self._move_vertebra(b, scale(axis, delta / 2.0), geometry_changes)
            disc["geometry"]["centroid"] = midpoint(
                self.objects[a]["geometry"]["centroid"],
                self.objects[b]["geometry"]["centroid"],
            )
            geometry_changes.append(
                {
                    "object_id": disc_id,
                    "field": "centroid",
                    "before": None,
                    "after": deepcopy(disc["geometry"]["centroid"]),
                }
            )
        disc["geometry"]["height"] = new_height
        disc["measurements"]["mean_height"] = new_height
        disc["constraints"]["height_modified_by_geometry_operation"] = True
        result = {
            "operation": operation,
            "target": disc_id,
            "parameters": parameters,
            "geometry_changes": geometry_changes,
            "relationship_changes": [
                {"type": "local_spacing_rebuilt", "disc": disc_id, "neighbors": neighbors}
            ],
            "created_objects": [],
        }
        return self._snapshot(result)

    def _move_vertebra(self, vertebra_id: str, translation: list[float], changes: list[dict[str, Any]]) -> None:
        obj = self.objects[vertebra_id]
        old = deepcopy(obj["geometry"]["centroid"])
        obj["geometry"]["centroid"] = add(old, translation)
        self.graph["nodes"][vertebra_id]["centroid"] = deepcopy(obj["geometry"]["centroid"])
        changes.append({"object_id": vertebra_id, "field": "centroid", "before": old, "after": deepcopy(obj["geometry"]["centroid"])})

    def _disc_height(self, disc_id: str) -> float:
        disc = self._object(disc_id)
        height = disc["geometry"].get("height")
        if height is None:
            raise ValueError(f"Disc {disc_id} does not have a height value.")
        return float(height)

    def _object(self, object_id: str) -> dict[str, Any]:
        if object_id not in self.objects:
            raise KeyError(f"Unknown surgical object: {object_id}")
        return self.objects[object_id]

    def _snapshot(self, result: dict[str, Any]) -> dict[str, Any]:
        result["generated_utc"] = utc_now()
        result["not_medical_advice"] = True
        self.history.append({k: v for k, v in result.items() if k != "surgical_state"})
        result["surgical_state"] = deepcopy(self.state)
        return result
