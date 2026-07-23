from __future__ import annotations

from pathlib import Path

from audit_mosaic_acs_scalar_confirmation import audit


ROOT = Path(__file__).resolve().parents[2]


def test_locked_scalar_confirmation_audit_passes() -> None:
    payload = audit(
        ROOT / "research/artifacts/mosaic_acs_scalar_confirmation_v1.json"
    )
    assert payload["pass"] is True
    assert payload["summary"]["familywise_confirmed_2023_utility_violations"] == 1
    assert payload["headline_witness"]["direct_2018"] == "deploy"
    assert payload["headline_witness"]["mosaic_2018"] == "abstain"
