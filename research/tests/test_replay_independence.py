from __future__ import annotations

import tempfile
from pathlib import Path

from audit_replay_independence import audit_source


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "research" / "scripts").is_dir() and (parent / ".git").exists():
            return parent
    return Path("/Volumes/Backups/FARO/github_export/vera-edit-or-abstain")


ROOT = find_repo_root()
LOCAL = Path(__file__).resolve().parent
FORBIDDEN = [
    ROOT / "research/scripts/analyze_controlled_shift_confirmatory.py",
    ROOT / "research/scripts/design_vera_controlled_shift_study.py",
    ROOT / "research/scripts/vera_controlled_shift.py",
    ROOT / "research/scripts/vera_robust_certificate.py",
]


def rejected(source: str, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="vera-replay-audit-", dir="/private/tmp") as tmp:
        path = Path(tmp) / "replay.py"
        path.write_text(source, encoding="utf-8")
        report = audit_source(path, FORBIDDEN)
        assert not report["passed"]
        assert any(expected in error for error in report["errors"]), report["errors"]


def main() -> None:
    repo_replay = ROOT / "research" / "scripts" / "independent_replay.py"
    replay = repo_replay if repo_replay.is_file() else LOCAL / "independent_replay.py"
    report = audit_source(replay, FORBIDDEN)
    assert report["passed"], report["errors"]
    print("PASS isolated replay source")
    rejected(
        "import analyze_controlled_shift_confirmatory\n",
        "forbidden import",
    )
    print("PASS forbidden project import")
    rejected("import subprocess\nsubprocess.run(['true'])\n", "forbidden import")
    print("PASS subprocess import and call")
    rejected("value = eval('1 + 1')\n", "dynamic evaluation")
    print("PASS dynamic evaluation")
    rejected(
        "note = 'design_vera_controlled_shift_study'\n",
        "forbidden project-source reference",
    )
    print("PASS source-name read-through reference")
    with tempfile.TemporaryDirectory(prefix="vera-replay-audit-", dir="/private/tmp") as tmp:
        path = Path(tmp) / "replay.py"
        path.write_text("import json\n", encoding="utf-8")
        missing = Path(tmp) / "missing.py"
        report = audit_source(path, [missing])
        assert not report["passed"]
        assert any("missing from the audit set" in error for error in report["errors"])
    print("PASS missing forbidden-source audit input")


if __name__ == "__main__":
    main()
