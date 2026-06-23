"""Generate OrthoTwin presentation and demo assets from frozen V1 outputs.

This is a communication layer only. It composes existing images and plots
already-generated JSON outputs without creating new measurements, simulations,
AI models, or scientific claims.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()
PRESENTATION_DIR = ROOT / "presentation"
VIS_DIR = ROOT / "visualization" / "presentation"
PPT_DIR = PRESENTATION_DIR / "ppt_assets"


def ensure_dirs() -> None:
    for directory in [
        PRESENTATION_DIR,
        VIS_DIR,
        PPT_DIR,
        PPT_DIR / "01_problem",
        PPT_DIR / "02_segmentation",
        PPT_DIR / "03_reconstruction",
        PPT_DIR / "04_measurements",
        PPT_DIR / "05_state",
        PPT_DIR / "06_graph",
        PPT_DIR / "07_surgery",
        PPT_DIR / "08_mesh",
        PPT_DIR / "09_results",
        PPT_DIR / "10_limitations",
        PPT_DIR / "11_future",
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def image(path: str) -> Path:
    return VIS_DIR / path


def imshow_file(ax, path: Path, title: str = "") -> None:
    ax.axis("off")
    if path.exists():
        ax.imshow(plt.imread(path))
    else:
        ax.text(0.5, 0.5, f"Missing\n{path.name}", ha="center", va="center", fontsize=12)
    if title:
        ax.set_title(title, fontsize=13, fontweight="bold")


def add_footer(fig, text: str = "Research prototype visualization. Not clinical validation.") -> None:
    fig.text(0.5, 0.015, text, ha="center", fontsize=8, color="#5b6166")


def save_fig(fig, path: Path) -> None:
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def bars(path: Path, labels: list[str], values: list[float], title: str, ylabel: str, color="#2b6f9e") -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.bar(labels, values, color=color)
    ax.set_title(title, fontsize=17, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.25)
    ax.tick_params(axis="x", rotation=35)
    for index, value in enumerate(values):
        ax.text(index, value, f"{value:.1f}", ha="center", va="bottom", fontsize=8)
    add_footer(fig)
    save_fig(fig, path)


def line_plot(path: Path, labels: list[str], values: list[float], title: str, ylabel: str, color="#6c5ce7") -> None:
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(labels, values, marker="o", color=color, linewidth=2.5)
    ax.fill_between(labels, values, alpha=0.12, color=color)
    ax.set_title(title, fontsize=17, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(alpha=0.25)
    ax.tick_params(axis="x", rotation=35)
    add_footer(fig)
    save_fig(fig, path)


def text_panel(path: Path, title: str, sections: list[tuple[str, str]], figsize=(12, 7)) -> None:
    fig, ax = plt.subplots(figsize=figsize)
    ax.axis("off")
    ax.set_title(title, fontsize=22, fontweight="bold", pad=18)
    y = 0.9
    for heading, body in sections:
        ax.text(0.04, y, heading, fontsize=14, fontweight="bold", color="#1f3a4a", transform=ax.transAxes)
        y -= 0.055
        ax.text(0.06, y, body, fontsize=11, color="#263238", transform=ax.transAxes, wrap=True, va="top")
        y -= 0.13
    add_footer(fig)
    save_fig(fig, path)


def presentation_dataset() -> dict:
    clinical = load_json(ROOT / "state" / "patient_states" / "clinical_state_vector.json")
    mesh_inventory = load_json(ROOT / "state" / "mesh" / "mesh_inventory.json")
    audit = load_json(ROOT / "reports" / "release_v1" / "orthotwin_v1_repository_audit.json")
    classification = load_json(ROOT / "reports" / "release_v1" / "orthotwin_v1_classification.json")
    phase8 = load_json(ROOT / "reports" / "phase8" / "mesh_impact_analysis.json")
    phase9 = load_json(ROOT / "reports" / "phase9" / "patient_alpha_spacing_audit.json")
    validation = load_json(ROOT / "reports" / "release_v1" / "orthotwin_v1_validation.json")
    structures = mesh_inventory.get("structures", [])
    return {
        "generated_utc": NOW,
        "scope": "Presentation dataset assembled from existing frozen V1 outputs only.",
        "patient": {
            "id": clinical.get("patient_id", "patient_alpha"),
            "disc_count": len(clinical.get("disc_heights", {})),
            "canal_level_count": len(clinical.get("canal_areas", {})),
        },
        "repository": {
            "total_files": audit.get("total_files"),
            "total_reports": audit.get("total_reports"),
            "total_state_files": audit.get("total_state_files"),
            "total_visualizations": audit.get("total_visualizations"),
            "total_simulation_outputs": audit.get("total_simulation_outputs"),
            "classification": classification.get("classification", "Digital Twin Prototype"),
        },
        "mesh": {
            "structure_count": len(structures),
            "vertebra_count": len([s for s in structures if "Vertebra" in s.get("name", "")]),
            "disc_count": len([s for s in structures if "Disc" in s.get("name", "")]),
            "vertex_count": sum(s.get("vertex_count", 0) for s in structures),
            "face_count": sum(s.get("face_count", 0) for s in structures),
        },
        "disc_heights": clinical.get("disc_heights", {}),
        "curvature": clinical.get("curvature", {}),
        "alignment": clinical.get("alignment", {}),
        "mesh_impact": phase8.get("surgeries", []),
        "calibration": {
            "status": phase9.get("status"),
            "confidence": phase9.get("confidence"),
            "spacing_found": phase9.get("spacing_found"),
        },
        "validation": validation,
        "important_paths": {
            "segmentation_visuals": str(ROOT / "visualization" / "segmentation"),
            "reconstruction_visuals": str(ROOT / "visualization" / "reconstruction"),
            "state_visuals": str(ROOT / "visualization" / "state"),
            "surgery_visuals": str(ROOT / "visualization" / "surgery"),
            "mesh_visuals": str(ROOT / "visualization" / "mesh"),
            "release_reports": str(ROOT / "reports" / "release_v1"),
        },
    }


def generate_segmentation() -> list[Path]:
    base = ROOT / "visualization" / "segmentation"
    outputs = []
    fig, axes = plt.subplots(1, 4, figsize=(15, 4))
    for ax, filename, title in zip(
        axes,
        [
            "patient_alpha_mri_slice_8.png",
            "patient_alpha_overlay_slice_8.png",
            "patient_alpha_pred_mask_slice_8.png",
            "patient_alpha_gt_mask_slice_8.png",
        ],
        ["Original MRI", "Segmentation Overlay", "Cleaned/Predicted Mask", "Reference Mask"],
    ):
        imshow_file(ax, base / filename, title)
    fig.suptitle("Segmentation Pipeline", fontsize=20, fontweight="bold")
    add_footer(fig)
    out = image("segmentation_pipeline.png")
    save_fig(fig, out)
    outputs.append(out)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    imshow_file(axes[0], base / "patient_alpha_overlay_slice_8.png", "Overlay")
    imshow_file(axes[1], base / "weighted_loss_results.png", "Training/Validation Artifact")
    fig.suptitle("Segmentation Comparison", fontsize=20, fontweight="bold")
    add_footer(fig)
    out = image("segmentation_comparison.png")
    save_fig(fig, out)
    outputs.append(out)

    state = load_json(ROOT / "state" / "patient_states" / "patient_state_vector_v2.json")
    seg = state.get("segmentation", {})
    labels = ["Structures", "Discs", "Canal Levels"]
    clinical = load_json(ROOT / "state" / "patient_states" / "clinical_state_vector.json")
    values = [
        float(seg.get("num_structures", 14) or 14),
        float(len(clinical.get("disc_heights", {}))),
        float(len(clinical.get("canal_areas", {}))),
    ]
    bars(image("segmentation_statistics.png"), labels, values, "Segmentation Statistics", "Count", "#4a90a4")
    outputs.append(image("segmentation_statistics.png"))
    return outputs


def generate_reconstruction() -> list[Path]:
    base = ROOT / "visualization" / "reconstruction"
    mesh_dir = ROOT / "visualization" / "mesh"
    outputs = []
    copies = {
        "reconstruction_full.png": base / "patient_alpha_reconstruction_matplotlib_front.png",
        "reconstruction_exploded.png": mesh_dir / "3d_mesh_overlays.png",
        "reconstruction_labeled.png": base / "patient_alpha_reconstruction_matplotlib_angled.png",
    }
    for out_name, src in copies.items():
        fig, ax = plt.subplots(figsize=(10, 8))
        imshow_file(ax, src, out_name.replace("_", " ").replace(".png", "").title())
        add_footer(fig)
        out = image(out_name)
        save_fig(fig, out)
        outputs.append(out)

    fig, axes = plt.subplots(2, 2, figsize=(13, 10))
    for ax, src, title in zip(
        axes.ravel(),
        [
            base / "patient_alpha_reconstruction_matplotlib_front.png",
            base / "patient_alpha_reconstruction_matplotlib_side.png",
            base / "patient_alpha_reconstruction_matplotlib_angled.png",
            mesh_dir / "3d_mesh_overlays.png",
        ],
        ["Front", "Side", "Angled", "Overlay"],
    ):
        imshow_file(ax, src, title)
    fig.suptitle("3D Reconstruction Gallery", fontsize=20, fontweight="bold")
    add_footer(fig)
    out = image("reconstruction_gallery.png")
    save_fig(fig, out)
    outputs.append(out)
    return outputs


def generate_measurements(dataset: dict) -> list[Path]:
    outputs = []
    disc_heights = dataset["disc_heights"]
    labels = [key.replace("disc_", "D") for key in disc_heights]
    means = [float(value.get("mean_height", 0)) for value in disc_heights.values()]
    mins = [float(value.get("minimum_height", 0)) for value in disc_heights.values()]
    maxs = [float(value.get("maximum_height", 0)) for value in disc_heights.values()]
    bars(image("disc_height_comparison.png"), labels, means, "Disc Height Comparison", "Mean height (voxel units)", "#2f80ed")
    outputs.append(image("disc_height_comparison.png"))

    clinical = load_json(ROOT / "state" / "patient_states" / "clinical_state_vector.json")
    areas = clinical.get("disc_areas", {})
    area_values = [float(value.get("average_cross_sectional_area", 0)) for value in areas.values()]
    bars(image("disc_volume_comparison.png"), labels[: len(area_values)], area_values, "Disc Area / Volume Proxy Comparison", "Area proxy (voxel squared)", "#27ae60")
    outputs.append(image("disc_volume_comparison.png"))

    curvature = clinical.get("curvature", {}).get("local_curvature", [])
    curv_labels = [item.get("at_node", f"L{i}") for i, item in enumerate(curvature)]
    curv_values = [float(item.get("curvature_estimate", 0)) for item in curvature]
    line_plot(image("curvature_visualization.png"), curv_labels, curv_values, "Curvature Visualization", "Curvature estimate", "#9b51e0")
    outputs.append(image("curvature_visualization.png"))

    align = clinical.get("alignment", {}).get("vertebral_pair_alignment", {})
    align_labels = [key.replace("vertebra_", "V").replace("__", "-") for key in align]
    align_values = [float(value.get("angle_difference_degrees", 0)) for value in align.values()]
    bars(image("alignment_visualization.png"), align_labels, align_values, "Alignment Visualization", "Angle difference (degrees)", "#f2994a")
    outputs.append(image("alignment_visualization.png"))

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    axes[0, 0].bar(labels, means, color="#2f80ed")
    axes[0, 0].set_title("Mean Disc Height")
    axes[0, 1].bar(labels, np.array(maxs) - np.array(mins), color="#eb5757")
    axes[0, 1].set_title("Height Range")
    axes[1, 0].plot(curv_labels, curv_values, marker="o", color="#9b51e0")
    axes[1, 0].set_title("Local Curvature")
    axes[1, 1].bar(align_labels, align_values, color="#f2994a")
    axes[1, 1].set_title("Pair Alignment")
    for ax in axes.ravel():
        ax.grid(alpha=0.25)
        ax.tick_params(axis="x", rotation=35)
    fig.suptitle("Measurement Dashboard", fontsize=22, fontweight="bold")
    add_footer(fig)
    out = image("measurement_dashboard.png")
    save_fig(fig, out)
    outputs.append(out)
    return outputs


def generate_graph_and_state(dataset: dict) -> list[Path]:
    outputs = []
    graph_img = ROOT / "visualization" / "state" / "spine_graph.png"
    fig, ax = plt.subplots(figsize=(10, 8))
    imshow_file(ax, graph_img, "Spine Graph Presentation")
    add_footer(fig)
    out = image("spine_graph_presentation.png")
    save_fig(fig, out)
    outputs.append(out)

    graph = load_json(ROOT / "state" / "graphs" / "spine_graph.json")
    node_count = len(graph.get("nodes", [])) if isinstance(graph.get("nodes"), list) else len(graph.get("nodes", {}))
    edge_count = len(graph.get("edges", []))
    text_panel(
        image("graph_explanation.png"),
        "Graph Explanation",
        [
            ("Connected System", f"The spine graph stores {node_count or 14} anatomy nodes connected by {edge_count or 'disc-vertebra'} relationships."),
            ("Presentation Meaning", "The graph lets the demo explain the spine as a connected system rather than isolated measurements."),
            ("Scientific Boundary", "Connectivity is real repository structure; load and risk propagation remain deterministic proxies."),
        ],
    )
    outputs.append(image("graph_explanation.png"))

    bars(
        image("state_vector_visualization.png"),
        ["Discs", "Canal Levels", "Mesh Structures", "Reports", "Sim Outputs"],
        [
            dataset["patient"]["disc_count"],
            dataset["patient"]["canal_level_count"],
            dataset["mesh"]["structure_count"],
            dataset["repository"]["total_reports"],
            dataset["repository"]["total_simulation_outputs"],
        ],
        "Digital Twin State Contents",
        "Count",
        "#34495e",
    )
    outputs.append(image("state_vector_visualization.png"))

    text_panel(
        image("digital_twin_overview.png"),
        "Digital Twin Overview",
        [
            ("State", "Clinical and patient state vectors collect measurements, geometry, graph links, and metadata."),
            ("Interventions", "Scenario, geometry surgery, and mesh surgery layers compare deterministic changes against baseline."),
            ("Evidence", "Release and Phase 9 reports separate real, derived, estimated, blocked, and unknown components."),
            ("Classification", dataset["repository"].get("classification", "Digital Twin Prototype")),
        ],
    )
    outputs.append(image("digital_twin_overview.png"))
    return outputs


def generate_surgery_and_mesh(dataset: dict) -> list[Path]:
    outputs = []
    surgery_base = ROOT / "visualization" / "surgery"
    surgery_map = {
        "implant_demo.png": surgery_base / "implant_before_after.png",
        "spacer_demo.png": surgery_base / "spacer_before_after.png",
        "fusion_demo.png": surgery_base / "fusion_before_after.png",
        "alignment_demo.png": surgery_base / "alignment_before_after.png",
    }
    for out_name, src in surgery_map.items():
        fig, ax = plt.subplots(figsize=(11, 7))
        imshow_file(ax, src, out_name.replace("_", " ").replace(".png", "").title())
        add_footer(fig)
        out = image(out_name)
        save_fig(fig, out)
        outputs.append(out)

    mesh_base = ROOT / "visualization" / "mesh"
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    imshow_file(axes[0], mesh_base / "implant_mesh_before_after.png", "Implant Mesh")
    imshow_file(axes[1], mesh_base / "spacer_mesh_before_after.png", "Spacer Mesh")
    fig.suptitle("Mesh Before / After", fontsize=20, fontweight="bold")
    add_footer(fig)
    out = image("mesh_before_after.png")
    save_fig(fig, out)
    outputs.append(out)

    surgeries = dataset.get("mesh_impact", [])
    labels = [item.get("surgery", "") for item in surgeries]
    avg = [float(item.get("average_displacement", 0)) for item in surgeries]
    maxv = [float(item.get("max_displacement", 0)) for item in surgeries]
    moved = [float(item.get("vertices_moved", 0)) for item in surgeries]
    bars(image("mesh_displacement_map.png"), labels, avg, "Mesh Vertex Displacement", "Average displacement (voxel units)", "#2d9cdb")
    outputs.append(image("mesh_displacement_map.png"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].bar(labels, moved, color="#56ccf2")
    axes[0].set_title("Vertices Moved")
    axes[1].bar(labels, maxv, color="#bb6bd9")
    axes[1].set_title("Maximum Displacement")
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=25)
    fig.suptitle("Mesh Change Heatmap", fontsize=20, fontweight="bold")
    add_footer(fig)
    out = image("mesh_change_heatmap.png")
    save_fig(fig, out)
    outputs.append(out)
    return outputs


def generate_outcome_timeline_poster(dataset: dict) -> list[Path]:
    outputs = []
    surgeries = dataset.get("mesh_impact", [])
    labels = [item.get("surgery", "") for item in surgeries]
    avg = [float(item.get("average_displacement", 0)) for item in surgeries]
    moved = [float(item.get("vertices_moved", 0)) for item in surgeries]

    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    axes[0, 0].bar(labels, avg, color="#2d9cdb")
    axes[0, 0].set_title("Average Mesh Displacement")
    axes[0, 1].bar(labels, moved, color="#27ae60")
    axes[0, 1].set_title("Vertices Moved")
    axes[1, 0].bar(["Reports", "States", "Visuals", "Sim Outputs"], [dataset["repository"]["total_reports"], dataset["repository"]["total_state_files"], dataset["repository"]["total_visualizations"], dataset["repository"]["total_simulation_outputs"]], color="#34495e")
    axes[1, 0].set_title("Repository Outputs")
    axes[1, 1].bar(["Spacing Found", "Validation"], [1 if dataset["calibration"]["spacing_found"] else 0, 1], color=["#eb5757", "#f2c94c"])
    axes[1, 1].set_title("Evidence Boundary")
    for ax in axes.ravel():
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=25)
    fig.suptitle("Outcome Comparison Dashboard", fontsize=22, fontweight="bold")
    add_footer(fig)
    out = image("outcome_comparison_dashboard.png")
    save_fig(fig, out)
    outputs.append(out)

    score = [a - (m / max(moved) if max(moved) else 0) * 0.05 for a, m in zip(avg, moved)]
    bars(image("surgery_ranking_dashboard.png"), labels, score, "Surgery Demo Ranking Dashboard", "Presentation effect proxy", "#8e44ad")
    outputs.append(image("surgery_ranking_dashboard.png"))

    stages = ["MRI", "Segmentation", "Reconstruction", "Measurements", "State", "Graph", "Simulation", "Mesh Surgery", "Evidence"]
    fig, ax = plt.subplots(figsize=(14, 4.8))
    ax.axis("off")
    xs = np.linspace(0.05, 0.95, len(stages))
    for i, (x, stage) in enumerate(zip(xs, stages)):
        ax.scatter([x], [0.55], s=900, color="#eaf2f8", edgecolor="#2c3e50", linewidth=1.5)
        ax.text(x, 0.55, str(i + 1), ha="center", va="center", fontsize=13, fontweight="bold")
        ax.text(x, 0.25, stage, ha="center", va="center", fontsize=10)
        if i < len(stages) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.035, 0.55), xytext=(x + 0.035, 0.55), arrowprops={"arrowstyle": "->", "lw": 1.5})
    ax.set_title("OrthoTwin Pipeline Timeline", fontsize=22, fontweight="bold")
    add_footer(fig)
    out = image("orthotwin_pipeline_timeline.png")
    save_fig(fig, out)
    outputs.append(out)

    text_panel(
        image("orthotwin_poster.png"),
        "OrthoTwin V1 Poster",
        [
            ("Input", "Patient Alpha segmentation-derived anatomy and reconstructed mesh geometry."),
            ("Processing", "Measurements, state vectors, graph relationships, scenarios, longitudinal rules, geometry surgery, and mesh surgery."),
            ("Outputs", "Reports, dashboards, visualizations, mesh impact analysis, and evidence matrices."),
            ("Validation Boundary", "Research prototype only. Physical calibration, FEM, and clinical validation remain missing."),
            ("Future Work", "Recover spacing, validate measurements, add real biomechanics only with material and boundary data."),
        ],
        figsize=(13, 9),
    )
    outputs.append(image("orthotwin_poster.png"))

    text_panel(
        image("executive_dashboard.png"),
        "Executive Dashboard",
        [
            ("Patient Alpha", f"{dataset['mesh']['structure_count']} structures, {dataset['mesh']['vertex_count']:,} vertices, {dataset['mesh']['face_count']:,} faces."),
            ("Repository", f"{dataset['repository']['total_reports']} reports, {dataset['repository']['total_simulation_outputs']} simulation outputs, classification: Digital Twin Prototype."),
            ("Most Important Limitation", "Physical calibration remains blocked; voxel-space measurements should not be treated as physical mm values."),
            ("Most Valuable Capability", "Connected spine state plus mesh-level transformation demonstration."),
        ],
        figsize=(13, 8),
    )
    outputs.append(image("executive_dashboard.png"))
    return outputs


def copy_ppt_assets(image_paths: list[Path]) -> int:
    mapping = {
        "01_problem": ["orthotwin_pipeline_timeline.png", "executive_dashboard.png"],
        "02_segmentation": ["segmentation_pipeline.png", "segmentation_comparison.png", "segmentation_statistics.png"],
        "03_reconstruction": ["reconstruction_full.png", "reconstruction_exploded.png", "reconstruction_labeled.png", "reconstruction_gallery.png"],
        "04_measurements": ["measurement_dashboard.png", "disc_height_comparison.png", "disc_volume_comparison.png", "curvature_visualization.png", "alignment_visualization.png"],
        "05_state": ["state_vector_visualization.png", "digital_twin_overview.png"],
        "06_graph": ["spine_graph_presentation.png", "graph_explanation.png"],
        "07_surgery": ["implant_demo.png", "spacer_demo.png", "fusion_demo.png", "alignment_demo.png"],
        "08_mesh": ["mesh_before_after.png", "mesh_displacement_map.png", "mesh_change_heatmap.png"],
        "09_results": ["outcome_comparison_dashboard.png", "surgery_ranking_dashboard.png"],
        "10_limitations": ["orthotwin_poster.png"],
        "11_future": ["orthotwin_poster.png", "orthotwin_pipeline_timeline.png"],
    }
    available = {path.name: path for path in image_paths}
    copied = 0
    for folder, names in mapping.items():
        target_dir = PPT_DIR / folder
        for name in names:
            src = available.get(name)
            if src and src.exists():
                shutil.copy2(src, target_dir / name)
                copied += 1
    return copied


def write_story_docs(dataset: dict, counts: dict) -> None:
    storyboard = """# OrthoTwin PPT Storyboard

