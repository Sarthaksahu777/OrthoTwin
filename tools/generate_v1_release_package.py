"""Generate OrthoTwin V1.0 release-candidate audit and documentation.

This script packages existing repository evidence only. It does not create new
engines, simulations, measurements, models, or validation claims.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()
RELEASE_DIR = ROOT / "reports" / "release_v1"
DOCS_DIR = ROOT / "docs"
MANIFEST_DIR = ROOT / "manifests"
VIS_DIR = ROOT / "visualization" / "release"

TEXT_EXTS = {".json", ".txt", ".md", ".py", ".csv", ".yaml", ".yml", ".ini", ".cfg"}
REPORT_EXTS = {".txt", ".md", ".json"}
VIS_EXTS = {".png", ".jpg", ".jpeg", ".svg", ".html"}
STATE_PATTERNS = ["state_vector", "state", "scenario", "rebuilt", "future_state", "dashboard"]
MEASUREMENT_HINTS = [
    "measurement",
    "height",
    "area",
    "curvature",
    "slippage",
    "alignment",
    "disc",
    "vertebral",
    "canal",
    "foraminal",
]
SIM_HINTS = [
    "simulation",
    "scenario",
    "surgery",
    "implant",
    "fusion",
    "spacer",
    "collapse",
    "restoration",
    "longitudinal",
    "mesh_result",
]


def ensure_dirs() -> None:
    for directory in [RELEASE_DIR, DOCS_DIR, MANIFEST_DIR, VIS_DIR, ROOT / "tools"]:
        directory.mkdir(parents=True, exist_ok=True)


def json_dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def file_ext(path: Path) -> str:
    return ".nii.gz" if path.name.lower().endswith(".nii.gz") else path.suffix.lower()


def collect_files() -> list[dict]:
    files: list[dict] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        files.append(
            {
                "path": str(path.relative_to(ROOT)),
                "absolute_path": str(path),
                "name": path.name,
                "extension": file_ext(path),
                "size_bytes": stat.st_size,
                "created_utc": datetime.fromtimestamp(stat.st_ctime, timezone.utc).isoformat(),
                "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            }
        )
    return files


def categorize(files: list[dict]) -> dict[str, list[dict]]:
    def is_report(file: dict) -> bool:
        path = file["path"].lower()
        return ("reports" in path or path.startswith("docs")) and file["extension"] in REPORT_EXTS

    def is_measurement(file: dict) -> bool:
        path = file["path"].lower()
        name = file["name"].lower()
        return (
            "measurement" in path or any(hint in name for hint in MEASUREMENT_HINTS)
        ) and file["extension"] in {".json", ".txt", ".csv", ".pkl"}

    def is_state(file: dict) -> bool:
        path = file["path"].lower()
        name = file["name"].lower()
        return ("state" in path or any(hint in name for hint in STATE_PATTERNS)) and file[
            "extension"
        ] in {".json", ".pkl"}

    def is_visual(file: dict) -> bool:
        return file["extension"] in VIS_EXTS or "visualization" in file["path"].lower()

    def is_manifest(file: dict) -> bool:
        return "manifest" in file["path"].lower() or "manifest" in file["name"].lower()

    def is_sim_output(file: dict) -> bool:
        path = file["path"].lower()
        name = file["name"].lower()
        return file["extension"] == ".json" and any(hint in path or hint in name for hint in SIM_HINTS)

    return {
        "reports": [file for file in files if is_report(file)],
        "measurements": [file for file in files if is_measurement(file)],
        "states": [file for file in files if is_state(file)],
        "visualizations": [file for file in files if is_visual(file)],
        "manifests": [file for file in files if is_manifest(file)],
        "simulation_outputs": [file for file in files if is_sim_output(file)],
    }


def candidate_refs_from_obj(obj: object) -> list[str]:
    refs: list[str] = []
    if isinstance(obj, dict):
        for value in obj.values():
            refs.extend(candidate_refs_from_obj(value))
    elif isinstance(obj, list):
        for value in obj:
            refs.extend(candidate_refs_from_obj(value))
    elif isinstance(obj, str):
        lower = obj.lower()
        if any(token in lower for token in [".json", ".txt", ".md", ".png", ".pkl", ".py", ".npy", ".mha", ".dcm", ".nii", ".csv"]):
            refs.append(obj.strip())
    return refs


def dependency_scan(files: list[dict]) -> tuple[list[dict], list[dict]]:
    existing_rel = {file["path"].replace("\\", "/") for file in files}
    path_refs: list[dict] = []
    broken_refs: list[dict] = []
    pattern = re.compile(
        r"[A-Za-z]:\\[^\n\r\"']+|(?:OrthoTwin[/\\][^\s\)\]\}\"']+\.(?:json|txt|md|png|pkl|py|npy|mha|dcm|nii|csv))"
    )

    for file in files:
        path = ROOT / file["path"]
        if file["extension"] not in TEXT_EXTS or file["size_bytes"] > 3_000_000:
            continue
        try:
            if file["extension"] == ".json":
                refs = candidate_refs_from_obj(json.loads(path.read_text(encoding="utf-8")))
            else:
                refs = pattern.findall(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            continue

        for ref in refs[:200]:
            raw = ref.strip().strip('"').strip("'")
            normalized = raw.replace("\\", "/")
            if ":" in raw[:4]:
                exists = Path(raw).exists()
            elif normalized.startswith("OrthoTwin/"):
                exists = (ROOT.parent / normalized).exists()
            elif normalized in existing_rel:
                exists = True
            else:
                exists = (path.parent / raw).exists() or (ROOT / raw).exists()

            record = {"source": file["path"], "reference": raw, "exists": bool(exists)}
            path_refs.append(record)
            if not exists:
                broken_refs.append({"source": file["path"], "reference": raw})
    return path_refs, broken_refs


def duplicate_scan(files: list[dict]) -> tuple[dict, dict]:
    name_groups: dict[str, list[str]] = defaultdict(list)
    for file in files:
        name_groups[file["name"].lower()].append(file["path"])
    duplicate_names = {key: value for key, value in name_groups.items() if len(value) > 1}

    hash_groups: dict[str, list[str]] = defaultdict(list)
    hashable_exts = TEXT_EXTS | {".png", ".jpg", ".jpeg", ".svg"}
    for file in files:
        if file["extension"] not in hashable_exts or file["size_bytes"] > 5_000_000:
            continue
        try:
            digest = hashlib.sha256((ROOT / file["path"]).read_bytes()).hexdigest()
        except Exception:
            continue
        hash_groups[digest].append(file["path"])
    duplicate_content = {key: value for key, value in hash_groups.items() if len(value) > 1}
    return duplicate_names, duplicate_content


def write_repository_audit(files: list[dict], categories: dict[str, list[dict]]) -> dict:
    by_ext = Counter(file["extension"] or "[none]" for file in files)
    _, broken_refs = dependency_scan(files)
    duplicate_names, duplicate_content = duplicate_scan(files)
    expected_roots = {
        "data",
        "models",
        "measurements",
        "state",
        "simulation",
        "visualization",
        "reports",
        "archive",
        "docs",
        "manifests",
        "config",
        "stage2",
        "tools",
    }
    orphaned = [
        file["path"]
        for file in files
        if Path(file["path"]).parts and Path(file["path"]).parts[0] not in expected_roots
    ]
    counts = {
        "total_files": len(files),
        "total_reports": len(categories["reports"]),
        "total_measurements": len(categories["measurements"]),
        "total_state_files": len(categories["states"]),
        "total_visualizations": len(categories["visualizations"]),
        "total_manifests": len(categories["manifests"]),
        "total_simulation_outputs": len(categories["simulation_outputs"]),
        "total_size_bytes": sum(file["size_bytes"] for file in files),
    }
    audit = {
        "generated_utc": NOW,
        "root": str(ROOT),
        **counts,
        "extensions": dict(sorted(by_ext.items())),
        "verification": {
            "broken_path_references_count": len(broken_refs),
            "duplicate_filename_groups_count": len(duplicate_names),
            "duplicate_content_groups_count": len(duplicate_content),
            "orphaned_files_count": len(orphaned),
        },
        "broken_path_references_sample": broken_refs[:100],
        "duplicate_filenames_sample": dict(list(duplicate_names.items())[:100]),
        "duplicate_content_sample": dict(list(duplicate_content.items())[:50]),
        "orphaned_files": orphaned[:500],
        "categories": {key: [file["path"] for file in value] for key, value in categories.items()},
    }
    json_dump(RELEASE_DIR / "orthotwin_v1_repository_audit.json", audit)
    return audit


def write_health_report(audit: dict) -> None:
    text = f"""# OrthoTwin V1 Repository Health Report

