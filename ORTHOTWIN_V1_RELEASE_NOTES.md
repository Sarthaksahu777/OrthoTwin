# ORTHOTWIN V1 Release Notes

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
