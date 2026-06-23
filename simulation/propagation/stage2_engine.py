"""Stage 2 spine state representation engine.

This module converts existing patient state measurements into a connected
digital spine representation. It does not retrain models, run inference,
recompute segmentation, or alter masks.
"""

from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector.json"
STAGE2_DIR = PROJECT_ROOT / "stage2"
FIGURE_DIR = STAGE2_DIR / "figures"


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _pyplot():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _vector(a: list[float], b: list[float]) -> list[float]:
    return [float(b[i]) - float(a[i]) for i in range(3)]


def _distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


def _dot(a: list[float], b: list[float]) -> float:
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _norm(v: list[float]) -> float:
    return math.sqrt(sum(float(x) ** 2 for x in v))


def _unit(v: list[float]) -> list[float]:
    length = _norm(v)
    if length == 0:
        return [0.0, 0.0, 0.0]
    return [float(x) / length for x in v]


def _angle_between(a: list[float], b: list[float]) -> float:
    denom = _norm(a) * _norm(b)
    if denom == 0:
        return 0.0
    cosine = max(-1.0, min(1.0, _dot(a, b) / denom))
    return math.degrees(math.acos(cosine))


def _safe_ratio(value: float | None, reference: float | None) -> float | None:
    if value is None or reference in (None, 0):
        return None
    return float(value) / float(reference)


def _structure_number(name: str) -> int | None:
    digits = ""
    for char in name:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return int(digits) if digits else None