Generated: {NOW}

## Inventory
- Total files: {audit['total_files']}
- Total size bytes: {audit['total_size_bytes']}
- Reports: {audit['total_reports']}
- Measurement files: {audit['total_measurements']}
- State files: {audit['total_state_files']}
- Visualizations: {audit['total_visualizations']}
- Manifests: {audit['total_manifests']}
- Simulation outputs: {audit['total_simulation_outputs']}

## Health Checks
- Broken path references found: {audit['verification']['broken_path_references_count']}
- Duplicate filename groups: {audit['verification']['duplicate_filename_groups_count']}
- Duplicate content groups among small files: {audit['verification']['duplicate_content_groups_count']}
- Orphaned files outside expected architecture roots: {audit['verification']['orphaned_files_count']}

## Interpretation
Broken references are repository/documentation references that could not be resolved by a conservative scanner. Some may be historical paths from earlier phases, not runtime failures.
Duplicate filenames are expected in staged outputs and archives, but they should be reviewed before packaging public releases.
No files were deleted, moved, or rewritten as part of this release freeze audit.

## Most Important Repository Risk
Physical calibration remains blocked unless a provably linked Patient Alpha source image/header is recovered.

## Most Valuable Repository Asset
The connected spine representation plus mesh-level transformation layer now provides a demonstrable digital twin prototype without claiming clinical validity.
"""
    (RELEASE_DIR / "repository_health_report.txt").write_text(text, encoding="utf-8")


def write_architecture_docs() -> None:
    nodes = [
        ("mri", "MRI / source imaging"),
        ("segmentation", "Segmentation"),
        ("cleanup", "Voxel cleanup / QC"),
        ("reconstruction", "3D reconstruction"),
        ("measurements", "Measurement engines"),
        ("clinical_state", "Clinical state vector"),
        ("spine_graph", "Spine graph"),
        ("scenario", "Scenario engine"),
        ("longitudinal", "Longitudinal engine"),
        ("geometry_surgery", "Geometry surgery engine"),
        ("mesh_surgery", "Mesh surgery engine"),
        ("evidence", "Evidence audit"),
        ("reports", "Reports / release package"),
    ]
    major_files = {
        "reconstruction": ["measurements/geometry/reconstructed_structures.pkl"],
        "measurements": ["state/patient_states/clinical_state_vector.json"],
        "spine_graph": ["state/graphs/spine_graph.json"],
        "scenario": ["simulation/scenario_engine.py", "reports/phase5"],
        "longitudinal": ["simulation/longitudinal_engine.py", "reports/phase6"],
        "geometry_surgery": ["simulation/surgery", "reports/phase7"],
        "mesh_surgery": ["simulation/mesh", "state/mesh", "reports/phase8"],
        "evidence": ["reports/phase9"],
    }
    graph = {
        "generated_utc": NOW,
        "nodes": [{"id": node_id, "label": label, "major_files": major_files.get(node_id, [])} for node_id, label in nodes],
        "edges": [{"from": nodes[i][0], "to": nodes[i + 1][0], "relationship": "feeds"} for i in range(len(nodes) - 1)],
    }
    json_dump(RELEASE_DIR / "architecture_graph.json", graph)

    md = """# OrthoTwin V1 Architecture

