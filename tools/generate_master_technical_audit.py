"""Generate the OrthoTwin V1.0 master technical audit.

This is a documentation/audit generator only. It uses existing repository
outputs and existing figures. It does not create science, simulations,
measurements, models, or validation claims.
"""

from __future__ import annotations

import json
import shutil
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()
OUT_DIR = ROOT / "reports" / "master_audit"
ASSET_DIR = OUT_DIR / "orthotwin_master_audit_assets"
MD_PATH = OUT_DIR / "orthotwin_master_audit.md"
PDF_PATH = OUT_DIR / "orthotwin_master_audit.pdf"


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)


def copy_asset(src: Path, name: str | None = None) -> str | None:
    if not src.exists():
        return None
    target = ASSET_DIR / (name or src.name)
    shutil.copy2(src, target)
    return target.name


def collect_assets() -> list[dict]:
    figure_sources = [
        ("Segmentation pipeline", ROOT / "visualization" / "presentation" / "segmentation_pipeline.png"),
        ("Segmentation comparison", ROOT / "visualization" / "presentation" / "segmentation_comparison.png"),
        ("Reconstruction gallery", ROOT / "visualization" / "presentation" / "reconstruction_gallery.png"),
        ("Architecture diagram", ROOT / "visualization" / "release" / "architecture_diagram.png"),
        ("Measurement dashboard", ROOT / "visualization" / "presentation" / "measurement_dashboard.png"),
        ("Spine graph", ROOT / "visualization" / "presentation" / "spine_graph_presentation.png"),
        ("Digital twin overview", ROOT / "visualization" / "presentation" / "digital_twin_overview.png"),
        ("Outcome comparison dashboard", ROOT / "visualization" / "presentation" / "outcome_comparison_dashboard.png"),
        ("Surgery ranking dashboard", ROOT / "visualization" / "presentation" / "surgery_ranking_dashboard.png"),
        ("Implant before after", ROOT / "visualization" / "simulation_suite" / "implant_before_after.png"),
        ("Spacer before after", ROOT / "visualization" / "simulation_suite" / "spacer_before_after.png"),
        ("Fusion relationship", ROOT / "visualization" / "simulation_suite" / "fusion_relationship_visualization.png"),
        ("Alignment centerline", ROOT / "visualization" / "simulation_suite" / "alignment_centerline_comparison.png"),
        ("Mesh displacement implant", ROOT / "visualization" / "simulation_suite" / "mesh_displacement_heatmap_implant.png"),
        ("Mesh displacement spacer", ROOT / "visualization" / "simulation_suite" / "mesh_displacement_heatmap_spacer.png"),
        ("State change dashboard", ROOT / "visualization" / "simulation_suite" / "state_change_dashboard.png"),
        ("Surgery comparison dashboard", ROOT / "visualization" / "simulation_suite" / "surgery_comparison_dashboard.png"),
        ("Digital twin story", ROOT / "visualization" / "simulation_suite" / "digital_twin_story.png"),
        ("Patient Alpha showcase", ROOT / "visualization" / "simulation_suite" / "patient_alpha_showcase.png"),
        ("Scientific limitations poster", ROOT / "visualization" / "presentation" / "orthotwin_poster.png"),
    ]
    assets = []
    for caption, src in figure_sources:
        copied = copy_asset(src)
        if copied:
            assets.append({"caption": caption, "filename": copied, "source": str(src)})
    return assets


