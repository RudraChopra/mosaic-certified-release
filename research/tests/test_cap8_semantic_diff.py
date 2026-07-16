from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "research" / "scripts").is_dir() and (parent / ".git").exists():
            return parent
    return Path("/Volumes/Backups/FARO/github_export/vera-edit-or-abstain")


ROOT = find_repo_root()
LOCAL = Path(__file__).resolve().parent
SCRIPTS = ROOT / "research" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(LOCAL))

from audit_cap8_semantic_diff import audit  # noqa: E402


LOCKED = ROOT / "research" / "scripts" / "analyze_controlled_shift_confirmatory.py"
CAP8 = (
    SCRIPTS / "analyze_controlled_shift_cap8.py"
    if (SCRIPTS / "analyze_controlled_shift_cap8.py").is_file()
    else LOCAL / "analyze_controlled_shift_cap8.py"
)
EVALUATOR = (
    SCRIPTS / "cap8_evaluator.py"
    if (SCRIPTS / "cap8_evaluator.py").is_file()
    else LOCAL / "cap8_evaluator.py"
)


def check(cap8_text: str, evaluator_text: str, locked_text: str | None = None) -> bool:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        locked = root / "locked.py"
        cap8 = root / "cap8.py"
        evaluator = root / "evaluator.py"
        locked.write_text(
            LOCKED.read_text(encoding="utf-8") if locked_text is None else locked_text,
            encoding="utf-8",
        )
        cap8.write_text(cap8_text, encoding="utf-8")
        evaluator.write_text(evaluator_text, encoding="utf-8")
        return bool(audit(locked, cap8, evaluator)["passed"])


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f"mutation target count is {text.count(old)}: {old}")
    return text.replace(old, new, 1)


def main() -> None:
    cap8 = CAP8.read_text(encoding="utf-8")
    evaluator = EVALUATOR.read_text(encoding="utf-8")
    locked = LOCKED.read_text(encoding="utf-8")
    assert check(cap8, evaluator)
    print("PASS authorized cap-8 semantic diff")

    mutations = {
        "wrong cap": (
            replace_once(cap8, "EXPECTED_GAMMA_CAP = 8.0", "EXPECTED_GAMMA_CAP = 4.0"),
            evaluator,
            None,
        ),
        "changed RNG": (
            replace_once(cap8, "8_000_000_000", "8_000_000_001"),
            evaluator,
            None,
        ),
        "changed threshold": (
            replace_once(
                cap8,
                "target_threshold=target_threshold,\n"
                "                            leakage_threshold=leakage_threshold,\n"
                "                            gamma_cap=gamma_cap,",
                "target_threshold=leakage_threshold,\n"
                "                            leakage_threshold=leakage_threshold,\n"
                "                            gamma_cap=gamma_cap,",
            ),
            evaluator,
            None,
        ),
        "changed allocation floor": (
            replace_once(cap8, "0.15 * budget", "0.20 * budget"),
            evaluator,
            None,
        ),
        "changed primary rows": (
            replace_once(
                cap8,
                "inference = primary_inference(primary_rows)",
                "inference = primary_inference(rows)",
            ),
            evaluator,
            None,
        ),
        "literal evaluator cap": (
            replace_once(cap8, "gamma_cap=gamma_cap,", "gamma_cap=4.0,"),
            evaluator,
            None,
        ),
        "changed rule": (
            cap8,
            replace_once(
                evaluator,
                '"iid_ltt": choose(evaluated, "iid_eligible"),',
                '"iid_ltt_changed": choose(evaluated, "iid_eligible"),',
            ),
            None,
        ),
        "aliased tie break": (
            cap8,
            replace_once(evaluator, "    choose,", "    choose as choose_changed,"),
            None,
        ),
        "changed locked analyzer": (
            cap8,
            evaluator,
            locked + "\n",
        ),
    }
    for label, (cap8_mutation, evaluator_mutation, locked_mutation) in mutations.items():
        assert not check(cap8_mutation, evaluator_mutation, locked_mutation), label
        print(f"PASS rejects {label}")


if __name__ == "__main__":
    main()
