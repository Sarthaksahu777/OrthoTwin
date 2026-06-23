"""Build the OrthoTwin Showcase Edition.

This curates existing V1 figures and reports into a GitHub/demo/PPT-ready
showcase layer. It does not create simulations, measurements, models, or alter
scientific outputs.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHOWCASE = ROOT / "showcase"
NOW = datetime.now(timezone.utc).isoformat()


SECTIONS = [
    "hero",
    "segmentation",
    "reconstruction",
    "measurements",
    "graph",
    "state",
    "surgery",
    "mesh",
    "dashboards",
    "limitations",
    "architecture",
    "reports",
    "ppt_assets",
]

PPT_SECTIONS = [
    "01_problem",
    "02_segmentation",
    "03_reconstruction",
    "04_measurements",
    "05_state",
    "06_graph",
    "07_surgery",
    "08_mesh",
    "09_results",
    "10_limitations",
    "11_future",
]


def ensure_dirs() -> None:
    for section in SECTIONS:
        (SHOWCASE / section).mkdir(parents=True, exist_ok=True)
    for section in PPT_SECTIONS:
        (SHOWCASE / "ppt_assets" / section).mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def copy(src: Path, dst_dir: Path, name: str | None = None) -> Path | None:
    if not src.exists():
        return None
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (name or src.name)
    shutil.copy2(src, dst)
    return dst


def visual_candidates() -> list[dict]:
    candidates = []
    for path in (ROOT / "visualization").rglob("*"):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".svg"}:
            rel = path.relative_to(ROOT)
            size = path.stat().st_size
            name = path.name.lower()
            score = 0
            reasons = []
            if any(token in name for token in ["showcase", "dashboard", "story", "gallery", "before_after", "heatmap"]):
                score += 4
                reasons.append("presentation_composite")
            if any(part in str(rel).lower() for part in ["simulation_suite", "presentation", "release"]):
                score += 3
                reasons.append("presentation_or_release_folder")
            if size > 80_000:
                score += 2
                reasons.append("high_resolution_or_composite")
            if any(token in name for token in ["candidate", "mask_slice", "weighted_loss", "error"]):
                score -= 3
                reasons.append("technical_support_or_error_artifact")
            tier = "A" if score >= 6 else "B" if score >= 2 else "C"
            candidates.append({"path": str(path), "relative_path": str(rel), "name": path.name, "size_bytes": size, "score": score, "tier": tier, "reasons": reasons})
    candidates.sort(key=lambda x: (x["tier"], -x["score"], x["name"]))
    return candidates


def curated_sources() -> dict[str, list[tuple[str, Path]]]:
    v = ROOT / "visualization"
    p = v / "presentation"
    s = v / "simulation_suite"
    return {
        "hero": [
            ("patient_alpha_showcase.png", s / "patient_alpha_showcase.png"),
            ("implant_before_after.png", s / "implant_before_after.png"),
            ("mesh_displacement_heatmap_implant.png", s / "mesh_displacement_heatmap_implant.png"),
            ("surgery_comparison_dashboard.png", s / "surgery_comparison_dashboard.png"),
            ("digital_twin_story.png", s / "digital_twin_story.png"),
        ],
        "segmentation": [
            ("segmentation_pipeline.png", p / "segmentation_pipeline.png"),
            ("segmentation_comparison.png", p / "segmentation_comparison.png"),
            ("segmentation_statistics.png", p / "segmentation_statistics.png"),
        ],
        "reconstruction": [
            ("reconstruction_gallery.png", p / "reconstruction_gallery.png"),
            ("reconstruction_full.png", p / "reconstruction_full.png"),
            ("reconstruction_labeled.png", p / "reconstruction_labeled.png"),
        ],
        "measurements": [
            ("measurement_dashboard.png", p / "measurement_dashboard.png"),
            ("disc_height_comparison.png", p / "disc_height_comparison.png"),
            ("curvature_visualization.png", p / "curvature_visualization.png"),
            ("alignment_visualization.png", p / "alignment_visualization.png"),
        ],
        "graph": [
            ("spine_graph_presentation.png", p / "spine_graph_presentation.png"),
            ("graph_explanation.png", p / "graph_explanation.png"),
        ],
        "state": [
            ("state_vector_visualization.png", p / "state_vector_visualization.png"),
            ("digital_twin_overview.png", p / "digital_twin_overview.png"),
            ("digital_twin_story.png", s / "digital_twin_story.png"),
        ],
        "surgery": [
            ("implant_before_after.png", s / "implant_before_after.png"),
            ("implant_difference_heatmap.png", s / "implant_difference_heatmap.png"),
            ("spacer_before_after.png", s / "spacer_before_after.png"),
            ("spacer_difference_heatmap.png", s / "spacer_difference_heatmap.png"),
            ("fusion_before_after.png", s / "fusion_before_after.png"),
            ("fusion_relationship_visualization.png", s / "fusion_relationship_visualization.png"),
            ("alignment_before_after.png", s / "alignment_before_after.png"),
            ("alignment_centerline_comparison.png", s / "alignment_centerline_comparison.png"),
        ],
        "mesh": [
            ("mesh_before_after.png", p / "mesh_before_after.png"),
            ("mesh_displacement_heatmap_implant.png", s / "mesh_displacement_heatmap_implant.png"),
            ("mesh_displacement_heatmap_spacer.png", s / "mesh_displacement_heatmap_spacer.png"),
            ("mesh_displacement_heatmap_alignment.png", s / "mesh_displacement_heatmap_alignment.png"),
            ("mesh_change_heatmap.png", p / "mesh_change_heatmap.png"),
        ],
        "dashboards": [
            ("executive_dashboard.png", p / "executive_dashboard.png"),
            ("outcome_comparison_dashboard.png", p / "outcome_comparison_dashboard.png"),
            ("state_change_dashboard.png", s / "state_change_dashboard.png"),
            ("surgery_comparison_dashboard.png", s / "surgery_comparison_dashboard.png"),
            ("surgery_ranking_dashboard.png", p / "surgery_ranking_dashboard.png"),
        ],
        "limitations": [
            ("orthotwin_poster.png", p / "orthotwin_poster.png"),
            ("calibration_decision_flowchart.png", v / "calibration" / "calibration_decision_flowchart.png"),
            ("spacing_candidate_dashboard.png", v / "calibration" / "spacing_candidate_dashboard.png"),
        ],
        "architecture": [
            ("architecture_diagram.png", v / "release" / "architecture_diagram.png"),
            ("orthotwin_pipeline_timeline.png", p / "orthotwin_pipeline_timeline.png"),
            ("digital_twin_story.png", s / "digital_twin_story.png"),
        ],
    }


def copy_curated() -> list[dict]:
    copied = []
    for section, files in curated_sources().items():
        for name, src in files:
            dst = copy(src, SHOWCASE / section, name)
            if dst:
                copied.append({"section": section, "name": name, "path": str(dst), "source": str(src)})
    return copied


def copy_reports() -> list[dict]:
    reports = [
        ROOT / "ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md",
        ROOT / "ORTHOTWIN_V1_RELEASE_NOTES.md",
        ROOT / "reports" / "master_audit" / "orthotwin_master_audit.md",
        ROOT / "reports" / "master_audit" / "orthotwin_master_audit.pdf",
        ROOT / "reports" / "calibration" / "phase95_calibration_audit.txt",
        ROOT / "reports" / "calibration" / "physical_calibration_decision.json",
        ROOT / "reports" / "release_v1" / "orthotwin_v1_classification.json",
        ROOT / "presentation" / "ppt_storyboard.md",
        ROOT / "presentation" / "demo_script.md",
        ROOT / "presentation" / "orthotwin_showcase_report.md",
    ]
    copied = []
    for src in reports:
        dst = copy(src, SHOWCASE / "reports")
        if dst:
            copied.append({"name": dst.name, "path": str(dst), "source": str(src)})
    return copied


def write_docs() -> None:
    (SHOWCASE / "README.md").write_text(
        """# OrthoTwin V1.0 Showcase Edition