OrthoTwin V1 is a research prototype that organizes segmentation-derived anatomy into a connected digital spine representation. It does not claim diagnosis, treatment recommendation, clinical validation, or physical biomechanics.

```text
MRI
  -> Segmentation
  -> Cleanup
  -> Reconstruction
  -> Measurements
  -> State Vector
  -> Spine Graph
  -> Scenario Engine
  -> Longitudinal Engine
  -> Geometry Surgery Engine
  -> Mesh Surgery Engine
  -> Evidence Audit
  -> Reports
```

## Major Data Flow

| Stage | Role | Representative Artifacts |
|---|---|---|
| MRI / source imaging | Source data, not physically calibrated for Patient Alpha in current release | data/, archive/ |
| Segmentation | Existing masks and segmentation outputs | data/processed, data/cleaned |
| Reconstruction | Mesh/geometry artifacts | measurements/geometry/reconstructed_structures.pkl |
| Measurements | Derived geometric and clinical-style measurements | measurements/, state/patient_states/clinical_state_vector.json |
| State Vector | Unified patient/twin state | state/patient_states/ |
| Spine Graph | Connected structural representation | state/graphs/spine_graph.json |
| Scenario Engine | Deterministic scenario comparison | simulation/scenario_engine.py, reports/phase5 |
| Longitudinal Engine | Rule-based future state projections | simulation/longitudinal_engine.py, state/longitudinal |
| Geometry Surgery Engine | Geometry-aware centroid/object transformations | simulation/surgery, reports/phase7 |
| Mesh Surgery Engine | Vertex-level mesh transformations | simulation/mesh, state/mesh, reports/phase8 |
| Evidence Audit | Classification of real/derived/estimated/unknown | reports/phase9 |
| Release | Audit, paper, readiness, roadmap | reports/release_v1 |