## Slide 1: Title / What OrthoTwin Is
Key Figure: executive_dashboard.png
Key Message: OrthoTwin V1 is a digital twin prototype, not a clinical tool.
Speaker Notes: Introduce Patient Alpha and the research-prototype boundary.
Expected Duration: 20 seconds

## Slide 2: Problem
Key Figure: orthotwin_pipeline_timeline.png
Key Message: Segmentation outputs need to become connected, explainable anatomy systems.
Speaker Notes: Explain the gap between masks, measurements, and twin-style reasoning.
Expected Duration: 30 seconds

## Slide 3: Segmentation
Key Figure: segmentation_pipeline.png
Key Message: The pipeline starts from existing segmentation-derived anatomy.
Speaker Notes: Show MRI, overlay, cleaned/predicted mask, and reference artifact.
Expected Duration: 40 seconds

## Slide 4: Reconstruction
Key Figure: reconstruction_gallery.png
Key Message: Anatomy is reconstructed into 3D structures.
Speaker Notes: Show front, side, angled, and overlay views.
Expected Duration: 40 seconds

## Slide 5: Measurements
Key Figure: measurement_dashboard.png
Key Message: Geometry-derived measurements populate the clinical-style state.
Speaker Notes: Be explicit that values are voxel-space unless calibrated.
Expected Duration: 50 seconds

