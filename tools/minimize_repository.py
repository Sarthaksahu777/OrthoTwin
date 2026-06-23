"""Forensic repository minimization and dataset pruning plan.

This tool inventories dataset/checkpoint artifacts, classifies them by retention
policy, moves clear removal/exclusion candidates into archive/internal, and
writes recovery manifests. It never deletes files.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()
REPORT_DIR = ROOT / "reports" / "repository_minimization"
INTERNAL = ROOT / "archive" / "internal"

DATASET_EXTS = {
    ".dcm",
    ".mha",
    ".mhd",
    ".nii",
    ".nii.gz",
    ".npy",
    ".npz",
    ".pkl",
    ".zip",
    ".pt",
    ".pth",
    ".ckpt",
    ".onnx",
}

KEEP_PATH_KEYWORDS = [
    "measurements/geometry/reconstructed_structures.pkl",
    "state/mesh",
    "state/patient_states",
    "state/graphs",
    "reports",
    "docs",
    "showcase",
    "presentation",
    "visualization",
]

KEEP_CHECKPOINTS = {
    "FINAL_SEGRESNET_WEIGHTED.pth",
    "segresnet_weighted_epoch12.pth",
    "showcase_patient.pt",
}


def suffix(path: Path) -> str:
    return ".nii.gz" if path.name.lower().endswith(".nii.gz") else path.suffix.lower()


def ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    INTERNAL.mkdir(parents=True, exist_ok=True)


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def dir_size(path: Path) -> tuple[int, int]:
    total = 0
    count = 0
    if path.is_file():
        return path.stat().st_size, 1
    for file in path.rglob("*"):
        if file.is_file():
            try:
                total += file.stat().st_size
                count += 1
            except OSError:
                pass
    return total, count


def references_index() -> Counter:
    refs = Counter()
    text_exts = {".py", ".json", ".md", ".txt", ".yaml", ".yml", ".csv"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_relative_to(INTERNAL):
            continue
        if suffix(path) not in text_exts or path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        for token in [
            "dicom_series",
            "spine_segmentation_dataset",
            "sub-verse500_dir-ax_ct.nii.gz",
            "final_segresnet_weighted.pth",
            "segresnet_weighted_epoch12.pth",
            "reconstructed_structures.pkl",
        ]:
            if token in text:
                refs[token] += 1
    return refs


def classify_dataset(path: Path, refs: Counter) -> dict:
    path_rel = rel(path)
    lower = path_rel.lower()
    size, files = dir_size(path)
    ext_counts = Counter(suffix(p) for p in path.rglob("*") if p.is_file()) if path.is_dir() else Counter({suffix(path): 1})

    classification = "unused"
    action = "archive_internal"
    reason = "Large or raw artifact not required for the frozen showcase repository."
    referenced = False
    dependency_count = 0
    usage_frequency = "none"

    if any(keyword in lower for keyword in KEEP_PATH_KEYWORDS):
        classification = "actively used"
        action = "keep"
        reason = "Referenced by active state, report, documentation, showcase, or visualization layer."
        referenced = True
        dependency_count = 1
        usage_frequency = "active"
    elif "data/raw/dicom_series" in lower:
        classification = "unused"
        action = "archive_internal"
        reason = "Very large DICOM collection; Phase 9.5 could not link it to active Patient Alpha reconstruction."
        dependency_count = refs["dicom_series"]
    elif "data/raw/spine_segmentation_dataset" in lower or (lower.startswith("data/raw") and suffix(path) in {".mha", ".mhd", ".nii", ".nii.gz"}):
        classification = "historically important"
        action = "archive_internal"
        reason = "Historical/raw training or downloaded imaging data; not needed for V1 showcase execution."
        dependency_count = refs["spine_segmentation_dataset"]
    elif lower.startswith("archive/") and not lower.startswith("archive/internal"):
        classification = "historically important"
        action = "archive_internal"
        reason = "Existing historical archive or duplicate output; recoverable but should not live in showcase repo root."
    elif lower.startswith("models/checkpoints"):
        if path.name in KEEP_CHECKPOINTS:
            classification = "reproducibility-critical"
            action = "keep"
            reason = "Final/best/showcase checkpoint retained by policy."
            referenced = path.name.lower() in {"final_segresnet_weighted.pth", "segresnet_weighted_epoch12.pth"}
            dependency_count = refs[path.name.lower()]
            usage_frequency = "documented"
        else:
            classification = "duplicate" if "copy of" in lower or path.name in {"latest.pth"} else "historically important"
            action = "archive_internal"
            reason = "Older, duplicate, or intermediate checkpoint; final/best checkpoints are retained."
    elif suffix(path) in {".pkl", ".npy", ".npz"} and "archive" not in lower:
        classification = "historically important"
        action = "archive_internal"
        reason = "Intermediate binary artifact outside active state/showcase paths."

    return {
        "dataset_name": path.name,
        "path": path_rel,
        "size_bytes": size,
        "size_mb": round(size / (1024 * 1024), 3),
        "file_count": files,
        "extension_counts": dict(ext_counts),
        "classification": classification,
        "usage_frequency": usage_frequency,
        "dependency_count": dependency_count,
        "referenced_by_active_code": bool(referenced),
        "action": action,
        "reason": reason,
    }


def inventory() -> list[dict]:
    refs = references_index()
    candidates: list[Path] = []

    # Directory-level datasets.
    for path in [
        ROOT / "data" / "raw" / "dicom_series",
        ROOT / "data" / "raw" / "spine_segmentation_dataset",
    ]:
        if path.exists():
            candidates.append(path)

    # Root raw image datasets as one-file dataset records.
    raw = ROOT / "data" / "raw"
    if raw.exists():
        for path in raw.iterdir():
            if path.is_file() and suffix(path) in DATASET_EXTS:
                candidates.append(path)

    # Checkpoints.
    ckpt = ROOT / "models" / "checkpoints"
    if ckpt.exists():
        candidates.extend([p for p in ckpt.iterdir() if p.is_file() and suffix(p) in DATASET_EXTS])

    # Existing historical archive children.
    archive = ROOT / "archive"
    if archive.exists():
        for child in archive.iterdir():
            if child.name == "internal":
                continue
            candidates.append(child)

    # Active reproducibility-critical binary artifacts.
    for path in [
        ROOT / "measurements" / "geometry" / "reconstructed_structures.pkl",
        ROOT / "state" / "mesh" / "mesh_state_vector.json",
        ROOT / "state" / "patient_states" / "clinical_state_vector.json",
    ]:
        if path.exists():
            candidates.append(path)

    seen = set()
    rows = []
    for path in candidates:
        if not path.exists():
            continue
        key = str(path.resolve()).lower()
        if key in seen or INTERNAL in path.parents:
            continue
        seen.add(key)
        rows.append(classify_dataset(path, refs))
    rows.sort(key=lambda r: (r["action"], -r["size_bytes"], r["path"]))
    return rows


def move_candidate(row: dict) -> dict | None:
    if row["action"] != "archive_internal":
        return None
    src = ROOT / row["path"]
    if not src.exists():
        row["move_status"] = "source_missing"
        return row

    dst = INTERNAL / row["path"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        row["move_status"] = "destination_exists_skipped"
        row["archive_path"] = rel(dst)
        return row
    shutil.move(str(src), str(dst))
    row["move_status"] = "moved"
    row["archive_path"] = rel(dst)
    return row


def write_plan(rows: list[dict]) -> None:
    lines = [
        "# Dataset Cleanup Plan",
        "",
        "No files are permanently deleted. Removal/exclusion candidates are moved to `archive/internal/` and recorded in `archive_manifest.json`.",
        "",
        "| Dataset Name | Size MB | Classification | Action | Reason |",
        "|---|---:|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['path']} | {row['size_mb']} | {row['classification']} | {row['action']} | {row['reason']} |"
        )
    (REPORT_DIR / "dataset_cleanup_plan.md").write_text("\n".join(lines), encoding="utf-8")


def update_gitignore() -> None:
    gitignore = ROOT / ".gitignore"
    entries = [
        "",
        "# OrthoTwin minimization: large internal recovery archive",
        "archive/internal/",
        "",
    ]
    existing = gitignore.read_text(encoding="utf-8", errors="ignore") if gitignore.exists() else ""
    if "archive/internal/" not in existing:
        gitignore.write_text(existing.rstrip() + "\n" + "\n".join(entries), encoding="utf-8")


def main() -> None:
    ensure_dirs()
    before_size, before_files = dir_size(ROOT)
    rows = inventory()
    save_json(REPORT_DIR / "dataset_inventory.json", {"generated_utc": NOW, "datasets": rows})
    write_plan(rows)

    moved = []
    for row in rows:
        result = move_candidate(row)
        if result:
            moved.append(result)

    update_gitignore()
    after_size, after_files = dir_size(ROOT)
    manifest = {
        "generated_utc": NOW,
        "archive_root": rel(INTERNAL),
        "policy": "No permanent deletion. Files moved to archive/internal are recoverable by original relative path.",
        "moved_items": moved,
        "moved_count": len([m for m in moved if m.get("move_status") == "moved"]),
        "skipped_count": len([m for m in moved if m.get("move_status") != "moved"]),
        "repository_size_before_bytes": before_size,
        "repository_size_after_bytes": after_size,
        "repository_file_count_before": before_files,
        "repository_file_count_after": after_files,
        "github_exclusion_added": "archive/internal/",
    }
    save_json(INTERNAL / "archive_manifest.json", manifest)
    save_json(REPORT_DIR / "archive_manifest.json", manifest)

    summary = f"""# Repository Minimization Summary

Generated: {NOW}

- Dataset records inventoried: {len(rows)}
- Items moved to archive/internal: {manifest['moved_count']}
- Items skipped: {manifest['skipped_count']}
- GitHub exclusion added: `archive/internal/`

The apparent working-tree size remains similar because files were moved, not deleted. GitHub-facing size is reduced by excluding `archive/internal/`.
"""
    (REPORT_DIR / "repository_minimization_summary.md").write_text(summary, encoding="utf-8")

    print("ORTHOTWIN REPOSITORY MINIMIZATION COMPLETE")
    print("Dataset records:", len(rows))
    print("Moved to archive/internal:", manifest["moved_count"])
    print("Skipped:", manifest["skipped_count"])
    print("Archive manifest:", INTERNAL / "archive_manifest.json")


if __name__ == "__main__":
    main()
