"""Rebuild clinical and graph metrics from modified surgical geometry."""

from __future__ import annotations

import json
import math
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_CLINICAL_STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json"
BASE_STATE_V2_PATH = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector_v2.json"
OUTPUT_DIR = PROJECT_ROOT / "state" / "surgery"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def vector(a: list[float], b: list[float]) -> list[float]:
    return [float(b[i]) - float(a[i]) for i in range(3)]


def angle_between(v1: list[float], v2: list[float]) -> float:
    n1 = math.sqrt(sum(item * item for item in v1))
    n2 = math.sqrt(sum(item * item for item in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    dot = sum(v1[i] * v2[i] for i in range(3)) / (n1 * n2)
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def rebuild_state(
    surgical_result: dict[str, Any],
    scenario_id: str = "rebuilt_state",
    output_path: Path | None = None,
) -> dict[str, Any]:
    base_clinical = load_json(BASE_CLINICAL_STATE_PATH)
    base_state_v2 = load_json(BASE_STATE_V2_PATH)
    surgical_state = surgical_result["surgical_state"]
    objects = surgical_state["objects"]
    graph = surgical_state["graph_state"]
    clinical = deepcopy(base_clinical)

    disc_ids = [node_id for node_id, node in graph.get("nodes", {}).items() if node.get("node_type") == "disc"]
    vertebra_ids = [
        node_id
        for node_id, node in graph.get("nodes", {}).items()
        if node.get("node_type", "").startswith("vertebra") and node_id in objects
    ]
    vertebra_ids.sort(key=lambda node_id: graph["nodes"][node_id].get("position_index", 0))

    spacing = {}
    for disc_id in disc_ids:
        disc = objects[disc_id]
        height = float(disc["geometry"].get("height") or 0.0)
        if disc_id in clinical.get("disc_heights", {}):
            old = clinical["disc_heights"][disc_id]
            original_mean_height = old.get("mean_height", height)
            ratio = safe_ratio(height, original_mean_height)
            for field in ("mean_height", "maximum_height", "minimum_height", "anterior_height", "posterior_height", "left_height", "right_height"):
                if isinstance(old.get(field), (int, float)):
                    old[field] = height if field == "mean_height" else old[field] * ratio
            old["recomputed_from_geometry"] = True
        neighbors = [n for n in disc["relationships"].get("neighbors", []) if n in objects]
        spacing[disc_id] = {
            "disc_height": height,
            "neighbor_distances": {
                neighbor: distance(disc["geometry"]["centroid"], objects[neighbor]["geometry"]["centroid"])
                for neighbor in neighbors
            },
        }

    alignment = {"patient_id": clinical.get("patient_id", "patient_alpha"), "vertebral_pair_alignment": {}, "disc_alignment": {}}
    for disc_id in disc_ids:
        neighbors = [n for n in objects[disc_id]["relationships"].get("neighbors", []) if n in objects and objects[n]["object_type"] == "Vertebra"]
        if len(neighbors) >= 2:
            a, b = neighbors[:2]
            segment = vector(objects[a]["geometry"]["centroid"], objects[b]["geometry"]["centroid"])
            disc_angle = angle_between(segment, [0.0, 1.0, 0.0])
            disc_tilt = math.degrees(math.atan2(segment[0], segment[1] if segment[1] else 1e-9))
            alignment["disc_alignment"][disc_id] = {
                "disc_name": clinical.get("disc_heights", {}).get(disc_id, {}).get("disc_name", disc_id),
                "disc_angle_degrees": disc_angle,
                "disc_tilt_degrees": disc_tilt,
                "recomputed_from_geometry": True,
            }
            key = f"{a}__{b}"
            alignment["vertebral_pair_alignment"][key] = {
                "above": a,
                "below": b,
                "angle_difference_degrees": disc_angle,
                "tilt_difference_degrees": abs(disc_tilt),
                "orientation_difference_degrees": disc_angle + abs(disc_tilt) * 0.1,
                "recomputed_from_geometry": True,
            }
    clinical["alignment"] = alignment

    slippage = {}
    for first, second in zip(vertebra_ids, vertebra_ids[1:]):
        a = objects[first]["geometry"]["centroid"]
        b = objects[second]["geometry"]["centroid"]
        displacement = float(b[0]) - float(a[0])
        width_proxy = max(1.0, abs(float(b[1]) - float(a[1])))
        slippage[f"{first}__{second}"] = {
            "from": first,
            "to": second,
            "relative_anterior_posterior_displacement": displacement,
            "percent_of_average_vertebral_width": displacement / width_proxy * 100.0,
            "not_diagnosis": True,
            "method": "geometry_rebuild_centroid_projection_proxy",
            "units": "voxel units / percent",
            "recomputed_from_geometry": True,
        }
    clinical["slippage"] = slippage

    curvature = rebuild_curvature(vertebra_ids, objects)
    clinical["curvature"] = curvature

    load_distribution = rebuild_load_distribution(base_state_v2, clinical, graph, objects)

    rebuilt = {
        "patient_id": clinical.get("patient_id", "patient_alpha"),
        "schema_version": "geometry_aware_rebuilt_state_v1",
        "generated_utc": utc_now(),
        "scenario_id": scenario_id,
        "source_operation": surgical_result.get("operation"),
        "surgical_geometry": surgical_state,
        "clinical_state": clinical,
        "graph_state": graph,
        "relative_spacing": spacing,
        "alignment": alignment,
        "slippage": slippage,
        "curvature": curvature,
        "load_distribution": load_distribution,
        "rebuild_policy": "metrics recomputed from modified surgical geometry proxies",
        "not_medical_advice": True,
        "clinical_validity_claim": "none",
    }
    if output_path:
        write_json(output_path, rebuilt)
    return rebuilt


def safe_ratio(new_value: float, old_value: Any) -> float:
    if not isinstance(old_value, (int, float)) or old_value == 0:
        return 1.0
    return float(new_value) / float(old_value)


def rebuild_curvature(vertebra_ids: list[str], objects: dict[str, Any]) -> dict[str, Any]:
    local = []
    total_length = 0.0
    for first, second in zip(vertebra_ids, vertebra_ids[1:]):
        total_length += distance(objects[first]["geometry"]["centroid"], objects[second]["geometry"]["centroid"])
    for prev_id, node_id, next_id in zip(vertebra_ids, vertebra_ids[1:], vertebra_ids[2:]):
        v1 = vector(objects[node_id]["geometry"]["centroid"], objects[prev_id]["geometry"]["centroid"])
        v2 = vector(objects[node_id]["geometry"]["centroid"], objects[next_id]["geometry"]["centroid"])
        angle = angle_between(v1, v2)
        segment_length = max(1.0, (distance(objects[prev_id]["geometry"]["centroid"], objects[node_id]["geometry"]["centroid"]) + distance(objects[node_id]["geometry"]["centroid"], objects[next_id]["geometry"]["centroid"])) / 2.0)
        local.append({"at_node": node_id, "angle_degrees": angle, "curvature_estimate": angle / segment_length, "recomputed_from_geometry": True})
    return {
        "generated_utc": utc_now(),
        "global_curvature": mean([item["curvature_estimate"] for item in local]),
        "maximum_local_curvature": max([item["curvature_estimate"] for item in local] or [0.0]),
        "local_curvature": local,
        "curvature_peaks": sorted(local, key=lambda item: item["curvature_estimate"], reverse=True)[:3],
        "centerline_length": total_length,
        "method": "geometry_rebuild_centroid_angle_change",
    }


def rebuild_load_distribution(
    base_state_v2: dict[str, Any],
    clinical: dict[str, Any],
    graph: dict[str, Any],
    objects: dict[str, Any],
) -> dict[str, Any]:
    disc_heights = {
        disc_id: float(values.get("mean_height", 0.0))
        for disc_id, values in clinical.get("disc_heights", {}).items()
    }
    average_height = mean(list(disc_heights.values()))
    structures = {}
    for node_id, node in graph.get("nodes", {}).items():
        base_record = base_state_v2.get("load_metrics", {}).get("structures", {}).get(node_id, {})
        if node.get("node_type") == "disc":
            h = disc_heights.get(node_id, average_height)
            height_factor = (average_height - h) / average_height if average_height else 0.0
            tilt = abs(clinical.get("alignment", {}).get("disc_alignment", {}).get(node_id, {}).get("disc_tilt_degrees", 0.0))
            relative_load = max(0.0, 1.0 + height_factor * 1.2 + tilt / 360.0 * 0.1)
        else:
            neighbor_loads = [
                structures[n]["relative_load_index"]
                for n in node.get("neighbors", [])
                if n in structures and graph.get("nodes", {}).get(n, {}).get("node_type") == "disc"
            ]
            relative_load = mean(neighbor_loads) if neighbor_loads else float(base_record.get("relative_load_index", 1.0))
            if objects.get(node_id, {}).get("constraints", {}).get("fused_with"):
                relative_load *= 1.08
        stress = max(0.0, min(1.0, relative_load * 0.14))
        structures[node_id] = {
            "structure_name": node.get("name", node_id),
            "structure_type": node.get("node_type"),
            "relative_load_index": relative_load,
            "stress_score": stress,
            "risk_score": max(0.0, min(1.0, stress * relative_load)),
            "method": "geometry_rebuild_load_proxy",
        }
    return {
        "patient_id": clinical.get("patient_id", "patient_alpha"),
        "model_type": "geometry_recomputed_load_proxy_v1",
        "physics_claim": "Not physics; deterministic load proxy recomputed after anatomy changes.",
        "structures": structures,
    }


def main() -> None:
    from OrthoTwin.simulation.surgery.anatomical_modification_engine import AnatomicalModificationEngine

    engine = AnatomicalModificationEngine()
    result = engine.insert_implant("disc_6_206_207", 18.0)
    rebuilt = rebuild_state(result, "rebuilt_state_demo", OUTPUT_DIR / "rebuilt_state.json")
    print(f"Rebuilt state generated with {len(rebuilt['relative_spacing'])} disc spacing records.")


if __name__ == "__main__":
    main()