## Slide 6: State Vector
Key Figure: state_vector_visualization.png
Key Message: Measurements become one structured patient state.
Speaker Notes: Explain state as the digital twin memory layer.
Expected Duration: 40 seconds

## Slide 7: Spine Graph
Key Figure: spine_graph_presentation.png
Key Message: Vertebrae and discs are connected as a system.
Speaker Notes: This enables relationships and propagation-style demonstrations.
Expected Duration: 45 seconds

## Slide 8: Surgery Demonstrations
Key Figure: implant_demo.png
Key Message: Geometry-aware surgery changes anatomy first, then downstream state.
Speaker Notes: Show implant, spacer, fusion, and alignment figures.
Expected Duration: 60 seconds

## Slide 9: Mesh-Level Upgrade
Key Figure: mesh_before_after.png
Key Message: Phase 8 moves vertices, not only abstract metrics.
Speaker Notes: Mention implant/collapse/spacer move vertices; fusion locks a relationship.
Expected Duration: 50 seconds

## Slide 10: Mesh Impact
Key Figure: mesh_displacement_map.png
Key Message: Mesh effects can be quantified for demo purposes.
Speaker Notes: Avoid clinical interpretation; this is a visualization of deterministic transforms.
Expected Duration: 40 seconds

## Slide 11: Outcome Comparison
Key Figure: outcome_comparison_dashboard.png
Key Message: The prototype can compare scenarios and outputs in one place.
Speaker Notes: Scores are internal and not medical advice.
Expected Duration: 45 seconds

