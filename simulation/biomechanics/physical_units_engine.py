"""Phase 4.5 physical calibration engine.

This module searches existing OrthoTwin files for image metadata and converts
voxel-space measurements to physical units only when spacing can be linked to
the active Patient Alpha state. It does not retrain, infer, segment, clean,
or modify reconstruction data.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = PROJECT_ROOT / "manifests" / "project_inventory.json"
STATE_PATH = PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector.json"
CENTERLINE_PATH = PROJECT_ROOT / "state" / "graphs" / "spine_centerline.json"

OUTPUT_DIR = PROJECT_ROOT / "measurements" / "calibration"
REPORT_DIR = PROJECT_ROOT / "reports" / "phase4_5"
MANIFEST_DIR = PROJECT_ROOT / "manifests"

IMAGE_EXTENSIONS = {".mha", ".nii", ".nii.gz", ".dcm", ".dicom"}
TEXT_EXTENSIONS = {".json", ".txt", ".md", ".yaml", ".yml", ".cfg", ".ini", ".py"}
SPACING_PATTERNS = (
    "spacing",
    "elementspacing",
    "slice thickness",
    "slicethickness",
    "pixelspacing",
    "voxel",
    "origin",
    "offset",
    "transformmatrix",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_extension(path: Path, inventory_extension: str | None = None) -> str:
    lower = str(path).lower()
    if lower.endswith(".nii.gz"):
        return ".nii.gz"
    if inventory_extension:
        return inventory_extension.lower()
    return path.suffix.lower()


def iter_inventory_files() -> list[dict[str, Any]]:
    if INVENTORY_PATH.exists():
        inventory = load_json(INVENTORY_PATH, [])
        if isinstance(inventory, list):
            return inventory
        if isinstance(inventory, dict):
            return inventory.get("files", [])

    records: list[dict[str, Any]] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        records.append(
            {
                "filename": path.name,
                "extension": normalize_extension(path),
                "full_path": str(path),
                "relative_path": str(path.relative_to(PROJECT_ROOT)),
                "size": stat.st_size,
            }
        )
    return records


def parse_number_list(value: str) -> list[float] | None:
    numbers = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", value)
    if not numbers:
        return None
    return [float(item) for item in numbers]


def parse_mha_header(path: Path) -> dict[str, Any]:
    header_bytes = b""
    with path.open("rb") as handle:
        while len(header_bytes) < 131072:
            chunk = handle.readline()
            if not chunk:
                break
            header_bytes += chunk
            if chunk.strip().lower().startswith(b"elementdatafile"):
                break

    text = header_bytes.decode("latin-1", errors="replace")
    fields: dict[str, str] = {}
    for raw_line in text.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        fields[key.strip()] = value.strip()

    return {
        "parser": "mha_header",
        "spacing": parse_number_list(fields.get("ElementSpacing", "")),
        "origin": parse_number_list(fields.get("Offset", "")),
        "orientation": fields.get("AnatomicalOrientation"),
        "direction": parse_number_list(fields.get("TransformMatrix", "")),
        "dimensions": parse_number_list(fields.get("DimSize", "")),
        "raw_fields": {
            key: fields.get(key)
            for key in (
                "ObjectType",
                "NDims",
                "DimSize",
                "ElementSpacing",
                "Offset",
                "TransformMatrix",
                "AnatomicalOrientation",
                "ElementType",
            )
            if key in fields
        },
    }


def parse_with_simpleitk(path: Path) -> dict[str, Any]:
    try:
        import SimpleITK as sitk  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local env
        return {"parser": "simpleitk_unavailable", "error": str(exc)}

    try:
        reader = sitk.ImageFileReader()
        reader.SetFileName(str(path))
        reader.ReadImageInformation()
        spacing = list(reader.GetSpacing())
        origin = list(reader.GetOrigin())
        direction = list(reader.GetDirection())
        dimensions = list(reader.GetSize())
        metadata = {}
        for key in reader.GetMetaDataKeys():
            if key.lower() in {"0028|0030", "0018|0050", "0020|0037", "0020|0032"}:
                metadata[key] = reader.GetMetaData(key)
        return {
            "parser": "simpleitk_header",
            "spacing": spacing,
            "origin": origin,
            "orientation": metadata.get("0020|0037"),
            "direction": direction,
            "dimensions": dimensions,
            "dicom_metadata": metadata,
        }
    except Exception as exc:
        return {"parser": "simpleitk_header_failed", "error": str(exc)}


def extract_text_metadata(path: Path, max_bytes: int = 2_000_000) -> list[dict[str, Any]]:
    try:
        if path.stat().st_size > max_bytes:
            return []
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    hits: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        lowered = line.lower()
        if any(pattern in lowered for pattern in SPACING_PATTERNS):
            snippet = line.strip()
            hits.append(
                {
                    "line": line_number,
                    "snippet": snippet[:240],
                    "numbers": parse_number_list(snippet),
                }
            )
        if len(hits) >= 20:
            break
    return hits


def collect_metadata() -> dict[str, Any]:
    files = iter_inventory_files()
    counts = {
        "total_files_scanned": len(files),
        "image_candidates": 0,
        "mha_files": 0,
        "nii_files": 0,
        "dicom_files": 0,
        "text_metadata_candidates": 0,
    }
    image_records: list[dict[str, Any]] = []
    text_records: list[dict[str, Any]] = []

    dicom_samples_parsed = 0
    max_dicom_samples = 30

    for item in files:
        path = Path(item.get("full_path", ""))
        extension = normalize_extension(path, item.get("extension"))
        if extension in IMAGE_EXTENSIONS:
            counts["image_candidates"] += 1
            record: dict[str, Any] = {
                "path": str(path),
                "relative_path": item.get("relative_path"),
                "extension": extension,
                "size": item.get("size"),
                "spacing": None,
                "origin": None,
                "orientation": None,
                "direction": None,
                "patient_alpha_link": "patient_alpha" in str(path).lower(),
            }
            if extension == ".mha":
                counts["mha_files"] += 1
                record.update(parse_mha_header(path))
            elif extension in {".nii", ".nii.gz"}:
                counts["nii_files"] += 1
                record.update(parse_with_simpleitk(path))
            else:
                counts["dicom_files"] += 1
                if dicom_samples_parsed < max_dicom_samples:
                    record.update(parse_with_simpleitk(path))
                    dicom_samples_parsed += 1
                else:
                    record.update({"parser": "dicom_sample_limit", "spacing": None})

            if record.get("spacing") or record.get("parser") != "dicom_sample_limit":
                image_records.append(record)

        elif extension in TEXT_EXTENSIONS:
            hits = extract_text_metadata(path)
            if hits:
                counts["text_metadata_candidates"] += 1
                text_records.append(
                    {
                        "path": str(path),
                        "relative_path": item.get("relative_path"),
                        "extension": extension,
                        "patient_alpha_link": "patient_alpha" in str(path).lower(),
                        "hits": hits,
                    }
                )

    return {
        "generated_utc": utc_now(),
        "search_scope": str(PROJECT_ROOT),
        "counts": counts,
        "image_metadata_records": image_records,
        "text_metadata_records": text_records,
    }


def rounded_spacing(spacing: Any) -> tuple[float, ...] | None:
    if not isinstance(spacing, list) or len(spacing) < 3:
        return None
    return tuple(round(float(value), 8) for value in spacing[:3])


def validate_spacing(metadata_report: dict[str, Any]) -> dict[str, Any]:
    spacings: dict[str, dict[str, Any]] = {}
    patient_alpha_image_records: list[dict[str, Any]] = []

    for record in metadata_report.get("image_metadata_records", []):
        spacing = rounded_spacing(record.get("spacing"))
        if spacing is None:
            continue
        key = " x ".join(str(value) for value in spacing)
        spacings.setdefault(key, {"spacing": list(spacing), "count": 0, "examples": []})
        spacings[key]["count"] += 1
        if len(spacings[key]["examples"]) < 5:
            spacings[key]["examples"].append(record.get("path"))
        if record.get("patient_alpha_link"):
            patient_alpha_image_records.append(record)

    runtime_evidence = []
    for report_path in (
        PROJECT_ROOT / "reports" / "phase3" / "runtime_recovery_report.txt",
        PROJECT_ROOT
        / "archive"
        / "OrthoTwin_Final_Archive"
        / "runtime_recovery_report.txt",
    ):
        if report_path.exists():
            text = report_path.read_text(encoding="utf-8", errors="ignore").lower()
            if "voxel spacing information was not explicitly available" in text:
                runtime_evidence.append(str(report_path))

    has_patient_spacing = any(rounded_spacing(item.get("spacing")) for item in patient_alpha_image_records)
    trusted_patient_alpha_spacing = bool(has_patient_spacing and not runtime_evidence)

    return {
        "generated_utc": utc_now(),
        "spacing_groups": list(spacings.values()),
        "unique_spacing_count": len(spacings),
        "is_spacing_identical_across_dataset": len(spacings) == 1,
        "is_spacing_patient_specific": len(spacings) > 1,
        "patient_alpha_image_records_with_spacing": patient_alpha_image_records,
        "runtime_reports_declaring_missing_mesh_spacing": runtime_evidence,
        "trusted_patient_alpha_spacing_available": trusted_patient_alpha_spacing,
        "calibration_decision": (
            "calibrate"
            if trusted_patient_alpha_spacing
            else "stop_missing_trusted_patient_alpha_spacing"
        ),
        "decision_reason": (
            "Patient Alpha image spacing was found and no contradictory mesh-spacing evidence was found."
            if trusted_patient_alpha_spacing
            else "Repository contains image metadata, but no spacing metadata is reliably linked to the Patient Alpha reconstructed mesh/state."
        ),
    }


def missing_spacing_report(validation: dict[str, Any]) -> str:
    return "\n".join(
        [
            "ORTHOTWIN PHASE 4.5 MISSING SPACING REPORT",
            "",
            "Physical calibration was stopped.",
            "",
            "Reason:",
            validation["decision_reason"],
            "",
            "Why calibration cannot be trusted:",
            "- Phase 4 measurements were generated from reconstructed mesh/state files stored in voxel units.",
            "- Raw image metadata exists in the repository, but it is not linked to the active Patient Alpha state vector.",
            "- A prior runtime report states that voxel spacing was not explicitly available in the loaded mesh data or measurement JSON.",
            "- Borrowing spacing from an unrelated raw image, dataset sample, or DICOM series would create false physical precision.",
            "",
            "Rules followed:",
            "- No 1 mm voxel assumption was used.",
            "- No estimated spacing was invented.",
            "- No segmentation, mask, reconstruction, inference, or training files were modified.",
            "",
            "Required to proceed:",
            "- The original Patient Alpha image header or DICOM series used to create patient_alpha_clean_prediction.npy.",
            "- A clear mapping from that image to reconstructed_structures.pkl and patient_state_vector_v2.json.",
            "- Verified voxel spacing, origin, direction/orientation, and axis order for the reconstruction.",
            "",
            f"Generated UTC: {utc_now()}",
        ]
    )


def build_blocked_calibration(validation: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_utc": utc_now(),
        "calibration_status": "blocked",
        "reason": validation["decision_reason"],
        "mm_per_voxel_x": None,
        "mm_per_voxel_y": None,
        "mm_per_voxel_z": None,
        "voxel_volume_mm3": None,
        "patient_alpha_spacing_source": None,
        "no_assumed_spacing": True,
    }


def scalar_spacing(spacing: list[float]) -> float:
    return float(sum(spacing[:3]) / 3.0)


def area_spacing(spacing: list[float]) -> float:
    values = [float(item) for item in spacing[:3]]
    products = [values[0] * values[1], values[0] * values[2], values[1] * values[2]]
    return float(sum(products) / len(products))


def calibrate_if_possible(validation: dict[str, Any]) -> list[Path]:
    if validation.get("calibration_decision") != "calibrate":
        calibration = build_blocked_calibration(validation)
        return [write_json(OUTPUT_DIR / "physical_calibration.json", calibration)]

    patient_record = validation["patient_alpha_image_records_with_spacing"][0]
    spacing = [float(item) for item in patient_record["spacing"][:3]]
    calibration = {
        "generated_utc": utc_now(),
        "calibration_status": "calibrated",
        "mm_per_voxel_x": spacing[0],
        "mm_per_voxel_y": spacing[1],
        "mm_per_voxel_z": spacing[2],
        "voxel_volume_mm3": spacing[0] * spacing[1] * spacing[2],
        "patient_alpha_spacing_source": patient_record["path"],
        "orientation": patient_record.get("orientation"),
        "origin": patient_record.get("origin"),
    }

    state = load_json(STATE_PATH, {})
    outputs = [write_json(OUTPUT_DIR / "physical_calibration.json", calibration)]
    length_factor = scalar_spacing(spacing)
    area_factor = area_spacing(spacing)
    volume_factor = calibration["voxel_volume_mm3"]

    length_fields = {
        "mean_height",
        "maximum_height",
        "minimum_height",
        "anterior_height",
        "posterior_height",
        "left_height",
        "right_height",
    }
    disc_heights_mm = {}
    for disc_id, values in state.get("disc_heights", {}).items():
        converted = dict(values)
        for field in length_fields:
            if isinstance(values.get(field), (int, float)):
                converted[f"{field}_mm"] = values[field] * length_factor
        converted["source_units"] = values.get("units", "voxel units")
        converted["units"] = "millimeters"
        disc_heights_mm[disc_id] = converted
    outputs.append(write_json(OUTPUT_DIR / "radiology_disc_heights_mm.json", disc_heights_mm))

    area_payload = {
        "disc_areas_mm2": convert_numeric_mapping(state.get("disc_areas", {}), area_factor, "mm squared"),
        "canal_areas_mm2": convert_numeric_mapping(state.get("canal_areas", {}), area_factor, "mm squared"),
        "foraminal_areas_mm2": convert_numeric_mapping(state.get("foraminal_areas", {}), area_factor, "mm squared"),
        "area_conversion_factor": area_factor,
    }
    outputs.append(write_json(OUTPUT_DIR / "physical_area_measurements.json", area_payload))

    volumes = collect_volume_sources()
    volume_payload = {
        "volume_conversion_factor_mm3_per_voxel3": volume_factor,
        "volumes_mm3": convert_numeric_mapping(volumes, volume_factor, "mm cubed"),
    }
    outputs.append(write_json(OUTPUT_DIR / "physical_volume_measurements.json", volume_payload))

    slippage = {}
    for pair, values in state.get("slippage", {}).items():
        converted = dict(values)
        if isinstance(values.get("relative_anterior_posterior_displacement"), (int, float)):
            converted["relative_anterior_posterior_displacement_mm"] = (
                values["relative_anterior_posterior_displacement"] * length_factor
            )
        converted["units"] = "millimeters / percent"
        slippage[pair] = converted
    outputs.append(write_json(OUTPUT_DIR / "physical_slippage_measurements.json", slippage))

    curvature = dict(state.get("curvature", {}))
    if isinstance(curvature.get("centerline_length"), (int, float)):
        curvature["centerline_length_mm"] = curvature["centerline_length"] * length_factor
    for item in curvature.get("local_curvature", []):
        if isinstance(item.get("curvature_estimate"), (int, float)):
            item["curvature_estimate_per_mm"] = item["curvature_estimate"] / length_factor
    curvature["units"] = "millimeters and inverse millimeters"
    outputs.append(write_json(OUTPUT_DIR / "physical_curvature_measurements.json", curvature))

    physical_state = {
        "patient_id": state.get("patient_id", "patient_alpha"),
        "schema_version": "clinical_state_physical_v1",
        "generated_utc": utc_now(),
        "calibration": calibration,
        "voxel_state": state,
        "disc_heights_mm": disc_heights_mm,
        "areas_mm2": area_payload,
        "volumes_mm3": volume_payload,
        "slippage_mm": slippage,
        "curvature_physical": curvature,
        "not_diagnosis": True,
    }
    outputs.append(write_json(PROJECT_ROOT / "state" / "patient_states" / "clinical_state_vector_physical.json", physical_state))
    outputs.append(write_json(OUTPUT_DIR / "literature_comparison_report.json", build_literature_comparison(disc_heights_mm, area_payload)))
    outputs.append(write_text(REPORT_DIR / "phase45_calibration_report.txt", success_report(outputs, calibration)))
    return outputs


def convert_numeric_mapping(payload: dict[str, Any], factor: float, units: str) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for key, values in payload.items():
        if not isinstance(values, dict):
            converted[key] = values
            continue
        item = {}
        for field, value in values.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                item[f"{field}_physical"] = value * factor
            else:
                item[field] = value
        item["units"] = units
        converted[key] = item
    return converted


def collect_volume_sources() -> dict[str, Any]:
    volumes: dict[str, Any] = {}
    for path in (
        PROJECT_ROOT / "measurements" / "geometry" / "patient_alpha_measurements.json",
        PROJECT_ROOT / "measurements" / "geometry" / "patient_alpha_clean_measurements.json",
    ):
        data = load_json(path, [])
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "name" in item and "approx_volume" in item:
                    volumes[item["name"]] = {"approx_volume": item["approx_volume"], "source": str(path)}
    return volumes


def build_literature_comparison(disc_heights_mm: dict[str, Any], area_payload: dict[str, Any]) -> dict[str, Any]:
    comparisons = []
    for disc_id, values in disc_heights_mm.items():
        patient_value = values.get("mean_height_mm")
        comparisons.append(
            {
                "metric": "disc_mean_height",
                "structure": disc_id,
                "reported_range": "Published ranges vary by spinal level, age, modality, and measurement plane.",
                "patient_value": patient_value,
                "difference": None,
                "not_diagnosis": True,
                "interpretation": "Numerical comparison withheld until spinal level mapping and modality-specific reference ranges are verified.",
            }
        )
    return {
        "generated_utc": utc_now(),
        "scope": "Numerical, non-diagnostic comparison framework.",
        "comparisons": comparisons,
        "requires_radiologist_validation": True,
        "requires_level_specific_literature_ranges": True,
    }


def success_report(outputs: list[Path], calibration: dict[str, Any]) -> str:
    return "\n".join(
        [
            "ORTHOTWIN PHASE 4.5 CALIBRATION REPORT",
            "",
            "Spacing successfully recovered: YES",
            f"Source: {calibration['patient_alpha_spacing_source']}",
            f"Spacing: {calibration['mm_per_voxel_x']}, {calibration['mm_per_voxel_y']}, {calibration['mm_per_voxel_z']} mm/voxel",
            "",
            "Measurements now physical:",
            "- Disc heights",
            "- Area measurements",
            "- Volume measurements",
            "- Slippage measurements",
            "- Curvature measurements",
            "",
            "Confidence: MEDIUM",
            "Reason: Calibration uses recovered spacing, but clinical accuracy still requires validated axis order, imaging metadata provenance, and radiologist review.",
            "",
            "Generated files:",
            *[f"- {path}" for path in outputs],
        ]
    )


def write_manifest(paths: list[Path], status: str) -> Path:
    entries = []
    for path in paths:
        entries.append(
            {
                "path": str(path),
                "exists": path.exists(),
                "size": path.stat().st_size if path.exists() else None,
            }
        )
    return write_json(
        MANIFEST_DIR / "phase45_manifest.json",
        {
            "generated_utc": utc_now(),
            "phase": "4.5_physical_calibration",
            "status": status,
            "files": entries,
            "all_files_exist": all(item["exists"] for item in entries),
        },
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

    metadata_report = collect_metadata()
    metadata_path = write_json(OUTPUT_DIR / "imaging_metadata_report.json", metadata_report)

    validation = validate_spacing(metadata_report)
    validation_path = write_json(OUTPUT_DIR / "spacing_validation_report.json", validation)

    output_paths = [metadata_path, validation_path]
    generated_calibration_paths = calibrate_if_possible(validation)
    output_paths.extend(generated_calibration_paths)

    if validation.get("calibration_decision") != "calibrate":
        missing_path = write_text(REPORT_DIR / "missing_spacing_report.txt", missing_spacing_report(validation))
        output_paths.append(missing_path)
        manifest_path = write_manifest(output_paths, "blocked_missing_trusted_patient_alpha_spacing")
        print("PHASE 4.5 CRITICAL STOP")
        print("Trusted Patient Alpha spacing was not found.")
        print(f"Metadata report: {metadata_path}")
        print(f"Spacing validation: {validation_path}")
        print(f"Missing spacing report: {missing_path}")
        print(f"Manifest: {manifest_path}")
        return

    manifest_path = write_manifest(output_paths, "complete")
    print("PHASE 4.5 COMPLETE")
    print("Calibrated measurements:")
    for path in generated_calibration_paths:
        print(f"- {path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