This folder is the curated demo layer for OrthoTwin V1.0.

It contains only copied or summarized outputs from the frozen repository. It does not create new measurements, simulations, models, or scientific claims.

## Recommended Start

1. Open `hero/patient_alpha_showcase.png`.
2. Open `architecture/digital_twin_story.png`.
3. Review `surgery/surgery_showcase.md`.
4. Review `mesh/mesh_showcase.md`.
5. End with `limitations/limitations_summary.md`.

## Best Figures

- `hero/patient_alpha_showcase.png`
- `hero/implant_before_after.png`
- `hero/mesh_displacement_heatmap_implant.png`
- `hero/surgery_comparison_dashboard.png`
- `hero/digital_twin_story.png`

## Scientific Boundary

OrthoTwin V1.0 is a Digital Twin Prototype. It is not a clinical tool, does not diagnose, does not recommend treatment, and does not claim validated biomechanics.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "ppt_assets" / "README.md").write_text(
        """# PPT Assets

The folders are organized for an 11-part presentation:

1. `01_problem`
2. `02_segmentation`
3. `03_reconstruction`
4. `04_measurements`
5. `05_state`
6. `06_graph`
7. `07_surgery`
8. `08_mesh`
9. `09_results`
10. `10_limitations`
11. `11_future`

Use these images directly in slides. They are copied from existing OrthoTwin outputs and do not introduce new scientific results.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "hero" / "hero_gallery.md").write_text(
        """# Hero Gallery

## patient_alpha_showcase.png
The cleanest baseline figure: labels, coordinate axes, centerline proxy, and the core anatomy story.

## implant_before_after.png
Shows the most intuitive intervention comparison: baseline versus implant geometry.

## mesh_displacement_heatmap_implant.png
Demonstrates the Phase 8 upgrade from metric-level changes to mesh-level displacement visualization.

## surgery_comparison_dashboard.png
Best single comparison figure for judges and reviewers.

## digital_twin_story.png
Explains the full pipeline from MRI to updated state and comparison.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "architecture" / "architecture_summary.md").write_text(
        """# Architecture Summary

OrthoTwin V1.0 is organized as:

MRI -> Segmentation -> Reconstruction -> Measurements -> State -> Graph -> Scenario/Surgery -> Mesh Transformations -> Evidence Audit -> Reports

This folder contains architecture, pipeline, and story diagrams suitable for slides and GitHub documentation.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "surgery" / "surgery_showcase.md").write_text(
        """# Surgery Showcase

Included interventions:

- Implant: before/after and heatmap.
- Spacer: before/after and heatmap.
- Fusion: before/after plus relationship visualization.
- Alignment correction: before/after plus centerline comparison.

Scientific boundary: these are existing deterministic geometry/state visualizations, not clinical surgery predictions.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "mesh" / "mesh_showcase.md").write_text(
        """# Mesh Showcase

This folder highlights the Phase 8 mesh-level upgrade.

Included:

- Mesh before/after comparisons.
- Vertex displacement heatmaps.
- Difference/change heatmaps.

Scientific boundary: vertex transformations are geometric demonstrations, not FEM or validated biomechanics.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "state" / "digital_twin_explainer.md").write_text(
        """# Digital Twin Explainer

OrthoTwin turns disconnected outputs into structured state:

- Patient state
- Clinical state
- Mesh state
- Spine graph
- Surgery states
- Comparison outputs

The value is the connected representation: anatomy, geometry, relationships, and limitations can be inspected together.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "limitations" / "limitations_summary.md").write_text(
        """# Limitations Summary

Be brutally honest:

- Physical calibration remains blocked.
- No trusted Patient Alpha spacing/orientation chain has been recovered.
- No FEM or validated biomechanics exists.
- No clinical validation exists.
- No diagnosis or treatment recommendation is supported.
- Load, risk, progression, and scenario rankings are deterministic proxies.

This is a Digital Twin Prototype, not clinical software.
""",
        encoding="utf-8",
    )

    (SHOWCASE / "ORTHOTWIN_SHOWCASE_SUMMARY.md").write_text(
        """# OrthoTwin Showcase Summary

## What Was Built

A curated showcase layer for OrthoTwin V1.0, collecting the strongest existing visuals, reports, dashboards, and explanation files into a GitHub/demo/PPT-ready structure.

## What Works

- Segmentation and reconstruction presentation.
- State and graph explanation.
- Surgery and mesh transformation demonstration.
- Dashboards for comparison.
- Evidence and limitations communication.

## What Is Estimated

- Canal/foraminal areas.
- Load/risk/progression scores.
- Scenario rankings.
- Surgical outcomes beyond geometry/rule demonstrations.

## What Remains Future Work

- Physical calibration recovery.
- Measurement validation.
- Real biomechanics/FEM with materials and boundary conditions.
- Clinical and longitudinal validation.

## Why This Is A Digital Twin Prototype

It connects patient anatomy, measurements, state, graph relationships, scenarios, surgery outputs, mesh transformations, and evidence audits. It is not yet clinically or biomechanically validated.
""",
        encoding="utf-8",
    )


