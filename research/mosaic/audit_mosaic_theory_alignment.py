#!/usr/bin/env python3
"""Audit preregistered MOSAIC abstention predictions against confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_PREREG = ROOT / "prereg_mosaic_synthetic_v1.json"
DEFAULT_SIDECAR = ROOT / "prereg_mosaic_synthetic_v1.sha256"
DEFAULT_THEORY = (
    REPOSITORY / "research" / "artifacts" / "mosaic_synthetic_theory_curve_v1.json"
)
DEFAULT_CONFIRMATION = (
    REPOSITORY / "research" / "artifacts" / "mosaic_synthetic_confirmation_v1.json"
)
DEFAULT_CONFIRMATION_AUDIT = (
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_synthetic_confirmation_audit_v1.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_synthetic_theory_alignment_audit_v1.json"
)
TOLERANCE = 1e-12


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--theory", type=Path, default=DEFAULT_THEORY)
    parser.add_argument("--confirmation", type=Path, default=DEFAULT_CONFIRMATION)
    parser.add_argument(
        "--confirmation-audit", type=Path, default=DEFAULT_CONFIRMATION_AUDIT
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    expected_prereg_hash = args.sidecar.read_text(encoding="utf-8").split()[0]
    actual_prereg_hash = sha256(args.prereg)
    if actual_prereg_hash != expected_prereg_hash:
        raise AssertionError("preregistration sidecar mismatch")
    prereg = load_json(args.prereg)
    theory = load_json(args.theory)
    confirmation = load_json(args.confirmation)
    confirmation_audit = load_json(args.confirmation_audit)
    if theory["preregistration_sha256"] != actual_prereg_hash:
        raise AssertionError("theory curve uses the wrong preregistration")
    if confirmation["preregistration_sha256"] != actual_prereg_hash:
        raise AssertionError("confirmation uses the wrong preregistration")
    if confirmation_audit["preregistration_sha256"] != actual_prereg_hash:
        raise AssertionError("confirmation audit uses the wrong preregistration")
    if confirmation_audit["report_sha256"] != sha256(args.confirmation):
        raise AssertionError("confirmation audit does not cover this report")
    if confirmation_audit["pass"] is not True:
        raise AssertionError("confirmation replay did not pass")
    if confirmation["pass_conditions"]["all_pass"] is not True or (
        confirmation_audit["independent_pass_conditions"]["all_pass"] is not True
    ):
        raise AssertionError("the locked confirmation gate did not pass")
    for lock_name in ("code_sha256", "pilot_artifact_sha256"):
        for relative_path, expected_hash in prereg[lock_name].items():
            if sha256(REPOSITORY / relative_path) != expected_hash:
                raise AssertionError(f"current {lock_name} mismatch")

    expected_keys = {
        (str(scenario["name"]), int(n))
        for scenario in prereg["scenarios"]
        for n in scenario["sample_sizes_per_stratum"]
    }
    theory_cells = {
        (str(cell["scenario"]), int(cell["sample_size_per_stratum"])): cell
        for cell in theory["cells"]
    }
    observed_cells = {
        (str(cell["scenario"]), int(cell["sample_size_per_stratum"])): cell
        for cell in confirmation["cells"]
        if cell["method"] == "mosaic"
    }
    if len(theory_cells) != len(theory["cells"]):
        raise AssertionError("theory receipt contains duplicate cells")
    if set(theory_cells) != expected_keys or set(observed_cells) != expected_keys:
        raise AssertionError("theory and confirmation must cover the locked grid")

    rows = []
    for key in sorted(expected_keys):
        prediction = theory_cells[key]
        observation = observed_cells[key]
        predicted_deployment = float(
            prediction["local_asymptotic_deployment_probability"]
        )
        observed_deployment = float(observation["deployment_rate"])
        concentration_upper = float(prediction["concentration_abstention_upper"])
        if not (
            math.isfinite(predicted_deployment)
            and 0.0 <= predicted_deployment <= 1.0
            and math.isfinite(concentration_upper)
            and 0.0 <= concentration_upper <= 1.0
        ):
            raise AssertionError("invalid preregistered theory value")
        rows.append(
            {
                "scenario": key[0],
                "sample_size_per_stratum": key[1],
                "predicted_deployment_rate": predicted_deployment,
                "observed_deployment_rate": observed_deployment,
                "predicted_abstention_rate": 1.0 - predicted_deployment,
                "observed_abstention_rate": 1.0 - observed_deployment,
                "absolute_deployment_error": abs(
                    predicted_deployment - observed_deployment
                ),
                "observed_deployment_cp95_lower": observation[
                    "deployment_cp95_lower"
                ],
                "observed_deployment_cp95_upper": observation[
                    "deployment_cp95_upper"
                ],
                "concentration_abstention_upper": concentration_upper,
                "active_set_stability_pass": prediction[
                    "active_set_stability_pass"
                ],
            }
        )

    alignment = prereg["pass_conditions"]["theory_alignment"]
    target_scenario = str(alignment["scenario"])
    target_rows = [row for row in rows if row["scenario"] == target_scenario]
    mean_absolute_error = sum(
        float(row["absolute_deployment_error"]) for row in target_rows
    ) / len(target_rows)
    primary_n = int(alignment["primary_sample_size_per_stratum"])
    primary_rows = [
        row for row in target_rows if int(row["sample_size_per_stratum"]) == primary_n
    ]
    if len(primary_rows) != 1:
        raise AssertionError("theory alignment primary cell is missing")
    primary_absolute_error = float(primary_rows[0]["absolute_deployment_error"])
    stability_pass = all(bool(row["active_set_stability_pass"]) for row in rows)
    monotone_prediction = all(
        all(
            float(left["predicted_deployment_rate"])
            <= float(right["predicted_deployment_rate"]) + TOLERANCE
            for left, right in zip(scenario_rows, scenario_rows[1:])
        )
        for scenario_name in {str(row["scenario"]) for row in rows}
        for scenario_rows in [
            sorted(
                [row for row in rows if row["scenario"] == scenario_name],
                key=lambda row: int(row["sample_size_per_stratum"]),
            )
        ]
    )
    alignment_pass = bool(
        stability_pass
        and monotone_prediction
        and mean_absolute_error
        <= float(alignment["maximum_mean_absolute_error"])
        and primary_absolute_error
        <= float(alignment["maximum_primary_absolute_error"])
    )
    payload: dict[str, object] = {
        "name": "MOSAIC preregistered theory-to-data alignment audit v1",
        "status": "complete_confirmatory_alignment",
        "preregistration_sha256": actual_prereg_hash,
        "theory_curve_sha256": sha256(args.theory),
        "confirmation_sha256": sha256(args.confirmation),
        "confirmation_audit_sha256": sha256(args.confirmation_audit),
        "rows": rows,
        "target_scenario": target_scenario,
        "mean_absolute_deployment_error": mean_absolute_error,
        "primary_absolute_deployment_error": primary_absolute_error,
        "all_active_sets_stable": stability_pass,
        "predicted_curves_monotone": monotone_prediction,
        "pass": alignment_pass,
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not alignment_pass:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