## Scientific Boundary

The system is an explainable research prototype. Measurements remain voxel-space unless physical calibration is recovered. Load, progression, scenario ranking, and surgical effects are deterministic approximations, not validated biomechanics.
"""
    (DOCS_DIR / "orthotwin_architecture.md").write_text(md, encoding="utf-8")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 11))
        ax.axis("off")
        for index, (_, label) in enumerate(nodes):
            y = len(nodes) - index - 1
            ax.text(
                0.5,
                y,
                label,
                ha="center",
                va="center",
                fontsize=10,
                bbox={"boxstyle": "round,pad=0.35", "fc": "#eef2f3", "ec": "#34495e", "lw": 1},
            )
            if y > 0:
                ax.annotate("", xy=(0.5, y - 0.42), xytext=(0.5, y - 0.08), arrowprops={"arrowstyle": "->", "lw": 1.2, "color": "#34495e"})
        ax.set_ylim(-1, len(nodes))
        ax.set_xlim(0, 1)
        fig.tight_layout()
        fig.savefig(VIS_DIR / "architecture_diagram.png", dpi=180)
        plt.close(fig)
    except Exception as exc:
        (VIS_DIR / "architecture_diagram_error.txt").write_text(str(exc), encoding="utf-8")


CAPABILITIES = [
    ("Segmentation", "COMPLETE", "Existing segmentation outputs and masks are present; no retraining in release."),
    ("Voxel cleanup / QC", "COMPLETE", "Cleanup and validation artifacts exist."),
    ("3D reconstruction", "COMPLETE", "reconstructed_structures.pkl contains vertebra and disc meshes."),
    ("Measurements", "PARTIAL", "Geometry-derived and estimated measurements exist; physical calibration and clinical validation missing."),
    ("State representation", "COMPLETE", "Patient state vectors and clinical state vector exist."),
    ("Spine graph", "COMPLETE", "Connected graph representation exists."),
    ("Propagation engine", "EXPERIMENTAL", "Deterministic graph propagation exists; not physics."),
    ("Scenario engine", "EXPERIMENTAL", "Scenario comparison exists; internal scoring only."),
    ("Longitudinal engine", "EXPERIMENTAL", "Rule-based future states exist; no follow-up validation."),
    ("Geometry surgery", "EXPERIMENTAL", "Anatomy-first centroid/object surgery exists; some metrics remain copied/estimated."),
    ("Mesh surgery", "EXPERIMENTAL", "Vertex-level transformations exist; no FEM or tissue mechanics."),
    ("Physical calibration", "BLOCKED", "Patient Alpha spacing/orientation/slice thickness could not be proven."),
    ("Biomechanics", "BLOCKED", "Material properties, boundary conditions, solver, and validated meshes missing."),
    ("Clinical validation", "BLOCKED", "No independent radiologist, biomechanical, prospective, or regulatory validation."),
]


def write_capability_and_limitations() -> None:
    json_dump(
        RELEASE_DIR / "capability_matrix.json",
        {"generated_utc": NOW, "capabilities": [{"subsystem": s, "status": st, "rationale": r} for s, st, r in CAPABILITIES]},
    )
    report = "# Capability Matrix Report\n\n" + "\n".join([f"- {s}: {st} - {r}" for s, st, r in CAPABILITIES]) + "\n"
    (RELEASE_DIR / "capability_matrix_report.txt").write_text(report, encoding="utf-8")

    limitations = """# Scientific Limitations

## What Is Real

- Segmentation-derived artifacts exist in the repository.
- Reconstructed mesh objects exist for vertebrae and discs.
- Mesh operations in Phase 8 modify vertices directly.
- Patient state, graph, scenario, longitudinal, surgery, and evidence files exist as structured repository artifacts.

## What Is Derived

- Disc heights are derived from mesh/PCA/projection methods.
- Relative spacing is derived from graph and geometry relationships.
- Curvature is derived from centroid/centerline geometry.
- Slippage-style displacement measures are centroid-projection measurements, not radiologist-validated measurements.