def copy_ppt_assets(curated: list[dict]) -> int:
    by_name = {Path(item["path"]).name: Path(item["path"]) for item in curated}
    mapping = {
        "01_problem": ["digital_twin_story.png", "executive_dashboard.png"],
        "02_segmentation": ["segmentation_pipeline.png", "segmentation_comparison.png"],
        "03_reconstruction": ["reconstruction_gallery.png", "patient_alpha_showcase.png"],
        "04_measurements": ["measurement_dashboard.png", "disc_height_comparison.png"],
        "05_state": ["state_vector_visualization.png", "digital_twin_overview.png"],
        "06_graph": ["spine_graph_presentation.png", "graph_explanation.png"],
        "07_surgery": ["implant_before_after.png", "spacer_before_after.png", "fusion_relationship_visualization.png", "alignment_before_after.png"],
        "08_mesh": ["mesh_before_after.png", "mesh_displacement_heatmap_implant.png", "mesh_displacement_heatmap_spacer.png"],
        "09_results": ["surgery_comparison_dashboard.png", "state_change_dashboard.png", "outcome_comparison_dashboard.png"],
        "10_limitations": ["orthotwin_poster.png", "calibration_decision_flowchart.png"],
        "11_future": ["architecture_diagram.png", "orthotwin_pipeline_timeline.png"],
    }
    count = 0
    for section, names in mapping.items():
        for name in names:
            src = by_name.get(name)
            if src and src.exists():
                shutil.copy2(src, SHOWCASE / "ppt_assets" / section / name)
                count += 1
    return count


