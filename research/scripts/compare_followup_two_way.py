"""First-read comparator for follow-up replay and protocol-cap outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from compare_three_way import compare_cap8, load_json, sha256


def write_report(
    replay_path: Path,
    cap8_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    replay = load_json(replay_path)
    cap8 = load_json(cap8_path)
    differences, crosswalk = compare_cap8(replay, cap8)
    report = {
        "schema_version": 1,
        "name": "VERA controlled-shift follow-up first-read comparison",
        "passed": differences.count == 0,
        "cap8_mismatch_count": differences.count,
        "cap8_mismatch_examples": differences.examples,
        "candidate_crosswalk": crosswalk,
        "input_sha256": {
            "independent_followup_replay": sha256(replay_path),
            "protocol_followup_cap8_analyzer": sha256(cap8_path),
        },
        "primary_setting": replay.get("primary_inference", {}),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--cap8", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_report(args.replay, args.cap8, args.output)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "cap8_mismatch_count": report["cap8_mismatch_count"],
                "output": str(args.output),
                "output_sha256": sha256(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