## Slide 12: Evidence and Honesty
Key Figure: orthotwin_poster.png
Key Message: The system separates real, derived, estimated, and missing evidence.
Speaker Notes: Emphasize physical calibration remains blocked.
Expected Duration: 50 seconds

## Slide 13: Why It Matters
Key Figure: digital_twin_overview.png
Key Message: The value is the connected architecture and transparent limitations.
Speaker Notes: Good student/research project because it is ambitious and honest.
Expected Duration: 40 seconds

## Slide 14: Future Work
Key Figure: orthotwin_pipeline_timeline.png
Key Message: Next steps are calibration, validation, and real biomechanics only with data.
Speaker Notes: No fake FEM, no fake validation.
Expected Duration: 35 seconds

## Slide 15: Closing
Key Figure: executive_dashboard.png
Key Message: OrthoTwin V1 is a demonstrable digital twin prototype.
Speaker Notes: Close with the strongest asset and the most important limitation.
Expected Duration: 25 seconds
"""
    (PRESENTATION_DIR / "ppt_storyboard.md").write_text(storyboard, encoding="utf-8")

    demo_script = """# OrthoTwin Demo Script

## 3-Minute Version

1. Open `executive_dashboard.png` and state the classification: Digital Twin Prototype.
2. Show `segmentation_pipeline.png`: existing MRI/segmentation-derived input.
3. Show `reconstruction_gallery.png`: reconstructed anatomy.
4. Show `spine_graph_presentation.png`: connected system representation.
5. Show `mesh_before_after.png` and `mesh_displacement_map.png`: vertex-level mesh transformations.
6. End on `orthotwin_poster.png`: limitations and next research steps.

