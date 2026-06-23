"""Phase 4 radiology-grade geometric measurement engine.

Uses existing state, graph, coordinate-system, centerline, and reconstructed
mesh files only. No retraining, inference, segmentation recomputation, or mask
modification is performed.
"""

from __future__ import annotations

import json
import math
import pickle
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PROJECT_ROOT.parent
ORTHOTWIN2_ROOT = WORKSPACE_ROOT / "OrthoTwin2"

STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "patient_state_vector_v2.json"
MESH_PATH = PROJECT_ROOT / "measurements" / "geometry" / "reconstructed_structures.pkl"
COORDINATE_PATH = PROJECT_ROOT / "measurements" / "alignment" / "spine_coordinate_system.json"
GRAPH_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_graph.json"
CENTERLINE_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_centerline.json"

OUTPUT_DIR = PROJECT_ROOT / "measurements" / "radiology"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase4"
VIS_DIR = PROJECT_ROOT / "visualization" / "state"
MANIFEST_DIR = PROJECT_ROOT / "manifests"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, data: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_meshes(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("rb") as handle:
        meshes = pickle.load(handle)
    return {item["name"]: item for item in meshes}


def unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return vector
    return vector / norm


def pca_axes(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    centered = points - points.mean(axis=0)
    covariance = np.cov(centered.T)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(values)[::-1]
    return values[order], vectors[:, order].T


def projection_range(points: np.ndarray, axis: np.ndarray) -> float:
    values = points @ unit(axis)
    return float(values.max() - values.min())


def region_height(points: np.ndarray, region_axis: np.ndarray, height_axis: np.ndarray, side: str) -> float:
    projections = points @ unit(region_axis)
    if side in {"anterior", "right"}:
        threshold = np.quantile(projections, 0.66)
        subset = points[projections >= threshold]
    else:
        threshold = np.quantile(projections, 0.34)
        subset = points[projections <= threshold]
    if len(subset) < 8:
        subset = points
    return projection_range(subset, height_axis)


def convex_hull_area(points_2d: np.ndarray) -> float:
    points = sorted({(float(x), float(y)) for x, y in points_2d})
    if len(points) < 3:
        return 0.0

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for point in points:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(points):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    hull = lower[:-1] + upper[:-1]
    area = 0.0
    for index in range(len(hull)):
        x1, y1 = hull[index]
        x2, y2 = hull[(index + 1) % len(hull)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def mesh_surface_area(verts: np.ndarray, faces: np.ndarray) -> float:
    tri = verts[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    return float(np.linalg.norm(cross, axis=1).sum() / 2.0)


def disc_records(state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        state.get("disc_features", {}).items(),
        key=lambda item: float(item[1].get("class_id", 999)),
    )


def vertebra_records(state: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return sorted(
        state.get("vertebral_features", {}).items(),
        key=lambda item: float(item[1].get("class_id", 999)),
    )


def compute_disc_heights(state: dict[str, Any], meshes: dict[str, dict[str, Any]], coordinates: dict[str, Any]) -> dict[str, Any]:
    axes = coordinates["axes"]
    ap_axis = unit(np.array(axes["anterior_posterior_axis"], dtype=float))
    lr_axis = unit(np.array(axes["left_right_axis"], dtype=float))
    measurements = {}
    for disc_id, disc in disc_records(state):
        mesh = meshes[disc["name"]]
        verts = np.asarray(mesh["verts"], dtype=float)
        _values, local_axes = pca_axes(verts)
        height_axis = local_axes[-1]
        full_height = projection_range(verts, height_axis)
        directional = {
            "anterior_height": region_height(verts, ap_axis, height_axis, "anterior"),
            "posterior_height": region_height(verts, ap_axis, height_axis, "posterior"),
            "left_height": region_height(verts, lr_axis, height_axis, "left"),
            "right_height": region_height(verts, lr_axis, height_axis, "right"),
        }
        sampled = [full_height, *directional.values()]
        measurements[disc_id] = {
            "disc_name": disc["name"],
            "mean_height": float(np.mean(sampled)),
            "maximum_height": float(np.max(sampled)),
            "minimum_height": float(np.min(sampled)),
            **directional,
            "height_axis": height_axis.tolist(),
            "method": "mesh_vertex_projection_on_local_minor_pca_axis",
            "uses_bounding_box": False,
            "units": "voxel units",
        }
    return {"generated_utc": utc_now(), "disc_heights": measurements}


def compute_disc_areas(state: dict[str, Any], meshes: dict[str, dict[str, Any]], disc_heights: dict[str, Any]) -> dict[str, Any]:
    measurements = {}
    for disc_id, disc in disc_records(state):
        mesh = meshes[disc["name"]]
        verts = np.asarray(mesh["verts"], dtype=float)
        faces = np.asarray(mesh["faces"], dtype=int)
        _values, axes = pca_axes(verts)
        in_plane = axes[:2]
        height_axis = axes[-1]
        projected = np.column_stack((verts @ in_plane[0], verts @ in_plane[1]))
        hull_area = convex_hull_area(projected)
        height_projection = verts @ unit(height_axis)
        top = verts[height_projection >= np.quantile(height_projection, 0.8)]
        bottom = verts[height_projection <= np.quantile(height_projection, 0.2)]
        top_projected = np.column_stack((top @ in_plane[0], top @ in_plane[1]))
        bottom_projected = np.column_stack((bottom @ in_plane[0], bottom @ in_plane[1]))
        volume = float(disc.get("state_variables", {}).get("volume") or disc.get("approx_volume") or 0.0)
        mean_height = disc_heights["disc_heights"][disc_id]["mean_height"]
        measurements[disc_id] = {
            "disc_name": disc["name"],
            "average_cross_sectional_area": volume / mean_height if mean_height else None,
            "projected_disc_footprint_area": hull_area,
            "superior_surface_area": convex_hull_area(top_projected),
            "inferior_surface_area": convex_hull_area(bottom_projected),
            "mesh_surface_area_reference": mesh_surface_area(verts, faces),
            "method": "mesh_projection_and_surface_band_estimate",
            "units": "voxel squared",
        }
    return {"generated_utc": utc_now(), "disc_area_measurements": measurements}


def compute_canal_measurements(state: dict[str, Any], centerline: dict[str, Any]) -> dict[str, Any]:
    measurements = {}
    centerline_by_node = {item["node_id"]: item for item in centerline["global_centerline"]}
    for vertebra_id, vertebra in vertebra_records(state):
        box = vertebra.get("bounding_box", {})
        pca = vertebra.get("pca_lengths", [0.0, 0.0, 0.0])
        width = float(box.get("width") or pca[1] or 0.0)
        depth = float(box.get("depth") or pca[-1] or 0.0)
        canal_width = width * 0.32
        canal_depth = max(depth * 0.75, float(pca[-1]) * 0.55 if pca else 0.0)
        measurements[vertebra_id] = {
            "vertebra_name": vertebra["name"],
            "canal_width": canal_width,
            "canal_depth": canal_depth,
            "canal_area": canal_width * canal_depth,
            "centerline_point_used": centerline_by_node.get(vertebra_id),
            "estimate_type": "GEOMETRIC ESTIMATE",
            "not_diagnosis": True,
            "method": "vertebral_geometry_scaled_by_centerline_level",
            "units": "voxel units / voxel squared",
        }
    return {"generated_utc": utc_now(), "canal_measurements": measurements}


def compute_foraminal_measurements(state: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    measurements = {}
    for disc_id, disc in disc_records(state):
        neighbors = graph["nodes"][disc_id]["neighbors"]
        vertebrae = [state["vertebral_features"][node] for node in neighbors if node in state["vertebral_features"]]
        disc_height = float(disc.get("state_variables", {}).get("height") or 0.0)
        if len(vertebrae) >= 2:
            centroid_gap = float(np.linalg.norm(np.array(vertebrae[0]["centroid"]) - np.array(vertebrae[1]["centroid"])))
            avg_width = float(np.mean([v["bounding_box"]["width"] for v in vertebrae]))
        else:
            centroid_gap = disc_height
            avg_width = float(disc.get("bounding_box", {}).get("width") or 0.0)
        base_area = disc_height * max(centroid_gap * 0.18, avg_width * 0.08)
        centroid = np.array(disc.get("centroid", [0.0, 0.0, 0.0]), dtype=float)
        asymmetry = float(np.clip((centroid[0] - np.mean([v["centroid"][0] for v in vertebrae])) / max(avg_width, 1.0), -0.2, 0.2)) if vertebrae else 0.0
        measurements[disc_id] = {
            "disc_name": disc["name"],
            "left_foraminal_area": base_area * (1.0 - asymmetry),
            "right_foraminal_area": base_area * (1.0 + asymmetry),
            "estimate_type": "GEOMETRIC ESTIMATE",
            "not_diagnosis": True,
            "method": "disc_height_by_adjacent_vertebral_spacing_proxy",
            "units": "voxel squared",
        }
    return {"generated_utc": utc_now(), "foraminal_measurements": measurements}


def compute_disc_degeneration_features(state: dict[str, Any], meshes: dict[str, dict[str, Any]], disc_heights: dict[str, Any]) -> dict[str, Any]:
    heights = [item["mean_height"] for item in disc_heights["disc_heights"].values()]
    volumes = [float(disc.get("state_variables", {}).get("volume") or disc.get("approx_volume") or 0.0) for _id, disc in disc_records(state)]
    reference_height = max(heights) if heights else 0.0
    reference_volume = max(volumes) if volumes else 0.0
    measurements = {}
    for disc_id, disc in disc_records(state):
        mesh = meshes[disc["name"]]
        verts = np.asarray(mesh["verts"], dtype=float)
        centroid = verts.mean(axis=0)
        distances = np.linalg.norm(verts - centroid, axis=1)
        irregularity = float(np.std(distances) / np.mean(distances)) if np.mean(distances) else 0.0
        height = disc_heights["disc_heights"][disc_id]["mean_height"]
        volume = float(disc.get("state_variables", {}).get("volume") or disc.get("approx_volume") or 0.0)
        height_loss = max(0.0, (reference_height - height) / reference_height * 100.0) if reference_height else None
        volume_loss = max(0.0, (reference_volume - volume) / reference_volume * 100.0) if reference_volume else None
        measurements[disc_id] = {
            "disc_name": disc["name"],
            "height_loss_percent": height_loss,
            "volume_loss_percent": volume_loss,
            "relative_collapse_score": float((height_loss or 0.0) * 0.6 + (volume_loss or 0.0) * 0.4) / 100.0,
            "shape_irregularity_score": irregularity,
            "not_diagnosis": True,
            "method": "relative_geometry_score_against_patient_internal_reference",
        }
    return {"generated_utc": utc_now(), "disc_degeneration_features": measurements}


def compute_vertebral_slippage(state: dict[str, Any], coordinates: dict[str, Any]) -> dict[str, Any]:
    ap_axis = unit(np.array(coordinates["axes"]["anterior_posterior_axis"], dtype=float))
    measurements = {}
    vertebrae = vertebra_records(state)
    for index in range(len(vertebrae) - 1):
        current_id, current = vertebrae[index]
        next_id, next_vertebra = vertebrae[index + 1]
        displacement = np.array(next_vertebra["centroid"], dtype=float) - np.array(current["centroid"], dtype=float)
        ap_displacement = float(displacement @ ap_axis)
        reference_width = float(np.mean([current["bounding_box"]["width"], next_vertebra["bounding_box"]["width"]]))
        measurements[f"{current_id}__{next_id}"] = {
            "from": current_id,
            "to": next_id,
            "relative_anterior_posterior_displacement": ap_displacement,
            "percent_of_average_vertebral_width": ap_displacement / reference_width * 100.0 if reference_width else None,
            "not_diagnosis": True,
            "method": "centroid_projection_on_global_anterior_posterior_axis",
            "units": "voxel units / percent",
        }
    return {"generated_utc": utc_now(), "vertebral_slippage": measurements}


def compute_curvature(centerline: dict[str, Any]) -> dict[str, Any]:
    local = centerline.get("curvature_estimate", [])
    values = [float(item["curvature_estimate"]) for item in local]
    peaks = sorted(local, key=lambda item: item["curvature_estimate"], reverse=True)[:3]
    return {
        "generated_utc": utc_now(),
        "global_curvature": float(np.mean(values)) if values else 0.0,
        "maximum_local_curvature": max(values) if values else 0.0,
        "local_curvature": local,
        "curvature_peaks": peaks,
        "centerline_length": centerline.get("centerline_length"),
        "method": "angle_change_per_centerline_segment_length",
    }


def build_clinical_state(
    state: dict[str, Any],
    disc_heights: dict[str, Any],
    disc_areas: dict[str, Any],
    canal: dict[str, Any],
    foraminal: dict[str, Any],
    degeneration: dict[str, Any],
    slippage: dict[str, Any],
    curvature: dict[str, Any],
) -> dict[str, Any]:
    return {
        "patient_id": state.get("patient_id"),
        "schema_version": "clinical_state_v1",
        "created_utc": utc_now(),
        "source_state": str(STATE_PATH),
        "disc_heights": disc_heights["disc_heights"],
        "disc_areas": disc_areas["disc_area_measurements"],
        "canal_areas": canal["canal_measurements"],
        "foraminal_areas": foraminal["foraminal_measurements"],
        "curvature": curvature,
        "alignment": state.get("alignment_metrics"),
        "slippage": slippage["vertebral_slippage"],
        "degeneration_features": degeneration["disc_degeneration_features"],
        "clinical_scope": {
            "not_diagnosis": True,
            "geometric_estimates_require_validation": True,
            "units": "voxel units unless calibrated by imaging metadata",
        },
    }


def validation_report() -> str:
    rows = [
        ("Disc directional heights", "MEDIUM", "Computed from reconstructed mesh vertex projections and local PCA axes. Needs voxel spacing and radiologist validation for clinical reporting."),
        ("Disc cross-sectional area", "MEDIUM", "Uses mesh footprint and volume/height proxies. Reasonable geometric feature, but not calibrated physical area without voxel spacing."),
        ("Canal measurements", "LOW", "No canal segmentation exists. Values are geometric estimates derived from vertebral dimensions and centerline level."),
        ("Foraminal measurements", "LOW", "No foraminal boundary segmentation exists. Values are proxy estimates using disc height and adjacent vertebral spacing."),
        ("Disc degeneration features", "LOW", "Relative internal geometry scores only. They are not diagnostic grades and do not use MRI signal intensity."),
        ("Vertebral slippage", "MEDIUM", "Centroid displacement along AP axis is measurable, but clinical slippage needs calibrated radiographic landmarks."),
        ("Curvature", "MEDIUM", "Computed from vertebral centroid centerline. Useful for system geometry, but not a radiographic Cobb-angle substitute."),
    ]
    lines = ["ORTHOTWIN PHASE 4 MEASUREMENT VALIDATION", "=" * 42, ""]
    for metric, confidence, reason in rows:
        lines.extend([metric, f"  Confidence: {confidence}", f"  Reason: {reason}", ""])
    return "\n".join(lines)


def phase4_report() -> str:
    return "\n".join(
        [
            "ORTHOTWIN PHASE 4 RADIOLOGY MEASUREMENTS REPORT",
            "=" * 50,
            "",
            "1. What measurements now exist?",
            "   Disc directional heights, disc area estimates, canal estimates, foraminal estimates, curvature, slippage, and relative degeneration features.",
            "",
            "2. Which measurements are clinically meaningful?",
            "   Disc height, AP displacement/slippage proxy, and centerline curvature are meaningful geometric measurements, pending calibration and validation.",
            "",
            "3. Which measurements remain geometric estimates?",
            "   Canal area, foraminal area, degeneration scores, and area estimates remain geometric estimates.",
            "",
            "4. Which measurements need MRI metadata?",
            "   Any measurement requiring millimeters or square millimeters needs voxel spacing, orientation, slice thickness, and acquisition metadata.",
            "",
            "5. Which measurements need radiologist validation?",
            "   All clinical interpretations need validation. Canal, foraminal, degeneration, and slippage measurements especially require landmark review.",
            "",
            "Scope",
            "   No diagnosis was made. No segmentation was recomputed or modified.",
        ]
    )


def plot_bar(labels: list[str], values: list[float], title: str, ylabel: str, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(labels, values, color="#2563eb")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def plot_line(labels: list[str], values: list[float], title: str, ylabel: str, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(labels, values, marker="o", color="#0f766e")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=35)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def arrange_orthtwin2_files() -> list[dict[str, Any]]:
    if not ORTHOTWIN2_ROOT.exists():
        return []
    moves = []
    for path in sorted(ORTHOTWIN2_ROOT.rglob("*")):
        if not path.is_file():
            continue
        lower = path.name.lower()
        if path.suffix.lower() in {".pth", ".pt"}:
            destination = PROJECT_ROOT / "models" / "checkpoints" / path.name
        elif lower.endswith(".pdf"):
            destination = PROJECT_ROOT / "docs" / path.name
        elif lower.endswith(".txt"):
            destination = PROJECT_ROOT / "archive" / "OrthoTwin2" / path.name
        elif lower.endswith(".pkl"):
            destination = PROJECT_ROOT / "measurements" / "geometry" / path.name
        elif lower.endswith(".json") and ("mesh" in lower or "status" in lower):
            destination = PROJECT_ROOT / "measurements" / "geometry" / path.name
        elif lower.endswith(".png") and "reconstruction" in lower:
            destination = PROJECT_ROOT / "visualization" / "reconstruction" / path.name
        elif lower.endswith(".png"):
            destination = PROJECT_ROOT / "visualization" / "segmentation" / path.name
        else:
            destination = PROJECT_ROOT / "archive" / "OrthoTwin2" / path.name
        destination = collision_safe(destination, "orthtwin2")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(destination))
        moves.append({"source": str(path), "destination": str(destination)})
    return moves


def collision_safe(destination: Path, suffix: str) -> Path:
    if not destination.exists():
        return destination
    candidate = destination.with_name(f"{destination.stem}_{suffix}{destination.suffix}")
    counter = 2
    while candidate.exists():
        candidate = destination.with_name(f"{destination.stem}_{suffix}_{counter}{destination.suffix}")
        counter += 1
    return candidate


def run_phase4() -> dict[str, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    orthtwin2_moves = arrange_orthtwin2_files()
    state = load_json(STATE_PATH)
    meshes = load_meshes(MESH_PATH)
    coordinates = load_json(COORDINATE_PATH)
    graph = load_json(GRAPH_PATH)
    centerline = load_json(CENTERLINE_PATH)

    disc_heights = compute_disc_heights(state, meshes, coordinates)
    disc_areas = compute_disc_areas(state, meshes, disc_heights)
    canal = compute_canal_measurements(state, centerline)
    foraminal = compute_foraminal_measurements(state, graph)
    degeneration = compute_disc_degeneration_features(state, meshes, disc_heights)
    slippage = compute_vertebral_slippage(state, coordinates)
    curvature = compute_curvature(centerline)
    clinical_state = build_clinical_state(state, disc_heights, disc_areas, canal, foraminal, degeneration, slippage, curvature)

    paths = {
        "radiology_disc_heights": OUTPUT_DIR / "radiology_disc_heights.json",
        "disc_area_measurements": OUTPUT_DIR / "disc_area_measurements.json",
        "canal_measurements": OUTPUT_DIR / "canal_measurements.json",
        "foraminal_measurements": OUTPUT_DIR / "foraminal_measurements.json",
        "disc_degeneration_features": OUTPUT_DIR / "disc_degeneration_features.json",
        "vertebral_slippage": OUTPUT_DIR / "vertebral_slippage.json",
        "curvature_measurements": OUTPUT_DIR / "curvature_measurements.json",
        "clinical_state_vector": PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json",
        "measurement_validation_report": REPORT_DIR / "measurement_validation_report.txt",
        "phase4_report": REPORT_DIR / "phase4_radiology_measurements_report.txt",
        "disc_height_plot": VIS_DIR / "phase4_disc_height_plot.png",
        "canal_area_plot": VIS_DIR / "phase4_canal_area_plot.png",
        "foraminal_area_plot": VIS_DIR / "phase4_foraminal_area_plot.png",
        "curvature_plot": VIS_DIR / "phase4_curvature_plot.png",
        "slippage_plot": VIS_DIR / "phase4_slippage_plot.png",
        "orthtwin2_arrangement_log": MANIFEST_DIR / "orthtwin2_arrangement_log.json",
        "phase4_manifest": MANIFEST_DIR / "phase4_manifest.json",
    }

    write_json(paths["radiology_disc_heights"], disc_heights)
    write_json(paths["disc_area_measurements"], disc_areas)
    write_json(paths["canal_measurements"], canal)
    write_json(paths["foraminal_measurements"], foraminal)
    write_json(paths["disc_degeneration_features"], degeneration)
    write_json(paths["vertebral_slippage"], slippage)
    write_json(paths["curvature_measurements"], curvature)
    write_json(paths["clinical_state_vector"], clinical_state)
    write_text(paths["measurement_validation_report"], validation_report())
    write_text(paths["phase4_report"], phase4_report())
    write_json(paths["orthtwin2_arrangement_log"], {"generated_utc": utc_now(), "moves": orthtwin2_moves})

    disc_labels = [item["disc_name"] for item in disc_heights["disc_heights"].values()]
    plot_bar(disc_labels, [item["mean_height"] for item in disc_heights["disc_heights"].values()], "Disc Height Plot", "Mean height (voxel units)", paths["disc_height_plot"])
    canal_labels = [item["vertebra_name"] for item in canal["canal_measurements"].values()]
    plot_bar(canal_labels, [item["canal_area"] for item in canal["canal_measurements"].values()], "Canal Area Plot", "Estimated area (voxel squared)", paths["canal_area_plot"])
    foraminal_labels = [item["disc_name"] for item in foraminal["foraminal_measurements"].values()]
    foraminal_values = [(item["left_foraminal_area"] + item["right_foraminal_area"]) / 2.0 for item in foraminal["foraminal_measurements"].values()]
    plot_bar(foraminal_labels, foraminal_values, "Foraminal Area Plot", "Estimated area (voxel squared)", paths["foraminal_area_plot"])
    plot_line([item["at_node"] for item in curvature["local_curvature"]], [item["curvature_estimate"] for item in curvature["local_curvature"]], "Curvature Plot", "Curvature estimate", paths["curvature_plot"])
    slippage_labels = list(slippage["vertebral_slippage"].keys())
    plot_bar(slippage_labels, [item["relative_anterior_posterior_displacement"] for item in slippage["vertebral_slippage"].values()], "Slippage Plot", "AP displacement (voxel units)", paths["slippage_plot"])

    manifest = {
        "generated_utc": utc_now(),
        "phase": "OrthoTwin Phase 4",
        "all_outputs_exist": all(path.exists() for key, path in paths.items() if key != "phase4_manifest"),
        "outputs": {key: str(path) for key, path in paths.items() if key != "phase4_manifest"},
        "input_files": {
            "patient_state_vector_v2": str(STATE_PATH),
            "reconstructed_structures": str(MESH_PATH),
            "spine_coordinate_system": str(COORDINATE_PATH),
            "spine_graph": str(GRAPH_PATH),
        },
        "orthtwin2_files_arranged": len(orthtwin2_moves),
        "scope": "Existing files only. No retraining, inference, segmentation recomputation, or mask modification.",
    }
    write_json(paths["phase4_manifest"], manifest)
    return paths


if __name__ == "__main__":
    generated = run_phase4()
    print("RADIOLOGY MEASUREMENT ENGINE COMPLETE")
    for name, path in generated.items():
        print(f"{name}: {path}")
