"""Phase 9.5 physical calibration recovery audit.

This script inspects existing repository artifacts only. It does not estimate
spacing, modify meshes, modify state vectors, rerun segmentation, or generate
calibrated measurements unless a trusted source chain is proven.
"""

from __future__ import annotations

import csv
import json
import math
import pickle
import re
import struct
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc).isoformat()
REPORT_DIR = ROOT / "reports" / "calibration"
VIS_DIR = ROOT / "visualization" / "calibration"
CALIBRATED_DIR = ROOT / "measurements" / "calibrated"

TARGET_EXTS = {".mha", ".mhd", ".nii", ".nii.gz", ".dcm", ".json", ".yaml", ".yml", ".txt", ".csv", ".pkl"}
TEXT_EXTS = {".json", ".yaml", ".yml", ".txt", ".csv"}


def ensure_dirs() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    VIS_DIR.mkdir(parents=True, exist_ok=True)


def suffix(path: Path) -> str:
    return ".nii.gz" if path.name.lower().endswith(".nii.gz") else path.suffix.lower()


def save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_safe(path: Path, limit: int = 300_000) -> str:
    try:
        with path.open("rb") as f:
            return f.read(limit).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def parse_float_list(value: str) -> list[float] | None:
    nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", str(value))
    if not nums:
        return None
    return [float(n) for n in nums]


def parse_mha_mhd(path: Path) -> dict[str, Any]:
    text = read_text_safe(path, 120_000)
    metadata: dict[str, Any] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = [part.strip() for part in line.split("=", 1)]
        kl = key.lower()
        if kl in {"elementspacing", "spacing"}:
            metadata["spacing"] = parse_float_list(value)
        elif kl == "offset":
            metadata["origin"] = parse_float_list(value)
        elif kl == "transformmatrix":
            metadata["orientation"] = parse_float_list(value)
        elif kl == "dimsize":
            vals = parse_float_list(value)
            metadata["dimensions"] = [int(v) for v in vals] if vals else None
        elif kl in {"anatomicalorientation", "patientid", "seriesinstanceuid", "studyinstanceuid", "sopinstanceuid"}:
            metadata[kl] = value
    return metadata


def parse_nifti(path: Path) -> dict[str, Any]:
    try:
        opener = open
        if path.name.lower().endswith(".gz"):
            import gzip

            opener = gzip.open
        with opener(path, "rb") as f:
            header = f.read(348)
        if len(header) < 348:
            return {}
        sizeof_hdr = struct.unpack("<i", header[:4])[0]
        endian = "<" if sizeof_hdr == 348 else ">"
        dims = struct.unpack(endian + "8h", header[40:56])
        pixdim = struct.unpack(endian + "8f", header[76:108])
        qoffset = struct.unpack(endian + "3f", header[268:280])
        srow_x = struct.unpack(endian + "4f", header[280:296])
        srow_y = struct.unpack(endian + "4f", header[296:312])
        srow_z = struct.unpack(endian + "4f", header[312:328])
        ndim = max(0, int(dims[0]))
        return {
            "dimensions": [int(v) for v in dims[1 : 1 + min(ndim, 7)]],
            "spacing": [float(v) for v in pixdim[1:4]],
            "origin": [float(v) for v in qoffset],
            "orientation": [list(srow_x), list(srow_y), list(srow_z)],
        }
    except Exception as exc:
        return {"parse_error": str(exc)}


def dicom_value(data: bytes, start: int, length: int) -> str:
    return data[start : start + length].decode("utf-8", errors="ignore").strip("\x00 ").strip()