def repo_stats() -> dict:
    release = load_json(ROOT / "reports" / "release_v1" / "orthotwin_v1_repository_audit.json")
    mesh = load_json(ROOT / "state" / "mesh" / "mesh_inventory.json")
    validation = load_json(ROOT / "reports" / "release_v1" / "orthotwin_v1_validation.json")
    confidence = load_json(ROOT / "reports" / "phase6" / "confidence_scoring.json")
    spacing = load_json(ROOT / "reports" / "phase9" / "patient_alpha_spacing_audit.json")
    phase95_decision = load_json(ROOT / "reports" / "calibration" / "physical_calibration_decision.json")
    classification = load_json(ROOT / "reports" / "release_v1" / "orthotwin_v1_classification.json")
    github_readiness = load_json(ROOT / "reports" / "repository_minimization" / "github_release_readiness_report.json")
    github_inclusion = load_json(ROOT / "reports" / "repository_minimization" / "github_inclusion_audit.json")
    archive_separation = load_json(ROOT / "reports" / "repository_minimization" / "internal_archive_separation.json")
    showcase_validation = load_json(ROOT / "showcase" / "showcase_validation.json")
    readme_audit = load_json(ROOT / "README_AUDIT.json")
    dataset_inventory = load_json(ROOT / "reports" / "repository_minimization" / "dataset_inventory.json")
    structures = mesh.get("structures", [])
    dicom_record = next((row for row in dataset_inventory.get("datasets", []) if row.get("path") == "data/raw/dicom_series"), {})
    archived_mha_count = len(list((ROOT.parent / "ORTHOTWIN_INTERNAL_DO_NOT_UPLOAD" / "data" / "raw").glob("*.mha"))) if (ROOT.parent / "ORTHOTWIN_INTERNAL_DO_NOT_UPLOAD" / "data" / "raw").exists() else 0
    return {
        "total_files": release.get("total_files", 0),
        "total_reports": release.get("total_reports", 0),
        "total_states": release.get("total_state_files", 0),
        "total_measurements": release.get("total_measurements", 0),
        "total_visualizations": release.get("total_visualizations", 0),
        "total_manifests": release.get("total_manifests", 0),
        "total_simulations": release.get("total_simulation_outputs", 0),
        "total_size_bytes": release.get("total_size_bytes", 0),
        "mesh_structures": len(structures),
        "vertebrae": len([s for s in structures if "Vertebra" in s.get("name", "")]),
        "discs": len([s for s in structures if "Disc" in s.get("name", "")]),
        "vertices": sum(s.get("vertex_count", 0) for s in structures),
        "faces": sum(s.get("face_count", 0) for s in structures),
        "validation": validation,
        "confidence": confidence,
        "spacing": spacing,
        "phase95_decision": phase95_decision,
        "github_readiness": github_readiness,
        "github_inclusion": github_inclusion,
        "archive_separation": archive_separation,
        "showcase_validation": showcase_validation,
        "readme_audit": readme_audit,
        "dicom_record": dicom_record,
        "archived_mri_scans": archived_mha_count,
        "classification": classification.get("classification", "Digital Twin Prototype"),
    }


