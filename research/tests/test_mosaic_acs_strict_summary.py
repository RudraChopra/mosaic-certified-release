from pathlib import Path

from summarize_mosaic_acs_strict_v3 import EXPECTED_SEEDS, summarize


ROOT = Path(__file__).resolve().parents[2]


def test_acs_strict_summary_has_complete_locked_confirmation() -> None:
    summary = summarize(
        ROOT / "research/artifacts/mosaic_acs_bridge_strict_v3_receipts",
        ROOT / "research/artifacts/mosaic_acs_bridge_strict_v3_audit.json",
    )
    assert tuple(summary["seeds"]) == EXPECTED_SEEDS
    assert summary["candidate_rows"] == 65
    assert summary["selection_by_utility_threshold"]["0.40"]["deployments"] == 0
    assert summary["selection_by_utility_threshold"]["0.45"]["deployments"] == 5
    assert summary["selection_by_utility_threshold"]["0.45"]["diagnostic_contract_violations"] == 0
