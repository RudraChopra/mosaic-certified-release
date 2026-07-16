from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import audit_controlled_shift_receipts_strict as wrapper


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        prereg = root / "prereg.json"
        prereg.write_text(
            json.dumps(
                {
                    "status": "locked_before_claim_grade_runs",
                    "real_study": {"synthetic": True},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        hash_file = root / "prereg.sha256"
        hash_file.write_text(f"{wrapper.sha256(prereg)}  prereg.json\n")
        output = root / "audit.json"
        original = wrapper.audit_closed_contract
        try:
            wrapper.audit_closed_contract = lambda study, receipt_dir, digest: {
                "passed": study == {"synthetic": True} and len(digest) == 64,
                "expected_receipt_files": ["a.json"],
                "observed_receipt_files": ["a.json"],
                "validated_closed_array_archive_count": 1,
                "errors": [],
            }
            report = wrapper.build_report(
                argparse.Namespace(
                    prereg=prereg,
                    hash_file=hash_file,
                    receipt_dir=root,
                    output=output,
                )
            )
            assert report["passed"]
            print("PASS strict receipt wrapper")
            hash_file.write_text(f"{'0' * 64}  prereg.json\n")
            try:
                wrapper.build_report(
                    argparse.Namespace(
                        prereg=prereg,
                        hash_file=hash_file,
                        receipt_dir=root,
                        output=output,
                    )
                )
            except RuntimeError:
                print("PASS strict receipt wrapper rejects hash mismatch")
            else:
                raise AssertionError("hash mismatch passed")
        finally:
            wrapper.audit_closed_contract = original


if __name__ == "__main__":
    main()
