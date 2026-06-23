# OrthoTwin V1 Demo Walkthrough

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
