"""Stable provenance manifests for ARASH JSON research artifacts."""

from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from arash import __version__

MAX_REPORT_BYTES = 10 * 1024 * 1024


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _strict_json_loads(raw: str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"invalid non-finite JSON constant: {value}")

    return json.loads(raw, parse_constant=reject_constant)


def build_research_manifest(report_path: str | Path) -> dict[str, Any]:
    """Hash and describe a JSON report without treating its content as trusted instructions."""
    path = Path(report_path)
    if not path.is_file():
        raise ValueError(f"report does not exist or is not a regular file: {path}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_REPORT_BYTES:
        raise ValueError(f"report size must be between 1 byte and {MAX_REPORT_BYTES} bytes")
    raw = path.read_bytes()
    try:
        report = _strict_json_loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("report must be valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise ValueError("report root must be a JSON object")

    dataset_sha = report.get("dataset_sha256")
    dataset = report.get("dataset")
    if isinstance(dataset, dict):
        dataset_sha = dataset.get("sha256", dataset_sha)
    metadata = report.get("metadata")
    experiment_sha = None
    if isinstance(metadata, dict):
        experiment_sha = metadata.get("experiment_fingerprint_sha256")
    experiment_sha = report.get("experiment_fingerprint_sha256", experiment_sha)
    configuration = report.get("configuration", report.get("config", {}))
    if not isinstance(configuration, (dict, list, str, int, float, bool, type(None))):
        configuration = {"unavailable": "report configuration was not JSON-compatible"}

    identity = {
        "manifest_format_version": 1,
        "application": {"name": "ARASH Foundation", "version": __version__},
        "artifact_sha256": _sha256(raw),
        "artifact_bytes": len(raw),
        "dataset_sha256": dataset_sha if _is_sha256(dataset_sha) else None,
        "experiment_fingerprint_sha256": experiment_sha if _is_sha256(experiment_sha) else None,
        "configuration_sha256": _sha256(_canonical_json(configuration).encode("utf-8")),
        "python_implementation": platform.python_implementation(),
        "python_version": platform.python_version(),
    }
    reproducibility_fingerprint = _sha256(_canonical_json(identity).encode("utf-8"))
    return {
        **identity,
        "artifact_name": path.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "reproducibility_fingerprint_sha256": reproducibility_fingerprint,
        "interpretation": (
            "This manifest identifies exact report bytes and known provenance fields; it does not "
            "prove the source data is authentic or that any research result is economically valid."
        ),
        "trade_action": "NONE",
        "execution_enabled": False,
        "orders_submitted": False,
    }


def manifest_fingerprint(manifest: dict[str, Any]) -> str:
    """Return the stable identity fingerprint for a manifest produced by this module."""
    identity_keys = (
        "manifest_format_version", "application", "artifact_sha256", "artifact_bytes",
        "dataset_sha256", "experiment_fingerprint_sha256", "configuration_sha256",
        "python_implementation", "python_version",
    )
    identity = {key: manifest.get(key) for key in identity_keys}
    return _sha256(_canonical_json(identity).encode("utf-8"))


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )
