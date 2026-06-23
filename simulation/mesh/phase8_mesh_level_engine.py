"""Phase 8 mesh-level digital twin runner.

This phase modifies reconstructed mesh vertices directly, then rebuilds
mesh-derived measurements. It does not implement FEM, fake biomechanics,
diagnosis, or treatment recommendations.
"""

from __future__ import annotations

import json
import pickle
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE_PARENT = Path(__file__).resolve().parents[3]
if str(PACKAGE_PARENT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_PARENT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from OrthoTwin.simulation.mesh.mesh_state_builder import (
    build_mesh_state,
    load_meshes,
    mesh_inventory,
    mesh_metrics,
    structure_id,
)
from OrthoTwin.simulation.mesh.mesh_transformation_engine import MeshTransformationEngine


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_graph.json"
STATE_DIR = PROJECT_ROOT / "state" / "mesh"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase8"
VIS_DIR = PROJECT_ROOT / "visualization" / "mesh"
MANIFEST_DIR = PROJECT_ROOT / "manifests"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def mesh_name_maps(meshes: dict[str, dict[str, Any]]) -> tuple[dict[str, str], dict[str, str]]:
    id_to_name = {structure_id(name): name for name in meshes}
    name_to_id = {name: sid for sid, name in id_to_name.items()}
    return id_to_name, name_to_id


def neighbors_for_disc(graph: dict[str, Any], meshes: dict[str, dict[str, Any]], disc_id: str) -> list[str]:
    id_to_name, _ = mesh_name_maps(meshes)
    return [id_to_name[n] for n in graph["nodes"][disc_id]["neighbors"] if n in id_to_name]


def rebuild_mesh_state(
    meshes: dict[str, dict[str, Any]], graph: dict[str, Any], scenario_id: str
) -> dict[str, Any]:
    state = build_mesh_state(meshes, include_arrays=False)
    id_to_name, _ = mesh_name_maps(meshes)
    structures = state["structures"]

    relative_spacing = {}
    for node_id, node in graph.get("nodes", {}).items():
        if node.get("node_type") != "disc" or node_id not in id_to_name:
            continue
        disc_name = id_to_name[node_id]
        disc_centroid = structures[node_id]["centroid"]
        relative_spacing[node_id] = {}
        for neighbor_id in node.get("neighbors", []):
            if neighbor_id not in structures:
                continue
            relative_spacing[node_id][neighbor_id] = distance(disc_centroid, structures[neighbor_id]["centroid"])

    vertebra_ids = [
        node_id
        for node_id, node in graph.get("nodes", {}).items()
        if node.get("node_type", "").startswith("vertebra") and node_id in structures
    ]
    vertebra_ids.sort(key=lambda item: graph["nodes"][item].get("position_index", 0))
    local_curvature = []
    for prev_id, node_id, next_id in zip(vertebra_ids, vertebra_ids[1:], vertebra_ids[2:]):
        a = np.asarray(structures[prev_id]["centroid"])
        b = np.asarray(structures[node_id]["centroid"])
        c = np.asarray(structures[next_id]["centroid"])
        angle = angle_between(a - b, c - b)
        seg = max(1.0, (np.linalg.norm(a - b) + np.linalg.norm(c - b)) / 2.0)
        local_curvature.append({"at_node": node_id, "angle_degrees": angle, "curvature_estimate": angle / seg})

    alignment = {}
    for node_id, node in graph.get("nodes", {}).items():
        if node.get("node_type") != "disc" or node_id not in id_to_name:
            continue
        neighbors = [n for n in node.get("neighbors", []) if n in structures]
        if len(neighbors) >= 2:
            vec = np.asarray(structures[neighbors[1]]["centroid"]) - np.asarray(structures[neighbors[0]]["centroid"])
            alignment[node_id] = {
                "disc_angle_degrees": angle_between(vec, np.array([0.0, 1.0, 0.0])),
                "disc_tilt_degrees": float(np.degrees(np.arctan2(vec[0], vec[1] if vec[1] else 1e-9))),
            }

    state.update(
        {
            "scenario_id": scenario_id,
            "relative_spacing": relative_spacing,
            "curvature": {
                "global_curvature": mean([item["curvature_estimate"] for item in local_curvature]),
                "maximum_local_curvature": max([item["curvature_estimate"] for item in local_curvature] or [0.0]),
                "local_curvature": local_curvature,
                "method": "mesh_centroid_angle_rebuild",
            },
            "alignment": alignment,
            "rebuild_policy": "all listed measurements recomputed after mesh vertex transforms",
        }
    )
    return state


def distance(a: list[float], b: list[float]) -> float:
    aa = np.asarray(a)
    bb = np.asarray(b)
    return float(np.linalg.norm(aa - bb))


def angle_between(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.degrees(np.arccos(np.clip(float(np.dot(a, b) / denom), -1.0, 1.0))))


def mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0


def run_surgery(
    name: str, meshes: dict[str, dict[str, Any]], graph: dict[str, Any], operation: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    engine = MeshTransformationEngine(meshes)
    if operation == "implant":
        disc = "Disc 6 (206/207)"
        engine.expand_disc_height(disc, 20.0, neighbors_for_disc(graph, meshes, "disc_6_206_207"))
        created = [{"id": "implant_mesh_disc_6_206_207", "type": "implant_proxy", "geometry_changed": True}]
    elif operation == "collapse":
        disc = "Disc 6 (206/207)"
        engine.compress_disc_height(disc, 20.0, neighbors_for_disc(graph, meshes, "disc_6_206_207"))
        created = []
    elif operation == "spacer":
        disc = "Disc 5 (205)"
        engine.expand_disc_height(disc, 15.0, neighbors_for_disc(graph, meshes, "disc_5_205"))
        created = [{"id": "spacer_mesh_disc_5_205", "type": "spacer_proxy", "geometry_changed": True}]
    elif operation == "fusion":
        created = [{"id": "fusion_mesh_vertebra_5_vertebra_6", "type": "fusion_segment", "geometry_changed": False}]
        engine.history.append(
            {
                "structure_name": "fusion_mesh_vertebra_5_vertebra_6",
                "operation": "fusion_constraint",
                "parameters": {"vertebra_a": "Vertebra 5", "vertebra_b": "Vertebra 6", "locked_relative_transform": True},
                "vertices_moved": 0,
                "average_displacement": 0.0,
                "max_displacement": 0.0,
            }
        )
    else:
        raise ValueError(operation)

    rebuilt = rebuild_mesh_state(engine.meshes, graph, f"{operation}_mesh_v3")
    result = {
        "scenario_id": f"{operation}_mesh_v3",
        "operation": operation,
        "mesh_operations": engine.history,
        "created_objects": created,
        "geometry_changed": any(item["vertices_moved"] > 0 for item in engine.history),
        "relationship_changed": operation == "fusion",
        "constraint_changed": operation == "fusion",
        "rebuilt_state": rebuilt,
        "not_medical_advice": True,
        "biomechanics_claim": "none",
        "clinical_validity_claim": "none",
    }
    return result, rebuilt


def impact_from_result(result: dict[str, Any]) -> dict[str, Any]:
    moved = [item for item in result["mesh_operations"] if item["vertices_moved"] > 0]
    total_vertices = sum(item["vertices_moved"] for item in moved)
    weighted_avg = (
        sum(item["average_displacement"] * item["vertices_moved"] for item in moved) / total_vertices
        if total_vertices
        else 0.0
    )
    return {
        "surgery": result["operation"],
        "vertices_moved": total_vertices,
        "average_displacement": weighted_avg,
        "max_displacement": max([item["max_displacement"] for item in result["mesh_operations"]] or [0.0]),
        "affected_structures": [item["structure_name"] for item in result["mesh_operations"]],
    }


def plot_before_after(base: dict[str, dict[str, Any]], result: dict[str, Any], filename: str, title: str) -> Path:
    changed_names = [item["structure_name"] for item in result["mesh_operations"] if item["structure_name"] in base]
    rebuilt_structures = result["rebuilt_state"]["structures"]
    _, name_to_id = mesh_name_maps(base)
    fig = plt.figure(figsize=(8, 6))
    ax = fig.add_subplot(111, projection="3d")
    for name in changed_names:
        before = base[name]["vertices"]
        after_centroid = np.asarray(rebuilt_structures[name_to_id[name]]["centroid"])
        before_centroid = before.mean(axis=0)
        sample = before[:: max(1, len(before) // 500)]
        ax.scatter(sample[:, 0], sample[:, 1], sample[:, 2], s=1, alpha=0.15, color="#4c78a8")
        ax.scatter([before_centroid[0]], [before_centroid[1]], [before_centroid[2]], color="#1f4e79", s=30)
        ax.scatter([after_centroid[0]], [after_centroid[1]], [after_centroid[2]], color="#d1495b", s=30)
        ax.plot([before_centroid[0], after_centroid[0]], [before_centroid[1], after_centroid[1]], [before_centroid[2], after_centroid[2]], color="#222222")
    ax.set_title(title)
    path = VIS_DIR / filename
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_overlay(base: dict[str, dict[str, Any]], results: dict[str, dict[str, Any]]) -> Path:
    fig = plt.figure(figsize=(9, 7))
    ax = fig.add_subplot(111, projection="3d")
    colors = {"implant": "#d1495b", "collapse": "#edae49", "spacer": "#66a182", "fusion": "#7b6d8d"}
    for operation, result in results.items():
        for item in result["mesh_operations"]:
            name = item["structure_name"]
            if name not in base:
                continue
            before = base[name]["vertices"]
            sample = before[:: max(1, len(before) // 300)]
            ax.scatter(sample[:, 0], sample[:, 1], sample[:, 2], s=1, alpha=0.08, color=colors[operation])
    ax.set_title("3D Mesh Overlay: Structures Touched By Phase 8")
    path = VIS_DIR / "3d_mesh_overlays.png"
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def report_text(inventory: dict[str, Any], impacts: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "ORTHOTWIN FINAL PROTOTYPE REPORT",
            "",
            "Phase 1: Segmentation artifacts exist and feed reconstruction.",
            "Phase 2: State representation and spine graph were built.",
            "Phase 3: Deterministic propagation exists, explicitly not physics.",
            "Phase 4: Radiology-style geometric measurements exist in voxel units.",
            "Phase 5: Scenario comparison exists with internal scoring only.",
            "Phase 6: Evidence, longitudinal assumptions, and reliability audits exist.",
            "Phase 7: Geometry-aware surgery moved from metric edits to centroid/object edits.",
            "Phase 8: Mesh-level twin modifies reconstructed vertices and rebuilds mesh-derived measurements.",
            "",
            "Final Classification: Digital Twin Prototype.",
            "Justification: OrthoTwin now has real reconstructed mesh objects, state/graph structure, deterministic scenario layers, evidence audits, and mesh-level transformations. It still lacks trusted physical calibration, FEM, material properties, boundary conditions, longitudinal validation, and clinical validation, so it is not yet a research-grade biomechanical digital twin.",
            "",
            f"Mesh structures loaded: {inventory['total_structures']} ({inventory['vertebra_meshes']} vertebrae, {inventory['disc_meshes']} discs).",
            "Average vertex displacements:",
            *[f"- {item['surgery']}: {item['average_displacement']:.4f} voxel units" for item in impacts],
            "",
            "No clinical claims. No biomechanics claims. No regulatory claims.",
        ]
    )


def main() -> None:
    for directory in (STATE_DIR, REPORT_DIR, VIS_DIR, MANIFEST_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    meshes = load_meshes()
    graph = load_json(GRAPH_PATH)
    inventory = mesh_inventory(meshes)
    mesh_state = build_mesh_state(meshes, include_arrays=False)
    inventory_path = write_json(STATE_DIR / "mesh_inventory.json", inventory)
    state_path = write_json(STATE_DIR / "mesh_state_vector.json", mesh_state)

    operations = {"implant": "implant", "collapse": "collapse", "spacer": "spacer", "fusion": "fusion"}
    results = {}
    rebuilt_paths = []
    result_paths = []
    for key, operation in operations.items():
        result, rebuilt = run_surgery(key, meshes, graph, operation)
        results[key] = result
        result_path = write_json(STATE_DIR / f"{key}_mesh_result.json", {k: v for k, v in result.items() if k != "rebuilt_state"})
        rebuilt_path = write_json(STATE_DIR / f"mesh_rebuilt_state_{key}.json", rebuilt)
        result_paths.append(result_path)
        rebuilt_paths.append(rebuilt_path)

    combined_rebuilt = write_json(
        STATE_DIR / "mesh_rebuilt_state.json",
        {
            "generated_utc": utc_now(),
            "states": {key: result["rebuilt_state"] for key, result in results.items()},
        },
    )
    impacts = [impact_from_result(result) for result in results.values()]
    impact_path = write_json(REPORT_DIR / "mesh_impact_analysis.json", {"generated_utc": utc_now(), "surgeries": impacts})

    limitations_path = write_json(
        REPORT_DIR / "phase8_limitations.json",
        {
            "generated_utc": utc_now(),
            "what_is_mesh_based": ["disc expansion/compression scales reconstructed vertices", "adjacent vertebra meshes are translated", "centroids/PCA/bounding boxes/heights are rebuilt from transformed vertices"],
            "what_remains_centroid_based": ["relative spacing", "curvature", "alignment summaries"],
            "what_remains_rule_based": ["choice of 20% implant/collapse and 15% spacer transforms", "fusion lock relationship"],
            "what_remains_estimated": ["volume estimate from bounding boxes", "surface/height proxy interpretation", "clinical meaning of changes"],
            "blocked": ["physical calibration", "FEM biomechanics", "clinical validation"],
        },
    )

    visual_paths = [
        plot_before_after(meshes, results["implant"], "implant_mesh_before_after.png", "Implant Mesh Before/After"),
        plot_before_after(meshes, results["collapse"], "collapse_mesh_before_after.png", "Collapse Mesh Before/After"),
        plot_before_after(meshes, results["fusion"], "fusion_mesh_before_after.png", "Fusion Mesh Constraint"),
        plot_before_after(meshes, results["spacer"], "spacer_mesh_before_after.png", "Spacer Mesh Before/After"),
        plot_overlay(meshes, results),
    ]

    report_path = write_text(REPORT_DIR / "orthotwin_final_prototype_report.txt", report_text(inventory, impacts))
    validation = {
        "generated_utc": utc_now(),
        "all_outputs_exist": all(path.exists() for path in [inventory_path, state_path, *result_paths, impact_path, limitations_path, report_path]),
        "all_mesh_operations_executed": all(result["mesh_operations"] for result in results.values()),
        "all_rebuilt_states_generated": all(path.exists() for path in [*rebuilt_paths, combined_rebuilt]),
        "all_visualizations_generated": all(path.exists() for path in visual_paths),
        "outputs": [str(path) for path in [inventory_path, state_path, *result_paths, *rebuilt_paths, combined_rebuilt, impact_path, limitations_path, report_path, *visual_paths]],
    }
    validation_path = write_json(REPORT_DIR / "phase8_validation_report.json", validation)
    manifest_path = write_json(
        MANIFEST_DIR / "phase8_manifest.json",
        {
            "generated_utc": utc_now(),
            "phase": "phase8_mesh_level_digital_twin",
            "files": validation["outputs"] + [str(validation_path)],
            "all_files_exist": validation["all_outputs_exist"] and validation["all_rebuilt_states_generated"] and validation["all_visualizations_generated"],
        },
    )

    print("ORTHOTWIN PHASE 8 COMPLETE")
    print(f"Mesh Structures Loaded: {inventory['total_structures']}")
    print("Mesh Surgeries Supported: implant, collapse, spacer, fusion")
    print("Average Vertex Displacements:")
    for item in impacts:
        print(f"- {item['surgery']}: {item['average_displacement']:.4f}")
    print("Final Prototype Classification: Digital Twin Prototype")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