## What Is Estimated

- Canal area and foraminal area are geometric estimates.
- Load redistribution is a deterministic proxy.
- Risk scores and scenario rankings are internal scoring rules.
- Longitudinal progression is assumption-driven.
- Surgical outcome effects are deterministic geometry/rule outputs, not validated outcomes.

## What Is Missing

- Proven Patient Alpha physical spacing and orientation.
- Physical units for all voxel-space measurements.
- Finite element modeling.
- Material properties and boundary conditions.
- Independent radiologist validation.
- Biomechanical validation.
- Longitudinal follow-up validation.
- Clinical or regulatory validation.
"""
    (DOCS_DIR / "scientific_limitations.md").write_text(limitations, encoding="utf-8")


def mesh_counts() -> tuple[int, int, int, int, int]:
    path = ROOT / "state" / "mesh" / "mesh_inventory.json"
    if not path.exists():
        return 0, 0, 0, 0, 0
    data = json.loads(path.read_text(encoding="utf-8"))
    structures = data.get("structures", [])
    return (
        len(structures),
        len([s for s in structures if "Vertebra" in s.get("name", "")]),
        len([s for s in structures if "Disc" in s.get("name", "")]),
        sum(s.get("vertex_count", 0) for s in structures),
        sum(s.get("face_count", 0) for s in structures),
    )


def write_papers_and_demo(audit: dict) -> None:
    structure_count, vertebra_count, disc_count, vertex_count, face_count = mesh_counts()
    whitepaper = f"""# OrthoTwin V1 Whitepaper

## Abstract

OrthoTwin V1 is an explainable research prototype for organizing spine segmentation outputs into a connected digital twin representation. The system includes reconstructed geometry, measurement extraction, patient state vectors, graph structure, deterministic scenarios, longitudinal projections, geometry-aware surgery, mesh-level surgery, and evidence auditing. It makes no diagnostic, therapeutic, biomechanical, regulatory, or clinical-validity claims.

## Problem Statement

Segmentation and measurement outputs are often disconnected. OrthoTwin V1 explores how existing anatomy-derived artifacts can be converted into a structured, inspectable, connected spine representation suitable for research planning.

## System Overview

The repository contains {audit['total_files']} files, including {audit['total_reports']} report-like artifacts, {audit['total_state_files']} state files, {audit['total_measurements']} measurement-related files, {audit['total_visualizations']} visualization artifacts, and {audit['total_simulation_outputs']} simulation output files.

## Dataset

The active patient is Patient Alpha. Existing artifacts include segmentation-derived data, reconstructed meshes, measurements, state vectors, graph outputs, scenarios, surgery outputs, and audits. Patient Alpha physical calibration remains blocked because spacing/orientation linkage could not be proven.

## Segmentation Pipeline

Segmentation artifacts exist from earlier phases. V1.0 release freeze does not retrain models, run inference, or alter masks.

## Reconstruction Pipeline

The reconstruction layer stores mesh geometry in `reconstructed_structures.pkl`. Phase 8 inventory identified {structure_count} mesh structures: {vertebra_count} vertebrae and {disc_count} discs, with {vertex_count} vertices and {face_count} faces.

## Measurement Pipeline

Measurements include disc heights, disc areas, canal/foraminal geometric estimates, curvature, alignment, slippage-style displacement, and degeneration-style internal features. These are derived or estimated and require calibration and validation.

## State Representation

Patient state vectors aggregate segmentation, measurements, graph, alignment, clinical-style measurements, scenario data, and longitudinal outputs.

## Graph Model

The spine graph connects vertebrae and discs into a system representation. This allows deterministic propagation and scenario comparisons across neighboring structures.

## Scenario Engine

The scenario engine compares deterministic interventions against baseline. It is useful for software demonstration and internal twin scoring, not clinical decision-making.

## Longitudinal Engine

The longitudinal engine creates future states using configurable assumptions. It is not patient-calibrated and has no temporal validation.

## Geometry Surgery Engine

Phase 7 introduced geometry-aware surgical objects and state rebuilds. The forensic audit found it partially geometry-first: implant, spacer, and alignment correction modify geometry; fusion is primarily relationship/constraint-based.

## Mesh Surgery Engine

Phase 8 upgrades surgery operations to mesh-level transformations. Implant, collapse, and spacer operations move vertices; fusion preserves geometry and records a locked relationship/constraint.

