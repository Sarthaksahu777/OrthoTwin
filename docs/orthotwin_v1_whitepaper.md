# OrthoTwin V1 Whitepaper

## Abstract

OrthoTwin V1 is an explainable research prototype for organizing spine segmentation outputs into a connected digital twin representation. The system includes reconstructed geometry, measurement extraction, patient state vectors, graph structure, deterministic scenarios, longitudinal projections, geometry-aware surgery, mesh-level surgery, and evidence auditing. It makes no diagnostic, therapeutic, biomechanical, regulatory, or clinical-validity claims.

## Problem Statement

Segmentation and measurement outputs are often disconnected. OrthoTwin V1 explores how existing anatomy-derived artifacts can be converted into a structured, inspectable, connected spine representation suitable for research planning.

## System Overview

The repository contains 148946 files, including 65 report-like artifacts, 71 state files, 103 measurement-related files, 104 visualization artifacts, and 53 simulation output files.

## Dataset

The active patient is Patient Alpha. Existing artifacts include segmentation-derived data, reconstructed meshes, measurements, state vectors, graph outputs, scenarios, surgery outputs, and audits. Patient Alpha physical calibration remains blocked because spacing/orientation linkage could not be proven.

## Segmentation Pipeline

Segmentation artifacts exist from earlier phases. V1.0 release freeze does not retrain models, run inference, or alter masks.

## Reconstruction Pipeline

The reconstruction layer stores mesh geometry in `reconstructed_structures.pkl`. Phase 8 inventory identified 14 mesh structures: 8 vertebrae and 6 discs, with 75312 vertices and 147636 faces.

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