## 5-Minute Version

1. Start with `orthotwin_pipeline_timeline.png`.
2. Show segmentation and reconstruction figures.
3. Open `measurement_dashboard.png` and explain voxel-space measurement boundary.
4. Show state vector and graph visuals.
5. Show implant, spacer, fusion, and alignment demo images.
6. Show mesh displacement dashboard.
7. End with evidence boundary: physical calibration remains blocked.

## 10-Minute Version

1. Present the problem and pipeline timeline.
2. Walk through segmentation, reconstruction, measurements, state, and graph.
3. Compare geometry surgery and mesh surgery.
4. Show outcome and ranking dashboards as internal demo comparisons only.
5. Review scientific limitations.
6. Explain research roadmap: spacing recovery, measurement validation, FEM only with real material/boundary data, clinical collaboration.

## What To Click

- `presentation/presentation_dataset.json`
- `visualization/presentation/executive_dashboard.png`
- `visualization/presentation/reconstruction_gallery.png`
- `visualization/presentation/measurement_dashboard.png`
- `visualization/presentation/spine_graph_presentation.png`
- `visualization/presentation/mesh_before_after.png`
- `visualization/presentation/orthotwin_poster.png`

## What To Explain

This is a transparent research prototype that connects anatomy, state, graph, scenarios, and mesh-level transformations. It is not a clinical or biomechanical validation claim.
"""
    (PRESENTATION_DIR / "demo_script.md").write_text(demo_script, encoding="utf-8")

    report = f"""# OrthoTwin Showcase Report

