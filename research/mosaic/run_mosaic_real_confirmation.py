#!/usr/bin/env python3
"""Execute the hash-locked MOSAIC real-feature confirmation end to end."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_PREREG = ROOT / "prereg_mosaic_real_v1.json"
DEFAULT_OUTPUT_DIR = REPOSITORY / "research" / "artifacts" / "mosaic_real_confirmation_v1"
DEFAULT_MANIFEST = REPOSITORY / "research" / "artifacts" / "mosaic_real_confirmation_manifest_v1.json"
DEFAULT_AUDIT = REPOSITORY / "research" / "artifacts" / "mosaic_real_confirmation_audit_v1.json"
RUNNER = ROOT / "run_mosaic_official_frontier_pilot.py"
AUDITOR = ROOT / "audit_mosaic_real_frontier.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def checked_git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def verify_lock(path: Path) -> tuple[dict[str, object], str]:
    prereg_sha = sha256(path)
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if not sidecar.exists() or sidecar.read_text(encoding="utf-8").strip() != prereg_sha:
        raise ValueError("preregistration sidecar does not match")
    prereg = json.loads(path.read_text(encoding="utf-8"))
    if prereg.get("status") != "locked_before_confirmatory_outcomes":
        raise ValueError("preregistration is not locked")
    for relative, expected in prereg["code_sha256"].items():
        candidate = REPOSITORY / relative
        if not candidate.exists() or sha256(candidate) != expected:
            raise ValueError(f"locked code mismatch: {relative}")
    for name, record in prereg["frozen_stores"].items():
        manifest = Path(record["path"]) / "manifest.json"
        if sha256(manifest) != record["manifest_sha256"]:
            raise ValueError(f"frozen-store manifest mismatch: {name}")
    for method, record in prereg["official_repositories"].items():
        repo = Path(record["path"])
        if checked_git(repo, "rev-parse", "HEAD") != record["commit"]:
            raise ValueError(f"official repository revision mismatch: {method}")
        if checked_git(repo, "status", "--porcelain"):
            raise ValueError(f"official repository is dirty: {method}")
    return prereg, prereg_sha


def output_name(dataset: str, seed: int) -> str:
    slug = dataset.lower().replace("-", "_").replace(" ", "_")
    return f"mosaic_real_confirmation_{slug}_seed{seed}.json"


def validate_existing_output(path: Path, prereg_sha: str, dataset: str, seed: int) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("status") != "confirmatory_locked_protocol"
        or payload.get("prereg_sha256") != prereg_sha
        or payload.get("dataset") != dataset
        or payload.get("seed") != seed
        or len(payload.get("results", [])) != 13
    ):
        raise ValueError(f"existing output is not a valid resumable receipt: {path}")


def run_confirmation(
    prereg: dict[str, object],
    prereg_path: Path,
    prereg_sha: str,
    output_dir: Path,
    *,
    resume: bool,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPOSITORY / "research" / "mosaic"),
            str(REPOSITORY / "research" / "scripts"),
        ]
    )
    environment.setdefault("OMP_NUM_THREADS", "1")
    environment.setdefault("OPENBLAS_NUM_THREADS", "1")
    environment.setdefault("VECLIB_MAXIMUM_THREADS", "1")
    outputs = []
    for dataset in prereg["datasets"]:
        for seed in prereg["confirmation_seeds"]:
            output = output_dir / output_name(str(dataset), int(seed))
            outputs.append(output)
            if output.exists():
                if not resume:
                    raise FileExistsError(f"refusing to overwrite confirmation output: {output}")
                validate_existing_output(output, prereg_sha, str(dataset), int(seed))
                print(f"validated existing {dataset} seed {seed}", flush=True)
                continue
            print(f"running {dataset} seed {seed}", flush=True)
            subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--dataset",
                    str(dataset),
                    "--seed",
                    str(seed),
                    "--output",
                    str(output),
                    "--confirmation-prereg",
                    str(prereg_path),
                ],
                cwd=REPOSITORY,
                env=environment,
                check=True,
            )
    return outputs


def run_audit(outputs: list[Path], audit: Path) -> dict[str, object]:
    if audit.exists():
        audit.unlink()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(REPOSITORY / "research" / "mosaic"),
            str(REPOSITORY / "research" / "scripts"),
        ]
    )
    subprocess.run(
        [sys.executable, str(AUDITOR), *(str(path) for path in outputs), "--output", str(audit)],
        cwd=REPOSITORY,
        env=environment,
        check=True,
    )
    return json.loads(audit.read_text(encoding="utf-8"))


def build_manifest(
    prereg: dict[str, object],
    prereg_sha: str,
    outputs: list[Path],
    audit: dict[str, object],
    audit_path: Path,
) -> dict[str, object]:
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in outputs]
    selections = [row["selection"] for row in rows]
    bias = [
        selection
        for row, selection in zip(rows, selections, strict=True)
        if row["dataset"] == "BiasBios-Clinical"
    ]
    deployed = [selection for selection in selections if selection["decision"] == "deploy"]
    estimable_deployments = [
        selection for selection in deployed if selection["external_estimable"]
    ]
    missing_support_rows = [
        {
            "dataset": row["dataset"],
            "seed": row["seed"],
            "candidate_count": sum(
                not bool(result.get("external_estimable")) for result in row["results"]
            ),
        }
        for row in rows
        if any(not bool(result.get("external_estimable")) for result in row["results"])
    ]
    gates = {
        "complete_execution": len(rows) == 25
        and all(len(row["results"]) == 13 for row in rows)
        and not any(
            "optimization_error" in result for row in rows for result in row["results"]
        ),
        "receipt_replay": bool(audit["passed"])
        and int(audit["candidate_rows_replayed"]) == 325,
        "positive_usefulness": sum(value["decision"] == "deploy" for value in bias) >= 4
        and all(value["external_safe"] for value in bias if value["external_estimable"]),
        "empirical_safety": not any(value["false_acceptance"] for value in estimable_deployments),
        "support_discipline": all(
            not result["external_safe"]
            for row in rows
            for result in row["results"]
            if not result["external_estimable"]
        ),
        "modality_coverage": set(row["dataset"] for row in rows)
        == set(prereg["datasets"]),
        "claim_discipline": prereg["claim_boundary"].startswith(
            "This confirmation evaluates"
        ),
    }
    return {
        "name": "MOSAIC real-feature confirmation manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prereg_sha256": prereg_sha,
        "output_count": len(outputs),
        "candidate_row_count": sum(len(row["results"]) for row in rows),
        "selected_deployments": len(deployed),
        "estimable_selected_deployments": len(estimable_deployments),
        "selected_false_acceptances": sum(
            bool(value["false_acceptance"]) for value in estimable_deployments
        ),
        "biasbios_deployments": sum(value["decision"] == "deploy" for value in bias),
        "missing_support_rows": missing_support_rows,
        "gates": gates,
        "all_pass": all(gates.values()),
        "audit": {"path": str(audit_path), "sha256": sha256(audit_path)},
        "outputs": [
            {
                "path": str(path),
                "sha256": sha256(path),
                "dataset": row["dataset"],
                "seed": row["seed"],
                "selection": row["selection"],
            }
            for path, row in zip(outputs, rows, strict=True)
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prereg, prereg_sha = verify_lock(args.prereg)
    if args.verify_only:
        print(
            json.dumps(
                {
                    "verified": True,
                    "prereg": str(args.prereg),
                    "prereg_sha256": prereg_sha,
                    "datasets": list(prereg["datasets"]),
                    "confirmation_seeds": prereg["confirmation_seeds"],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.manifest.exists() and not args.resume:
        raise FileExistsError(f"refusing to overwrite confirmation manifest: {args.manifest}")
    outputs = run_confirmation(
        prereg,
        args.prereg,
        prereg_sha,
        args.output_dir,
        resume=args.resume,
    )
    audit = run_audit(outputs, args.audit)
    manifest = build_manifest(prereg, prereg_sha, outputs, audit, args.audit)
    atomic_json_dump(manifest, args.manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    if not manifest["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
