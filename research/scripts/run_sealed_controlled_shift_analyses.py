"""Generate and seal the three controlled-shift analysis artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(repo: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_committed_analysis_sources(repo: Path) -> None:
    result = subprocess.run(
        [
            "git",
            "status",
            "--porcelain",
            "--",
            "research/scripts",
            "research/tests",
            "research/prereg_controlled_shift.json",
            "research/prereg_controlled_shift.sha256",
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        raise RuntimeError("analysis sources or protocol are not committed at HEAD")


def require_absent(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise RuntimeError(f"sealed output already exists: {path}")


def run_suppressed(
    command: Sequence[str], *, cwd: Path, log_path: Path
) -> dict[str, object]:
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        }
    )
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
    )
    log_path.write_bytes(result.stdout + b"\n--- stderr ---\n" + result.stderr)
    log_path.chmod(0o400)
    if result.returncode != 0:
        raise RuntimeError(
            f"sealed analysis failed with exit code {result.returncode}; "
            f"inspect {log_path} only after recording the failed run"
        )
    return {
        "command_sha256": hashlib.sha256(
            json.dumps(list(command), separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "returncode": result.returncode,
        "log_sha256": sha256(log_path),
        "log_size": log_path.stat().st_size,
    }


def seal(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
        raise RuntimeError(f"analysis did not create a regular nonempty file: {path}")
    path.chmod(0o444)
    return {
        "path": str(path),
        "sha256": sha256(path),
        "size": path.stat().st_size,
        "mode": oct(path.stat().st_mode & 0o777),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--hash-file", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    scripts = repo / "research" / "scripts"
    require_committed_analysis_sources(repo)
    source_commit = git_head(repo)
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False, mode=0o700)
    paths = {
        "independent_cap8_replay": output_dir / "independent_cap8_replay.json",
        "protocol_cap8_analyzer": output_dir / "protocol_cap8_analyzer.json",
        "locked_cap4_analyzer": output_dir / "locked_cap4_analyzer.json",
    }
    logs = {name: output_dir / f"{name}.suppressed.log" for name in paths}
    for path in (*paths.values(), *logs.values()):
        require_absent(path)

    shared = [
        "--prereg",
        str(args.prereg),
        "--hash-file",
        str(args.hash_file),
        "--receipt-dir",
        str(args.receipt_dir),
    ]
    commands = {
        "independent_cap8_replay": [
            str(args.python),
            str(scripts / "independent_replay.py"),
            *shared,
            "--output",
            str(paths["independent_cap8_replay"]),
        ],
        "protocol_cap8_analyzer": [
            str(args.python),
            str(scripts / "analyze_controlled_shift_cap8.py"),
            *shared,
            "--output",
            str(paths["protocol_cap8_analyzer"]),
        ],
        "locked_cap4_analyzer": [
            str(args.python),
            str(scripts / "analyze_controlled_shift_confirmatory.py"),
            *shared,
            "--output",
            str(paths["locked_cap4_analyzer"]),
        ],
    }
    execution: dict[str, dict[str, object]] = {}
    artifacts: dict[str, dict[str, object]] = {}
    for name in (
        "independent_cap8_replay",
        "protocol_cap8_analyzer",
        "locked_cap4_analyzer",
    ):
        execution[name] = run_suppressed(
            commands[name], cwd=repo, log_path=logs[name]
        )
        artifacts[name] = seal(paths[name])
    manifest = {
        "schema_version": 1,
        "name": "VERA sealed controlled-shift analysis manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scientific_values_printed": False,
        "comparison_performed": False,
        "source_git_commit": source_commit,
        "source_sha256": {
            Path(command[1]).name: sha256(Path(command[1]))
            for command in commands.values()
        },
        "artifacts": artifacts,
        "execution": execution,
    }
    manifest_path = output_dir / "seal_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest_path.chmod(0o444)
    print(
        json.dumps(
            {
                "status": "sealed",
                "artifact_count": len(artifacts),
                "manifest": str(manifest_path),
                "manifest_sha256": sha256(manifest_path),
                "scientific_values_printed": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