## Why Is This Project Interesting?

OrthoTwin turns segmentation-derived spine artifacts into a connected, explainable digital twin prototype. The interesting part is not a single model; it is the full system structure from anatomy to state, graph, scenario comparison, mesh transformation, and evidence reporting.

## What Was Built?

- A presentation dataset assembled from frozen V1 outputs.
- {counts['visualizations']} presentation visualizations and dashboards.
- A PPT asset package with {counts['ppt_assets']} copied assets.
- A 10-15 slide storyboard.
- 3-minute, 5-minute, and 10-minute demo scripts.

## What Is Novel?

The project connects segmentation, 3D reconstruction, state representation, graph structure, deterministic scenarios, geometry surgery, mesh-level transformations, and evidence auditing in one repository.

## What Are The Limitations?

Physical calibration remains blocked. Many measurements are derived or estimated. Load, progression, and scenario ranking are deterministic proxies. No diagnosis, treatment recommendation, clinical validity, or biomechanics claim is made.

## Why Is It A Strong Student Project?

It is ambitious, system-level, visually demonstrable, technically organized, and scientifically honest. It shows how a medical-imaging project can mature from segmentation into a transparent research prototype while clearly identifying what remains missing.

## Most Impressive Figure

`reconstruction_gallery.png` and `mesh_before_after.png`.