def manifest(curated: list[dict], reports: list[dict], ranking: list[dict], ppt_count: int) -> None:
    ppt_assets = [str(path) for path in (SHOWCASE / "ppt_assets").rglob("*") if path.is_file()]
    required_dirs = SECTIONS
    validation = {
        "generated_utc": NOW,
        "all_required_directories_exist": all((SHOWCASE / section).exists() for section in required_dirs),
        "top_level_readme_exists": (SHOWCASE / "README.md").exists(),
        "ppt_readme_exists": (SHOWCASE / "ppt_assets" / "README.md").exists(),
        "hero_gallery_exists": (SHOWCASE / "hero" / "hero_gallery.md").exists(),
        "architecture_summary_exists": (SHOWCASE / "architecture" / "architecture_summary.md").exists(),
        "surgery_showcase_exists": (SHOWCASE / "surgery" / "surgery_showcase.md").exists(),
        "mesh_showcase_exists": (SHOWCASE / "mesh" / "mesh_showcase.md").exists(),
        "digital_twin_explainer_exists": (SHOWCASE / "state" / "digital_twin_explainer.md").exists(),
        "limitations_summary_exists": (SHOWCASE / "limitations" / "limitations_summary.md").exists(),
        "showcase_summary_exists": (SHOWCASE / "ORTHOTWIN_SHOWCASE_SUMMARY.md").exists(),
        "curated_figure_count": len(curated),
        "ppt_asset_count": ppt_count,
        "classification": "Digital Twin Prototype",
        "no_new_science": True,
    }
    save_json(SHOWCASE / "showcase_validation.json", validation)
    save_json(
        SHOWCASE / "showcase_manifest.json",
        {
            "generated_utc": NOW,
            "classification": "Digital Twin Prototype",
            "figures": curated,
            "reports": reports,
            "ppt_assets": ppt_assets,
            "ppt_asset_count": ppt_count,
            "top_10_figures": [item["name"] for item in curated[:10]],
            "recommended_ppt_assets": [
                "patient_alpha_showcase.png",
                "digital_twin_story.png",
                "reconstruction_gallery.png",
                "measurement_dashboard.png",
                "spine_graph_presentation.png",
                "implant_before_after.png",
                "mesh_displacement_heatmap_implant.png",
                "surgery_comparison_dashboard.png",
                "orthotwin_poster.png",
                "calibration_decision_flowchart.png",
            ],
            "figure_ranking_file": str(SHOWCASE / "showcase_figure_ranking.json"),
            "validation_file": str(SHOWCASE / "showcase_validation.json"),
            "no_new_science": True,
            "no_new_measurements": True,
            "no_new_simulations": True,
        },
    )


def main() -> None:
    ensure_dirs()
    ranking = visual_candidates()
    save_json(SHOWCASE / "showcase_figure_ranking.json", ranking)
    curated = copy_curated()
    reports = copy_reports()
    write_docs()
    ppt_count = copy_ppt_assets(curated)
    manifest(curated, reports, ranking, ppt_count)
    print("ORTHOTWIN SHOWCASE EDITION COMPLETE")
    print("Total showcase figures:", len(curated))
    print("Top 10 figures:", ", ".join([item["name"] for item in curated[:10]]))
    print("Recommended PPT assets:", ppt_count)
    print("Repository classification: Digital Twin Prototype")


if __name__ == "__main__":
    main()