def make_markdown(assets: list[dict], stats: dict) -> str:
    fig = {asset["caption"]: f"orthotwin_master_audit_assets/{asset['filename']}" for asset in assets}
    confidence = stats.get("confidence", {})
    readiness = confidence.get("digital_twin_readiness_score", "not available")
    evidence_status = stats["spacing"].get("status", "unknown")
    calibration_confidence = stats["spacing"].get("confidence", "unknown")
    phase95_decision = stats.get("phase95_decision", {}).get("decision", "unknown")
    phase95_confidence = stats.get("phase95_decision", {}).get("confidence", "unknown")
    github_readiness = stats.get("github_readiness", {})
    github_inclusion = stats.get("github_inclusion", {})
    archive_separation = stats.get("archive_separation", {})
    showcase_validation = stats.get("showcase_validation", {})
    readme_audit = stats.get("readme_audit", {})
    public_size_mb = github_inclusion.get("public_repository_size_mb", "not available")
    public_file_count = github_inclusion.get("public_repository_file_count", "not available")
    internal_archive_folder = archive_separation.get("internal_archive_folder", "not separated")
    github_score = github_readiness.get("overall_score", "not available")
    readme_score = readme_audit.get("quality_score_out_of_10", "not available")
    curated_figures = showcase_validation.get("curated_figure_count", "not available")
    ppt_assets = showcase_validation.get("ppt_asset_count", "not available")
    archived_mri_scans = stats.get("archived_mri_scans", 0)

    return f"""# OrthoTwin V1.0 Master Technical Audit

Generated: {NOW}

Audience: professors, researchers, engineers, judges, and future collaborators.

Scientific boundary: this document uses existing repository outputs only. It creates no new science, no new measurements, and no new simulations.

---

## Section 1. Executive Summary

OrthoTwin is a research prototype for converting segmentation-derived spine anatomy into a connected, inspectable digital twin representation. It began as an imaging and segmentation project and evolved into a broader architecture for state representation, graph modeling, scenario comparison, geometry-aware surgery, mesh-level transformation, and evidence auditing.

The project was built to solve a common problem in medical-imaging research: segmentation masks and measurements are often useful but disconnected. OrthoTwin organizes those artifacts into a system where anatomy, measurements, relationships, interventions, mesh transformations, limitations, and evidence can be inspected together.

What was achieved is substantial from an engineering perspective. The repository now includes segmentation-derived artifacts, 3D reconstruction outputs, clinical-style state vectors, a spine graph, deterministic scenario outputs, longitudinal projections, geometry-aware surgery outputs, mesh-level transformation outputs, visualization packages, release-level documentation, a curated Showcase Edition, GitHub community files, lightweight CI, and repository minimization reports. The current release audit counted {stats['total_files']} files, {stats['total_reports']} report-like artifacts, {stats['total_states']} state files, {stats['total_measurements']} measurement-related files, {stats['total_visualizations']} visualization artifacts, and {stats['total_simulations']} simulation output files.

The most important unresolved issue is physical calibration. Phase 9 reports `{evidence_status}` with confidence `{calibration_confidence}`. Phase 9.5 reports `{phase95_decision}` with confidence `{phase95_confidence}`. Therefore, voxel-space measurements must not be treated as validated physical millimeter measurements. The project is also missing independent radiologist validation, biomechanics, finite element modeling, longitudinal clinical validation, outcome prediction, and regulatory validation.

After repository minimization, the public GitHub-facing repository is estimated at {public_size_mb} MB and {public_file_count} files. The large internal recovery archive has been physically separated to `{internal_archive_folder}` and is not part of the public upload folder. The GitHub release readiness score is {github_score}/10. The README quality score is {readme_score}/10.

Final classification: **{stats['classification']}**.

![Architecture Diagram]({fig.get('Architecture diagram','')})

---

## Section 2. Project Evolution

The initial ambition was:

```text
MRI -> Segmentation -> World Model -> Surgery Prediction
```

That ambition evolved because each layer exposed a missing prerequisite. Segmentation alone produced masks, but a digital twin requires anatomy, relationships, state, evidence, and controlled transformations. The project therefore moved through the following phases:

| Phase | Focus | Why It Was Added |
|---|---|---|
| Phase 1 | Segmentation | Establish anatomy extraction from MRI-derived data. |
| Phase 2 | State Representation | Convert disconnected files into a structured patient state. |
| Phase 3 | Graph Modeling | Make the spine behave like a connected system. |
| Phase 4 | Measurement Engine | Extract geometry-derived and clinical-style measurements. |
| Phase 5 | Scenario Engine | Compare deterministic future states against baseline. |
| Phase 6 | Evidence Framework | Separate real, derived, estimated, unsupported, and unknown elements. |
| Phase 7 | Geometry-Aware Surgery | Move from metric edits toward anatomy-first transformations. |
| Phase 8 | Mesh-Level Digital Twin | Move from centroid abstractions to vertex-level mesh transformations. |
| Phase 9 | Scientific Grounding Audit | Identify what is scientifically supported and what is blocked. |
| Phase 9.5 | Calibration Recovery Audit | Test whether trusted Patient Alpha physical calibration could be recovered without estimating spacing. |
| V1 Release | Freeze and Packaging | Make the project explainable, auditable, and demonstrable. |
| Showcase Edition | Presentation Layer | Curate the strongest visuals and reports for GitHub, demo, and PPT use. |
| Repository Minimization | Public Repo Hygiene | Move raw datasets, old archives, and duplicate checkpoints out of the public repository surface. |
| GitHub Polish | Open-Source Readiness | Add README, license, contribution files, citation metadata, issue templates, pull request template, and lightweight CI. |

The evolution is important: OrthoTwin did not become a clinical predictor. It became a technical prototype that makes the requirements for a future research-grade digital twin visible.

![Digital Twin Story]({fig.get('Digital twin story','')})

---

## Section 3. Dataset and Inputs

The active case is Patient Alpha. Available artifacts include MRI-related files, segmentation outputs, masks, reconstructed structures, measurement JSON files, state vectors, graph files, simulation outputs, reports, and visualizations.

The repository contains a large imaging footprint, including `.mha`, `.nii.gz`, and `.dcm` files reported by the Phase 9 spacing audit. However, the active Patient Alpha state and reconstructed structures could not be physically calibrated from a provably linked source image header. This is the key dataset limitation.

Known input formats include:

- MHA image files.
- NIfTI-style files.
- DICOM files.
- NumPy arrays.
- Pickled reconstructed mesh structures.
- JSON measurement, state, graph, simulation, and report outputs.

Known limitations:

- Patient Alpha physical spacing is not proven.
- Orientation and slice thickness are not proven for the active state.
- Segmentation-derived geometry depends on earlier masks and preprocessing.
- Clinical ground truth is absent.
- The archived raw imaging collection is intentionally separated from the public repository. It exists for local recovery only and should not be uploaded to GitHub.
- The public repository is designed around reproducibility-critical derived artifacts, source code, reports, and showcase assets rather than full raw-data redistribution.

Repository minimization classified the large DICOM directory as unused for the active V1 showcase pipeline because Phase 9.5 could not link it to the active reconstruction chain. The archived raw MHA count is {archived_mri_scans}, and the DICOM collection record reports {stats.get('dicom_record', {}).get('file_count', 'unknown')} DICOM files and {stats.get('dicom_record', {}).get('size_mb', 'unknown')} MB.

---

## Section 4. Segmentation System

The repository includes segmentation-derived outputs and earlier SegResNet-related artifacts. The V1 audit does not retrain models and does not rerun inference. Segmentation is treated as an existing input layer for the later digital twin architecture.

The segmentation pipeline includes model training artifacts, validation artifacts, prediction masks, cleaned segmentation outputs, and visualization figures. The available segmentation figures show MRI slices, overlays, predicted/cleaned masks, and label-related visual summaries.

The cleanup pipeline included connected-component filtering and voxel cleanup in prior stages. Those outputs support later reconstruction and measurement steps.

Limitations:

- No independent clinical segmentation validation is documented.
- Dice scores and training details are repository artifacts rather than a prospective validation study.
- Any downstream measurement inherits segmentation uncertainty.

![Segmentation Pipeline]({fig.get('Segmentation pipeline','')})

![Segmentation Comparison]({fig.get('Segmentation comparison','')})

---

## Section 5. 3D Reconstruction

The reconstruction layer converts segmentation-derived structures into mesh representations. Phase 8 inventory reports {stats['mesh_structures']} mesh structures: {stats['vertebrae']} vertebrae and {stats['discs']} discs. The mesh inventory contains {stats['vertices']} vertices and {stats['faces']} faces.

For every structure, the mesh state stores centroids, PCA axes, PCA lengths, bounding boxes, volume estimates, and surface area estimates. These are geometry-derived and voxel-space unless calibration is recovered.

PCA methodology is used to describe local shape axes and dimensions. Centerline extraction uses vertebral centroids as a spine-level geometry proxy.

Limitations:

- The meshes are segmentation-derived.
- Mesh geometry is in voxel coordinate space.
- Volume and surface area are geometry estimates, not clinically validated measurements.

![Reconstruction Gallery]({fig.get('Reconstruction gallery','')})

![Patient Alpha Showcase]({fig.get('Patient Alpha showcase','')})

---

## Section 6. Measurement Engine

The measurement engine generates disc heights, disc areas, canal estimates, foraminal estimates, slippage-style displacement, curvature, alignment, PCA dimensions, centroids, bounding boxes, and degeneration-style internal scores.

Evidence classification:

| Measurement Type | Status |
|---|---|
| Mesh centroids | Geometry derived |
| PCA lengths | Geometry derived |
| Bounding boxes | Geometry derived |
| Disc heights | Geometry derived |
| Disc areas | Geometry derived / estimated |
| Canal area | Estimated |
| Foraminal area | Estimated |
| Curvature | Geometry derived |
| Alignment | Geometry derived |
| Load metrics | Rule derived |
| Risk scores | Rule derived |
| Longitudinal progression | Assumption driven |

Calibration limitation: because physical spacing is blocked, voxel units cannot be converted into trusted physical units.

![Measurement Dashboard]({fig.get('Measurement dashboard','')})

---

## Section 7. Digital Twin State Model

The state model is the core abstraction of OrthoTwin. It converts measurements and metadata into structured patient state files. The project contains patient state, clinical state, mesh state, graph state, surgery states, scenario states, and longitudinal future states.

State representation matters because it creates a stable interface between anatomy, measurement, graph relationships, interventions, comparison, and reporting. Without state representation, the project would remain a collection of disconnected measurement files.

The clinical state vector includes disc heights, disc areas, canal estimates, foraminal estimates, curvature, alignment, slippage-style displacement, degeneration features, and scope warnings. The mesh state vector adds vertices-derived metadata such as centroids, PCA axes, bounding boxes, surface area, and volume estimates.

![Digital Twin Overview]({fig.get('Digital twin overview','')})

---

## Section 8. Spine Graph

The spine graph represents vertebrae and discs as connected nodes. Edges define disc-vertebra and vertebra-disc relationships. This graph enables the spine to be represented as a connected system rather than an independent set of measurements.

Graph outputs include nodes, edges, disc relationships, centerline outputs, relative metrics, load path estimates, and validation reports from earlier stages.

The load path model is explicitly not physics. It is a deterministic geometric approximation layer. It should be interpreted as a software mechanism for propagation-style demonstrations, not a biomechanical result.

![Spine Graph]({fig.get('Spine graph','')})

---

## Section 9. Simulation Framework

The simulation framework includes deterministic scenario comparison, future states, intervention framework, and state transition outputs. Its conceptual form is:

```text
Before State -> Action -> After State
```

The scenario engine compares baseline, collapse, restoration, fusion, and implant-style scenarios. The longitudinal engine creates projected future states from configurable assumptions. These systems support demonstration and internal comparison, not clinical prediction.

Limitations:

- No validated physical model.
- No clinical outcome data.
- No patient-specific temporal calibration.
- No treatment recommendation.

![Outcome Comparison Dashboard]({fig.get('Outcome comparison dashboard','')})

![Surgery Ranking Dashboard]({fig.get('Surgery ranking dashboard','')})

---

## Section 10. Geometry-Aware Surgery

Phase 7 introduced surgical objects and anatomy-aware modifications. Supported surgery demonstrations include implant insertion, spacer insertion, fusion, and alignment correction.

The Phase 7 forensic audit found that implant, spacer, and alignment correction are partially geometry-first because they modify disc height, centroids, or local geometry before rebuilding dependent state. Fusion is relationship/constraint-heavy: it creates a fusion relationship and lock but does not substantially modify mesh geometry.

This is a major architectural improvement over direct metric edits, but it is still not a validated surgical simulator.

![Implant Before After]({fig.get('Implant before after','')})

![Spacer Before After]({fig.get('Spacer before after','')})

![Fusion Relationship]({fig.get('Fusion relationship','')})

![Alignment Centerline]({fig.get('Alignment centerline','')})

---

## Section 11. Mesh-Level Digital Twin

Phase 8 moved the architecture from centroid-level geometry toward mesh-level transformations. The mesh transformation engine supports vertex operations such as translation, rotation, scaling, disc height expansion, disc compression, and local alignment changes.

Existing Phase 8 mesh outputs include implant, collapse, spacer, and fusion. Implant, collapse, and spacer move vertices. Fusion preserves geometry and records a relationship/constraint change.

Mesh impact summary:

| Surgery | Interpretation |
|---|---|
| Implant | Vertex-level change around target disc and adjacent vertebrae. |
| Collapse | Vertex-level compression around target disc and adjacent vertebrae. |
| Spacer | Vertex-level local expansion around target disc and neighbors. |
| Fusion | Relationship/constraint change with geometry preserved. |

Limitations:

- Mesh transformation is geometric, not biomechanical.
- No material properties.
- No boundary conditions.
- No FEM solver.
- No clinical validation.

![Mesh Displacement Implant]({fig.get('Mesh displacement implant','')})

![Mesh Displacement Spacer]({fig.get('Mesh displacement spacer','')})

---

## Section 12. Results

The most significant technical result is integration. OrthoTwin now demonstrates a full path from segmentation-derived artifacts to reconstructed mesh, measurements, state, graph, scenarios, surgery, mesh-level transformations, evidence audit, and presentation-ready outputs.

Key repository-derived results:

| Result | Value |
|---|---:|
| Mesh structures | {stats['mesh_structures']} |
| Vertebrae | {stats['vertebrae']} |
| Discs | {stats['discs']} |
| Vertices | {stats['vertices']} |
| Faces | {stats['faces']} |
| Reports | {stats['total_reports']} |
| State files | {stats['total_states']} |
| Visualizations | {stats['total_visualizations']} |
| Simulation outputs | {stats['total_simulations']} |
| Curated showcase figures | {curated_figures} |
| PPT-ready assets | {ppt_assets} |
| Public GitHub size after internal separation | {public_size_mb} MB |
| Public GitHub file count | {public_file_count} |
| GitHub release readiness score | {github_score}/10 |
| README quality score | {readme_score}/10 |

![State Change Dashboard]({fig.get('State change dashboard','')})

![Surgery Comparison Dashboard]({fig.get('Surgery comparison dashboard','')})

### Showcase Edition Results

The Showcase Edition was created as a curated layer above the engineering repository. Its goal is to help professors, researchers, engineers, recruiters, and judges understand the system quickly without browsing every internal artifact. It includes hero figures, segmentation figures, reconstruction figures, measurement dashboards, graph diagrams, state explanations, surgery demonstrations, mesh displacement views, limitations summaries, architecture summaries, and PPT-ready assets.

The showcase validation reports {curated_figures} curated figures and {ppt_assets} PPT assets. It explicitly marks `no_new_science: true`; the showcase is a communication layer, not a source of new measurements or simulations.

### GitHub Release Engineering Results

The final GitHub polish pass added standard open-source project files: `LICENSE`, `requirements.txt`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `CITATION.cff`, issue templates, pull request template, and a lightweight GitHub Actions workflow. The workflow checks imports, compiles Python files, and verifies key repository artifacts. It does not train models, rerun segmentation, or run heavy simulations.

The public repository was then separated from internal data. The upload folder is `C:/OrthoTwin/OrthoTwin`; the local recovery archive is `{internal_archive_folder}`. The public repository size is estimated at {public_size_mb} MB with {public_file_count} files. No critical source code is hidden in the internal archive.

---

## Section 13. Evidence Audit

The evidence audit is one of the most important parts of the project because it prevents overclaiming.

Evidence categories:

- Real repository artifacts: files, masks, meshes, reports, generated states.
- Geometry derived: centroids, PCA dimensions, bounding boxes, disc heights, curvature proxies.
- Estimated: canal area, foraminal area, degeneration-style scores.
- Rule derived: load redistribution, risk scores, scenario ranking, longitudinal progression.
- Unsupported or blocked: physical calibration, clinical validation, biomechanics, outcome prediction.

Phase 9 concluded that physical calibration is blocked. This means physical units should not be claimed unless a provably linked source image/header is recovered.

Phase 9.5 then attempted a deeper forensic recovery. It scanned image and metadata artifacts, built a Patient Alpha linkage graph, traced backward from `reconstructed_structures.pkl`, ranked spacing candidates, and produced a formal calibration decision. The decision remained `{phase95_decision}` with confidence `{phase95_confidence}`. This is scientifically important: failure to recover calibration is not a failure of the audit; it is an honest result that prevents false millimeter-scale claims.

The calibration recovery pass also established a strict rule for future work: calibrated measurements should only be generated when a complete evidence chain exists from image metadata to masks to reconstruction to state. Since that chain is not currently proven, no calibrated measurement files were generated.

---

## Section 14. Limitations

This section is deliberately blunt.

Missing:

- Physical calibration.
- Trusted voxel spacing for active Patient Alpha outputs.
- Independent radiologist validation.
- Biomechanical validation.
- FEM.
- Material models.
- Boundary conditions.
- Longitudinal validation.
- Outcome prediction.
- Clinical validation.
- Regulatory validation.

The system cannot be treated as a clinical tool. It is a research prototype and software architecture demonstration.

![Scientific Limitations Poster]({fig.get('Scientific limitations poster','')})

---

## Section 15. What OrthoTwin Can Do

Current capabilities:

- Organize segmentation-derived spine artifacts.
- Store reconstructed mesh structure metadata.
- Build patient, clinical, graph, scenario, surgery, and mesh states.
- Visualize segmentation, reconstruction, measurements, graph, surgery, mesh changes, and evidence boundaries.
- Run deterministic scenario comparisons from existing state.
- Demonstrate geometry-aware and mesh-level transformations.
- Generate release, evidence, and presentation reports.

Supported workflows:

- Patient Alpha state inspection.
- Mesh inventory and reconstruction review.
- Graph connectivity review.
- Scenario comparison.
- Surgery demonstration.
- Evidence and limitation review.

---

## Section 16. What OrthoTwin Cannot Do

OrthoTwin cannot:

- Diagnose disease.
- Recommend treatment.
- Predict clinical outcomes.
- Forecast validated progression.
- Claim physical millimeter accuracy without spacing.
- Claim biomechanical accuracy.
- Replace FEM.
- Replace radiologist measurement validation.
- Support regulatory or clinical deployment.

---

## Section 17. Scientific Assessment

Existing Phase 6 readiness score: `{readiness}`.

Assessment:

| Dimension | Status |
|---|---|
| Engineering maturity | Strong prototype architecture |
| Research maturity | Promising but requires external validation |
| Clinical maturity | Low; no clinical validation |
| Digital twin maturity | Prototype; connected state and mesh transformations exist |
| Repository maturity | Strong documentation and audit package |
| Biomechanics maturity | Blocked |
| Calibration maturity | Blocked |

The project is strongest as a transparent research software prototype. It is weakest where external evidence is required.

---

## Section 18. Future Work

Short term:

- Recover provably linked Patient Alpha spacing and orientation.
- Verify measurements against radiologist-reviewed references.
- Reduce copied or stale sections in rebuilt states.
- Add reproducible command-level run documentation.

Medium term:

- Build multi-patient validation dataset.
- Integrate real material properties and boundary conditions.
- Prepare FEM-compatible mesh pipeline.
- Validate graph and state changes against known cases.

Long term:

- Longitudinal validation.
- Prospective research study.
- Outcome-linked dataset.
- Regulatory planning only after clinical purpose and validation pathway are defined.

---

## Section 19. Repository Statistics

| Repository Metric | Count |
|---|---:|
| Total files | {stats['total_files']} |
| Total repository bytes | {stats['total_size_bytes']} |
| Reports | {stats['total_reports']} |
| State files | {stats['total_states']} |
| Measurement-related files | {stats['total_measurements']} |
| Visualizations | {stats['total_visualizations']} |
| Manifests | {stats['total_manifests']} |
| Simulation outputs | {stats['total_simulations']} |
| Mesh structures | {stats['mesh_structures']} |
| Vertices | {stats['vertices']} |
| Faces | {stats['faces']} |

Architecture artifacts include release documentation, architecture graph JSON, architecture diagram, whitepaper, roadmap, executive summary, presentation package, simulation visualization suite, and this master technical audit.

---

## Section 20. Final Verdict

OrthoTwin is a **Digital Twin Prototype**.

It successfully demonstrates:

- A complete repository-level architecture.
- Connected patient state representation.
- Spine graph modeling.
- Geometry-derived measurements.
- Deterministic scenario comparison.
- Geometry-aware surgery demonstrations.
- Mesh-level transformation demonstrations.
- Honest evidence and limitation reporting.

It is technically interesting because it moves beyond segmentation into a connected anatomy-state-graph-mesh architecture. It is not yet a clinical system because it lacks calibration, clinical validation, biomechanics, longitudinal validation, outcome validation, and regulatory evidence.

The correct final interpretation is:

```text
Research software prototype
not clinical software
not treatment planning
not validated biomechanics
```

---

## Referenced Outputs

The master audit references {len(assets)} copied assets in `orthotwin_master_audit_assets/`, plus repository outputs from release, phase, state, visualization, and evidence folders.
"""


