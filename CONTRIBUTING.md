# Contributing to OrthoTwin

OrthoTwin is a research prototype. Contributions should preserve scientific honesty and avoid overstating clinical, diagnostic, biomechanical, or regulatory validity.

## Good Contributions

- Documentation improvements.
- Reproducibility fixes.
- Visualization cleanup.
- Audit/report improvements.
- Deterministic code quality improvements.
- Clear separation of real, derived, estimated, and unknown outputs.

## Not Accepted

- Claims of diagnosis or treatment recommendation.
- Fake validation.
- Fake physical calibration.
- Fake biomechanics.
- New AI/ML claims without evidence.
- Large raw datasets committed directly to the public repository.

## Development Checks

Run:

```bash
python -m compileall -q OrthoTwin
python OrthoTwin/tools/github_inclusion_audit.py
```

## Data Policy

Large local recovery archives live under `archive/internal/` and are excluded from GitHub.