def _sorted_structures(items: dict[str, dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        items.items(),
        key=lambda pair: (
            _structure_number(pair[1].get("name", "")) or pair[1].get("class_id", 999),
            pair[1].get("class_id", 999),
        ),
    )


def _primary_vertebrae(
    state: dict[str, Any],
) -> tuple[list[tuple[str, dict[str, Any]]], list[tuple[str, dict[str, Any]]]]:
    vertebrae = _sorted_structures(state.get("vertebrae", {}))
    disc_count = len(state.get("discs", {}))
    primary = []
    auxiliary = []
    for item in vertebrae:
        number = _structure_number(item[1].get("name", ""))
        if number is not None and number <= disc_count + 1:
            primary.append(item)
        else:
            auxiliary.append(item)
    return primary, auxiliary


def _disc_height(disc: dict[str, Any]) -> float:
    return float(
        disc.get("state_variables", {}).get("height")
        or disc.get("bounding_box", {}).get("depth")
        or 0.0
    )


def _disc_volume(disc: dict[str, Any]) -> float:
    return float(
        disc.get("state_variables", {}).get("volume")
        or disc.get("approx_volume")
        or 0.0
    )


def _vertebra_height(vertebra: dict[str, Any]) -> float:
    return float(vertebra.get("bounding_box", {}).get("height") or 0.0)


def _vertebra_width(vertebra: dict[str, Any]) -> float:
    return float(vertebra.get("bounding_box", {}).get("width") or 0.0)


def _vertebra_volume(vertebra: dict[str, Any]) -> float:
    return float(vertebra.get("approx_volume") or 0.0)


def build_spine_graph(state: dict[str, Any]) -> dict[str, Any]:
    discs = _sorted_structures(state.get("discs", {}))
    primary_vertebrae, auxiliary_vertebrae = _primary_vertebrae(state)
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []

    def add_node(
        node_id: str,
        node_type: str,
        position_index: float,
        structure: dict[str, Any],
    ) -> None:
        nodes[node_id] = {
            "node_id": node_id,
            "node_type": node_type,
            "name": structure.get("name"),
            "class_id": structure.get("class_id"),
            "neighbors": [],
            "position_index": position_index,
            "centroid": structure.get("centroid"),
        }

    for index, (vertebra_id, vertebra) in enumerate(primary_vertebrae, start=1):
        add_node(vertebra_id, "vertebra", float(index * 2 - 2), vertebra)
    for index, (disc_id, disc) in enumerate(discs, start=1):
        add_node(disc_id, "disc", float(index * 2 - 1), disc)

    for index, (disc_id, _disc) in enumerate(discs):
        if index >= len(primary_vertebrae) - 1:
            continue
        above_id = primary_vertebrae[index][0]
        below_id = primary_vertebrae[index + 1][0]
        for source, target in ((above_id, disc_id), (disc_id, below_id)):
            nodes[source]["neighbors"].append(target)
            nodes[target]["neighbors"].append(source)
            edges.append({"source": source, "target": target, "edge_type": "anatomic_adjacency"})

    for aux_index, (vertebra_id, vertebra) in enumerate(auxiliary_vertebrae, start=1):
        nearest_id, nearest_distance = min(
            (
                (node_id, _distance(vertebra["centroid"], node["centroid"]))
                for node_id, node in nodes.items()
                if node["node_type"] == "vertebra"
            ),
            key=lambda item: item[1],
        )
        add_node(
            vertebra_id,
            "vertebra_auxiliary",
            nodes[nearest_id]["position_index"] + aux_index * 0.1,
            vertebra,
        )
        nodes[vertebra_id]["neighbors"].append(nearest_id)
        nodes[nearest_id]["neighbors"].append(vertebra_id)
        edges.append(
            {
                "source": vertebra_id,
                "target": nearest_id,
                "edge_type": "nearest_centroid_auxiliary_link",
                "distance": nearest_distance,
            }
        )

    return {
        "patient_id": state.get("patient_id"),
        "graph_type": "spine_adjacency_graph",
        "nodes": nodes,
        "edges": edges,
        "primary_chain": [
            node_id for node_id, node in sorted(nodes.items(), key=lambda item: item[1]["position_index"])
            if node["node_type"] in {"vertebra", "disc"}
        ],
        "notes": [
            "Disc numbering is mapped between sequential primary vertebrae.",
            "Out-of-chain vertebra-labeled structures are retained and connected by nearest centroid.",
        ],
    }


def build_disc_relationships(state: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    relationships = {}
    for disc_id, disc in _sorted_structures(state.get("discs", {})):
        neighbors = graph["nodes"][disc_id]["neighbors"]
        vertebral_neighbors = [
            neighbor for neighbor in neighbors if graph["nodes"][neighbor]["node_type"].startswith("vertebra")
        ]
        ordered_neighbors = sorted(
            vertebral_neighbors,
            key=lambda node_id: graph["nodes"][node_id]["position_index"],
        )
        above_id = ordered_neighbors[0] if ordered_neighbors else None
        below_id = ordered_neighbors[-1] if len(ordered_neighbors) > 1 else None
        above = state["vertebrae"].get(above_id, {}) if above_id else {}
        below = state["vertebrae"].get(below_id, {}) if below_id else {}
        above_vector = _vector(disc["centroid"], above["centroid"]) if above else None
        below_vector = _vector(disc["centroid"], below["centroid"]) if below else None
        relationships[disc_id] = {
            "disc_name": disc.get("name"),
            "structure_above": above_id,
            "structure_above_name": above.get("name"),
            "structure_below": below_id,
            "structure_below_name": below.get("name"),
            "distance_to_above": _distance(disc["centroid"], above["centroid"]) if above else None,
            "distance_to_below": _distance(disc["centroid"], below["centroid"]) if below else None,
            "relative_orientation": {
                "above_vector": above_vector,
                "below_vector": below_vector,
                "above_below_angle_degrees": _angle_between(above_vector, below_vector)
                if above_vector and below_vector
                else None,
            },
        }
    return {"patient_id": state.get("patient_id"), "disc_relationships": relationships}


def build_relative_disc_metrics(state: dict[str, Any]) -> dict[str, Any]:
    discs = _sorted_structures(state.get("discs", {}))
    heights = [_disc_height(disc) for _, disc in discs]
    volumes = [_disc_volume(disc) for _, disc in discs]
    avg_height = mean(heights) if heights else 0.0
    avg_volume = mean(volumes) if volumes else 0.0
    metrics = {}
    for index, (disc_id, disc) in enumerate(discs):
        prev_disc = discs[index - 1][1] if index > 0 else None
        next_disc = discs[index + 1][1] if index + 1 < len(discs) else None
        height = _disc_height(disc)
        volume = _disc_volume(disc)
        metrics[disc_id] = {
            "disc_name": disc.get("name"),
            "height": height,
            "volume": volume,
            "height_relative_to_previous_disc": _safe_ratio(height, _disc_height(prev_disc)) if prev_disc else None,
            "height_relative_to_next_disc": _safe_ratio(height, _disc_height(next_disc)) if next_disc else None,
            "height_relative_to_average_disc_height": _safe_ratio(height, avg_height),
            "volume_relative_to_previous_disc": _safe_ratio(volume, _disc_volume(prev_disc)) if prev_disc else None,
            "volume_relative_to_next_disc": _safe_ratio(volume, _disc_volume(next_disc)) if next_disc else None,
            "volume_relative_to_average_disc_volume": _safe_ratio(volume, avg_volume),
        }
    return {
        "patient_id": state.get("patient_id"),
        "average_disc_height": avg_height,
        "average_disc_volume": avg_volume,
        "relative_disc_metrics": metrics,
    }


def build_relative_vertebral_metrics(state: dict[str, Any]) -> dict[str, Any]:
    vertebrae, auxiliary = _primary_vertebrae(state)
    ordered = vertebrae + auxiliary
    metrics = {}
    for index, (vertebra_id, vertebra) in enumerate(ordered):
        previous_vertebra = ordered[index - 1][1] if index > 0 else None
        next_vertebra = ordered[index + 1][1] if index + 1 < len(ordered) else None
        height = _vertebra_height(vertebra)
        width = _vertebra_width(vertebra)
        volume = _vertebra_volume(vertebra)
        pca = [float(value) for value in vertebra.get("pca_lengths", [])]
        prev_pca = previous_vertebra.get("pca_lengths", []) if previous_vertebra else []
        next_pca = next_vertebra.get("pca_lengths", []) if next_vertebra else []
        metrics[vertebra_id] = {
            "vertebra_name": vertebra.get("name"),
            "relative_height": {
                "to_previous": _safe_ratio(height, _vertebra_height(previous_vertebra)) if previous_vertebra else None,
                "to_next": _safe_ratio(height, _vertebra_height(next_vertebra)) if next_vertebra else None,
            },
            "relative_width": {
                "to_previous": _safe_ratio(width, _vertebra_width(previous_vertebra)) if previous_vertebra else None,
                "to_next": _safe_ratio(width, _vertebra_width(next_vertebra)) if next_vertebra else None,
            },
            "relative_volume": {
                "to_previous": _safe_ratio(volume, _vertebra_volume(previous_vertebra)) if previous_vertebra else None,
                "to_next": _safe_ratio(volume, _vertebra_volume(next_vertebra)) if next_vertebra else None,
            },
            "relative_pca_lengths": {
                "to_previous": [
                    _safe_ratio(pca[i], prev_pca[i]) if i < len(prev_pca) else None
                    for i in range(len(pca))
                ],
                "to_next": [
                    _safe_ratio(pca[i], next_pca[i]) if i < len(next_pca) else None
                    for i in range(len(pca))
                ],
            },
        }
    return {"patient_id": state.get("patient_id"), "relative_vertebral_metrics": metrics}


def build_centerline(state: dict[str, Any]) -> dict[str, Any]:
    primary, _auxiliary = _primary_vertebrae(state)
    points = [
        {"node_id": vertebra_id, "name": vertebra["name"], "centroid": vertebra["centroid"]}
        for vertebra_id, vertebra in primary
    ]
    segments = []
    total_length = 0.0
    for index in range(len(points) - 1):
        start = points[index]
        end = points[index + 1]
        direction = _vector(start["centroid"], end["centroid"])
        length = _norm(direction)
        total_length += length
        segments.append(
            {
                "start_node": start["node_id"],
                "end_node": end["node_id"],
                "start": start["centroid"],
                "end": end["centroid"],
                "length": length,
                "unit_direction": _unit(direction),
            }
        )
    curvature = []
    for index in range(len(segments) - 1):
        angle = _angle_between(
            segments[index]["unit_direction"],
            segments[index + 1]["unit_direction"],
        )
        avg_segment_length = mean([segments[index]["length"], segments[index + 1]["length"]])
        curvature.append(
            {
                "at_node": points[index + 1]["node_id"],
                "angle_degrees": angle,
                "curvature_estimate": angle / avg_segment_length if avg_segment_length else 0.0,
            }
        )
    return {
        "patient_id": state.get("patient_id"),
        "global_centerline": points,
        "local_centerline_segments": segments,
        "curvature_estimate": curvature,
        "centerline_length": total_length,
        "units": "voxel units",
    }


def build_local_alignment_metrics(state: dict[str, Any]) -> dict[str, Any]:
    primary, _auxiliary = _primary_vertebrae(state)
    discs = _sorted_structures(state.get("discs", {}))
    vertebral_pairs = {}
    for index in range(len(primary) - 1):
        first_id, first = primary[index]
        second_id, second = primary[index + 1]
        first_axis = first.get("principal_axes", [[0, 0, 0]])[0]
        second_axis = second.get("principal_axes", [[0, 0, 0]])[0]
        centroid_vector = _vector(first["centroid"], second["centroid"])
        vertebral_pairs[f"{first_id}__{second_id}"] = {
            "above": first_id,
            "below": second_id,
            "angle_difference_degrees": _angle_between(first_axis, second_axis),
            "tilt_difference_degrees": abs(
                math.degrees(math.atan2(first_axis[0], first_axis[1]))
                - math.degrees(math.atan2(second_axis[0], second_axis[1]))
            ),
            "orientation_difference_degrees": _angle_between(first_axis, centroid_vector),
        }
    disc_alignment = {}
    global_axis = state.get("alignment", {}).get("axes", {}).get("superior_inferior_axis", [0, 1, 0])
    for disc_id, disc in discs:
        disc_axis = disc.get("principal_axes", [[0, 0, 0]])[0]
        disc_alignment[disc_id] = {
            "disc_name": disc.get("name"),
            "disc_angle_degrees": _angle_between(disc_axis, global_axis),
            "disc_tilt_degrees": math.degrees(math.atan2(disc_axis[0], disc_axis[1])),
        }
    return {
        "patient_id": state.get("patient_id"),
        "vertebral_pair_alignment": vertebral_pairs,
        "disc_alignment": disc_alignment,
    }


def build_load_path_model(
    state: dict[str, Any],
    relative_disc_metrics: dict[str, Any],
    alignment_metrics: dict[str, Any],
) -> dict[str, Any]:
    disc_metrics = relative_disc_metrics["relative_disc_metrics"]
    load_model = {}
    for disc_id, disc in _sorted_structures(state.get("discs", {})):
        metrics = disc_metrics[disc_id]
        height_ratio = metrics["height_relative_to_average_disc_height"] or 1.0
        volume_ratio = metrics["volume_relative_to_average_disc_volume"] or 1.0
        height_deficit = max(0.0, 1.0 - height_ratio)
        volume_deficit = max(0.0, 1.0 - volume_ratio)
        tilt = abs(alignment_metrics["disc_alignment"][disc_id]["disc_tilt_degrees"])
        relative_load_index = 1.0 + height_deficit * 0.8 + volume_deficit * 0.5
        stress_score = min(1.0, height_deficit * 0.45 + volume_deficit * 0.35 + tilt / 180.0 * 0.2)
        load_model[disc_id] = {
            "structure_name": disc.get("name"),
            "structure_type": "disc",
            "relative_load_index": relative_load_index,
            "stress_score": stress_score,
            "risk_score": min(1.0, stress_score * relative_load_index),
            "rule_basis": {
                "height_ratio_to_average": height_ratio,
                "volume_ratio_to_average": volume_ratio,
                "tilt_degrees": tilt,
            },
        }
    for vertebra_id, vertebra in _sorted_structures(state.get("vertebrae", {})):
        neighbor_disc_loads = []
        number = _structure_number(vertebra.get("name", ""))
        for disc_id, _disc in _sorted_structures(state.get("discs", {})):
            disc_number = _structure_number(_disc.get("name", ""))
            if number is not None and disc_number in {number - 1, number} and disc_id in load_model:
                neighbor_disc_loads.append(load_model[disc_id]["relative_load_index"])
        relative_load_index = mean(neighbor_disc_loads) if neighbor_disc_loads else 1.0
        quality_penalty = 0.1 if vertebra.get("quality", {}).get("flagged") else 0.0
        stress_score = min(1.0, abs(relative_load_index - 1.0) * 0.6 + quality_penalty)
        load_model[vertebra_id] = {
            "structure_name": vertebra.get("name"),
            "structure_type": "vertebra",
            "relative_load_index": relative_load_index,
            "stress_score": stress_score,
            "risk_score": min(1.0, stress_score * relative_load_index),
            "rule_basis": {
                "neighbor_disc_loads": neighbor_disc_loads,
                "quality_flag_used_as_penalty": bool(quality_penalty),
            },
        }
    return {
        "patient_id": state.get("patient_id"),
        "model_type": "rule_based_geometric_load_approximation_v1",
        "physics_claim": "This is not physics; it is a deterministic geometric approximation layer.",
        "structures": load_model,
    }


def validate_state(graph: dict[str, Any], relationships: dict[str, Any]) -> dict[str, Any]:
    nodes = graph["nodes"]
    edges = graph["edges"]
    node_ids = set(nodes)
    issues = []
    visited = set()
    stack = [next(iter(node_ids))] if node_ids else []
    while stack:
        node_id = stack.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        stack.extend(nodes[node_id]["neighbors"])

    missing_neighbors = [
        {"node": node_id, "missing_neighbor": neighbor}
        for node_id, node in nodes.items()
        for neighbor in node["neighbors"]
        if neighbor not in node_ids
    ]
    broken_edges = [
        edge for edge in edges if edge["source"] not in node_ids or edge["target"] not in node_ids
    ]
    impossible_ordering = [
        node_id
        for node_id, node in nodes.items()
        if node["node_type"] == "disc" and len(node["neighbors"]) < 2
    ]
    missing_relationships = [
        disc_id
        for disc_id, relationship in relationships["disc_relationships"].items()
        if not relationship.get("structure_above") or not relationship.get("structure_below")
    ]

    if len(visited) != len(nodes):
        issues.append("Graph is not fully connected.")
    if missing_neighbors:
        issues.append("Missing neighbor references detected.")
    if broken_edges:
        issues.append("Broken edge references detected.")
    if impossible_ordering:
        issues.append("Some discs do not have two vertebral neighbors.")
    if missing_relationships:
        issues.append("Some disc relationships are incomplete.")

    return {
        "patient_id": graph.get("patient_id"),
        "validated_utc": datetime.now(timezone.utc).isoformat(),
        "graph_connected": len(visited) == len(nodes),
        "node_count": len(nodes),
        "edge_count": len(edges),
        "visited_node_count": len(visited),
        "missing_nodes": sorted(node_ids - visited),
        "missing_neighbor_references": missing_neighbors,
        "broken_relationships": broken_edges,
        "impossible_ordering": impossible_ordering,
        "missing_disc_relationships": missing_relationships,
        "issues": issues,
        "status": "pass" if not issues else "warning",
    }


def build_patient_state_vector_v2(
    state: dict[str, Any],
    graph: dict[str, Any],
    relationships: dict[str, Any],
    relative_disc_metrics: dict[str, Any],
    relative_vertebral_metrics: dict[str, Any],
    centerline: dict[str, Any],
    alignment_metrics: dict[str, Any],
    load_model: dict[str, Any],
    validation_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "patient_id": state.get("patient_id"),
        "schema_version": "2.0",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "segmentation": copy.deepcopy(state.get("segmentation", {})),
        "disc_features": copy.deepcopy(state.get("discs", {})),
        "vertebral_features": copy.deepcopy(state.get("vertebrae", {})),
        "graph_structure": graph,
        "disc_relationships": relationships,
        "centerline": centerline,
        "alignment_metrics": alignment_metrics,
        "relative_metrics": {
            "disc_metrics": relative_disc_metrics,
            "vertebral_metrics": relative_vertebral_metrics,
        },
        "load_metrics": load_model,
        "quality_metrics": copy.deepcopy(state.get("quality_metrics", {})),
        "state_validation": validation_report,
        "intervention_history": copy.deepcopy(state.get("intervention_history", [])),
        "representation_notes": [
            "Official Stage 2 digital twin state.",
            "Generated from existing deterministic measurements only.",
            "No diagnosis, disease assignment, inference, or surgery simulation performed.",
        ],
    }


def plot_spine_graph(graph: dict[str, Any], output_path: Path) -> Path:
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(7, 9))
    for edge in graph["edges"]:
        source = graph["nodes"][edge["source"]]
        target = graph["nodes"][edge["target"]]
        ax.plot(
            [source["centroid"][0], target["centroid"][0]],
            [source["centroid"][1], target["centroid"][1]],
            color="#6b7280",
            linewidth=1.5,
        )
    colors = {"vertebra": "#2563eb", "disc": "#dc2626", "vertebra_auxiliary": "#7c3aed"}
    for node in graph["nodes"].values():
        ax.scatter(node["centroid"][0], node["centroid"][1], s=80, color=colors.get(node["node_type"], "#111827"))
        ax.text(node["centroid"][0] + 1.0, node["centroid"][1] + 1.0, node["node_id"], fontsize=8)
    ax.set_title("Spine Graph")
    ax.set_xlabel("X centroid")
    ax.set_ylabel("Y centroid")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_centerline(centerline: dict[str, Any], output_path: Path) -> Path:
    plt = _pyplot()
    points = centerline["global_centerline"]
    xs = [point["centroid"][0] for point in points]
    ys = [point["centroid"][1] for point in points]
    fig, ax = plt.subplots(figsize=(7, 9))
    ax.plot(xs, ys, marker="o", color="#0f766e", linewidth=2.0)
    for point in points:
        ax.text(point["centroid"][0] + 1.0, point["centroid"][1], point["node_id"], fontsize=8)
    ax.set_title("Spine Centerline")
    ax.set_xlabel("X centroid")
    ax.set_ylabel("Y centroid")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_relative_disc_height(metrics: dict[str, Any], output_path: Path) -> Path:
    plt = _pyplot()
    disc_metrics = metrics["relative_disc_metrics"]
    names = [item["disc_name"] for item in disc_metrics.values()]
    values = [item["height_relative_to_average_disc_height"] for item in disc_metrics.values()]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(names, values, color="#0891b2")
    ax.axhline(1.0, color="#111827", linewidth=1.0)
    ax.set_title("Relative Disc Height")
    ax.set_ylabel("Ratio to average height")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_relative_volume(metrics: dict[str, Any], output_path: Path) -> Path:
    plt = _pyplot()
    disc_metrics = metrics["relative_disc_metrics"]
    names = [item["disc_name"] for item in disc_metrics.values()]
    values = [item["volume_relative_to_average_disc_volume"] for item in disc_metrics.values()]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.bar(names, values, color="#16a34a")
    ax.axhline(1.0, color="#111827", linewidth=1.0)
    ax.set_title("Relative Disc Volume")
    ax.set_ylabel("Ratio to average volume")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_alignment(alignment_metrics: dict[str, Any], output_path: Path) -> Path:
    plt = _pyplot()
    disc_alignment = alignment_metrics["disc_alignment"]
    names = [item["disc_name"] for item in disc_alignment.values()]
    angles = [item["disc_angle_degrees"] for item in disc_alignment.values()]
    tilts = [item["disc_tilt_degrees"] for item in disc_alignment.values()]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(names, angles, marker="o", label="Angle")
    ax.plot(names, tilts, marker="o", label="Tilt")
    ax.set_title("Local Disc Alignment")
    ax.set_ylabel("Degrees")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_load_distribution(load_model: dict[str, Any], output_path: Path) -> Path:
    plt = _pyplot()
    structures = load_model["structures"]
    disc_items = [item for item in structures.values() if item["structure_type"] == "disc"]
    names = [item["structure_name"] for item in disc_items]
    loads = [item["relative_load_index"] for item in disc_items]
    risks = [item["risk_score"] for item in disc_items]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(names, loads, marker="o", label="Relative load index")
    ax.plot(names, risks, marker="o", label="Risk score")
    ax.set_title("Rule-Based Load Distribution")
    ax.tick_params(axis="x", rotation=30)
    ax.legend()
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def generate_readiness_report(validation_report: dict[str, Any]) -> str:
    connectivity_answer = "Yes" if validation_report["graph_connected"] else "Not fully"
    transition_answer = "Yes" if validation_report["status"] in {"pass", "warning"} else "Limited"
    return "\n".join(
        [
            "ORTHOTWIN STAGE 2 READINESS REPORT",
            "=" * 36,
            "",
            "1. Can the spine now be represented as a connected system?",
            f"   {connectivity_answer}. The generated graph contains {validation_report['node_count']} nodes and {validation_report['edge_count']} edges.",
            "",
            "2. Can interventions propagate through neighboring structures?",
            "   Yes. Disc and vertebral neighbor relationships are explicit, so future transition rules can update adjacent nodes.",
            "",
            "3. Are state transitions now possible?",
            f"   {transition_answer}. Stage 2 adds graph, relative metrics, local alignment, and load approximation fields for deterministic transitions.",
            "",
            "4. What data is still missing for biomechanics?",
            "   Material properties, boundary conditions, calibrated forces, ligament/facet data, patient scale, and validated motion/loading measurements.",
            "",
            "5. What data is still missing for surgical simulation?",
            "   Surgical approach constraints, instrument geometry, implant catalogs, collision models, tissue behavior, vascular/neural safety margins, and surgeon-defined goals.",
            "",
            "6. What is required for Stage 3?",
            "   A deterministic propagation engine that consumes the graph, updates neighboring structures, records state transitions, and validates every predicted state against consistency rules.",
            "",
            "Scope Statement",
            "   No diagnosis, disease assignment, inference, or surgery simulation was performed.",
        ]
    )


def generate_manifest(paths: dict[str, Path]) -> dict[str, Any]:
    files = {
        name: {
            "path": str(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else None,
        }
        for name, path in paths.items()
    }
    return {
        "stage": "OrthoTwin Stage 2",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "all_files_exist": all(item["exists"] for item in files.values()),
        "files": files,
    }


def run_stage2(state_path: Path = STATE_PATH, output_dir: Path = STAGE2_DIR) -> dict[str, Path]:
    state = _load_json(state_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)

    graph = build_spine_graph(state)
    relationships = build_disc_relationships(state, graph)
    relative_disc_metrics = build_relative_disc_metrics(state)
    relative_vertebral_metrics = build_relative_vertebral_metrics(state)
    centerline = build_centerline(state)
    alignment_metrics = build_local_alignment_metrics(state)
    load_model = build_load_path_model(state, relative_disc_metrics, alignment_metrics)
    validation_report = validate_state(graph, relationships)
    patient_state_v2 = build_patient_state_vector_v2(
        state,
        graph,
        relationships,
        relative_disc_metrics,
        relative_vertebral_metrics,
        centerline,
        alignment_metrics,
        load_model,
        validation_report,
    )

    paths = {
        "spine_graph": output_dir / "spine_graph.json",
        "disc_relationships": output_dir / "disc_relationships.json",
        "relative_disc_metrics": output_dir / "relative_disc_metrics.json",
        "relative_vertebral_metrics": output_dir / "relative_vertebral_metrics.json",
        "spine_centerline": output_dir / "spine_centerline.json",
        "local_alignment_metrics": output_dir / "local_alignment_metrics.json",
        "load_path_model": output_dir / "load_path_model.json",
        "state_validation_report": output_dir / "state_validation_report.json",
        "patient_state_vector_v2": output_dir / "patient_state_vector_v2.json",
        "stage2_readiness_report": output_dir / "stage2_readiness_report.txt",
        "spine_graph_plot": FIGURE_DIR / "spine_graph.png",
        "centerline_plot": FIGURE_DIR / "centerline_plot.png",
        "relative_disc_height_plot": FIGURE_DIR / "relative_disc_height_plot.png",
        "relative_volume_plot": FIGURE_DIR / "relative_volume_plot.png",
        "alignment_plot": FIGURE_DIR / "alignment_plot.png",
        "load_distribution_plot": FIGURE_DIR / "load_distribution_plot.png",
    }

    _write_json(paths["spine_graph"], graph)
    _write_json(paths["disc_relationships"], relationships)
    _write_json(paths["relative_disc_metrics"], relative_disc_metrics)
    _write_json(paths["relative_vertebral_metrics"], relative_vertebral_metrics)
    _write_json(paths["spine_centerline"], centerline)
    _write_json(paths["local_alignment_metrics"], alignment_metrics)
    _write_json(paths["load_path_model"], load_model)
    _write_json(paths["state_validation_report"], validation_report)
    _write_json(paths["patient_state_vector_v2"], patient_state_v2)
    _write_text(paths["stage2_readiness_report"], generate_readiness_report(validation_report))

    plot_spine_graph(graph, paths["spine_graph_plot"])
    plot_centerline(centerline, paths["centerline_plot"])
    plot_relative_disc_height(relative_disc_metrics, paths["relative_disc_height_plot"])
    plot_relative_volume(relative_disc_metrics, paths["relative_volume_plot"])
    plot_alignment(alignment_metrics, paths["alignment_plot"])
    plot_load_distribution(load_model, paths["load_distribution_plot"])

    manifest_path = output_dir / "stage2_manifest.json"
    paths["stage2_manifest"] = manifest_path
    _write_json(manifest_path, generate_manifest(paths))
    _write_json(manifest_path, generate_manifest(paths))
    return paths


if __name__ == "__main__":
    generated = run_stage2()
    print("OrthoTwin Stage 2 complete.")
    for name, path in generated.items():
        print(f"{name}: {path}")
