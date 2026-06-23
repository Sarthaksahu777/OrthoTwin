# OrthoTwin V1 Architecture

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