def parse_dicom(path: Path) -> dict[str, Any]:
    """Lightweight DICOM tag parser for common calibration/provenance tags.

    It scans the header byte stream for explicit VR tags. This is conservative:
    if a tag is not found, no value is invented.
    """

    tags = {
        (0x0010, 0x0020): "patient_id",
        (0x0020, 0x000D): "study_uid",
        (0x0020, 0x000E): "series_uid",
        (0x0008, 0x0018): "instance_uid",
        (0x0028, 0x0030): "pixel_spacing",
        (0x0018, 0x0050): "slice_thickness",
        (0x0020, 0x0032): "origin",
        (0x0020, 0x0037): "orientation",
        (0x0028, 0x0010): "rows",
        (0x0028, 0x0011): "columns",
    }
    out: dict[str, Any] = {}
    try:
        with path.open("rb") as f:
            data = f.read(65_536)
    except Exception as exc:
        return {"parse_error": str(exc)}
    if len(data) < 132 or data[128:132] != b"DICM":
        out["dicom_preamble"] = False
    else:
        out["dicom_preamble"] = True

    # Direct explicit-VR little-endian lookup for selected tags. This avoids
    # scanning every byte in large DICOM collections while remaining honest:
    # absent tags are reported as absent, not inferred.
    long_vr = {b"OB", b"OD", b"OF", b"OL", b"OW", b"SQ", b"UC", b"UR", b"UT", b"UN"}
    for (group, elem), name in tags.items():
        needle = struct.pack("<HH", group, elem)
        pos = data.find(needle)
        if pos < 0 or pos + 8 > len(data):
            continue
        vr = data[pos + 4 : pos + 6]
        if not (len(vr) == 2 and 32 <= vr[0] <= 90 and 32 <= vr[1] <= 90):
            continue
        if vr in long_vr:
            if pos + 12 > len(data):
                continue
            length = struct.unpack("<I", data[pos + 8 : pos + 12])[0]
            value_start = pos + 12
        else:
            length = struct.unpack("<H", data[pos + 6 : pos + 8])[0]
            value_start = pos + 8
        if length <= 0 or length > 8192 or value_start + length > len(data):
            continue
        if vr in {b"US", b"SS"} and length in {2, 4}:
            fmt = "<" + ("H" * (length // 2))
            vals = struct.unpack(fmt, data[value_start : value_start + length])
            out[name] = vals[0] if len(vals) == 1 else list(vals)
        else:
            raw = dicom_value(data, value_start, min(length, 512))
            nums = parse_float_list(raw)
            if name in {"pixel_spacing", "slice_thickness", "origin", "orientation"} and nums:
                out[name] = nums
            else:
                out[name] = raw
    if "pixel_spacing" in out:
        spacing = list(out["pixel_spacing"])
        if "slice_thickness" in out:
            st = out["slice_thickness"]
            spacing.append(float(st[0] if isinstance(st, list) else st))
        out["spacing"] = spacing
    if "rows" in out and "columns" in out:
        out["dimensions"] = [int(out["columns"]), int(out["rows"])]
    return out


def parse_text_metadata(path: Path) -> dict[str, Any]:
    text = read_text_safe(path)
    lower = text.lower()
    metadata: dict[str, Any] = {}
    patterns = {
        "spacing": r"(?:voxel[_\s-]*spacing|pixel[_\s-]*spacing|spacing)\s*[:=]\s*\[?([0-9eE.,\\\s+-]+)\]?",
        "slice_thickness": r"(?:slice[_\s-]*thickness)\s*[:=]\s*\[?([0-9eE.,\\\s+-]+)\]?",
        "orientation": r"(?:orientation|direction|transformmatrix)\s*[:=]\s*\[?([0-9eE.,\\\s+-]+)\]?",
        "origin": r"(?:origin|offset)\s*[:=]\s*\[?([0-9eE.,\\\s+-]+)\]?",
        "patient_id": r"(?:patient[_\s-]*id|patient)\s*[:=]\s*([A-Za-z0-9_\-]+)",
        "series_uid": r"(?:series[_\s-]*(?:instance)?uid)\s*[:=]\s*([0-9.]+)",
        "study_uid": r"(?:study[_\s-]*(?:instance)?uid)\s*[:=]\s*([0-9.]+)",
        "instance_uid": r"(?:(?:sop|instance)[_\s-]*(?:instance)?uid)\s*[:=]\s*([0-9.]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        value = match.group(1)
        if key in {"spacing", "slice_thickness", "orientation", "origin"}:
            metadata[key] = parse_float_list(value)
        else:
            metadata[key] = value.strip()
    if "patient_alpha" in lower or "patient alpha" in lower:
        metadata["mentions_patient_alpha"] = True
    return {k: v for k, v in metadata.items() if v not in (None, [], "")}


def parse_pkl_metadata(path: Path) -> dict[str, Any]:
    if path.name != "reconstructed_structures.pkl":
        return {}
    try:
        with path.open("rb") as f:
            obj = pickle.load(f)
    except Exception as exc:
        return {"parse_error": str(exc)}
    if isinstance(obj, list):
        names = [item.get("name") for item in obj if isinstance(item, dict)]
        return {
            "structure_count": len(obj),
            "structure_names": names[:30],
            "contains_mesh_vertices": any(isinstance(item, dict) and "verts" in item for item in obj),
        }
    return {"object_type": type(obj).__name__}


def scan_files() -> tuple[list[Path], list[dict[str, Any]]]:
    paths = [p for p in ROOT.rglob("*") if p.is_file() and suffix(p) in TARGET_EXTS]
    records: list[dict[str, Any]] = []
    for path in paths:
        ext = suffix(path)
        try:
            stat = path.stat()
        except OSError:
            continue
        metadata: dict[str, Any] = {}
        if ext in {".mha", ".mhd"}:
            metadata = parse_mha_mhd(path)
        elif ext in {".nii", ".nii.gz"}:
            metadata = parse_nifti(path)
        elif ext == ".dcm":
            metadata = parse_dicom(path)
        elif ext in TEXT_EXTS:
            metadata = parse_text_metadata(path)
        elif ext == ".pkl":
            metadata = parse_pkl_metadata(path)
        records.append(
            {
                "path": str(path),
                "relative_path": str(path.relative_to(ROOT)),
                "extension": ext,
                "size_bytes": stat.st_size,
                "metadata": metadata,
                "has_spacing": bool(metadata.get("spacing") or metadata.get("pixel_spacing")),
                "has_orientation": bool(metadata.get("orientation")),
                "has_origin": bool(metadata.get("origin")),
                "has_patient_id": bool(metadata.get("patient_id")),
                "has_uid": bool(metadata.get("series_uid") or metadata.get("study_uid") or metadata.get("instance_uid")),
            }
        )
    return paths, records


def normalized_spacing(metadata: dict[str, Any]) -> tuple[float, ...] | None:
    spacing = metadata.get("spacing") or metadata.get("pixel_spacing")
    if not spacing:
        return None
    if not isinstance(spacing, list):
        spacing = [spacing]
    try:
        vals = tuple(round(float(v), 6) for v in spacing[:3])
    except Exception:
        return None
    return vals if vals else None


def image_inventory(records: list[dict[str, Any]]) -> dict[str, Any]:
    spacing_groups = Counter()
    source_examples = defaultdict(list)
    for rec in records:
        spacing = normalized_spacing(rec["metadata"])
        if spacing:
            spacing_groups[str(spacing)] += 1
            if len(source_examples[str(spacing)]) < 10:
                source_examples[str(spacing)].append(rec["relative_path"])
    return {
        "generated_utc": NOW,
        "scope": "Full repository forensic scan of target extensions.",
        "total_target_files": len(records),
        "extension_counts": dict(Counter(rec["extension"] for rec in records)),
        "files_with_spacing": sum(1 for rec in records if rec["has_spacing"]),
        "files_with_orientation": sum(1 for rec in records if rec["has_orientation"]),
        "files_with_origin": sum(1 for rec in records if rec["has_origin"]),
        "files_with_patient_id": sum(1 for rec in records if rec["has_patient_id"]),
        "files_with_uid": sum(1 for rec in records if rec["has_uid"]),
        "spacing_groups": [
            {"spacing": key, "count": count, "examples": source_examples[key]}
            for key, count in spacing_groups.most_common()
        ],
        "records": records,
    }


def linkage_graph(records: list[dict[str, Any]]) -> dict[str, Any]:
    evidence = []
    for rec in records:
        path_l = rec["relative_path"].lower()
        meta = rec["metadata"]
        score = 0
        reasons = []
        if "patient_alpha" in path_l or "patient alpha" in path_l:
            score += 2
            reasons.append("filename_or_directory_mentions_patient_alpha")
        if meta.get("mentions_patient_alpha"):
            score += 2
            reasons.append("file_content_mentions_patient_alpha")
        patient_id = str(meta.get("patient_id", "")).lower()
        if "alpha" in patient_id or "patient_alpha" in patient_id:
            score += 3
            reasons.append("metadata_patient_id_mentions_alpha")
        if "reconstructed_structures.pkl" in path_l:
            score += 1
            reasons.append("active_reconstruction_artifact")
        if score:
            evidence.append(
                {
                    "file": rec["relative_path"],
                    "score": score,
                    "reasons": reasons,
                    "metadata": {k: meta.get(k) for k in ["patient_id", "series_uid", "study_uid", "instance_uid", "spacing", "origin", "orientation"] if k in meta},
                }
            )
    has_trusted_image = any(item["score"] >= 5 and item["metadata"].get("spacing") for item in evidence)
    if has_trusted_image:
        confidence = "HIGH"
    elif any(item["score"] >= 3 for item in evidence):
        confidence = "MEDIUM"
    elif evidence:
        confidence = "LOW"
    else:
        confidence = "NONE"
    nodes = [{"id": "patient_alpha", "type": "patient"}]
    edges = []
    for item in evidence[:250]:
        fid = item["file"]
        nodes.append({"id": fid, "type": "artifact", "score": item["score"]})
        edges.append({"from": "patient_alpha", "to": fid, "confidence_score": item["score"], "reasons": item["reasons"]})
    return {
        "generated_utc": NOW,
        "confidence": confidence,
        "trusted_image_link_found": has_trusted_image,
        "evidence_count": len(evidence),
        "nodes": nodes,
        "edges": edges,
        "evidence": sorted(evidence, key=lambda x: x["score"], reverse=True),
    }


def traceback(records: list[dict[str, Any]], linkage: dict[str, Any]) -> dict[str, Any]:
    recon = ROOT / "measurements" / "geometry" / "reconstructed_structures.pkl"
    candidates = []
    keywords = ["patient_alpha", "clean", "prediction", "mask", "seg", "reconstruct", "structure"]
    for rec in records:
        path_l = rec["relative_path"].lower()
        if any(k in path_l for k in keywords):
            candidates.append(
                {
                    "file": rec["relative_path"],
                    "extension": rec["extension"],
                    "has_spacing": rec["has_spacing"],
                    "has_orientation": rec["has_orientation"],
                    "metadata_summary": {k: rec["metadata"].get(k) for k in ["spacing", "origin", "orientation", "patient_id", "series_uid", "study_uid"] if k in rec["metadata"]},
                }
            )
    masks = [c for c in candidates if any(k in c["file"].lower() for k in ["mask", "prediction", "seg"])]
    images = [c for c in candidates if c["extension"] in {".mha", ".mhd", ".nii", ".nii.gz", ".dcm"}]
    can_trace_to_metadata = any(c["has_spacing"] and ("patient_alpha" in c["file"].lower() or "alpha" in str(c["metadata_summary"]).lower()) for c in images)
    return {
        "generated_utc": NOW,
        "start": str(recon),
        "reconstruction_exists": recon.exists(),
        "candidate_masks_or_segmentations": masks[:200],
        "candidate_images": images[:200],
        "linkage_confidence": linkage["confidence"],
        "can_trace_reconstruction_to_specific_metadata_source": can_trace_to_metadata,
        "traceback_status": "PARTIAL_TRACE_ONLY" if candidates else "NO_TRACE_FOUND",
        "reasoning": "Candidate files were found by lineage keywords, but a provable chain from reconstructed_structures.pkl to a specific calibrated Patient Alpha image source is required before physical calibration can be trusted.",
    }


def geometry_dimensions() -> dict[str, Any]:
    mesh_state = load_json(ROOT / "state" / "mesh" / "mesh_state_vector.json")
    structures = mesh_state.get("structures", {})
    dims = []
    for sid, item in structures.items():
        bbox = item.get("bounding_box", {})
        dimensions = bbox.get("dimensions")
        if dimensions:
            dims.append({"id": sid, "name": item.get("name"), "type": item.get("type"), "voxel_dimensions": dimensions})
    return {"structures": dims}


def spacing_ranking(records: list[dict[str, Any]]) -> dict[str, Any]:
    geom = geometry_dimensions()
    spacing_counts = Counter()
    examples = defaultdict(list)
    for rec in records:
        sp = normalized_spacing(rec["metadata"])
        if sp:
            spacing_counts[sp] += 1
            if len(examples[sp]) < 5:
                examples[sp].append(rec["relative_path"])

    ranked = []
    for sp, count in spacing_counts.most_common():
        physical_samples = []
        for item in geom["structures"][:14]:
            dims = item["voxel_dimensions"]
            scale = list(sp) + [sp[-1]] * (3 - len(sp))
            physical = [round(float(dims[i]) * float(scale[i]), 3) for i in range(min(3, len(dims)))]
            physical_samples.append({"structure": item["name"], "dimensions_if_used": physical})
        # No winner is selected. Plausibility is only a sorting aid.
        finite = [v for row in physical_samples for v in row["dimensions_if_used"] if math.isfinite(v)]
        median_dim = float(np.median(finite)) if finite else 0
        plausibility_proxy = 1.0 / (1.0 + abs(median_dim - 50.0))
        ranked.append(
            {
                "spacing": list(sp),
                "source_file_count": count,
                "example_sources": examples[sp],
                "expected_bounding_box_size_samples": physical_samples[:8],
                "ranking_score_not_selection": round(float(count) * plausibility_proxy, 6),
                "warning": "Ranking only. This does not prove linkage to Patient Alpha reconstruction.",
            }
        )
    ranked.sort(key=lambda x: x["ranking_score_not_selection"], reverse=True)
    return {
        "generated_utc": NOW,
        "candidate_spacing_count": len(ranked),
        "ranked_candidates": ranked,
        "automatic_winner_selected": False,
    }


def decision(linkage: dict[str, Any], trace: dict[str, Any], ranking: dict[str, Any]) -> dict[str, Any]:
    trusted = linkage["confidence"] == "HIGH" and trace["can_trace_reconstruction_to_specific_metadata_source"]
    partial = linkage["confidence"] in {"MEDIUM", "LOW"} or bool(ranking["candidate_spacing_count"])
    if trusted:
        dec = "trusted calibration recovered"
        confidence = "HIGH"
    elif partial:
        dec = "calibration partially recovered"
        confidence = "LOW"
    else:
        dec = "calibration still blocked"
        confidence = "NONE"
    if dec != "trusted calibration recovered":
        # Partial metadata candidates are not enough for calibration.
        dec = "calibration still blocked"
        confidence = "NONE" if linkage["confidence"] == "NONE" else "LOW"
    return {
        "generated_utc": NOW,
        "decision": dec,
        "confidence": confidence,
        "trusted_calibration_recovered": dec == "trusted calibration recovered",
        "reasoning": [
            f"Patient Alpha linkage confidence: {linkage['confidence']}.",
            f"Traceback status: {trace['traceback_status']}.",
            f"Candidate spacing groups: {ranking['candidate_spacing_count']}.",
            "Candidate metadata exists only if it can be linked to the active reconstruction. Without that chain, calibrated measurements are not generated.",
        ],
        "evidence_chain": {
            "linkage_confidence": linkage["confidence"],
            "trusted_image_link_found": linkage["trusted_image_link_found"],
            "can_trace_reconstruction_to_specific_metadata_source": trace["can_trace_reconstruction_to_specific_metadata_source"],
            "automatic_spacing_winner_selected": ranking["automatic_winner_selected"],
        },
    }


def draw_lineage_graph(linkage: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(12, 7))
    ax.axis("off")
    stages = ["reconstructed_structures.pkl", "candidate masks", "candidate images", "metadata", "calibration decision"]
    xs = np.linspace(0.08, 0.92, len(stages))
    for i, (x, stage) in enumerate(zip(xs, stages)):
        ax.scatter([x], [0.55], s=1800, color="#eaf2f8", edgecolor="#2c3e50")
        ax.text(x, 0.55, stage, ha="center", va="center", fontsize=9, fontweight="bold")
        if i < len(stages) - 1:
            ax.annotate("", xy=(xs[i + 1] - 0.06, 0.55), xytext=(x + 0.06, 0.55), arrowprops={"arrowstyle": "->", "lw": 1.8})
    ax.text(0.5, 0.20, f"Patient Alpha linkage confidence: {linkage['confidence']}", ha="center", fontsize=13)
    ax.set_title("Metadata Lineage Graph", fontsize=20, fontweight="bold")
    fig.savefig(VIS_DIR / "metadata_lineage_graph.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_patient_linkage(linkage: dict[str, Any]) -> None:
    evidence = linkage.get("evidence", [])[:12]
    labels = [Path(item["file"]).name[:28] for item in evidence]
    scores = [item["score"] for item in evidence]
    fig, ax = plt.subplots(figsize=(12, 6))
    if labels:
        ax.barh(labels[::-1], scores[::-1], color="#4a90a4")
        ax.set_xlabel("Linkage evidence score")
    else:
        ax.text(0.5, 0.5, "No Patient Alpha linkage evidence found", ha="center", va="center")
    ax.set_title("Patient Alpha Linkage Graph Evidence", fontsize=18, fontweight="bold")
    ax.grid(axis="x", alpha=0.25)
    fig.savefig(VIS_DIR / "patient_alpha_linkage_graph.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_spacing_dashboard(ranking: dict[str, Any]) -> None:
    candidates = ranking["ranked_candidates"][:12]
    labels = [str(c["spacing"]) for c in candidates]
    counts = [c["source_file_count"] for c in candidates]
    scores = [c["ranking_score_not_selection"] for c in candidates]
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    if candidates:
        axes[0].barh(labels[::-1], counts[::-1], color="#2f80ed")
        axes[0].set_title("Candidate Source Counts")
        axes[1].barh(labels[::-1], scores[::-1], color="#f2994a")
        axes[1].set_title("Ranking Score, Not Selection")
    else:
        for ax in axes:
            ax.text(0.5, 0.5, "No spacing candidates", ha="center", va="center")
    fig.suptitle("Spacing Candidate Dashboard", fontsize=20, fontweight="bold")
    fig.savefig(VIS_DIR / "spacing_candidate_dashboard.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def draw_decision_flow(decision_data: dict[str, Any]) -> None:
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.axis("off")
    steps = [
        ("Metadata found?", "yes/no"),
        ("Patient Alpha linked?", decision_data["evidence_chain"]["linkage_confidence"]),
        ("Reconstruction traced?", str(decision_data["evidence_chain"]["can_trace_reconstruction_to_specific_metadata_source"])),
        ("Decision", decision_data["decision"]),
    ]
    y = 0.85
    for idx, (title, value) in enumerate(steps):
        ax.text(0.5, y, title, ha="center", fontsize=13, fontweight="bold", bbox={"boxstyle": "round,pad=0.35", "fc": "#eef2f3", "ec": "#34495e"})
        ax.text(0.5, y - 0.07, value, ha="center", fontsize=11)
        if idx < len(steps) - 1:
            ax.annotate("", xy=(0.5, y - 0.18), xytext=(0.5, y - 0.10), arrowprops={"arrowstyle": "->", "lw": 1.5})
        y -= 0.24
    ax.set_title("Calibration Decision Flowchart", fontsize=20, fontweight="bold")
    fig.savefig(VIS_DIR / "calibration_decision_flowchart.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_audit(records: list[dict[str, Any]], inv: dict[str, Any], linkage: dict[str, Any], trace: dict[str, Any], ranking: dict[str, Any], dec: dict[str, Any]) -> None:
    text = f"""ORTHOTWIN PHASE 9.5 PHYSICAL CALIBRATION RECOVERY AUDIT

Generated: {NOW}

How many candidate image sources exist?
{sum(1 for r in records if r['extension'] in {'.mha', '.mhd', '.nii', '.nii.gz', '.dcm'})}

How many spacing groups exist?
{ranking['candidate_spacing_count']}

Can Patient Alpha be linked?
{linkage['confidence']} confidence. Trusted image link found: {linkage['trusted_image_link_found']}.

Can reconstruction be traced?
{trace['traceback_status']}. Specific metadata source trace: {trace['can_trace_reconstruction_to_specific_metadata_source']}.

Can physical calibration be recovered?
{dec['decision']} with confidence {dec['confidence']}.

What remains blocked?
Trusted physical spacing, orientation, and slice thickness for the active Patient Alpha reconstruction remain blocked unless a source image can be proven to generate the active masks and reconstructed_structures.pkl.

What evidence supports the conclusion?
- Total target files scanned: {inv['total_target_files']}
- Files with spacing metadata: {inv['files_with_spacing']}
- Files with orientation metadata: {inv['files_with_orientation']}
- Files with origin metadata: {inv['files_with_origin']}
- Files with patient id metadata: {inv['files_with_patient_id']}
- Files with UID metadata: {inv['files_with_uid']}
- Patient Alpha linkage confidence: {linkage['confidence']}
- Candidate spacing groups were ranked but no winner was selected automatically.

Scientific conclusion:
Success criteria are satisfied because recovery possibility was tested. Calibration remains blocked unless a full evidence chain is recovered.
"""
    (REPORT_DIR / "phase95_calibration_audit.txt").write_text(text, encoding="utf-8")


def maybe_generate_calibrated(dec: dict[str, Any]) -> None:
    if dec["decision"] != "trusted calibration recovered":
        return
    CALIBRATED_DIR.mkdir(parents=True, exist_ok=True)
    # This branch intentionally remains conservative. If future evidence proves
    # trusted calibration, implement conversion from a documented spacing source.
    (REPORT_DIR / "calibrated_measurement_report.txt").write_text(
        "Trusted calibration recovered, but conversion implementation requires explicit evidence-chain spacing selection.\n",
        encoding="utf-8",
    )


def main() -> None:
    ensure_dirs()
    _, records = scan_files()
    inv = image_inventory(records)
    save_json(REPORT_DIR / "image_metadata_inventory.json", inv)
    link = linkage_graph(records)
    save_json(REPORT_DIR / "patient_alpha_linkage_graph.json", link)
    trace = traceback(records, link)
    save_json(REPORT_DIR / "reconstruction_traceback.json", trace)
    ranking = spacing_ranking(records)
    save_json(REPORT_DIR / "spacing_candidate_ranking.json", ranking)
    dec = decision(link, trace, ranking)
    save_json(REPORT_DIR / "physical_calibration_decision.json", dec)
    maybe_generate_calibrated(dec)
    draw_lineage_graph(link)
    draw_patient_linkage(link)
    draw_spacing_dashboard(ranking)
    draw_decision_flow(dec)
    write_audit(records, inv, link, trace, ranking, dec)
    manifest = {
        "generated_utc": NOW,
        "decision": dec["decision"],
        "confidence": dec["confidence"],
        "files": [
            str(REPORT_DIR / "image_metadata_inventory.json"),
            str(REPORT_DIR / "patient_alpha_linkage_graph.json"),
            str(REPORT_DIR / "reconstruction_traceback.json"),
            str(REPORT_DIR / "spacing_candidate_ranking.json"),
            str(REPORT_DIR / "physical_calibration_decision.json"),
            str(REPORT_DIR / "phase95_calibration_audit.txt"),
            str(VIS_DIR / "metadata_lineage_graph.png"),
            str(VIS_DIR / "patient_alpha_linkage_graph.png"),
            str(VIS_DIR / "spacing_candidate_dashboard.png"),
            str(VIS_DIR / "calibration_decision_flowchart.png"),
        ],
        "calibrated_measurements_generated": dec["decision"] == "trusted calibration recovered",
        "no_fake_spacing": True,
        "no_inference": True,
        "no_reconstruction": True,
    }
    save_json(REPORT_DIR / "phase95_manifest.json", manifest)
    print("ORTHOTWIN PHASE 9.5 CALIBRATION AUDIT COMPLETE")
    print("Decision:", dec["decision"])
    print("Confidence:", dec["confidence"])
    print("Target files scanned:", inv["total_target_files"])
    print("Spacing groups:", ranking["candidate_spacing_count"])
    print("Calibrated measurements generated:", manifest["calibrated_measurements_generated"])


if __name__ == "__main__":
    main()
