"""Create presentation-ready simulation visualizations from Phase 7/8 outputs.

Visualization only: this script does not create simulations, measurements,
models, or modify existing scientific outputs.
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
OUT = ROOT / "visualization" / "simulation_suite"
GALLERY = OUT / "showcase_gallery"


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    GALLERY.mkdir(parents=True, exist_ok=True)


def fig_save(fig, name: str) -> Path:
    path = OUT / name
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def footer(fig) -> None:
    fig.text(0.5, 0.015, "Visualization only. Existing Phase 7/8 outputs. No new simulation or measurement.", ha="center", fontsize=8, color="#586069")


def mesh_structures() -> dict:
    return load_json(ROOT / "state" / "mesh" / "mesh_state_vector.json").get("structures", {})


def structure_points() -> tuple[list[str], np.ndarray, list[str]]:
    structures = mesh_structures()
    names, points, types = [], [], []
    for item in structures.values():
        centroid = item.get("centroid")
        if not centroid:
            continue
        names.append(item.get("name", item.get("id", "")))
        points.append(centroid)
        types.append(item.get("type", "structure"))
    return names, np.asarray(points, dtype=float), types


def get_disc_key(result: dict) -> str | None:
    for key in ["disc", "target_disc", "affected_disc"]:
        if isinstance(result.get(key), str):
            return result[key]
    for obj in result.get("changed_anatomical_structures", []):
        if isinstance(obj, str) and obj.startswith("disc"):
            return obj
    return None


def inventory() -> dict:
    phase7_outputs = sorted([str(path) for path in (ROOT / "state" / "surgery").glob("*.json")])
    phase7_reports = sorted([str(path) for path in (ROOT / "reports" / "phase7").glob("*") if path.is_file()])
    phase8_outputs = sorted([str(path) for path in (ROOT / "state" / "mesh").glob("*.json")])
    phase8_reports = sorted([str(path) for path in (ROOT / "reports" / "phase8").glob("*") if path.is_file()])
    state_outputs = sorted([str(path) for path in (ROOT / "state").rglob("*.json")])
    comparison_outputs = [
        str(ROOT / "reports" / "phase7" / "surgical_comparison_matrix.json"),
        str(ROOT / "reports" / "phase7" / "geometry_vs_rule_based_breakdown.json"),
        str(ROOT / "reports" / "phase8" / "mesh_impact_analysis.json"),
    ]
    structures = mesh_structures()
    data = {
        "generated_utc": NOW,
        "scope": "Existing Phase 7 and Phase 8 visualization audit only.",
        "available_meshes": [
            {
                "id": sid,
                "name": item.get("name"),
                "type": item.get("type"),
                "vertex_count": item.get("vertex_count"),
                "face_count": item.get("face_count"),
            }
            for sid, item in structures.items()
        ],
        "available_surgery_states": phase7_outputs,
        "available_mesh_outputs": phase8_outputs,
        "available_reports": phase7_reports + phase8_reports,
        "available_state_outputs": state_outputs,
        "available_comparisons": comparison_outputs,
    }
    save_json(OUT / "visualization_inventory.json", data)
    return data


def draw_spine_scatter(ax, highlight: dict[str, float] | None = None, title: str = "") -> None:
    names, pts, types = structure_points()
    if pts.size == 0:
        ax.text(0.5, 0.5, "No mesh state points", ha="center")
        return
    colors = ["#3b82f6" if t == "vertebra" else "#f97316" for t in types]
    sizes = [90 if t == "vertebra" else 70 for t in types]
    values = []
    for name in names:
        key = name.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        values.append(highlight.get(key, 0) if highlight else 0)
    if highlight:
        scatter = ax.scatter(pts[:, 2], pts[:, 1], c=values, cmap="magma", s=np.array(sizes) + 60, edgecolor="#222", linewidth=0.5)
        plt.colorbar(scatter, ax=ax, fraction=0.046, pad=0.04, label="Change magnitude")
    else:
        ax.scatter(pts[:, 2], pts[:, 1], c=colors, s=sizes, edgecolor="#222", linewidth=0.5)
    order = np.argsort(pts[:, 1])[::-1]
    ax.plot(pts[order, 2], pts[order, 1], color="#111827", linewidth=1.5, alpha=0.7, label="Centerline proxy")
    for name, p, typ in zip(names, pts, types):
        label = name.replace("Vertebra ", "V").replace("Disc ", "D")
        ax.text(p[2] + 1.5, p[1], label, fontsize=8, color="#111827")
    ax.arrow(pts[:, 2].min(), pts[:, 1].min(), 18, 0, head_width=2, color="#374151")
    ax.arrow(pts[:, 2].min(), pts[:, 1].min(), 0, 18, head_width=2, color="#374151")
    ax.text(pts[:, 2].min() + 20, pts[:, 1].min(), "X", fontsize=9)
    ax.text(pts[:, 2].min(), pts[:, 1].min() + 20, "Y", fontsize=9)
    ax.set_aspect("equal", adjustable="box")
    ax.grid(alpha=0.2)
    ax.set_title(title)
    ax.set_xlabel("Voxel axis projection")
    ax.set_ylabel("Superior/inferior projection")


def patient_alpha_showcase() -> Path:
    fig, ax = plt.subplots(figsize=(10, 11))
    draw_spine_scatter(ax, title="Patient Alpha Baseline: Mesh State, Labels, Axes, Centerline")
    fig.suptitle("Patient Alpha Digital Spine Showcase", fontsize=22, fontweight="bold")
    footer(fig)
    return fig_save(fig, "patient_alpha_showcase.png")


def existing_image_panel(src: Path, out_name: str, title: str) -> Path:
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.axis("off")
    if src.exists():
        ax.imshow(plt.imread(src))
    else:
        ax.text(0.5, 0.5, f"Missing source\n{src.name}", ha="center", va="center")
    ax.set_title(title, fontsize=18, fontweight="bold")
    footer(fig)
    return fig_save(fig, out_name)


def displacement_map_from_result(result_path: Path, out_name: str, title: str) -> Path:
    result = load_json(result_path)
    changed = result.get("changed_structures", result.get("affected_structures", []))
    if isinstance(changed, dict):
        changed = list(changed.keys())
    highlight: dict[str, float] = {}
    for entry in changed or []:
        if isinstance(entry, str):
            key = entry.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
            highlight[key] = 1.0
    for item in result.get("operations", []):
        sid = item.get("structure_id") or item.get("object_id")
        if sid:
            highlight[str(sid).lower()] = float(item.get("average_displacement", 1.0) or 1.0)
    fig, ax = plt.subplots(figsize=(10, 9))
    draw_spine_scatter(ax, highlight=highlight, title=title)
    fig.suptitle(title, fontsize=20, fontweight="bold")
    footer(fig)
    return fig_save(fig, out_name)


def mesh_heatmap(surgery_name: str, out_name: str, title: str) -> Path:
    impact = load_json(ROOT / "reports" / "phase8" / "mesh_impact_analysis.json").get("surgeries", [])
    selected = next((item for item in impact if item.get("surgery") == surgery_name), {})
    affected = selected.get("affected_structures", [])
    highlight = {}
    for name in affected:
        key = str(name).lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        highlight[key] = float(selected.get("average_displacement", 1.0))
    fig, ax = plt.subplots(figsize=(10, 9))
    draw_spine_scatter(ax, highlight=highlight, title=title)
    caption = f"Vertices moved: {selected.get('vertices_moved', 0)} | Avg displacement: {selected.get('average_displacement', 0):.3f}"
    ax.text(0.02, 0.02, caption, transform=ax.transAxes, fontsize=10, bbox={"fc": "white", "ec": "#d0d7de", "alpha": 0.85})
    fig.suptitle(title, fontsize=20, fontweight="bold")
    footer(fig)
    return fig_save(fig, out_name)


def alignment_centerline_comparison() -> Path:
    base = load_json(ROOT / "state" / "mesh" / "mesh_state_vector.json").get("structures", {})
    aligned = load_json(ROOT / "state" / "surgery" / "rebuilt_state_alignment_correction.json")
    names, pts, types = structure_points()
    corrected = pts.copy()
    changed = aligned.get("geometry_changes", [])
    for change in changed:
        if change.get("object_id") == "vertebra_6" and change.get("after"):
            for i, name in enumerate(names):
                if name == "Vertebra 6":
                    after = change["after"]
                    corrected[i] = [after[2], after[1], after[0]] if len(after) == 3 else corrected[i]
    order = np.argsort(pts[:, 1])[::-1]
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.plot(pts[order, 2], pts[order, 1], marker="o", label="Baseline centerline proxy", color="#2563eb")
    ax.plot(corrected[order, 2], corrected[order, 1], marker="o", label="Alignment-corrected proxy", color="#dc2626")
    ax.legend()
    ax.grid(alpha=0.25)
    ax.set_title("Alignment Centerline Comparison", fontsize=18, fontweight="bold")
    ax.set_xlabel("Voxel axis projection")
    ax.set_ylabel("Superior/inferior projection")
    footer(fig)
    return fig_save(fig, "alignment_centerline_comparison.png")


def fusion_relationship_visualization() -> Path:
    fig, ax = plt.subplots(figsize=(10, 9))
    draw_spine_scatter(ax, title="Fusion Relationship Visualization")
    names, pts, _ = structure_points()
    lookup = {name: p for name, p in zip(names, pts)}
    if "Vertebra 5" in lookup and "Vertebra 6" in lookup:
        a, b = lookup["Vertebra 5"], lookup["Vertebra 6"]
        ax.plot([a[2], b[2]], [a[1], b[1]], color="#dc2626", linewidth=6, alpha=0.65, label="Fusion constraint")
        ax.legend()
        ax.text((a[2] + b[2]) / 2 + 3, (a[1] + b[1]) / 2, "Locked relationship", color="#991b1b", fontweight="bold")
    fig.suptitle("Fusion: Relationship/Constraint Change", fontsize=20, fontweight="bold")
    footer(fig)
    return fig_save(fig, "fusion_relationship_visualization.png")


def state_change_dashboard() -> Path:
    baseline = load_json(ROOT / "state" / "patient_states" / "clinical_state_vector.json")
    phase7 = load_json(ROOT / "reports" / "phase7" / "geometry_vs_rule_based_breakdown.json").get("surgeries", {})
    surgeries = ["implant", "spacer", "fusion", "alignment_correction"]
    affected = [len(phase7.get(s, {}).get("changed_anatomical_structures", [])) for s in surgeries]
    geom = [len(phase7.get(s, {}).get("geometry_changes", [])) for s in surgeries]
    rule = [len(phase7.get(s, {}).get("values_changed_because_deterministic_rules_changed_them", [])) for s in surgeries]
    curvature = [float(phase7.get(s, {}).get("geometry_magnitude_proxy", 0) or 0) for s in surgeries]
    disc_height_changes = [len(phase7.get(s, {}).get("recomputed_measurements", {}).get("disc_height_changes", {})) for s in surgeries]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    axes[0, 0].bar(surgeries, affected, color="#2563eb")
    axes[0, 0].set_title("Affected Structures")
    axes[0, 1].bar(surgeries, geom, color="#16a34a")
    axes[0, 1].set_title("Geometry Changes")
    axes[1, 0].bar(surgeries, rule, color="#f97316")
    axes[1, 0].set_title("Rule-Rebuilt State Sections")
    axes[1, 1].bar(surgeries, disc_height_changes, color="#7c3aed")
    axes[1, 1].set_title("Disc Height Records Changed")
    for ax in axes.ravel():
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle("State Change Dashboard", fontsize=22, fontweight="bold")
    footer(fig)
    return fig_save(fig, "state_change_dashboard.png")


def surgery_comparison_dashboard() -> Path:
    phase7 = load_json(ROOT / "reports" / "phase7" / "geometry_vs_rule_based_breakdown.json").get("surgeries", {})
    impact = {item.get("surgery"): item for item in load_json(ROOT / "reports" / "phase8" / "mesh_impact_analysis.json").get("surgeries", [])}
    rows = ["implant", "spacer", "fusion", "alignment_correction"]
    cols = ["structures affected", "geometry changed", "state changed", "graph changed", "displacement magnitude"]
    matrix = []
    for row in rows:
        data = phase7.get(row, {})
        impact_key = "alignment" if row == "alignment_correction" else row
        matrix.append(
            [
                len(data.get("changed_anatomical_structures", [])),
                len(data.get("geometry_changes", [])),
                len(data.get("values_changed_because_deterministic_rules_changed_them", [])),
                len(data.get("relationship_changes", [])),
                float(impact.get(impact_key, {}).get("average_displacement", 0)),
            ]
        )
    fig, ax = plt.subplots(figsize=(12, 5))
    im = ax.imshow(matrix, cmap="viridis")
    ax.set_xticks(range(len(cols)), labels=cols, rotation=25, ha="right")
    ax.set_yticks(range(len(rows)), labels=rows)
    for i in range(len(rows)):
        for j in range(len(cols)):
            ax.text(j, i, f"{matrix[i][j]:.2f}" if j == 4 else str(int(matrix[i][j])), ha="center", va="center", color="white", fontweight="bold")
    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Surgery Comparison Dashboard", fontsize=20, fontweight="bold")
    footer(fig)
    return fig_save(fig, "surgery_comparison_dashboard.png")


def digital_twin_story() -> Path:
    stages = ["MRI", "Segmentation", "Reconstruction", "State", "Surgery", "Updated State", "Comparison"]
    fig, ax = plt.subplots(figsize=(15, 5))
    ax.axis("off")
    xs = np.linspace(0.06, 0.94, len(stages))
    colors = ["#dbeafe", "#cffafe", "#dcfce7", "#fef9c3", "#fee2e2", "#ede9fe", "#e5e7eb"]
    for i, (x, stage) in enumerate(zip(xs, stages)):
        ax.scatter([x], [0.55], s=1800, color=colors[i], edgecolor="#111827", linewidth=1.2)
        ax.text(x, 0.55, stage, ha="center", va="center", fontsize=10, fontweight="bold")
        if i < len(stages) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.055, 0.55), xytext=(x + 0.055, 0.55), arrowprops={"arrowstyle": "->", "lw": 2})
    ax.text(0.5, 0.18, "Existing outputs only: Phase 7 geometry-aware surgery + Phase 8 mesh-level transformations", ha="center", fontsize=11)
    ax.set_title("Digital Twin Storyboard", fontsize=23, fontweight="bold")
    footer(fig)
    return fig_save(fig, "digital_twin_story.png")


def generate_all() -> list[Path]:
    outputs = [patient_alpha_showcase()]
    outputs.append(existing_image_panel(ROOT / "visualization" / "mesh" / "implant_mesh_before_after.png", "implant_before_after.png", "Implant Surgery: Baseline vs Implant"))
    outputs.append(mesh_heatmap("implant", "implant_difference_heatmap.png", "Implant Difference Heatmap"))
    outputs.append(existing_image_panel(ROOT / "visualization" / "mesh" / "spacer_mesh_before_after.png", "spacer_before_after.png", "Spacer Surgery: Baseline vs Spacer"))
    outputs.append(mesh_heatmap("spacer", "spacer_difference_heatmap.png", "Spacer Difference Heatmap"))
    outputs.append(existing_image_panel(ROOT / "visualization" / "mesh" / "fusion_mesh_before_after.png", "fusion_before_after.png", "Fusion: Baseline vs Constraint State"))
    outputs.append(fusion_relationship_visualization())
    outputs.append(existing_image_panel(ROOT / "visualization" / "surgery" / "alignment_before_after.png", "alignment_before_after.png", "Alignment Correction: Baseline vs Corrected"))
    outputs.append(alignment_centerline_comparison())
    outputs.append(mesh_heatmap("implant", "mesh_displacement_heatmap_implant.png", "Mesh Displacement Heatmap: Implant"))
    outputs.append(mesh_heatmap("spacer", "mesh_displacement_heatmap_spacer.png", "Mesh Displacement Heatmap: Spacer"))
    outputs.append(displacement_map_from_result(ROOT / "state" / "surgery" / "alignment_geometry_result.json", "mesh_displacement_heatmap_alignment.png", "Alignment Displacement Map: Phase 7 Geometry Output"))
    outputs.append(state_change_dashboard())
    outputs.append(surgery_comparison_dashboard())
    outputs.append(digital_twin_story())
    return outputs


def build_gallery(outputs: list[Path]) -> None:
    selected = [
        "patient_alpha_showcase.png",
        "implant_before_after.png",
        "spacer_before_after.png",
        "fusion_before_after.png",
        "alignment_before_after.png",
        "mesh_displacement_heatmap_implant.png",
        "mesh_displacement_heatmap_spacer.png",
        "mesh_displacement_heatmap_alignment.png",
        "state_change_dashboard.png",
        "surgery_comparison_dashboard.png",
        "digital_twin_story.png",
    ]
    output_map = {path.name: path for path in outputs}
    lines = ["# OrthoTwin Simulation Showcase Gallery\n"]
    descriptions = {
        "patient_alpha_showcase.png": "Hero baseline view with mesh-state labels, coordinate axes, and centerline proxy.",
        "implant_before_after.png": "Existing Phase 8 implant before/after mesh visualization.",
        "spacer_before_after.png": "Existing Phase 8 spacer before/after mesh visualization.",
        "fusion_before_after.png": "Existing Phase 8 fusion before/after constraint visualization.",
        "alignment_before_after.png": "Existing Phase 7 alignment correction comparison.",
        "mesh_displacement_heatmap_implant.png": "Mesh displacement magnitude presentation map for implant output.",
        "mesh_displacement_heatmap_spacer.png": "Mesh displacement magnitude presentation map for spacer output.",
        "mesh_displacement_heatmap_alignment.png": "Available Phase 7 alignment displacement map; not a Phase 8 mesh simulation.",
        "state_change_dashboard.png": "State and rule-rebuild comparison across surgery outputs.",
        "surgery_comparison_dashboard.png": "Rows/columns comparison of affected structures, geometry, state, graph, and displacement.",
        "digital_twin_story.png": "One-slide digital twin workflow story.",
    }
    for name in selected:
        src = output_map.get(name)
        if src and src.exists():
            shutil.copy2(src, GALLERY / name)
            lines.append(f"## {name}\n\n{descriptions[name]}\n\n![{name}]({name})\n")
    (GALLERY / "showcase_index.md").write_text("\n".join(lines), encoding="utf-8")


def summary(outputs: list[Path]) -> None:
    impact = load_json(ROOT / "reports" / "phase8" / "mesh_impact_analysis.json").get("surgeries", [])
    largest = max(impact, key=lambda item: item.get("average_displacement", 0), default={})
    text = f"""ORTHOTWIN VISUALIZATION SUITE COMPLETE

