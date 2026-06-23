# OrthoTwin System Architecture

Generated: 2026-06-19T17:46:24.096366+00:00

## Project Overview

OrthoTwin is organized as a deterministic digital twin pipeline. The repository
keeps raw imaging, trained checkpoint artifacts, measurement outputs, patient
state vectors, graph representations, reports, and future simulation interfaces
in separate folders.

No retraining, inference, segmentation recomputation, mask editing, diagnosis,
or surgery simulation is performed by the refactor.

## Folder Structure

- `data/raw/`
- `data/processed/`
- `data/cleaned/`
- `models/checkpoints/`
- `models/configs/`
- `measurements/geometry/`
- `measurements/alignment/`
- `measurements/discs/`
- `measurements/vertebrae/`
- `state/patient_states/`
- `state/graphs/`
- `state/transitions/`
- `simulation/interventions/`
- `simulation/propagation/`
- `simulation/biomechanics/`
- `visualization/segmentation/`
- `visualization/reconstruction/`
- `visualization/state/`
- `visualization/simulation/`
- `reports/phase1/`
- `reports/phase2/`
- `reports/phase3/`
- `archive/`
- `docs/`
- `manifests/`

## Data Flow

- MRI -> Segmentation
- Segmentation -> Cleanup
- Cleanup -> Measurements
- Measurements -> State Vector
- State Vector -> Graph
- Graph -> Simulation

## Digital Twin Design

The current digital twin state is built from cleaned geometry, disc ranking,
component analysis, and spine coordinate measurements. Stage 2 adds graph
structure, disc-vertebra relationships, relative metrics, centerline geometry,
local alignment metrics, and a rule-based load approximation layer.

## Future Simulation Design

Stage 3 starts with interfaces for biomechanics, graph-based propagation, and
outcome comparison. These interfaces define expected inputs and outputs only;
they intentionally do not implement biomechanics or surgical simulation.

## Biomechanics Roadmap

Required future inputs include material properties, calibrated loads, boundary
conditions, ligament/facet data, patient scale, solver settings, and validation
targets. Until those are available, load values remain deterministic geometric
approximations rather than physics.

## Pipeline Validation

- Readiness score: 100
- Complete chain available: True

## Missing Links

- None