## Evidence Framework

Phase 9 classifies measurements and outcomes as real, derived, estimated, rule-derived, unsupported, or blocked. The most important blocked item is physical calibration.

## Results

OrthoTwin V1 demonstrates a complete repository-level prototype from reconstruction through state, graph, scenarios, surgery, mesh transformations, and evidence reports. It is best classified as a Digital Twin Prototype.

## Limitations

The system lacks proven physical calibration, clinical validation, biomechanical validation, material models, FEM, boundary conditions, and longitudinal follow-up. It should not be used for diagnosis or treatment planning.

## Future Work

Recover Patient Alpha spacing, validate measurements with radiologist-reviewed references, add FEM only with real material and boundary data, validate longitudinal changes, and establish external clinical/research collaboration.

## Conclusion

OrthoTwin V1 is a demonstrable research prototype and architecture foundation. It is not a clinical device or validated biomechanical simulator.
"""
    (DOCS_DIR / "orthotwin_v1_whitepaper.md").write_text(whitepaper, encoding="utf-8")

    walkthrough = """# OrthoTwin V1 Demo Walkthrough

## Demo 1: Patient Alpha Reconstruction

Input: `measurements/geometry/reconstructed_structures.pkl`
Processing: Load reconstructed mesh structures and inspect vertex/face inventory.
Output: `state/mesh/mesh_inventory.json`, mesh visualizations.

## Demo 2: State Representation

Input: patient state and clinical state files.
Processing: Open the unified state vector and review discs, vertebrae, alignment, graph, and evidence sections.
Output: `state/patient_states/clinical_state_vector.json` and related state artifacts.

## Demo 3: Implant Surgery

Input: disc mesh/state and neighboring vertebrae.
Processing: Expand target disc mesh and translate adjacent vertebra meshes.
Output: `state/mesh/implant_mesh_result.json`, `implant_mesh_before_after.png`.

## Demo 4: Spacer Surgery

Input: disc 5 mesh/state and neighboring vertebrae.
Processing: Expand local disc space using mesh-level transformation rules.
Output: `state/mesh/spacer_mesh_result.json`, `spacer_mesh_before_after.png`.

## Demo 5: Fusion

Input: adjacent vertebrae and graph relationship.
Processing: Create fused segment constraint while preserving mesh geometry.
Output: `state/mesh/fusion_mesh_result.json`, `fusion_mesh_before_after.png`.

## Demo 6: Mesh-Level Simulation

Input: reconstructed mesh structures.
Processing: Apply vertex-level transformation operations and rebuild geometry-derived state.
Output: `mesh_rebuilt_state_*.json`, `mesh_impact_analysis.json`.

## Demo 7: Evidence Audit

Input: repository reports, measurements, assumptions, and surgery outputs.
Processing: Classify artifacts as real, derived, estimated, rule-derived, unknown, or blocked.
Output: `reports/phase9/*`.
"""
    (DOCS_DIR / "demo_walkthrough.md").write_text(walkthrough, encoding="utf-8")


def write_readiness_roadmap_release(audit: dict) -> None:
    readiness = {
        "generated_utc": NOW,
        "can_support_publication": "possibly_as_methods_or_prototype_paper_only",
        "evidence_exists": [
            "structured repository",
            "mesh reconstruction artifacts",
            "state/graph architecture",
            "deterministic scenario outputs",
            "mesh transformation layer",
            "evidence audit",
        ],
        "validation_missing": [
            "physical calibration",
            "radiologist measurement validation",
            "biomechanical validation",
            "longitudinal validation",
            "external reproducibility",
        ],
        "datasets_missing": [
            "original linked Patient Alpha metadata",
            "multi-patient cohort",
            "follow-up imaging",
            "ground truth clinical measurements",
            "outcome labels",
        ],
        "collaborators_needed": [
            "radiologist",
            "spine biomechanics researcher",
            "clinical study designer",
            "medical imaging data manager",
            "FEM specialist",
        ],
        "publication_positioning": "research software architecture and prototype demonstration, not clinical performance study",
    }
    json_dump(RELEASE_DIR / "research_readiness_report.json", readiness)

    roadmap = """# OrthoTwin Roadmap

## Short Term

- Recover provably linked Patient Alpha physical spacing and orientation.
- Verify measurement formulas against known phantoms or radiologist-reviewed cases.
- Reduce stale copied fields in rebuilt states.
- Add reproducible run scripts for existing phases without adding new science.

