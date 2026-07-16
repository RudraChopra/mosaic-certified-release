from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

from run_native_eraser_probe_diagnostic import balanced, json_safe
from run_native_probe_matrix import execute, key, valid_existing


def main() -> None:
    assert balanced(np.array([0, 0, 1, 1]), np.array([0, 1, 1, 1])) == 0.75
    assert balanced(np.array([0, 0]), np.array([0, 0])) is None
    assert json_safe({"x": [float("nan"), np.float64(2.0)]}) == {
        "x": [None, 2.0]
    }
    assert key("Waterbirds", "inlp", 45) == "Waterbirds__inlp__seed-45"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        receipt = root / "receipt.json"
        receipt.write_text(
            json.dumps(
                {
                    "dataset": "Waterbirds",
                    "method": "inlp",
                    "seed": 45,
                    "formal_guarantee": False,
                    "cross_method_native_probe_equivalence_claimed": False,
                }
            ),
            encoding="utf-8",
        )
        assert valid_existing(receipt, "Waterbirds", "inlp", 45)
        assert not valid_existing(receipt, "Waterbirds", "inlp", 46)
        log = root / "run.log"
        returncode, digest = execute(
            ["/bin/sh", "-c", "printf diagnostic"], cwd=root, log_path=log
        )
        assert returncode == 0 and len(digest) == 64
    print("PASS native-probe diagnostic helpers")


if __name__ == "__main__":
    main()
