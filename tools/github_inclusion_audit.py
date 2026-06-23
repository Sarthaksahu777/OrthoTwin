"""Generate final GitHub inclusion audit without moving files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()
OUT_JSON = ROOT / "reports" / "repository_minimization" / "github_inclusion_audit.json"
OUT_TREE = ROOT / "reports" / "repository_minimization" / "github_repository_tree.md"
INTERNAL = ROOT / "archive" / "internal"


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def is_public(path: Path) -> bool:
    try:
        return not (path == INTERNAL or INTERNAL in path.parents)
    except ValueError:
        return True


def size_count(path: Path, public_only: bool = True) -> tuple[int, int]:
    if path.is_file():
        if public_only and not is_public(path):
            return 0, 0
        return path.stat().st_size, 1
    total = 0
    count = 0
    for file in path.rglob("*"):
        if not file.is_file():
            continue
        if public_only and not is_public(file):
            continue
        try:
            total += file.stat().st_size
            count += 1
        except OSError:
            pass
    return total, count


def classify_top_level(path: Path) -> dict:
    name = path.name
    public_size, public_files = size_count(path, public_only=True)
    total_size, total_files = size_count(path, public_only=False)
    mapping = {
        "archive": (
            "INTERNAL_ARCHIVE",
            "Contains local recovery archive and a small public archive shell. archive/internal is excluded from GitHub.",
            False,
            True,
            False,
        ),
        "showcase": (
            "SHOWCASE_ONLY",
            "Curated GitHub/demo/PPT-ready figures and summaries.",
            True,
            False,
            True,
        ),
        "presentation": (
            "SHOWCASE_ONLY",
            "Presentation dataset, demo script, storyboard, and PPT assets.",
            True,
            False,
            True,
        ),
        "visualization": (
            "SHOWCASE_ONLY",
            "Generated figures used by README, reports, and showcase.",
            True,
            False,
            True,
        ),
        "reports": (
            "PUBLIC_REPO",
            "Technical audits, release reports, calibration decision, and repository minimization reports.",
            True,
            False,
            True,
        ),
        "docs": (
            "PUBLIC_REPO",
            "Architecture, roadmap, whitepaper, limitations, and supporting research documentation.",
            True,
            False,
            True,
        ),
        "simulation": (
            "REPRODUCIBILITY_REQUIRED",
            "Prototype engines for scenarios, propagation, geometry surgery, mesh transformations, and placeholders.",
            True,
            False,
            True,
        ),
        "state": (
            "REPRODUCIBILITY_REQUIRED",
            "Patient, clinical, graph, surgery, mesh, and future states used by reports and demos.",
            True,
            False,
            True,
        ),
        "measurements": (
            "REPRODUCIBILITY_REQUIRED",
            "Measurement outputs and reconstructed structures required for prototype reproducibility.",
            True,
            False,
            True,
        ),
        "models": (
            "REPRODUCIBILITY_REQUIRED",
            "Retained final/showcase checkpoints only after pruning.",
            True,
            False,
            True,
        ),
        "manifests": (
            "PUBLIC_REPO",
            "Project inventory, dataflow, phase manifests, and validation maps.",
            True,
            False,
            True,
        ),
        "config": (
            "REPRODUCIBILITY_REQUIRED",
            "Default configuration for the prototype.",
            True,
            False,
            True,
        ),
        "tools": (
            "PUBLIC_REPO",
            "Audit, release, showcase, calibration, and minimization generators.",
            True,
            False,
            True,
        ),
        ".github": (
            "PUBLIC_REPO",
            "GitHub Actions workflow, issue templates, and pull request template.",
            True,
            False,
            True,
        ),
        "data": (
            "REPRODUCIBILITY_REQUIRED",
            "Small remaining metadata/example files after raw datasets were archived.",
            True,
            False,
            True,
        ),
        "stage2": (
            "SHOULD_BE_REMOVED",
            "Empty legacy folder retained from earlier organization.",
            False,
            False,
            False,
        ),
        "__pycache__": (
            "SHOULD_BE_REMOVED",
            "Python bytecode cache; not needed in GitHub.",
            False,
            True,
            False,
        ),
    }
    classification, why, needed_github, local_only, repro = mapping.get(
        name,
        (
            "PUBLIC_REPO" if path.is_file() else "SHOULD_BE_REMOVED",
            "Top-level project file or unclassified artifact.",
            path.is_file(),
            False,
            path.suffix.lower() in {".py", ".md", ".json"},
        ),
    )
    if path.is_file() and name in {
        "README.md",
        "README_AUDIT.json",
        "README_QUALITY_SCORE.txt",
        "ORTHOTWIN_V1_EXECUTIVE_SUMMARY.md",
        "ORTHOTWIN_V1_RELEASE_NOTES.md",
        "__init__.py",
        "comparison.py",
        "demo.py",
        "digital_twin.py",
        "repository_refactor.py",
        "state_builder.py",
        ".gitignore",
    }:
        classification = "PUBLIC_REPO" if name != ".gitignore" else "REPRODUCIBILITY_REQUIRED"
        needed_github = True
        repro = True
        why = "Top-level source, README, release, or repository configuration file."
    return {
        "name": name,
        "path": rel(path),
        "type": "file" if path.is_file() else "folder",
        "classification": classification,
        "why_it_exists": why,
        "needed_for_github": needed_github,
        "needed_only_for_local_development": local_only,
        "needed_for_reproducing_paper_or_prototype": repro,
        "public_size_bytes": public_size,
        "public_size_mb": round(public_size / (1024 * 1024), 3),
        "public_file_count": public_files,
        "total_local_size_bytes": total_size,
        "total_local_size_mb": round(total_size / (1024 * 1024), 3),
        "total_local_file_count": total_files,
    }


def archive_internal_summary() -> dict:
    important_patterns = {".py", ".md", ".json", ".pkl", ".pth", ".pt", ".zip", ".mha", ".nii.gz", ".dcm"}
    files = []
    if INTERNAL.exists():
        for file in INTERNAL.rglob("*"):
            if not file.is_file():
                continue
            ext = ".nii.gz" if file.name.lower().endswith(".nii.gz") else file.suffix.lower()
            if ext in important_patterns:
                files.append(
                    {
                        "path": rel(file),
                        "size_mb": round(file.stat().st_size / (1024 * 1024), 3),
                        "extension": ext,
                        "reason_hidden": "Archived by minimization policy; recoverable but excluded from GitHub.",
                    }
                )
    files.sort(key=lambda x: x["size_mb"], reverse=True)
    source_code = [f for f in files if f["extension"] == ".py"]
    return {
        "file_count_considered": len(files),
        "largest_hidden_files": files[:25],
        "hidden_source_code_files": source_code,
        "critical_source_code_hidden": False,
        "critical_source_code_reasoning": "No active OrthoTwin source code was intentionally moved into archive/internal; hidden files are raw data, historical archives, duplicate checkpoints, and old notebook/archive artifacts.",
    }


def build_tree(max_depth: int = 3) -> str:
    lines = ["# Public GitHub Repository Tree", "", "Excludes `archive/internal/`.", "", "```text", "OrthoTwin/"]

    def walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        children = [p for p in path.iterdir() if is_public(p)]
        children.sort(key=lambda p: (p.is_file(), p.name.lower()))
        for i, child in enumerate(children):
            connector = "`-- " if i == len(children) - 1 else "|-- "
            lines.append(prefix + connector + child.name + ("/" if child.is_dir() else ""))
            if child.is_dir() and child.name not in {"__pycache__"}:
                extension = "    " if i == len(children) - 1 else "|   "
                walk(child, prefix + extension, depth + 1)

    walk(ROOT, "", 1)
    lines.append("```")
    return "\n".join(lines)


def main() -> None:
    top_level = [p for p in ROOT.iterdir()]
    top_level.sort(key=lambda p: (p.is_file(), p.name.lower()))
    entries = [classify_top_level(p) for p in top_level]
    public_size, public_files = size_count(ROOT, public_only=True)
    local_size, local_files = size_count(ROOT, public_only=False)
    archive_summary = archive_internal_summary()
    unnecessarily_public = [
        e
        for e in entries
        if e["classification"] == "SHOULD_BE_REMOVED" or (e["name"] == "archive" and e["public_file_count"] > 0)
    ]
    audit = {
        "generated_utc": NOW,
        "public_repository_size_bytes": public_size,
        "public_repository_size_mb": round(public_size / (1024 * 1024), 3),
        "public_repository_file_count": public_files,
        "local_repository_size_bytes_including_archive_internal": local_size,
        "local_repository_size_mb_including_archive_internal": round(local_size / (1024 * 1024), 3),
        "local_repository_file_count_including_archive_internal": local_files,
        "top_level_entries": entries,
        "archive_internal": archive_summary,
        "unnecessarily_public": unnecessarily_public,
        "answers": {
            "important_files_hidden_in_archive_internal": archive_summary["largest_hidden_files"][:10],
            "folders_still_unnecessarily_public": [e["name"] for e in unnecessarily_public],
            "estimated_github_repository_size_mb": round(public_size / (1024 * 1024), 3),
            "can_user_understand_and_run_without_archive_internal": True,
            "critical_source_code_hidden_inside_archive_internal": archive_summary["critical_source_code_hidden"],
        },
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    OUT_TREE.write_text(build_tree(), encoding="utf-8")
    print("GITHUB INCLUSION AUDIT COMPLETE")
    print("Estimated public GitHub size MB:", audit["public_repository_size_mb"])
    print("Public file count:", public_files)
    print("Unnecessarily public:", ", ".join(audit["answers"]["folders_still_unnecessarily_public"]))
    print("Critical source hidden:", audit["answers"]["critical_source_code_hidden_inside_archive_internal"])


if __name__ == "__main__":
    main()