def write_pdf(markdown: str, assets: list[dict]) -> int:
    pages = []
    sections = markdown.split("\n---\n")
    for section in sections:
        pages.append({"text": section.strip(), "asset": None})

    # Add dedicated image appendix pages to make the PDF readable and auditable.
    for asset in assets:
        pages.append({"text": f"Figure: {asset['caption']}\nSource: {asset['source']}", "asset": ASSET_DIR / asset["filename"]})

    with PdfPages(PDF_PATH) as pdf:
        for page in pages:
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.patch.set_facecolor("white")
            if page["asset"] and page["asset"].exists():
                ax_img = fig.add_axes([0.08, 0.20, 0.84, 0.65])
                ax_img.axis("off")
                ax_img.imshow(plt.imread(page["asset"]))
                ax_text = fig.add_axes([0.08, 0.05, 0.84, 0.12])
                ax_text.axis("off")
                ax_text.text(0, 1, page["text"], va="top", fontsize=9, wrap=True)
            else:
                ax = fig.add_axes([0.08, 0.06, 0.84, 0.88])
                ax.axis("off")
                lines = []
                for raw in page["text"].splitlines():
                    if raw.startswith("#"):
                        lines.append(raw.replace("#", "").strip())
                    elif raw.startswith("!["):
                        continue
                    else:
                        width = 92 if not raw.startswith("|") else 110
                        lines.extend(textwrap.wrap(raw, width=width) if raw else [""])
                ax.text(0, 1, "\n".join(lines[:65]), va="top", fontsize=8.5, family="DejaVu Sans")
            pdf.savefig(fig)
            plt.close(fig)
    return len(pages)


def count_tables(markdown: str) -> int:
    return sum(1 for line in markdown.splitlines() if line.startswith("|") and "---" in line)


def main() -> None:
    ensure_dirs()
    assets = collect_assets()
    stats = repo_stats()
    markdown = make_markdown(assets, stats)
    MD_PATH.write_text(markdown, encoding="utf-8")
    page_count = write_pdf(markdown, assets)
    table_count = count_tables(markdown)
    manifest = {
        "generated_utc": NOW,
        "markdown": str(MD_PATH),
        "pdf": str(PDF_PATH),
        "assets_directory": str(ASSET_DIR),
        "page_count": page_count,
        "figure_count": len(assets),
        "table_count": table_count,
        "referenced_outputs": len(assets),
        "final_classification": stats["classification"],
        "no_new_science": True,
        "no_new_measurements": True,
        "no_new_simulations": True,
    }
    save_path = OUT_DIR / "orthotwin_master_audit_manifest.json"
    save_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("ORTHOTWIN MASTER AUDIT COMPLETE")
    print("Page count:", page_count)
    print("Figure count:", len(assets))
    print("Table count:", table_count)
    print("Referenced outputs:", len(assets))
    print("Final classification:", stats["classification"])


if __name__ == "__main__":
    main()