## Medium Term

- Integrate validated FEM only after material properties and boundary conditions are available.
- Define mesh quality requirements for simulation-ready anatomy.
- Replace rule-based load proxies with validated biomechanical models.
- Create multi-patient test set and reproducibility protocol.

## Long Term

- Patient-specific validation with longitudinal follow-up.
- Prospective studies under clinical/research governance.
- External validation across scanners, protocols, and institutions.
- Regulatory planning only after clinical purpose, risk class, and validation pathway are defined.
"""
    (DOCS_DIR / "orthotwin_roadmap.md").write_text(roadmap, encoding="utf-8")

    classification = {
        "generated_utc": NOW,
        "classification": "Digital Twin Prototype",
        "chosen_from": ["Data Pipeline", "Measurement Platform", "Digital Twin Prototype", "Research Platform"],
        "why": "The system now connects anatomy-derived state, graph structure, deterministic scenarios, longitudinal projections, geometry-aware surgery, mesh-level transformations, and evidence auditing. It goes beyond a data pipeline or measurement platform, but it is not yet a validated research platform because physical calibration, clinical validation, and biomechanics remain blocked.",
        "not_claimed": ["clinical validity", "diagnosis", "treatment recommendation", "biomechanical accuracy", "regulatory readiness"],
    }
    json_dump(RELEASE_DIR / "orthotwin_v1_classification.json", classification)

    release_notes = """# ORTHOTWIN V1 Release Notes

## What Was Built

OrthoTwin V1 packages segmentation-derived geometry, reconstruction, measurement extraction, state vectors, spine graph structure, deterministic scenario comparison, longitudinal projections, geometry-aware surgery, mesh-level surgery, and evidence auditing.

## What Works

- Repository organization and audit artifacts.
- Patient Alpha state and clinical state representation.
- Spine graph and connected relationships.
- Deterministic propagation/scenario outputs.
- Mesh-level transformations for implant, collapse, spacer, and fusion constraint representation.
- Evidence and limitation reporting.

## What Does Not Work

- Physical millimeter calibration for Patient Alpha is not proven.
- FEM/biomechanics are not implemented.
- Clinical outcomes are not predicted.
- No diagnosis or treatment recommendation is supported.

## Known Limitations

- Voxel-space measurements remain active where spacing is missing.
- Load and risk values are deterministic proxies.
- Longitudinal projections are assumption-based.
- Surgical outputs are geometry/rule demonstrations, not validated surgical simulations.

## Known Risks

- Misinterpreting derived estimates as clinical measurements.
- Treating deterministic proxy scores as biomechanics.
- Treating internal scenario rankings as medical advice.

## Future Directions

Recover physical metadata, validate measurements externally, build FEM only from real material and boundary data, expand to multi-patient cohorts, and pursue clinical collaboration for validation.
"""
    (ROOT / "ORTHOTWIN_V1_RELEASE_NOTES.md").write_text(release_notes, encoding="utf-8")

    summary = f"""# ORTHOTWIN V1 Executive Summary

OrthoTwin V1 is a research prototype for turning segmentation-derived spine anatomy into a connected, inspectable digital twin representation. It does not diagnose, recommend treatment, claim clinical validity, or claim biomechanical accuracy.

## What Exists

The repository now contains a full pipeline of artifacts: reconstruction, measurements, patient state vectors, a spine graph, deterministic propagation, scenario comparison, longitudinal projection, geometry-aware surgery, mesh-level transformations, and evidence auditing. The release audit counted {audit['total_files']} files, {audit['total_reports']} report-like artifacts, {audit['total_state_files']} state files, and {audit['total_visualizations']} visualization artifacts.

## Most Valuable Capability

The most valuable capability is the connected spine representation: anatomy, measurements, graph structure, scenarios, and mesh transformations can be inspected together rather than as disconnected files.

## Scientific Status

The system is scientifically honest but not clinically validated. Disc and geometry measurements are derived from segmentation/reconstruction outputs. Canal, foraminal, load, risk, progression, and scenario rankings remain estimated or rule-derived. Physical calibration for Patient Alpha remains blocked because spacing and orientation could not be proven from linked source metadata.

## What It Can Demonstrate

OrthoTwin can show how a patient-specific spine state is organized, how structures connect in a graph, how deterministic scenarios compare against baseline, and how mesh-level transformations affect anatomy-derived measurements.