## Most Important Story Slide

Slide 12: Evidence and Honesty. It protects the project from overstating what the data can support.
"""
    (PRESENTATION_DIR / "orthotwin_showcase_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    dataset = presentation_dataset()
    save_json(PRESENTATION_DIR / "presentation_dataset.json", dataset)

    outputs: list[Path] = []
    outputs.extend(generate_segmentation())
    outputs.extend(generate_reconstruction())
    outputs.extend(generate_measurements(dataset))
    outputs.extend(generate_graph_and_state(dataset))
    outputs.extend(generate_surgery_and_mesh(dataset))
    outputs.extend(generate_outcome_timeline_poster(dataset))

    ppt_assets = copy_ppt_assets(outputs)
    dashboards = [
        "measurement_dashboard.png",
        "outcome_comparison_dashboard.png",
        "surgery_ranking_dashboard.png",
        "executive_dashboard.png",
    ]
    demo_figures = [
        "segmentation_pipeline.png",
        "reconstruction_gallery.png",
        "implant_demo.png",
        "spacer_demo.png",
        "fusion_demo.png",
        "mesh_before_after.png",
        "orthotwin_poster.png",
    ]
    counts = {
        "visualizations": len(outputs),
        "ppt_assets": ppt_assets,
        "dashboards": len(dashboards),
        "demo_figures": len(demo_figures),
    }
    write_story_docs(dataset, counts)
    save_json(
        PRESENTATION_DIR / "showcase_manifest.json",
        {
            "generated_utc": NOW,
            "visualizations": [str(path) for path in outputs],
            "ppt_assets_directory": str(PPT_DIR),
            "ppt_asset_count": ppt_assets,
            "dashboards": dashboards,
            "demo_figures": demo_figures,
            "all_visualizations_exist": all(path.exists() for path in outputs),
            "all_documents_exist": all(
                (PRESENTATION_DIR / name).exists()
                for name in [
                    "presentation_dataset.json",
                    "ppt_storyboard.md",
                    "demo_script.md",
                    "orthotwin_showcase_report.md",
                ]
            ),
            "most_impressive_figure": "reconstruction_gallery.png",
            "most_important_story_slide": "Slide 12: Evidence and Honesty",
            "no_new_science": True,
        },
    )

    print("ORTHOTWIN SHOWCASE PACKAGE COMPLETE")
    print("Number of Visualizations:", counts["visualizations"])
    print("Number of PPT Assets:", counts["ppt_assets"])
    print("Number of Dashboards:", counts["dashboards"])
    print("Number of Demo Figures:", counts["demo_figures"])
    print("Most Impressive Figure: reconstruction_gallery.png")
    print("Most Important Story Slide: Slide 12 - Evidence and Honesty")


if __name__ == "__main__":
    main()
