from __future__ import annotations

import argparse
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
sys.path.insert(0, str(ROOT / "research" / "scripts"))
sys.path.insert(0, str(LOCAL))

from audit_three_venue_sources import audit  # noqa: E402


SOURCE_PATHS = {
    "aaai": ROOT
    / "research/maintrack/aaai2027_template/AuthorKit27/vera_paper_body.tex",
    "iclr": ROOT
    / "research/maintrack/venue_variants/ICLR_2027_SCIENTIFIC_CONTENT.tex",
    "neurips": ROOT
    / "research/maintrack/venue_variants/NEURIPS_2027_SCIENTIFIC_CONTENT.tex",
    "bibliography": ROOT / "research/maintrack/references_verified.bib",
    "theory": ROOT / "research/maintrack/appendix_shift_robust_theory.tex",
}


def run(
    mutations: dict[str, tuple[str, str]] | None = None, *, final: bool = False
) -> bool:
    mutations = mutations or {}
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory)
        paths = {}
        for name, source in SOURCE_PATHS.items():
            text = source.read_text(encoding="utf-8")
            if name in mutations:
                old, new = mutations[name]
                if text.count(old) != 1:
                    raise AssertionError(
                        f"mutation target count for {name} is {text.count(old)}"
                    )
                text = text.replace(old, new, 1)
            path = target / source.name
            path.write_text(text, encoding="utf-8")
            paths[name] = path
        args = argparse.Namespace(**paths, output=None, final=final)
        return bool(audit(args)["passed"])


def main() -> None:
    assert run()
    print("PASS current three-venue sources")
    mutations = {
        "missing result macro": {
            "aaai": (
                "\\ControlledMainResultTable\n\\ControlledMainResultFigure",
                "\\ControlledMainResultTable\n\\MissingMainResultFigure",
            )
        },
        "changed threshold": {"iclr": ("$(0.20,0.55)$", "$(0.20,0.56)$")},
        "changed historical count": {
            "neurips": ("35 of 128", "34 of 128")
        },
        "legacy candidate token": {
            "aaai": (
                "INLP, R-LACE, LEACE, kernel methods",
                "INLP, RLACE, LEACE, kernel methods",
            )
        },
        "missing LTT positioning": {
            "iclr": ("Learn Then Test;", "A generic test;")
        },
        "unresolved citation": {
            "neurips": (
                r"\cite{ravfogel2020null,ravfogel2022linear,"
                r"belrose2023leace,ravfogel2022kernel,jourdan2023taco,"
                r"holstege2025splince,avitan2026mance}",
                r"\cite{not_a_real_reference}",
            )
        },
        "missing theory label": {
            "theory": (
                r"\label{thm:unsupported}",
                r"\label{thm:unsupported_changed}",
            )
        },
        "missing AI disclosure": {"aaai": ("OpenAI Codex", "An AI tool")},
        "changed contribution count": {
            "neurips": (
                "We make four contributions.",
                "We make five contributions.",
            )
        },
        "stale run count": {
            "iclr": (
                "1,280 dataset--method runs",
                "200 official-method runs and 1,280 dataset--method runs",
            )
        },
    }
    for label, mutation in mutations.items():
        assert not run(mutation), label
        print(f"PASS rejects {label}")
    assert not run(final=True)
    print("PASS final mode rejects pending result text")


if __name__ == "__main__":
    main()