## What It Cannot Claim

It cannot claim diagnosis, treatment planning, clinical outcome prediction, physical measurement accuracy, validated biomechanics, or regulatory readiness.

## Final Classification

Digital Twin Prototype. It is more than a data pipeline or measurement platform because it includes connected state evolution and mesh-level transformations. It is not yet a research-grade validated digital twin because calibration, external validation, and biomechanics remain missing.
"""
    (ROOT / "ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md").write_text(summary, encoding="utf-8")


def write_final_validation(categories: dict[str, list[dict]]) -> dict:
    expected = [
        RELEASE_DIR / "orthotwin_v1_repository_audit.json",
        RELEASE_DIR / "repository_health_report.txt",
        DOCS_DIR / "orthotwin_architecture.md",
        RELEASE_DIR / "architecture_graph.json",
        VIS_DIR / "architecture_diagram.png",
        RELEASE_DIR / "capability_matrix.json",
        RELEASE_DIR / "capability_matrix_report.txt",
        DOCS_DIR / "scientific_limitations.md",
        DOCS_DIR / "orthotwin_v1_whitepaper.md",
        DOCS_DIR / "demo_walkthrough.md",
        RELEASE_DIR / "research_readiness_report.json",
        DOCS_DIR / "orthotwin_roadmap.md",
        RELEASE_DIR / "orthotwin_v1_classification.json",
        ROOT / "ORTHOTWIN_V1_RELEASE_NOTES.md",
        ROOT / "ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md",
    ]
    major_outputs = [
        ROOT / "state" / "patient_states" / "clinical_state_vector.json",
        ROOT / "state" / "graphs" / "spine_graph.json",
        ROOT / "state" / "mesh" / "mesh_state_vector.json",
        ROOT / "reports" / "phase9" / "patient_alpha_spacing_audit.json",
    ]
    validation = {
        "generated_utc": NOW,
        "all_reports_exist": all(path.exists() for path in [RELEASE_DIR / "repository_health_report.txt", RELEASE_DIR / "capability_matrix_report.txt", ROOT / "ORTHOTWIN_V1_RELEASE_NOTES.md", ROOT / "ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md"]),
        "all_manifests_exist": len(categories["manifests"]) > 0,
        "all_major_outputs_exist": all(path.exists() for path in major_outputs),
        "all_architecture_documents_exist": all(path.exists() for path in [DOCS_DIR / "orthotwin_architecture.md", RELEASE_DIR / "architecture_graph.json", VIS_DIR / "architecture_diagram.png"]),
        "all_release_documents_exist": all(path.exists() for path in expected),
        "missing_release_documents": [str(path) for path in expected if not path.exists()],
        "major_outputs_checked": [str(path) for path in major_outputs],
        "final_classification": "Digital Twin Prototype",
        "most_important_limitation": "Physical calibration for Patient Alpha remains blocked.",
        "most_valuable_capability": "Connected spine representation with mesh-level transformation demonstration.",
    }
    json_dump(RELEASE_DIR / "orthotwin_v1_validation.json", validation)
    manifest = {
        "generated_utc": NOW,
        "phase": "orthotwin_v1_release_candidate",
        "files": [str(path) for path in expected + [RELEASE_DIR / "orthotwin_v1_validation.json"]],
        "all_files_exist": all(path.exists() for path in expected + [RELEASE_DIR / "orthotwin_v1_validation.json"]),
    }
    json_dump(MANIFEST_DIR / "orthotwin_v1_release_manifest.json", manifest)
    return validation


def main() -> None:
    ensure_dirs()
    files = collect_files()
    categories = categorize(files)
    audit = write_repository_audit(files, categories)
    write_health_report(audit)
    write_architecture_docs()
    write_capability_and_limitations()
    write_papers_and_demo(audit)
    write_readiness_roadmap_release(audit)
    validation = write_final_validation(categories)

    print("ORTHOTWIN V1.0 COMPLETE")
    print("Final Classification: Digital Twin Prototype")
    print(f"Repository Size: {audit['total_files']} files / {audit['total_size_bytes']} bytes")
    print("Number of Components:", len(CAPABILITIES))
    print("Number of Reports:", audit["total_reports"])
    print("Number of Simulations:", audit["total_simulation_outputs"])
    print("Most Important Limitation: Physical calibration for Patient Alpha remains blocked.")
    print("Most Valuable Capability: Connected spine representation with mesh-level transformation demonstration.")
    print("Release Validation:", json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