Generated: {NOW}

Number of visualizations generated: {len(outputs)}
Best visualization: patient_alpha_showcase.png
Most dramatic surgery: {largest.get('surgery', 'implant')}
Largest mesh displacement: {largest.get('average_displacement', 0):.4f}
Strongest comparison figure: surgery_comparison_dashboard.png

Scientific boundary:
No new science.
No new measurements.
No new simulations.
Visualization only.

Note:
The alignment displacement visualization is based on existing Phase 7 geometry output. Phase 8 mesh outputs include implant, collapse, spacer, and fusion; there is no separate Phase 8 alignment mesh simulation in the frozen outputs.
"""
    (OUT / "simulation_visualization_summary.txt").write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    inv = inventory()
    outputs = generate_all()
    build_gallery(outputs)
    summary(outputs)
    save_json(
        OUT / "simulation_visualization_manifest.json",
        {
            "generated_utc": NOW,
            "visualization_count": len(outputs),
            "visualizations": [str(path) for path in outputs],
            "all_visualizations_exist": all(path.exists() for path in outputs),
            "gallery": str(GALLERY),
            "gallery_index": str(GALLERY / "showcase_index.md"),
            "inventory": str(OUT / "visualization_inventory.json"),
            "source_scope": inv["scope"],
            "no_new_science": True,
            "no_new_measurements": True,
            "no_new_simulations": True,
        },
    )
    print("ORTHOTWIN VISUALIZATION SUITE COMPLETE")
    print("Number of visualizations generated:", len(outputs))
    print("Best visualization: patient_alpha_showcase.png")
    print("Most dramatic surgery: implant/spacer by existing average displacement")
    print("Largest mesh displacement: see mesh_impact_analysis.json and summary")
    print("Strongest comparison figure: surgery_comparison_dashboard.png")


if __name__ == "__main__":
    main()
