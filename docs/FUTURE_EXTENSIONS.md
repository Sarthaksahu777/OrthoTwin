# OrthoTwin Future Extension Notes

Version 1 is deterministic and geometric. It uses patient state plus explicit
intervention rules to produce a predicted state. It does not use AI models,
neural networks, inference, or LLMs.

Future versions can extend the same architecture with:

- Biomechanics: add force, stiffness, load-sharing, and range-of-motion fields to the state vector.
- Finite element models: attach meshes, material properties, boundary conditions, and solver outputs to state transitions.
- Surgical planning: model approach, target anatomy, decompression zones, implant trajectories, and risk constraints.
- Implant optimization: search deterministic implant sizes and placements against alignment, height, and load objectives.
- Outcome prediction: add calibrated clinical endpoints once validated outcome data exists.
- ML-based state transitions: optional future transition engines can be introduced behind the same `StateTransition` contract, while keeping deterministic rules as the auditable baseline.

